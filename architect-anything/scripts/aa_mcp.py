#!/usr/bin/env python3
"""Architect Anything MCP server (stdio, newline-delimited JSON-RPC 2.0).

Exposes the same operations as the agent CLI as MCP tools. It uses only the
Python standard library, never executes inspected targets, and never installs
or registers anything. Findings are still authored by the investigating agent.
"""
from __future__ import annotations

import json
import subprocess
import sys

from aa_cli import CommandError, parser, run
from aa_model import VERSION

SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
STRING = {"type": "string"}


def schema(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required),
            "additionalProperties": False}


EXCLUDE = {"type": "array", "items": STRING, "description": "Glob patterns to leave out of the inventory"}
TOOLS = {
    "aa_start": ("Prepare a catch-up or focused investigation workspace. Does not analyze the target.",
                 schema({"target": STRING, "focus": {"type": "string", "description": "The user's feature or design question"},
                         "depth": {"enum": ["overview", "standard", "deep"]},
                         "kind": {"enum": ["auto", "source", "product", "hybrid", "capture"]},
                         "output": STRING, "exclude": EXCLUDE}, ["target"])),
    "aa_status": ("Read an investigation's checklist, depth and report state.",
                  schema({"workspace": STRING}, ["workspace"])),
    "aa_checklist": ("Record the answer to one investigation checklist item (status plus a concrete note).",
                     schema({"workspace": STRING, "item": STRING,
                             "status": {"enum": ["unresolved", "answered", "partial", "not-applicable"]},
                             "note": STRING}, ["workspace", "item", "status"])),
    "aa_cite": ("Build a hashed evidence record for a local file; append=true adds it to the working report.",
                schema({"workspace": STRING, "path": STRING, "lines": STRING, "id": STRING,
                        "kind": {"enum": ["source", "artifact", "document"]}, "note": STRING,
                        "append": {"type": "boolean"}}, ["workspace", "path"])),
    "aa_finish": ("Check collection state and publish the authored report as an immutable snapshot.",
                  schema({"workspace": STRING, "partial": {"type": "boolean"}}, ["workspace"])),
    "aa_validate": ("Validate a report model, optionally checking cited local files and hashes.",
                    schema({"report": STRING, "check_files": {"type": "boolean"}}, ["report"])),
    "aa_render": ("Publish an authored report model without an investigation workspace.",
                  schema({"report": STRING, "output": STRING}, ["report", "output"])),
    "aa_inventory": ("Fingerprint selected local files into a new JSON file.",
                     schema({"target": STRING, "out": STRING, "exclude": EXCLUDE}, ["target", "out"])),
    "aa_compare": ("Compare two inventories or two reports.",
                   schema({"kind": {"enum": ["inventory", "report"]}, "before": STRING, "after": STRING,
                           "out": STRING}, ["kind", "before", "after"])),
    "aa_schema": ("Return a machine-readable contract: report, investigation or commands.",
                  schema({"subject": {"enum": ["report", "investigation", "commands"]}})),
    "aa_rea_status": ("Probe an existing REA CLI. Does not prove providers are ready or MCP is connected.",
                      schema({"config": STRING})),
    "aa_rea_run": ("Run one REA CLI operation, retaining output and a receipt at a new path.",
                   schema({"out": STRING, "config": STRING,
                           "arguments": {"type": "array", "items": STRING, "minItems": 1}}, ["out", "arguments"])),
}


def argv_for(name, a):
    """Translate a tool call to CLI arguments so both interfaces share one implementation."""
    def flag(option, key):
        return [option, str(a[key])] if a.get(key) not in (None, "") else []

    def many(option, key):
        return [item for value in a.get(key, []) for item in (option, str(value))]

    if name == "aa_start":
        return (["start", a["target"]] + flag("--focus", "focus") + flag("--depth", "depth")
                + flag("--kind", "kind") + flag("--output", "output") + many("--exclude", "exclude"))
    if name == "aa_status":
        return ["status", a["workspace"]]
    if name == "aa_checklist":
        return ["checklist", a["workspace"], a["item"], "--status", a["status"]] + flag("--note", "note")
    if name == "aa_cite":
        return (["cite", a["workspace"], a["path"]] + flag("--lines", "lines") + flag("--id", "id")
                + flag("--kind", "kind") + flag("--note", "note") + (["--append"] if a.get("append") else []))
    if name == "aa_finish":
        return ["finish", a["workspace"]] + (["--partial"] if a.get("partial") else [])
    if name == "aa_validate":
        return ["validate", a["report"]] + (["--check-files"] if a.get("check_files") else [])
    if name == "aa_render":
        return ["render", a["report"], "--output", a["output"]]
    if name == "aa_inventory":
        return ["inventory", a["target"], "--out", a["out"]] + many("--exclude", "exclude")
    if name == "aa_compare":
        return ["diff" if a["kind"] == "inventory" else "compare", a["before"], a["after"]] + flag("--out", "out")
    if name == "aa_schema":
        return ["schema", a.get("subject", "commands")]
    if name == "aa_rea_status":
        return ["rea", "status"] + flag("--config", "config")
    if name == "aa_rea_run":
        return ["rea", "run", "--out", a["out"]] + flag("--config", "config") + ["--", *map(str, a["arguments"])]
    raise KeyError(name)


def check_arguments(name, a):
    spec = TOOLS[name][1]
    if not isinstance(a, dict):
        raise ValueError("Tool arguments must be an object")
    for key in spec["required"]:
        if key not in a:
            raise ValueError(f"Missing required argument: {key}")
    for key, value in a.items():
        if key not in spec["properties"]:
            raise ValueError(f"Unknown argument: {key}")
        want = spec["properties"][key]
        if want.get("type") == "string" and not isinstance(value, str):
            raise ValueError(f"Argument {key} must be a string")
        if want.get("type") == "boolean" and not isinstance(value, bool):
            raise ValueError(f"Argument {key} must be a boolean")
        if want.get("type") == "array" and not (isinstance(value, list) and all(isinstance(v, str) for v in value)):
            raise ValueError(f"Argument {key} must be an array of strings")
        if "enum" in want and value not in want["enum"]:
            raise ValueError(f"Argument {key} must be one of {want['enum']}")


def call_tool(name, arguments):
    """Return an MCP tool result. Failures use the CLI's stable error codes."""
    try:
        if name not in TOOLS:
            raise ValueError(f"Unknown tool: {name}")
        arguments = arguments or {}
        check_arguments(name, arguments)
        cli = parser()
        result = run(cli.parse_args(argv_for(name, arguments)), cli)
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


def handle(message):
    """Return a response object, or None for notifications."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}
    method, ident, params = message.get("method"), message.get("id"), message.get("params") or {}
    if "id" not in message:
        return None  # notifications, including notifications/initialized
    if method == "initialize":
        asked = params.get("protocolVersion") if isinstance(params, dict) else None
        version = asked if asked in SUPPORTED_PROTOCOLS else SUPPORTED_PROTOCOLS[0]
        result = {"protocolVersion": version, "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": {"name": "architect-anything", "version": VERSION},
                  "instructions": "Organizes and publishes evidence-backed architecture reports. "
                                  "Call aa_start, investigate the target, author report.json, then aa_finish. "
                                  "A scaffold is not a finding."}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": [{"name": n, "description": d, "inputSchema": s} for n, (d, s) in TOOLS.items()]}
    elif method == "tools/call":
        if not isinstance(params, dict) or not isinstance(params.get("name"), str):
            return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32602, "message": "Tool name is required"}}
        result = call_tool(params["name"], params.get("arguments"))
    else:
        return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": f"Method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": ident, "result": result}


def main():
    for stream in (sys.stdin, sys.stdout):
        stream.reconfigure(encoding="utf-8", newline="\n")
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            response = handle(json.loads(line))
        except ValueError:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        except Exception as exc:  # keep the transport alive; report without leaking a traceback to stdout
            print(f"architect-anything-mcp internal error: {exc!r}", file=sys.stderr, flush=True)
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": "Internal error"}}
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=True) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
