#!/usr/bin/env python3
"""Architect Anything deterministic helpers. Run --help for interfaces."""
import argparse
import json
import sys
from pathlib import Path

from aa_inventory import compare_inventory, inventory
from aa_model import compare_reports, json_text, read_json, validate
from aa_render import publish


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inv = commands.add_parser("inventory", help="Hash selected files without executing the target")
    inv.add_argument("target")
    inv.add_argument("--exclude", action="append", default=[])
    inv.add_argument("--max-files", type=int, default=100000)
    inv.add_argument("--max-file-bytes", type=int, default=268435456)
    inv.add_argument("--out", required=True)
    for name in ("diff", "compare"):
        cmd = commands.add_parser(name)
        cmd.add_argument("before")
        cmd.add_argument("after")
        cmd.add_argument("--out")
    check = commands.add_parser("validate")
    check.add_argument("report")
    check.add_argument("--check-files", action="store_true")
    render = commands.add_parser("render")
    render.add_argument("report")
    render.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "inventory":
        if args.max_files < 1 or args.max_file_bytes < 0:
            parser.error("limits must be positive; max-file-bytes=0 permits unlimited streaming hashes")
        target, dest = Path(args.target).resolve(), Path(args.out).resolve()
        if dest == target:
            parser.error("inventory output cannot overwrite the target")
        excluded = list(args.exclude)
        if dest.is_relative_to(target):
            excluded.append(dest.relative_to(target).as_posix())
        result = inventory(target, excluded, args.max_files, args.max_file_bytes)
    elif args.command == "diff":
        result = compare_inventory(read_json(args.before), read_json(args.after))
    elif args.command == "compare":
        result = compare_reports(read_json(args.before), read_json(args.after))
    elif args.command == "validate":
        result = validate(read_json(args.report), args.check_files)
    else:
        result = publish(read_json(args.report), args.output)
    destination = getattr(args, "out", None)
    if destination:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json_text(result), encoding="utf-8")
        print(json_text({"output": str(path.resolve()), "command": args.command}), end="")
    else:
        print(json_text(result), end="")
    return 1 if args.command == "validate" and not result["valid"] else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        raise SystemExit(1)
