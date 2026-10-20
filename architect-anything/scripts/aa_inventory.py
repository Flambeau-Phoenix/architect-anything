"""Bounded inventories and conservative comparisons; never execute target code."""
from __future__ import annotations

import datetime as dt
import fnmatch
import hashlib
import json
import os
import subprocess
from pathlib import Path

from aa_model import digest

DEFAULT_EXCLUDES = [".git", "node_modules", ".venv", "venv", "__pycache__", ".cache",
                    "docs/architecture"]


def git(root, *args):
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                              timeout=30, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None


def inventory(target, excludes=(), max_files=100000, max_bytes=268435456):
    root = Path(target).resolve(strict=True)
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    patterns = sorted(set(DEFAULT_EXCLUDES + list(excludes)))
    files, omissions, errors = [], [], []
    git_state = None
    selection_source = "explicit-file" if root.is_file() else "filesystem"
    candidates = []
    if root.is_file():
        candidates = [root]
    else:
        revision = git(root, "rev-parse", "HEAD")
        ignored_root = git(root, "check-ignore", "-q", "--", ".") is not None
        listing = None if ignored_root else git(root, "ls-files", "-c", "-o", "--exclude-standard", "-z")
        if listing is not None:
            selection_source = "git"
            candidates = [root / os.fsdecode(p) for p in sorted(set(listing.split(b"\0"))) if p]
            status = git(root, "status", "--porcelain=v1", "-z", "--", ".")
            git_state = {"revision": revision.decode().strip() if revision else None,
                         "status_records": [os.fsdecode(v) for v in (status or b"").split(b"\0") if v],
                         "status_available": status is not None}
        else:
            if ignored_root:
                selection_source = "filesystem-ignored-root"
            def walk_error(exc):
                errors.append({"path": str(exc.filename), "reason": str(exc)})
            for directory, dirs, names in os.walk(root, followlinks=False, onerror=walk_error):
                for name in list(dirs):
                    p = Path(directory) / name
                    rel = p.relative_to(root).as_posix()
                    if p.is_symlink() or getattr(p, "is_junction", lambda: False)() or excluded(rel, patterns):
                        dirs.remove(name)
                        reason = "link" if p.is_symlink() or getattr(p, "is_junction", lambda: False)() else "exclusion"
                        omissions.append({"path": rel, "reason": reason})
                candidates.extend(Path(directory) / name for name in names)
    for position, path in enumerate(sorted(candidates)):
        rel = path.name if root.is_file() else path.relative_to(root).as_posix()
        if position >= max_files:
            omissions.append({"path": "*", "reason": f"candidate limit {max_files}; remaining files unexamined"})
            break
        if excluded(rel, patterns):
            omissions.append({"path": rel, "reason": "exclusion"})
            continue
        try:
            # A tracked path may traverse a directory replaced by a link.
            if path.is_symlink() or path.resolve() != path.absolute():
                omissions.append({"path": rel, "reason": "link"})
                continue
            if not path.is_file():
                omissions.append({"path": rel, "reason": "missing or non-regular"})
                continue
            before = path.stat()
            if not root.is_file() and max_bytes and before.st_size > max_bytes:
                omissions.append({"path": rel, "reason": f"over byte limit {max_bytes}"})
                continue
            sha = digest(path)
            after = path.stat()
            stable = (before.st_size, before.st_mtime_ns, before.st_ino) == (
                after.st_size, after.st_mtime_ns, after.st_ino)
            files.append({"path": rel, "bytes": after.st_size, "sha256": sha, "stable": stable})
            if not stable:
                errors.append({"path": rel, "reason": "changed while hashing"})
        except OSError as exc:
            errors.append({"path": rel, "reason": str(exc)})
    git_end = git(root, "status", "--porcelain=v1", "-z", "--", ".") if git_state else None
    if git_state and git_end is not None:
        if git_state["status_records"] != [os.fsdecode(v) for v in git_end.split(b"\0") if v]:
            errors.append({"path": ".", "reason": "git state changed during inventory"})
    fingerprint = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {"schema_version": 1, "target": str(root), "target_kind": "file" if root.is_file() else "directory",
            "started_at": started, "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "git": git_state, "selection_source": selection_source, "excludes": patterns, "files": files, "omissions": omissions, "errors": errors,
            "selection_sha256": fingerprint, "coverage": "partial" if errors or omissions else "complete",
            "notice": "Coverage describes selected local files, not architecture or runtime completeness. Git inventories omit ignored files; an explicitly selected ignored directory uses filesystem traversal."}


def excluded(relative, patterns):
    return any(fnmatch.fnmatchcase(relative, p) or relative.startswith(p.rstrip("/") + "/")
               or any(fnmatch.fnmatchcase(part, p) for part in relative.split("/")) for p in patterns)


def compare_inventory(old, new):
    if old.get("schema_version") != 1 or new.get("schema_version") != 1:
        raise ValueError("Unsupported inventory version")
    if old["target"] != new["target"]:
        raise ValueError("Different inventory targets; compare selected versions with report/REA comparison")
    a, b = ({f["path"]: f for f in item["files"]} for item in (old, new))
    # Changes inside explicitly excluded output/dependency trees do not change selected coverage.
    # Unexpected omissions (links, capacity, missing files) remain comparable evidence.
    meaningful_omissions = lambda item: [o for o in item["omissions"] if o["reason"] != "exclusion"]
    coverage_changed = (old.get("selection_source") != new.get("selection_source")
                        or old.get("excludes") != new.get("excludes") or old.get("errors") != new.get("errors")
                        or meaningful_omissions(old) != meaningful_omissions(new))
    result = {"added": sorted(b.keys() - a.keys()), "removed": sorted(a.keys() - b.keys()),
              "changed": sorted(p for p in a.keys() & b.keys() if a[p]["sha256"] != b[p]["sha256"]),
              "unchanged": sorted(p for p in a.keys() & b.keys() if a[p]["sha256"] == b[p]["sha256"]),
              "coverage_changed": coverage_changed,
              "comparable": not coverage_changed and not old["errors"] and not new["errors"]}
    result["notice"] = "Removals under changed/incomplete coverage may be unobserved files, not deletions."
    return result
