#!/usr/bin/env python3
"""Generate an inspectable source fixture and offline report in a new directory."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT/"architect-anything"
sys.path.insert(0, str(SKILL/"scripts"))
sys.path.insert(0, str(SKILL/"tests"))
from aa_model import json_text
from aa_render import publish
from fixture_factory import create_source, sample_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=".demo", help="New directory; existing directories are not overwritten")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = create_source(output/"fixture")
    report = sample_report(source, run_id="field-notes-demo")
    (output/"report.json").write_text(json_text(report), encoding="utf-8")
    result = publish(report, output/"reports")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
