import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from aa_investigation import (
    DEEP_FOCUS,
    FOCUS,
    LENSES,
    MECHANISM,
    finish,
    load,
    questions_for,
    set_checklist,
    start,
    status,
)
from fixture_factory import create_source, sample_report

SKILL = Path(__file__).resolve().parents[1]
CLI = SKILL/"scripts/aa_cli.py"
MCP = SKILL/"scripts/aa_mcp.py"
IDS = [key for key, _ in MECHANISM]


class Checklists(unittest.TestCase):
    def ids(self, mode, depth, lens=None):
        return [key for key, _ in questions_for(mode, depth, lens)]

    def test_standard_lens_checklist(self):
        self.assertEqual(self.ids("focus", "standard", "mechanism"),
                         ["answer", "trace", "contract", "essentials", "assumptions", "choices", "limits"])

    def test_overview_keeps_the_owner_level_core(self):
        self.assertEqual(self.ids("focus", "overview", "mechanism"), ["answer", "essentials", "choices", "limits"])

    def test_deep_adds_the_same_technical_rows_as_other_focused_runs(self):
        deep = self.ids("focus", "deep", "mechanism")
        self.assertEqual(deep[:len(IDS)], IDS)
        self.assertEqual(deep[len(IDS):], [key for key, _ in DEEP_FOCUS])

    def test_no_lens_is_unchanged(self):
        self.assertEqual(self.ids("focus", "standard"), [key for key, _ in FOCUS])
        self.assertEqual(self.ids("focus", "standard", None), self.ids("focus", "standard"))

    def test_lens_needs_a_focus_and_must_be_known(self):
        with self.assertRaisesRegex(ValueError, "needs a focus"):
            questions_for("catch-up", "standard", "mechanism")
        with self.assertRaisesRegex(ValueError, "Lens must be one of"):
            questions_for("focus", "standard", "poetry")

    def test_every_lens_row_has_a_title(self):
        from aa_investigation import TITLES
        self.assertTrue(all(key in TITLES for key in IDS))
        self.assertEqual(LENSES, ("mechanism",))


class Workspace(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = create_source(self.root/"project")

    def tearDown(self):
        self.temp.cleanup()

    def test_start_records_the_lens_and_lays_out_sections(self):
        opened = start(self.source, focus="How are writes serialized?", lens="mechanism")
        self.assertEqual(opened["lens"], "mechanism")
        _path, data = load(opened["workspace"])
        self.assertEqual(data["lens"], "mechanism")
        self.assertEqual([r["id"] for r in data["checklist"]], IDS)
        report = json.loads(Path(data["paths"]["report"]).read_text(encoding="utf-8"))
        detail = {s["id"]: s["detail"] for s in report["sections"]}
        for owner_level in ("answer", "essentials", "choices", "limits"):
            self.assertFalse(detail[owner_level], owner_level)
        for technical in ("trace", "contract", "assumptions"):
            self.assertTrue(detail[technical], technical)
        self.assertEqual(status(opened["workspace"])["lens"], "mechanism")

    def test_without_a_lens_the_manifest_is_unchanged(self):
        opened = start(self.source, focus="How are writes serialized?")
        _, data = load(opened["workspace"])
        self.assertNotIn("lens", data)
        self.assertIsNone(status(opened["workspace"])["lens"])
        self.assertIsNone(opened["lens"])

    def test_start_refuses_a_lens_without_a_focus(self):
        with self.assertRaisesRegex(ValueError, "needs a focus"):
            start(self.source, lens="mechanism")

    def test_a_lens_run_publishes_like_any_other(self):
        opened = start(self.source, focus="How are writes serialized?", lens="mechanism", depth="overview")
        _path, data = load(opened["workspace"])
        report = sample_report(self.source, data["id"])
        report["target"] = data["target"]
        Path(data["paths"]["report"]).write_text(json.dumps(report), encoding="utf-8")
        for row in data["checklist"]:
            set_checklist(opened["workspace"], row["id"], "answered", "Traced in the authored report with source claims.")
        self.assertTrue(Path(finish(opened["workspace"])["html"]).is_file())

    def test_a_scaffold_is_still_refused(self):
        opened = start(self.source, focus="How are writes serialized?", lens="mechanism")
        with self.assertRaisesRegex(ValueError, "scaffold"):
            finish(opened["workspace"], partial=True)


class Interfaces(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.source = create_source(Path(self.temp.name)/"project")

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        process = subprocess.run([sys.executable, str(CLI), *map(str, args)], capture_output=True, text=True, env=env, check=False)
        return process, json.loads(process.stdout or process.stderr)

    def test_cli_accepts_the_lens(self):
        process, out = self.cli("start", self.source, "--focus", "How are writes serialized?", "--lens", "mechanism")
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(out["result"]["lens"], "mechanism")

    def test_cli_error_envelope_for_a_lens_without_focus(self):
        process, out = self.cli("start", self.source, "--lens", "mechanism")
        self.assertEqual(process.returncode, 2)
        self.assertEqual(out["error"]["code"], "invalid_input")
        process, out = self.cli("start", self.source, "--focus", "x", "--lens", "poetry")
        self.assertEqual(process.returncode, 2)
        self.assertEqual(out["error"]["code"], "invalid_arguments")

    def test_mcp_start_accepts_the_lens(self):
        frames = "".join(json.dumps(m)+"\n" for m in [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "aa_start", "arguments": {
                "target": str(self.source), "focus": "How are writes serialized?", "lens": "mechanism"}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "aa_start", "arguments": {
                "target": str(self.source), "lens": "mechanism"}}},
        ])
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        process = subprocess.run([sys.executable, str(MCP)], input=frames, capture_output=True, text=True, env=env, timeout=120, check=False)
        by_id = {r["id"]: r["result"] for r in map(json.loads, process.stdout.splitlines())}
        start_tool = next(t for t in by_id[1]["tools"] if t["name"] == "aa_start")
        self.assertEqual(start_tool["inputSchema"]["properties"]["lens"]["enum"], ["mechanism"])
        self.assertFalse(by_id[2]["isError"])
        self.assertEqual(by_id[2]["structuredContent"]["result"]["lens"], "mechanism")
        self.assertTrue(by_id[3]["isError"])  # a lens without a focus is refused


class Documentation(unittest.TestCase):
    """The guide, the checklist and the skill's routing must not drift apart."""

    def test_guide_covers_every_checklist_row(self):
        guide = (SKILL/"references/mechanism-lens.md").read_text(encoding="utf-8")
        for key in IDS:
            self.assertIn(f"`{key}`", guide, key)

    def test_skill_routes_to_the_guide_and_names_the_flag(self):
        skill = (SKILL/"SKILL.md").read_text(encoding="utf-8")
        self.assertIn("references/mechanism-lens.md", skill)
        self.assertIn("--lens mechanism", skill)
        self.assertIn("1:1", skill)


if __name__ == "__main__":
    unittest.main()
