#!/usr/bin/env python3
"""Architect Anything MCP server (stdio, newline-delimited JSON-RPC 2.0).

Exposes the agent CLI and report-authoring operations as first-class MCP tools,
resources, and prompts. It uses only the Python standard library, never executes
inspected targets, and never installs or registers anything automatically.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

from aa_cli import CommandError, command_contract, parser, write_result
from aa_inventory import compare_inventory, inventory
from aa_investigation import (
    CHECKLIST_STATUSES,
    CITE_KINDS,
    DEPTHS,
    LENSES,
    cite,
    finish,
    load,
    set_checklist,
    set_run_meta,
    start,
    status,
    upsert_claim,
    upsert_diagram,
    upsert_section,
)
from aa_model import (
    PACKAGE,
    SCHEMA,
    VERSION,
    compare_reports,
    json_text,
    read_json,
    schema_errors,
    validate,
)
from aa_render import EMIT_PACKS, publish

SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
STRING = {"type": "string"}
STRING_ARRAY = {"type": "array", "items": STRING}


def schema(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required),
            "additionalProperties": False}


def annotations(title, read_only=False, destructive=False, idempotent=True, open_world=False):
    return {
        "title": title,
        "readOnlyHint": read_only,
        "destructiveHint": destructive,
        "idempotentHint": idempotent,
        "openWorldHint": open_world,
    }


EXCLUDE = {"type": "array", "items": STRING, "description": "Glob patterns to leave out of the inventory"}
EMIT_PROP = {
    "type": "array",
    "items": {"enum": [*EMIT_PACKS, "all"]},
    "description": "Optional companion report packs to generate alongside HTML/Markdown (mermaid, adr, onboarding, delta, llms-txt, or all)",
}

TOOLS = {
    "aa_start": (
        "Prepare a catch-up or focused investigation workspace. Does not analyze the target.",
        schema({
            "target": STRING,
            "focus": {"type": "string", "description": "The user's feature or design question"},
            "depth": {"enum": list(DEPTHS)},
            "lens": {"enum": list(LENSES),
                     "description": "Specialized investigation lens: mechanism (requires focus), onboarding, delta, boundaries, or operations"},
            "emit": EMIT_PROP,
            "kind": {"enum": ["auto", "source", "product", "hybrid", "capture"]},
            "output": STRING,
            "exclude": EXCLUDE,
        }, ["target"]),
        annotations("Start Investigation Workspace", read_only=False, idempotent=False),
    ),
    "aa_status": (
        "Read an investigation's checklist, depth, lens, and report validation state.",
        schema({"workspace": STRING}, ["workspace"]),
        annotations("Read Investigation Status", read_only=True, idempotent=True),
    ),
    "aa_checklist": (
        "Record the answer to one investigation checklist item (status plus a concrete note).",
        schema({
            "workspace": STRING,
            "item": STRING,
            "status": {"enum": list(CHECKLIST_STATUSES)},
            "note": STRING,
        }, ["workspace", "item", "status"]),
        annotations("Update Checklist Item", read_only=False, idempotent=True),
    ),
    "aa_cite": (
        "Build a hashed evidence record for a local file; append=true adds it to the working report.",
        schema({
            "workspace": STRING,
            "path": STRING,
            "lines": STRING,
            "id": STRING,
            "kind": {"enum": list(CITE_KINDS)},
            "note": STRING,
            "append": {"type": "boolean"},
        }, ["workspace", "path"]),
        annotations("Cite Evidence File", read_only=False, idempotent=True),
    ),
    "aa_upsert_claim": (
        "Add or update a claim in the working report with immediate reference validation.",
        schema({
            "workspace": STRING,
            "id": STRING,
            "text": STRING,
            "authority": {"enum": ["observation", "derived", "inference", "contradiction", "unknown"]},
            "freshness": {"enum": ["verified", "stale", "unverified"]},
            "evidence": STRING_ARRAY,
        }, ["workspace", "id", "text"]),
        annotations("Upsert Report Claim", read_only=False, idempotent=True),
    ),
    "aa_upsert_section": (
        "Add or update a report section, automatically pruning replaced scaffold placeholders.",
        schema({
            "workspace": STRING,
            "id": STRING,
            "title": STRING,
            "body": STRING_ARRAY,
            "claims": STRING_ARRAY,
            "detail": {"type": "boolean"},
            "freshness": {"enum": ["verified", "stale", "unverified"]},
            "table": {
                "type": "object",
                "additionalProperties": False,
                "required": ["columns", "rows"],
                "properties": {
                    "columns": STRING_ARRAY,
                    "rows": {"type": "array", "items": STRING_ARRAY},
                },
            },
        }, ["workspace", "id", "body", "claims"]),
        annotations("Upsert Report Section", read_only=False, idempotent=True),
    ),
    "aa_upsert_diagram": (
        "Add or update a diagram in the working report with immediate structural validation.",
        schema({
            "workspace": STRING,
            "id": STRING,
            "title": STRING,
            "kind": {"enum": ["context", "component", "sequence", "data", "state"]},
            "freshness": {"enum": ["verified", "stale", "unverified"]},
            "nodes": {
                "type": "array",
                "minItems": 1,
                "maxItems": 12,
                "items": schema({"id": STRING, "label": STRING, "claims": STRING_ARRAY}, ["id", "label", "claims"]),
            },
            "edges": {
                "type": "array",
                "items": schema({"from": STRING, "to": STRING, "label": STRING, "claims": STRING_ARRAY},
                                ["from", "to", "label", "claims"]),
            },
        }, ["workspace", "id", "title", "kind", "nodes", "edges"]),
        annotations("Upsert Report Diagram", read_only=False, idempotent=True),
    ),
    "aa_set_run_meta": (
        "Set working report title, subtitle, target name, run status, coverage, limitations, changes, or tools.",
        schema({
            "workspace": STRING,
            "title": STRING,
            "subtitle": STRING,
            "target_name": STRING,
            "run_status": {"enum": ["complete", "partial", "interrupted"]},
            "coverage": {"enum": ["complete", "partial", "unknown"]},
            "limitations": STRING_ARRAY,
            "changes": STRING_ARRAY,
            "tools": STRING_ARRAY,
        }, ["workspace"]),
        annotations("Set Report Metadata", read_only=False, idempotent=True),
    ),
    "aa_finish": (
        "Check collection state and publish the authored report as an immutable snapshot.",
        schema({"workspace": STRING, "partial": {"type": "boolean"}, "emit": EMIT_PROP}, ["workspace"]),
        annotations("Finish & Publish Investigation", read_only=False, idempotent=True),
    ),
    "aa_validate": (
        "Validate a report model, optionally checking cited local files and hashes.",
        schema({"report": STRING, "check_files": {"type": "boolean"}}, ["report"]),
        annotations("Validate Report Model", read_only=True, idempotent=True),
    ),
    "aa_render": (
        "Publish an authored report model without an investigation workspace.",
        schema({"report": STRING, "output": STRING, "emit": EMIT_PROP}, ["report", "output"]),
        annotations("Render & Publish Report", read_only=False, idempotent=True),
    ),
    "aa_inventory": (
        "Fingerprint selected local files into a new JSON file.",
        schema({"target": STRING, "out": STRING, "exclude": EXCLUDE}, ["target", "out"]),
        annotations("Collect File Inventory", read_only=False, idempotent=True),
    ),
    "aa_compare": (
        "Compare two inventories or two reports.",
        schema({"kind": {"enum": ["inventory", "report"]}, "before": STRING, "after": STRING, "out": STRING},
               ["kind", "before", "after"]),
        annotations("Compare Inventories or Reports", read_only=True, idempotent=True),
    ),
    "aa_schema": (
        "Return a machine-readable contract: report, investigation or commands.",
        schema({"subject": {"enum": ["report", "investigation", "commands"]}}),
        annotations("Read Schema Contract", read_only=True, idempotent=True),
    ),
    "aa_rea_status": (
        "Probe an existing REA CLI. Does not prove providers are ready or MCP is connected.",
        schema({"config": STRING}),
        annotations("Check REA CLI Status", read_only=True, idempotent=True, open_world=True),
    ),
    "aa_rea_run": (
        "Run one REA CLI operation, retaining output and a receipt at a new path.",
        schema({
            "out": STRING,
            "config": STRING,
            "arguments": {"type": "array", "items": STRING, "minItems": 1},
        }, ["out", "arguments"]),
        annotations("Run REA CLI Operation", read_only=False, idempotent=False, open_world=True),
    ),
}

PROMPTS = {
    "catch-up": {
        "name": "catch-up",
        "description": "Catch up on a repository or product and publish an evidence-backed architecture report.",
        "arguments": [
            {"name": "target", "description": "Absolute path or URL of the target", "required": True},
            {"name": "depth", "description": "overview, standard, or deep", "required": False},
            {"name": "lens", "description": "Optional lens: onboarding, delta, boundaries, operations", "required": False},
        ],
    },
    "explain-feature": {
        "name": "explain-feature",
        "description": "Trace a specific feature, subsystem, or design question end-to-end with citations and diagrams.",
        "arguments": [
            {"name": "target", "description": "Absolute path or URL of the target", "required": True},
            {"name": "focus", "description": "Feature or design question to explain", "required": True},
            {"name": "depth", "description": "overview, standard, or deep", "required": False},
        ],
    },
    "extract-mechanism": {
        "name": "extract-mechanism",
        "description": "Extract the portable, product-neutral formula behind a mechanism without cloning the product.",
        "arguments": [
            {"name": "target", "description": "Absolute path or URL of the target", "required": True},
            {"name": "focus", "description": "Mechanism question to extract", "required": True},
        ],
    },
}

RESOURCES = [
    {
        "uri": "aa://schema/report",
        "name": "Architect Anything Report Schema v1",
        "description": "JSON Schema contract for report.json",
        "mimeType": "application/json",
    },
    {
        "uri": "aa://schema/investigation",
        "name": "Architect Anything Investigation Manifest Schema v1",
        "description": "JSON Schema contract for investigation.json",
        "mimeType": "application/json",
    },
    {
        "uri": "aa://guide/lenses-and-packs",
        "name": "Lenses and Companion Report Packs Guide",
        "description": "Overview of available investigation lenses and optional emit packs",
        "mimeType": "text/markdown",
    },
]

RESOURCE_TEMPLATES = [
    {
        "uriTemplate": "aa://workspace/{workspace}/status",
        "name": "Investigation Status & Checklist",
        "description": "Live checklist, validation summary, and next step for a workspace path",
        "mimeType": "application/json",
    },
    {
        "uriTemplate": "aa://workspace/{workspace}/report",
        "name": "Working Report Model",
        "description": "Current working report.json for a workspace path",
        "mimeType": "application/json",
    },
]


def check_arguments(name, a):
    spec = TOOLS[name][1]
    if not isinstance(a, dict):
        raise ValueError("Tool arguments must be an object")
    for key in spec["required"]:
        if key not in a:
            raise ValueError(f"Missing required argument: {key}")
    for key in a:
        if key not in spec["properties"]:
            raise ValueError(f"Unknown argument: {key}")
    errors = schema_errors(a, spec, "$")
    if errors:
        raise ValueError("; ".join(errors))


def dispatch_tool(name, a):
    """Execute the underlying domain function directly without round-tripping through argparse."""
    if name == "aa_start":
        return start(
            a["target"],
            output=a.get("output"),
            focus=a.get("focus"),
            kind=a.get("kind", "auto"),
            excludes=a.get("exclude", ()),
            depth=a.get("depth", "standard"),
            lens=a.get("lens"),
            emit=a.get("emit", ()),
        )
    if name == "aa_status":
        return status(a["workspace"])
    if name == "aa_checklist":
        return set_checklist(a["workspace"], a["item"], a["status"], a.get("note", ""))
    if name == "aa_cite":
        return cite(
            a["workspace"],
            a["path"],
            lines=a.get("lines"),
            ident=a.get("id"),
            kind=a.get("kind", "source"),
            note=a.get("note", ""),
            append=bool(a.get("append", False)),
        )
    if name == "aa_upsert_claim":
        return upsert_claim(
            a["workspace"],
            a["id"],
            a["text"],
            authority=a.get("authority", "observation"),
            freshness=a.get("freshness", "verified"),
            evidence=a.get("evidence", ()),
        )
    if name == "aa_upsert_section":
        return upsert_section(
            a["workspace"],
            a["id"],
            title=a.get("title"),
            body=a["body"],
            claims=a["claims"],
            detail=a.get("detail"),
            freshness=a.get("freshness", "verified"),
            table=a.get("table"),
        )
    if name == "aa_upsert_diagram":
        return upsert_diagram(
            a["workspace"],
            a["id"],
            title=a["title"],
            kind=a["kind"],
            nodes=a["nodes"],
            edges=a["edges"],
            freshness=a.get("freshness", "verified"),
        )
    if name == "aa_set_run_meta":
        return set_run_meta(
            a["workspace"],
            title=a.get("title"),
            subtitle=a.get("subtitle"),
            target_name=a.get("target_name"),
            run_status=a.get("run_status"),
            coverage=a.get("coverage"),
            limitations=a.get("limitations"),
            changes=a.get("changes"),
            tools=a.get("tools"),
        )
    if name == "aa_finish":
        return finish(a["workspace"], partial=bool(a.get("partial", False)), emit=a.get("emit", ()))
    if name == "aa_validate":
        res = validate(read_json(a["report"]), bool(a.get("check_files", False)))
        if not res["valid"]:
            raise CommandError("validation_failed", "Report validation failed", 1, res)
        return res
    if name == "aa_render":
        return publish(read_json(a["report"]), a["output"], emit=a.get("emit", ()))
    if name == "aa_inventory":
        target, dest = Path(a["target"]).resolve(), Path(a["out"]).resolve()
        if target == dest:
            raise ValueError("Inventory output cannot overwrite the target")
        excluded = list(a.get("exclude", ()))
        if dest.is_relative_to(target):
            excluded.append(dest.relative_to(target).as_posix())
        return write_result(dest, inventory(target, excluded))
    if name == "aa_compare":
        comp = compare_inventory if a["kind"] == "inventory" else compare_reports
        res = comp(read_json(a["before"]), read_json(a["after"]))
        return write_result(a["out"], res) if a.get("out") else res
    if name == "aa_schema":
        subject = a.get("subject", "commands")
        return SCHEMA if subject == "report" else (
            read_json(PACKAGE / "assets/investigation.schema.json")
            if subject == "investigation"
            else command_contract(parser())
        )
    if name in ("aa_rea_status", "aa_rea_run"):
        rea_action = "status" if name == "aa_rea_status" else "run"
        command = [sys.executable, str(PACKAGE / "scripts/rea_bridge.py"), rea_action]
        if a.get("config"):
            command += ["--config", a["config"]]
        if rea_action == "run":
            operation = a["arguments"][1:] if a["arguments"][:1] == ["--"] else a["arguments"]
            if not operation:
                raise ValueError("REA run needs an operation")
            command += ["--out", a["out"], "--", *map(str, operation)]
        process = subprocess.run(command, capture_output=True, text=True, check=False)
        if process.returncode:
            try:
                details = json.loads(process.stdout or process.stderr)
            except ValueError:
                details = {"diagnostic": process.stderr.strip()}
            raise CommandError("rea_unavailable_or_failed", "REA bridge did not complete successfully", 4, details)
        return json.loads(process.stdout)
    raise KeyError(name)


def call_tool(name, arguments):
    """Return an MCP tool result. Failures use the CLI's stable error codes."""
    try:
        if name not in TOOLS:
            raise ValueError(f"Unknown tool: {name}")
        arguments = arguments or {}
        check_arguments(name, arguments)
        result = dispatch_tool(name, arguments)
        payload, error = {"ok": True, "command": name, "result": result}, False
    except CommandError as exc:
        body = {"code": exc.code, "message": str(exc)}
        if exc.details is not None:
            body["details"] = exc.details
        payload, error = {"ok": False, "command": name, "error": body}, True
    except (ValueError, KeyError, TypeError) as exc:
        payload, error = {"ok": False, "command": name, "error": {"code": "invalid_input", "message": str(exc)}}, True
    except (OSError, subprocess.SubprocessError) as exc:
        payload, error = {"ok": False, "command": name, "error": {"code": "operation_failed", "message": str(exc)}}, True
    text = json.dumps(payload, ensure_ascii=True, indent=2)
    return {"content": [{"type": "text", "text": text}], "structuredContent": payload, "isError": error}


def read_mcp_resource(uri):
    if uri == "aa://schema/report":
        return [{"uri": uri, "mimeType": "application/json", "text": json_text(SCHEMA)}]
    if uri == "aa://schema/investigation":
        return [{"uri": uri, "mimeType": "application/json",
                 "text": json_text(read_json(PACKAGE / "assets/investigation.schema.json"))}]
    if uri == "aa://guide/lenses-and-packs":
        guide = PACKAGE / "references/lenses-and-packs.md"
        text = guide.read_text(encoding="utf-8") if guide.is_file() else "# Lenses and Packs\nSee SKILL.md."
        return [{"uri": uri, "mimeType": "text/markdown", "text": text}]
    if uri.startswith("aa://workspace/"):
        rest = uri[len("aa://workspace/"):]
        if rest.endswith("/status"):
            ws = unquote(rest[:-len("/status")])
            return [{"uri": uri, "mimeType": "application/json", "text": json_text(status(ws))}]
        if rest.endswith("/report"):
            ws = unquote(rest[:-len("/report")])
            _, data = load(ws)
            return [{"uri": uri, "mimeType": "application/json", "text": json_text(read_json(data["paths"]["report"]))}]
    raise ValueError(f"Unknown resource URI: {uri}")


def get_mcp_prompt(name, args):
    if name not in PROMPTS:
        raise ValueError(f"Unknown prompt: {name}")
    args = args or {}
    target = args.get("target", "<TARGET>")
    depth = args.get("depth", "standard")
    if name == "catch-up":
        lens = args.get("lens")
        lens_part = f', lens="{lens}"' if lens else ""
        text = (
            f"Run an Architect Anything catch-up investigation on `{target}` (depth={depth}{lens_part}).\n"
            f"1. Call `aa_start` with target=\"{target}\", depth=\"{depth}\"{lens_part}.\n"
            "2. Inspect the target, record evidence with `aa_cite` (append=true), author claims/sections/diagrams "
            "with `aa_upsert_claim`, `aa_upsert_section`, `aa_upsert_diagram`, and `aa_set_run_meta`, and answer "
            "every checklist item with `aa_checklist`.\n"
            "3. Validate with `aa_validate` (check_files=true) and publish with `aa_finish`."
        )
    elif name == "explain-feature":
        focus = args.get("focus", "<QUESTION>")
        text = (
            f"Explain `{focus}` in `{target}` using Architect Anything (depth={depth}).\n"
            f"1. Call `aa_start` with target=\"{target}\", focus=\"{focus}\", depth=\"{depth}\".\n"
            "2. Trace from trigger to result, cite evidence with `aa_cite`, author claims/sections/diagrams "
            "via `aa_upsert_*`, update checklist items via `aa_checklist`, and publish via `aa_finish`."
        )
    else:
        focus = args.get("focus", "<MECHANISM_QUESTION>")
        text = (
            f"Extract the portable mechanism formula for `{focus}` in `{target}`.\n"
            f"1. Call `aa_start` with target=\"{target}\", focus=\"{focus}\", lens=\"mechanism\".\n"
            "2. State the core idea in product-neutral terms, separate essentials from incidentals, "
            "record host assumptions and builder choices, and publish with `aa_finish`."
        )
    return {
        "description": PROMPTS[name]["description"],
        "messages": [{"role": "user", "content": {"type": "text", "text": text}}],
    }


def handle_one(message):
    """Return a response object for a single JSON-RPC request, or None for notifications."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}
    method, ident, params = message.get("method"), message.get("id"), message.get("params") or {}
    if "id" not in message:
        return None  # notifications, including notifications/initialized
    try:
        if method == "initialize":
            asked = params.get("protocolVersion") if isinstance(params, dict) else None
            version = asked if asked in SUPPORTED_PROTOCOLS else SUPPORTED_PROTOCOLS[0]
            result = {
                "protocolVersion": version,
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                    "prompts": {"listChanged": False},
                },
                "serverInfo": {"name": "architect-anything", "version": VERSION},
                "instructions": (
                    "Organizes and publishes evidence-backed architecture reports. "
                    "Call aa_start, investigate the target, record citations with aa_cite, author claims/sections/diagrams "
                    "with aa_upsert_claim, aa_upsert_section, aa_upsert_diagram, and aa_set_run_meta, answer the checklist "
                    "with aa_checklist, then publish with aa_finish. A scaffold is not a finding."
                ),
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {
                "tools": [
                    {"name": n, "description": d, "inputSchema": s, "annotations": ann}
                    for n, (d, s, ann) in TOOLS.items()
                ]
            }
        elif method == "tools/call":
            if not isinstance(params, dict) or not isinstance(params.get("name"), str):
                return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32602, "message": "Tool name is required"}}
            result = call_tool(params["name"], params.get("arguments"))
        elif method == "resources/list":
            result = {"resources": RESOURCES}
        elif method == "resources/templates/list":
            result = {"resourceTemplates": RESOURCE_TEMPLATES}
        elif method == "resources/read":
            if not isinstance(params, dict) or not isinstance(params.get("uri"), str):
                return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32602, "message": "Resource URI is required"}}
            try:
                result = {"contents": read_mcp_resource(params["uri"])}
            except (ValueError, OSError) as exc:
                return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32602, "message": str(exc)}}
        elif method == "prompts/list":
            result = {"prompts": list(PROMPTS.values())}
        elif method == "prompts/get":
            if not isinstance(params, dict) or not isinstance(params.get("name"), str):
                return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32602, "message": "Prompt name is required"}}
            try:
                result = get_mcp_prompt(params["name"], params.get("arguments"))
            except ValueError as exc:
                return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32602, "message": str(exc)}}
        else:
            return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": f"Method not found: {method}"}}
        return {"jsonrpc": "2.0", "id": ident, "result": result}
    except Exception as exc:
        print(f"architect-anything-mcp internal error: {exc!r}", file=sys.stderr, flush=True)
        return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32603, "message": "Internal error"}}


def handle(message):
    """Handle single JSON-RPC message or batch array."""
    if isinstance(message, list):
        if not message:
            return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}
        replies = [r for item in message if (r := handle_one(item)) is not None]
        return replies or None
    return handle_one(message)


def main():
    for stream in (sys.stdin, sys.stdout):
        stream.reconfigure(encoding="utf-8", newline="\n")
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except ValueError:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        else:
            response = handle(parsed)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=True) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
