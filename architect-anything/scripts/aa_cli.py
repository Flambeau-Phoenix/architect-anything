#!/usr/bin/env python3
"""Agent-facing architecture workflow. Findings are authored by the investigating agent."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from aa_inventory import compare_inventory, inventory
from aa_investigation import DEFAULT_DEPTH, DEPTHS, finish, start, status
from aa_model import PACKAGE, SCHEMA, VERSION, compare_reports, json_text, read_json, validate
from aa_render import publish


class CommandError(Exception):
    def __init__(self, code, message, exit_code=2, details=None):
        super().__init__(message)
        self.code, self.exit_code, self.details = code, exit_code, details


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise CommandError("invalid_arguments", message)


def parser():
    p = Parser(prog="architect-anything", description=__doc__)
    p.add_argument("--version", action="version", version=VERSION)
    commands = p.add_subparsers(dest="command", required=True)
    begin = commands.add_parser("start", help="Set up a catch-up or focused investigation for the agent")
    begin.add_argument("target", help="Local project/artifact path or product URL")
    begin.add_argument("--focus", help="The user's feature or design question")
    begin.add_argument("--output", help="Report directory; defaults to docs/architecture for source")
    begin.add_argument("--kind", choices=["auto", "source", "product", "hybrid", "capture"], default="auto")
    begin.add_argument("--depth", choices=list(DEPTHS), default=DEFAULT_DEPTH,
                       help="overview: owner-level answer; standard: full walkthrough; deep: verbose technical reference")
    begin.add_argument("--exclude", action="append", default=[])
    begin.add_argument("--max-files", type=int, default=100000)
    begin.add_argument("--max-file-bytes", type=int, default=268435456)
    inspect = commands.add_parser("status", help="Read an investigation's checklist and report state")
    inspect.add_argument("workspace")
    end = commands.add_parser("finish", help="Check collection state and publish the authored report")
    end.add_argument("workspace")
    end.add_argument("--partial", action="store_true", help="Explicitly publish documented remaining gaps")
    schema = commands.add_parser("schema", help="Return a machine-readable contract")
    schema.add_argument("subject", choices=["report", "investigation", "commands"], default="commands", nargs="?")
    inv = commands.add_parser("inventory", help="Fingerprint selected local files")
    inv.add_argument("target")
    inv.add_argument("--exclude", action="append", default=[])
    inv.add_argument("--out", required=True)
    for name in ("diff", "compare"):
        item = commands.add_parser(name, help="Compare inventories" if name == "diff" else "Compare report findings")
        item.add_argument("before")
        item.add_argument("after")
        item.add_argument("--out")
    val = commands.add_parser("validate", help="Validate a report and optionally its local evidence")
    val.add_argument("report")
    val.add_argument("--check-files", action="store_true")
    render = commands.add_parser("render", help="Publish an authored model without an investigation workspace")
    render.add_argument("report")
    render.add_argument("--output", required=True)
    rea = commands.add_parser("rea", help="Use an existing REA CLI through its configured bridge")
    actions = rea.add_subparsers(dest="rea_action", required=True)
    for name in ("status", "run"):
        action = actions.add_parser(name)
        action.add_argument("--config")
        if name == "run":
            action.add_argument("--out", required=True)
            action.add_argument("arguments", nargs=argparse.REMAINDER)
    install = commands.add_parser("install-skill", help="Install this skill for the local agent")
    install.add_argument("--host", choices=["codex", "antigravity"], default="codex")
    install.add_argument("--destination", help="Exact architect-anything skill directory; overrides --host")
    install.add_argument("--rea-config")
    return p


def command_contract(p):
    result = {"schema_version": 1, "version": VERSION, "invocation": "architect-anything",
              "success": {"ok": True, "command": "command name", "result": "operation result"},
              "failure": {"ok": False, "command": "command name", "error": {"code": "stable code", "message": "explanation"}},
              "streams": {"stdout": "Success JSON; help/version are plain text", "stderr": "Failure JSON"},
              "exit_codes": {"0": "success", "1": "report validation failed", "2": "invalid arguments or input",
                             "3": "filesystem/process failure", "4": "REA unavailable or failed"},
              "commands": []}
    group = next(a for a in p._actions if isinstance(a, argparse._SubParsersAction))
    for name, cmd in group.choices.items():
        result["commands"].append({"name": name, "help": cmd.format_help()})
    return result


def write_result(path, result):
    output = Path(path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json_text(result), encoding="utf-8")
    return {"output": str(output)}


def run(args, p):
    if args.command == "start":
        return start(args.target, args.output, args.focus, args.kind, args.exclude, args.max_files,
                     args.max_file_bytes, args.depth)
    if args.command == "status":
        return status(args.workspace)
    if args.command == "finish":
        return finish(args.workspace, args.partial)
    if args.command == "schema":
        return SCHEMA if args.subject == "report" else (
            read_json(PACKAGE/"assets/investigation.schema.json") if args.subject == "investigation" else command_contract(p))
    if args.command == "inventory":
        target, dest = Path(args.target).resolve(), Path(args.out).resolve()
        if target == dest:
            raise ValueError("Inventory output cannot overwrite the target")
        excluded = list(args.exclude)
        if dest.is_relative_to(target):
            excluded.append(dest.relative_to(target).as_posix())
        return write_result(dest, inventory(target, excluded))
    if args.command in ("diff", "compare"):
        compare = compare_inventory if args.command == "diff" else compare_reports
        result = compare(read_json(args.before), read_json(args.after))
        return write_result(args.out, result) if args.out else result
    if args.command == "validate":
        result = validate(read_json(args.report), args.check_files)
        if not result["valid"]:
            raise CommandError("validation_failed", "Report validation failed", 1, result)
        return result
    if args.command == "render":
        return publish(read_json(args.report), args.output)
    if args.command == "rea":
        command = [sys.executable, str(PACKAGE/"scripts/rea_bridge.py"), args.rea_action]
        if args.config:
            command += ["--config", args.config]
        if args.rea_action == "run":
            operation = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
            if not operation:
                raise ValueError("REA run needs an operation after --")
            command += ["--out", args.out, "--", *operation]
        process = subprocess.run(command, capture_output=True, text=True)
        if process.returncode:
            try:
                details = json.loads(process.stdout or process.stderr)
            except ValueError:
                details = {"diagnostic": process.stderr.strip()}
            raise CommandError("rea_unavailable_or_failed", "REA bridge did not complete successfully", 4, details)
        return json.loads(process.stdout)
    if args.command == "install-skill":
        from install import default_destination, install
        return install(args.destination or default_destination(args.host), args.rea_config)
    raise ValueError("Unknown command")


def main(argv=None):
    name = None
    try:
        p = parser()
        args = p.parse_args(argv)
        name = args.command
        result = run(args, p)
        print(json_text({"ok": True, "command": name, "result": result}), end="")
        return 0
    except CommandError as exc:
        error = {"code": exc.code, "message": str(exc)}
        if exc.details is not None:
            error["details"] = exc.details
        print(json_text({"ok": False, "command": name, "error": error}), file=sys.stderr, end="")
        return exc.exit_code
    except (ValueError, KeyError, TypeError) as exc:
        print(json_text({"ok": False, "command": name, "error": {"code": "invalid_input", "message": str(exc)}}), file=sys.stderr, end="")
        return 2
    except (OSError, subprocess.SubprocessError) as exc:
        print(json_text({"ok": False, "command": name, "error": {"code": "operation_failed", "message": str(exc)}}), file=sys.stderr, end="")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
