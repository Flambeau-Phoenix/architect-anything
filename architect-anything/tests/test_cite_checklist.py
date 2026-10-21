import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from aa_investigation import cite, finish, load, parse_lines, set_checklist, start, status
from aa_model import digest, read_json, validate
from fixture_factory import create_source, sample_report
from install import default_destination, install

SKILL = Path(__file__).resolve().parents[1]
CLI = SKILL/"scripts/aa_cli.py"
MCP = SKILL/"scripts/aa_mcp.py"


class Checklist(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = create_source(self.root/"project")
        self.opened = start(self.source)

    def tearDown(self):
        self.temp.cleanup()

    def test_records_answer_and_reports_remaining(self):
        result = set_checklist(self.opened["workspace"], "briefing", "answered", "Entry points and README read.")
        self.assertEqual(result["item"]["status"], "answered")
        self.assertNotIn("briefing", result["remaining"])
        saved = {r["id"]: r for r in load(self.opened["workspace"])[1]["checklist"]}
        self.assertEqual(saved["briefing"]["note"], "Entry points and README read.")
        self.assertEqual(status(self.opened["workspace"])["remaining"], result["remaining"])

    def test_note_is_required_except_to_reopen(self):
        with self.assertRaisesRegex(ValueError, "explanatory note"):
            set_checklist(self.opened["workspace"], "data", "partial", "  ")
        set_checklist(self.opened["workspace"], "data", "partial", "Only the file store was traced.")
        reopened = set_checklist(self.opened["workspace"], "data", "unresolved")
        self.assertEqual(reopened["item"]["note"], "")

    def test_rejects_unknown_item_and_status(self):
        with self.assertRaisesRegex(ValueError, "Unknown checklist item"):
            set_checklist(self.opened["workspace"], "nonsense", "answered", "x")
        with self.assertRaisesRegex(ValueError, "Status must be"):
            set_checklist(self.opened["workspace"], "briefing", "done", "x")

    def test_deep_note_warning_matches_finish_rule(self):
        deep = start(self.source, depth="deep", output=self.root/"deep")
        result = set_checklist(deep["workspace"], "interfaces", "answered", "Short.")
        self.assertIn("warning", result)
        ok = set_checklist(deep["workspace"], "interfaces", "answered", "HTTP routes and the store module contracts were read in full.")
        self.assertNotIn("warning", ok)

    def test_status_points_to_next_step(self):
        self.assertIn("unresolved checklist items", status(self.opened["workspace"])["next"])


class Cite(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = create_source(self.root/"project")
        self.opened = start(self.source)

    def tearDown(self):
        self.temp.cleanup()

    def test_builds_hashed_relative_record(self):
        record = cite(self.opened["workspace"], "service.js", lines="5-9", note="Writes are chained")["evidence"]
        self.assertEqual(record["path"], "service.js")
        self.assertEqual((record["line_start"], record["line_end"]), (5, 9))
        self.assertEqual(record["sha256"], digest(self.source/"service.js"))
        self.assertEqual(record["locator"], "service.js:5-9")
        self.assertRegex(record["id"], r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")

    def test_absolute_path_inside_target_is_cited_relatively(self):
        record = cite(self.opened["workspace"], str(self.source/"store.js"))["evidence"]
        self.assertEqual(record["path"], "store.js")
        self.assertNotIn("line_start", record)

    def test_rejects_missing_file_bad_range_and_kind(self):
        workspace = self.opened["workspace"]
        with self.assertRaisesRegex(ValueError, "does not exist"):
            cite(workspace, "absent.js")
        with self.assertRaisesRegex(ValueError, "outside the file"):
            cite(workspace, "service.js", lines="1-999")
        with self.assertRaisesRegex(ValueError, "Lines must"):
            cite(workspace, "service.js", lines="9-5")
        with self.assertRaisesRegex(ValueError, "Lines must"):
            cite(workspace, "service.js", lines="abc")
        with self.assertRaisesRegex(ValueError, "kinds"):
            cite(workspace, "service.js", kind="rea")
        with self.assertRaisesRegex(ValueError, "Evidence ID"):
            cite(workspace, "service.js", ident="9bad")

    def test_append_is_idempotent_and_refuses_duplicate_ids(self):
        workspace = self.opened["workspace"]
        first = cite(workspace, "service.js", lines="1-3", append=True)
        again = cite(workspace, "service.js", lines="1-3", append=True)
        self.assertTrue(again["already_present"])
        self.assertEqual(again["evidence"]["id"], first["evidence"]["id"])
        report = read_json(first["report"])
        self.assertEqual(len(report["evidence"]), 1)
        with self.assertRaisesRegex(ValueError, "already exists"):
            cite(workspace, "store.js", ident=first["evidence"]["id"], append=True)
        other = cite(workspace, "service.js", lines="1-4", append=True)
        self.assertNotEqual(other["evidence"]["id"], first["evidence"]["id"])

    def test_remote_target_requires_absolute_path(self):
        remote = start("https://example.invalid/app", output=self.root/"remote")
        with self.assertRaisesRegex(ValueError, "URL"):
            cite(remote["workspace"], "bundle.js")
        capture = self.root/"capture.json"
        capture.write_text("{}\n", encoding="utf-8")
        record = cite(remote["workspace"], str(capture), kind="artifact")["evidence"]
        self.assertEqual(Path(record["path"]), capture.resolve())

    def test_parse_lines(self):
        self.assertEqual(parse_lines(None), (None, None))
        self.assertEqual(parse_lines("7"), (7, 7))
        self.assertEqual(parse_lines(" 3-9 "), (3, 9))


class WorkflowWithHelpers(unittest.TestCase):
    """An agent finishes a whole investigation using only the CLI helpers plus authored prose."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = create_source(self.root/"project")

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        process = subprocess.run([sys.executable, str(CLI), *map(str, args)], capture_output=True, text=True, env=env)
        return process, json.loads(process.stdout or process.stderr)

    def test_cli_cite_checklist_validate_finish(self):
        process, started = self.cli("start", self.source, "--depth", "overview")
        self.assertEqual(process.returncode, 0, process.stderr)
        workspace = started["result"]["workspace"]
        process, cited = self.cli("cite", workspace, "service.js", "--lines", "5-9", "--note", "Serialized writes", "--append")
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertTrue(cited["result"]["appended"])
        path, data = load(workspace)
        report = sample_report(self.source, data["id"])
        report["target"] = data["target"]
        write_report = Path(data["paths"]["report"])
        write_report.write_text(json.dumps(report), encoding="utf-8")
        for row in data["checklist"]:
            process, marked = self.cli("checklist", workspace, row["id"], "--status", "answered",
                                       "--note", "Investigated and written into the authored report.")
            self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(marked["result"]["remaining"], [])
        process, checked = self.cli("validate", write_report, "--check-files")
        self.assertEqual(process.returncode, 0, checked)
        process, done = self.cli("finish", workspace)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertTrue(Path(done["result"]["html"]).is_file())

    def test_cli_errors_use_the_stable_envelope(self):
        process, started = self.cli("start", self.source)
        workspace = started["result"]["workspace"]
        process, failed = self.cli("cite", workspace, "missing.js")
        self.assertEqual(process.returncode, 2)
        self.assertEqual(failed["error"]["code"], "invalid_input")
        process, failed = self.cli("checklist", workspace, "briefing", "--status", "answered")
        self.assertEqual(process.returncode, 2)

    def test_mcp_tools_share_the_cli_implementation(self):
        opened = start(self.source)
        frames = "".join(json.dumps(m)+"\n" for m in [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "aa_cite", "arguments": {
                "workspace": opened["workspace"], "path": "store.js", "lines": "1-2", "append": True}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "aa_checklist", "arguments": {
                "workspace": opened["workspace"], "item": "briefing", "status": "answered", "note": "Read the entry points."}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "aa_checklist", "arguments": {
                "workspace": opened["workspace"], "item": "briefing", "status": "bogus"}}},
        ])
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        process = subprocess.run([sys.executable, str(MCP)], input=frames, capture_output=True, text=True, env=env, timeout=120)
        by_id = {r["id"]: r["result"] for r in map(json.loads, process.stdout.splitlines())}
        self.assertFalse(by_id[1]["isError"])
        self.assertTrue(by_id[1]["structuredContent"]["result"]["appended"])
        self.assertFalse(by_id[2]["isError"])
        self.assertTrue(by_id[3]["isError"])


class FinishMessages(unittest.TestCase):
    """The refusal text must name the real cause so an agent fixes the right thing."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = create_source(self.root/"project")
        self.opened = start(self.source, depth="overview")
        self.path, self.data = load(self.opened["workspace"])

    def tearDown(self):
        self.temp.cleanup()

    def author(self, status):
        report = sample_report(self.source, self.data["id"])
        report["target"] = self.data["target"]
        report["run"]["status"] = status
        Path(self.data["paths"]["report"]).write_text(json.dumps(report), encoding="utf-8")

    def answer(self, skip=()):
        for row in self.data["checklist"]:
            if row["id"] not in skip:
                set_checklist(self.opened["workspace"], row["id"], "answered", "Investigated and written into the report.")

    def test_unresolved_items_are_named(self):
        self.author("complete")
        self.answer(skip=("changes", "assessment"))
        with self.assertRaisesRegex(ValueError, r"unresolved checklist items: changes, assessment"):
            finish(self.opened["workspace"])

    def test_partial_status_message_explains_status_versus_coverage(self):
        self.author("partial")
        self.answer()
        with self.assertRaises(ValueError) as caught:
            finish(self.opened["workspace"])
        message = str(caught.exception)
        self.assertIn("Every checklist item is resolved", message)
        self.assertNotIn("unresolved checklist items", message)  # must not blame the checklist
        self.assertIn("run.status to 'complete' and run.coverage to 'partial'", message)

    def test_following_the_advice_publishes(self):
        self.author("partial")
        self.answer()
        self.author("complete")  # sample_report already has coverage "partial" and honest limitations
        self.assertTrue(Path(finish(self.opened["workspace"])["html"]).is_file())

    def test_explicit_partial_still_publishes_unfinished_work(self):
        self.author("partial")
        self.answer(skip=("changes",))
        self.assertTrue(Path(finish(self.opened["workspace"], partial=True)["html"]).is_file())


class Cookbook(unittest.TestCase):
    def test_authoring_snippets_compose_into_a_valid_report(self):
        text = (SKILL/"references/report-authoring.md").read_text(encoding="utf-8")
        blocks = [json.loads(b) for b in re.findall(r"```json\n(.*?)\n```", text, re.S) if '"sha256"' not in b or "<64" not in b]
        by_kind = {}
        for block in blocks:
            by_kind[block.get("kind", "claim" if "authority" in block else "section")] = block
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)/"src"
            target.mkdir()
            lines = "".join(f"line {n}\n" for n in range(1, 80))
            (target/"sync.py").write_text(lines, encoding="utf-8")
            evidence = {"id": "ev-src-sync-py-L40-72", "kind": "source", "locator": "src/sync.py:40-72", "note": "Retry loop",
                        "path": "sync.py", "sha256": digest(target/"sync.py"), "line_start": 40, "line_end": 72}
            report = read_json(SKILL/"examples/minimal-report.json")
            report["target"] = {"name": "t", "kind": "source", "locator": str(target), "revision": None}
            report["evidence"] = [evidence]
            report["claims"] = [by_kind["claim"]]
            report["sections"] = [by_kind["section"]]
            report["diagrams"] = [by_kind["component"]]
            report["run"].update(status="partial", coverage="partial", limitations=["Cookbook example"])
            self.assertEqual(validate(report, check_files=True)["errors"], [])


class InstallHosts(unittest.TestCase):
    def test_claude_destination_honors_config_dir(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": temp}):
            self.assertEqual(Path(default_destination("claude")), Path(temp)/"skills/architect-anything")

    def test_install_to_claude_layout_is_idempotent_and_protects_edits(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp)/"skills/architect-anything"
            first = install(str(destination))
            self.assertTrue(first["verified"])
            self.assertTrue((destination/"SKILL.md").is_file())
            self.assertTrue(install(str(destination))["unchanged"])
            (destination/"SKILL.md").write_text("edited\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "independent changes"):
                install(str(destination))

    def test_upgrade_backup_is_kept_out_of_the_skills_directory(self):
        """A backup inside skills/ would be discovered by agents as a second copy of the skill."""
        import install as installer
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp)/"package"
            shutil.copytree(SKILL, package, ignore=shutil.ignore_patterns("__pycache__", "local.json"))
            destination = Path(temp)/"home/skills/architect-anything"
            with mock.patch.object(installer, "PACKAGE", package):
                self.assertIsNone(installer.install(str(destination))["backup"])
                (package/"SKILL.md").write_text((package/"SKILL.md").read_text(encoding="utf-8") + "\nnew line\n", encoding="utf-8")
                upgraded = installer.install(str(destination))
            backup = Path(upgraded["backup"])
            self.assertTrue((backup/"SKILL.md").is_file())  # the previous version is preserved
            self.assertFalse(backup.is_relative_to(destination.parent))  # ...but not where agents look
            self.assertEqual([p.name for p in destination.parent.iterdir()], ["architect-anything"])
            self.assertIn("new line", (destination/"SKILL.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
