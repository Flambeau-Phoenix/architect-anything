#!/usr/bin/env python3
"""Build a deterministic portable skill archive. Does not commit or publish."""
import hashlib
import json
import os
from pathlib import Path
import zipfile

from check_release import ROOT, SKILL, check

TEXT_SUFFIXES = {".py", ".md", ".json", ".yaml", ".yml", ".css", ".js", ".txt"}


def main():
    checked = check()
    if not checked["valid"]:
        raise ValueError("\n".join(checked["errors"]))
    version = checked["version"]
    output = ROOT/"dist"
    output.mkdir(exist_ok=True)
    archive = output/f"architect-anything-{version}.zip"
    temp = output/f".architect-anything-{version}.zip.tmp"
    payloads = {}
    for path in sorted(SKILL.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        name = "architect-anything/"+path.relative_to(SKILL).as_posix()
        data = path.read_bytes()
        if path.suffix in TEXT_SUFFIXES or path.name == "LICENSE":
            data = data.replace(b"\r\n", b"\n")
        payloads[name] = data
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as stream:
            for name, data in payloads.items():
                info = zipfile.ZipInfo(name, date_time=(1980,1,1,0,0,0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                stream.writestr(info, data)
        with zipfile.ZipFile(temp) as stream:
            if stream.testzip() is not None:
                raise ValueError("Archive CRC validation failed")
            if set(stream.namelist()) != set(payloads):
                raise ValueError("Archive contents differ from selected package")
            for name, data in payloads.items():
                if stream.read(name) != data:
                    raise ValueError(f"Archive payload mismatch: {name}")
        os.replace(temp, archive)
    finally:
        temp.unlink(missing_ok=True)
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest = {"version": version, "archive": archive.name, "sha256": sha,
                "normalization": "Text payloads use LF; fixed ZIP timestamps and permissions.",
                "files": {name: hashlib.sha256(data).hexdigest() for name,data in payloads.items()}}
    (output/f"{archive.name}.sha256").write_text(f"{sha}  {archive.name}\n", encoding="utf-8")
    (output/f"architect-anything-{version}.manifest.json").write_text(
        json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"archive": str(archive), "sha256": sha, "skill_files": len(payloads)}, indent=2))


if __name__ == "__main__":
    main()
