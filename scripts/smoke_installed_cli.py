#!/usr/bin/env python3
"""Exercise the installed console command from outside the source checkout."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"architect-anything/scripts"))
sys.path.insert(0,str(ROOT/"architect-anything/tests"))
from aa_model import json_text, read_json
from fixture_factory import create_source, sample_report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--command",default="architect-anything")
    args = p.parse_args()
    command = shutil.which(args.command)
    if not command:
        raise ValueError("Install the CLI or provide --command with its executable path")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = create_source(root/"field-notes")
        env = dict(os.environ,PYTHONDONTWRITEBYTECODE="1")
        env.pop("PYTHONPATH",None)
        def run(*arguments, expected=0):
            process = subprocess.run([command,*map(str,arguments)],cwd=root,env=env,
                                     capture_output=True,text=True,check=False)
            if process.returncode != expected:
                raise ValueError(f"Command failed: {arguments}: {process.stderr}")
            if expected:
                assert not process.stdout
                result = json.loads(process.stderr)
                assert not result["ok"]
            else:
                assert not process.stderr
                result = json.loads(process.stdout)
                assert result["ok"]
            return result
        version = subprocess.run([command,"--version"],cwd=root,env=env,check=True,
                                 capture_output=True,text=True).stdout.strip()
        assert re.fullmatch(r"\d+\.\d+\.\d+",version)
        assert "run" in run("schema","report")["result"]["properties"]
        opened = run("start",source)["result"]
        assert opened["mode"] == "catch-up"
        rejected = run("finish",opened["workspace"],expected=2)
        assert "scaffold" in rejected["error"]["message"]
        work = Path(opened["workspace"])
        manifest = read_json(work/"investigation.json")
        report = sample_report(source,manifest["id"])
        report["target"] = manifest["target"]
        (work/"report.json").write_text(json_text(report),encoding="utf-8")
        for row in manifest["checklist"]:
            row["status"] = "answered" if row["id"] != "changes" else "not-applicable"
            row["note"] = "Fixture source inspected; see report citations." if row["id"] != "changes" else "First report; no prior baseline."
        (work/"investigation.json").write_text(json_text(manifest),encoding="utf-8")
        finished = run("finish",work)["result"]
        assert Path(finished["html"]).is_file()
        assert run("finish",work)["result"]["already_published"]
        current = (source/"docs/architecture/current.json").read_bytes()
        question = "How are overlapping writes prevented?"
        focused = run("start",source,"--focus",question)["result"]
        assert focused["question"] == question and focused["mode"] == "focus"
        assert run("status",focused["workspace"])["result"]["question"] == question
        assert (source/"docs/architecture/current.json").read_bytes() == current
        unavailable = root/"rea.json"
        unavailable.write_text(json.dumps({"command":[str(root/"not-installed")]}),encoding="utf-8")
        assert run("rea","status","--config",unavailable,expected=4)["error"]["code"] == "rea_unavailable_or_failed"
    print(json.dumps({"installed_cli":True,"version":version,
                      "checks":["bundled schema","catch-up publication","scaffold refusal","resume",
                                "focused question","whole-project preservation","REA error protocol"]},indent=2))


if __name__ == "__main__":
    main()
