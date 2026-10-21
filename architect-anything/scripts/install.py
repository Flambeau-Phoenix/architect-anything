#!/usr/bin/env python3
"""Install a matching skill copy, preserving local edits and machine settings."""
import argparse
import datetime as dt
import os
import shutil
import sys
import tempfile
from pathlib import Path

from aa_model import PACKAGE, digest, json_text, read_json

HOSTS = ["codex", "claude", "agents", "antigravity"]


def default_destination(host="codex"):
    """Resolve the personal skill directory for a supported agent host."""
    if host == "antigravity":
        return str(Path.home()/".gemini/config/skills/architect-anything")
    if host == "codex":
        return str(Path(os.environ.get("CODEX_HOME", str(Path.home()/".codex")))/"skills/architect-anything")
    if host == "claude":
        return str(Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home()/".claude")))/"skills/architect-anything")
    if host == "agents":
        return str(Path.home()/".agents/skills/architect-anything")
    raise ValueError("Host must be one of: "+", ".join(HOSTS))


def host_root(host):
    """The agent's own configuration directory; its presence means the agent is installed."""
    if host == "antigravity":
        return Path.home()/".gemini"
    return Path(default_destination(host)).parents[1]


def detect_hosts():
    """Hosts whose configuration directory already exists on this machine."""
    return [host for host in HOSTS if host_root(host).is_dir()]


def install(destination, rea_config=None):
    dest = Path(destination).expanduser().resolve()
    if dest.name != "architect-anything":
        raise ValueError("Destination must be the exact architect-anything skill directory")
    if dest == PACKAGE or dest.is_relative_to(PACKAGE) or PACKAGE.is_relative_to(dest):
        raise ValueError("Installation source and destination must be separate")
    source_files = {p.relative_to(PACKAGE).as_posix(): p for p in PACKAGE.rglob("*")
                    if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
                    and p.name not in ("local.json", ".install-manifest.json")}
    old = read_json(dest/".install-manifest.json") if (dest/".install-manifest.json").is_file() else None
    if dest.exists():
        for p in dest.rglob("*"):
            if not p.is_file() or p.name in ("local.json", ".install-manifest.json") or "__pycache__" in p.parts:
                continue
            relative = p.relative_to(dest).as_posix()
            if not old or digest(p) != old.get("files", {}).get(relative):
                raise ValueError(f"Installed file has independent changes: {p}; reconcile before replacing")
    manifest = {relative: digest(path) for relative, path in source_files.items()}
    desired_local = {"rea_config": str(Path(rea_config).resolve(strict=True))} if rea_config else None
    current_local = read_json(dest/"local.json") if (dest/"local.json").is_file() else None
    if old and old.get("files") == manifest and all((dest/r).is_file() for r in manifest) and (
            desired_local is None or desired_local == current_local):
        return {"installed": str(dest), "files": len(source_files), "backup": None,
                "verified": True, "unchanged": True}
    dest.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".architect-install-", dir=dest.parent))
    backup = None
    try:
        for relative, source in source_files.items():
            target = stage/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        if dest.exists() and (dest/"local.json").is_file():
            shutil.copy2(dest/"local.json", stage/"local.json")
        if rea_config:
            config = Path(rea_config).resolve(strict=True)
            (stage/"local.json").write_text(json_text({"rea_config": str(config)}), encoding="utf-8")
        (stage/".install-manifest.json").write_text(json_text({"files": manifest}), encoding="utf-8")
        if dest.exists():
            stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            # Keep backups out of the skills directory: an agent that scans it would otherwise
            # find a second copy of this skill (with its own SKILL.md) next to the real one.
            backups = dest.parent.parent/".architect-anything-backups"
            backups.mkdir(exist_ok=True)
            backup = backups/stamp
            dest.rename(backup)
        try:
            stage.rename(dest)
        except OSError:
            if backup:
                backup.rename(dest)
            raise
        return {"installed": str(dest), "files": len(source_files),
                "backup": str(backup) if backup else None,
                "verified": all(digest(dest/r) == sha for r, sha in manifest.items())}
    finally:
        if stage.exists():
            if not stage.resolve().is_relative_to(dest.parent):
                raise ValueError("Refusing cleanup outside the selected installation parent")
            shutil.rmtree(stage)  # Own temporary sibling, created above.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=HOSTS,
                        help="Agent to install for; omitted, every agent found on this machine is used")
    parser.add_argument("--destination", help="Exact architect-anything skill directory; overrides --host")
    parser.add_argument("--rea-config")
    args = parser.parse_args()
    if args.destination or args.host:
        print(json_text(install(args.destination or default_destination(args.host), args.rea_config)), end="")
        return
    found = detect_hosts()
    if not found:
        raise ValueError("No supported agent found (looked for "
                         + ", ".join(str(host_root(h)) for h in HOSTS) + "); pass --host or --destination")
    results = {host: install(default_destination(host), args.rea_config) for host in found}
    print(json_text({"detected": found, "installs": results}), end="")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
