#!/usr/bin/env python3
"""Optional argument-array bridge to an existing REA CLI. No installation."""
import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from aa_model import PACKAGE, digest, json_text, read_json


def configuration(path=None):
    selected = path or os.environ.get("ARCHITECT_ANYTHING_REA_CONFIG")
    local = PACKAGE / "local.json"
    if not selected and local.is_file():
        selected = read_json(local).get("rea_config")
    config = read_json(selected) if selected else {}
    command = config.get("command") or ([shutil.which("rea")] if shutil.which("rea") else [])
    if not isinstance(command, list) or not all(isinstance(v, str) and v for v in command):
        raise ValueError("REA command must be a nonempty array of command/arguments")
    if not command:
        raise ValueError("No REA CLI found. Supply --config, ARCHITECT_ANYTHING_REA_CONFIG or a connected MCP server.")
    env = config.get("env", {})
    if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise ValueError("REA env must be a string-to-string object")
    executable = shutil.which(command[0]) or (command[0] if Path(command[0]).is_file() else None)
    if not executable:
        raise ValueError(f"REA executable unavailable: {command[0]}")
    command[0] = executable
    return command, config.get("cwd"), {**os.environ, **env}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["status", "run"])
    parser.add_argument("--config")
    parser.add_argument("--out")
    # split explicitly at -- so positional operation arguments are never parsed as bridge flags
    argv = sys.argv[1:]
    separator = argv.index("--") if "--" in argv else len(argv)
    args = parser.parse_args(argv[:separator])
    forwarded = argv[separator+1:] if separator < len(argv) else []
    command, cwd, env = configuration(args.config)
    if args.action == "status":
        result = subprocess.run(command + ["--version"], cwd=cwd, env=env, capture_output=True,
                                text=True, timeout=30, check=False)
        print(json_text({"available": result.returncode == 0, "command": command,
                         "version_output": result.stdout.strip(), "stderr": result.stderr.strip(),
                         "notice": "CLI availability only; provider readiness and MCP connection are not established."}), end="")
        return result.returncode
    if not args.out or not forwarded:
        parser.error("run requires --out and an operation after --")
    output = Path(args.out).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    error_path, receipt_path = Path(str(output)+".stderr.txt"), Path(str(output)+".receipt.json")
    if any(p.exists() for p in (output, error_path, receipt_path)):
        raise ValueError("Evidence output/sidecar already exists; choose a new filename")
    with output.open("xb") as stdout, error_path.open("xb") as stderr:
        # No blanket timeout: provider cleanup/lifecycle must finish. Ctrl-C remains available.
        result = subprocess.run(command + forwarded, cwd=cwd, env=env, stdout=stdout, stderr=stderr, check=False)
    receipt = {"command": command + forwarded, "exit_code": result.returncode,
               "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
               "output": str(output), "sha256": digest(output), "stderr": str(error_path),
               "complete": result.returncode == 0}
    receipt_path.write_text(json_text(receipt), encoding="utf-8")
    print(json_text(receipt), end="")
    return result.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        raise SystemExit(1)
