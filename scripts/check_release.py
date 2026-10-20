#!/usr/bin/env python3
"""Check the portable skill, repository links and public-release boundaries."""
import ast
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT/"architect-anything"
sys.path.insert(0, str(SKILL/"scripts"))
from aa_model import validate, read_json

IGNORED = {".git", "__pycache__", ".demo", ".cli-demo", ".test-temp", "dist", ".venv", "build"}
FORBIDDEN = {"local.json", ".install-manifest.json", ".env"}
TEXT_SUFFIXES = {".py", ".md", ".json", ".toml", ".yaml", ".yml", ".js", ".css", ".txt"}


def files():
    return sorted(p for p in ROOT.rglob("*") if p.is_file()
                  and not any(part in IGNORED or part.endswith(".egg-info") for part in p.relative_to(ROOT).parts))


def check():
    errors = []
    required = ["README.md", "LICENSE", "CHANGELOG.md", "CONTRIBUTING.md",
                "THIRD_PARTY_NOTICES.md", ".gitignore", ".gitattributes",
                ".github/workflows/validate.yml", "docs/validation.md",
                "docs/release-1.0.0.md", "architect-anything/SKILL.md",
                "architect-anything/LICENSE", "architect-anything/agents/openai.yaml",
                "architect-anything/assets/REA-LICENSE.txt", "pyproject.toml",
                "architect-anything/scripts/aa_cli.py", "architect-anything/references/catch-up-and-focus.md"]
    for name in required:
        if not (ROOT/name).is_file():
            errors.append(f"Missing release file: {name}")
    entry = (SKILL/"SKILL.md").read_text(encoding="utf-8")
    if not entry.startswith("---\n") or "name: architect-anything\n" not in entry:
        errors.append("Skill identity/frontmatter is invalid")
    version = re.search(r'^\s+version: "(\d+\.\d+\.\d+)"$', entry, flags=re.M)
    if not version:
        errors.append("Skill version is missing")
    if (ROOT/"LICENSE").read_bytes() != (SKILL/"LICENSE").read_bytes():
        errors.append("Portable and repository MIT licenses differ")
    count = 0
    for path in files():
        relative = path.relative_to(ROOT)
        if path.is_symlink():
            errors.append(f"Release file is a symlink: {relative}")
        if path.name in FORBIDDEN or path.name.endswith(".local.json"):
            errors.append(f"Machine/private setting included: {relative}")
        if path.suffix.lower() in {".exe", ".dll", ".node", ".asar", ".har", ".saz", ".pcap", ".pcapng", ".zip", ".whl"}:
            errors.append(f"Generated/runtime artifact included: {relative}")
        if path.stat().st_size > 1024*1024:
            errors.append(f"Unexpectedly large public file: {relative}")
        if path.suffix in TEXT_SUFFIXES or path.name in ("LICENSE", ".gitignore", ".gitattributes"):
            text = path.read_text(encoding="utf-8-sig")
            # Generic C:/tools examples are allowed; real account/workspace paths are not.
            private_path = re.search(r"(?i)\b[A-Z]:[\\/](?:Users[\\/][^\\/\s\"']+|Architect-Anything|SolarFlareGitRepo)\b", text)
            private_key = re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", text)
            access_token = re.search(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b", text)
            if private_path or private_key or access_token:
                errors.append(f"Private path or credential-shaped content: {relative}")
        if path.suffix == ".py":
            try:
                ast.parse(path.read_text(encoding="utf-8"), feature_version=(3,10))
            except SyntaxError as exc:
                errors.append(f"Python 3.10 syntax: {relative}: {exc}")
        if path.suffix == ".md":
            for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                if "://" in target or target.startswith("#"):
                    continue
                file_target = target.split("#",1)[0].strip("<>")
                if file_target and not (path.parent/file_target).exists():
                    errors.append(f"Broken local link: {relative} -> {target}")
        count += 1
    result = validate(read_json(SKILL/"examples/minimal-report.json"), check_files=True)
    if not result["valid"]:
        errors.extend(result["errors"])
    return {"valid": not errors, "version": version.group(1) if version else None,
            "public_files": count, "errors": errors}


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["valid"] else 1)
