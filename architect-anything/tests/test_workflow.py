import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from aa_investigation import finish, load, start, status, write_json
from aa_model import read_json
from fixture_factory import create_source, sample_report

CLI = Path(__file__).resolve().parents[1]/"scripts/aa_cli.py"


class Workflow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = create_source(self.root/"project")

    def tearDown(self):
        self.temp.cleanup()

    def ready(self, opened):
        path, data = load(opened["workspace"])
        report = sample_report(self.source, data["id"])
        report["target"] = data["target"]
        for row in data["checklist"]:
            row["status"] = "answered" if row["id"] != "changes" else "not-applicable"
            row["note"] = "Fixture source inspected; source citations in the authored report." if row["id"] != "changes" else "First report; no verified prior record."
        write_json(data["paths"]["report"], report)
        write_json(path, data)
        return data

    def cli(self, *args):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable,str(CLI),*map(str,args)],capture_output=True,text=True,env=env)

    def test_catchup_scaffold_is_not_published(self):
        opened = start(self.source)
        self.assertEqual(opened["mode"], "catch-up")
        self.assertIsNone(opened["question"])
        self.assertFalse((self.source/"docs/architecture/current.json").exists())
        for partial in (False,True):
            with self.assertRaisesRegex(ValueError, "scaffold"):
                finish(opened["workspace"], partial)
        self.assertEqual(status(opened["workspace"])["status"], "investigating")

    def test_focus_preserves_question_and_whole_project_report(self):
        broad = start(self.source)
        self.ready(broad)
        finish(broad["workspace"])
        current = (self.source/"docs/architecture/current.json").read_bytes()
        question = "How are writes serialized?"
        focused = start(self.source, focus=question)
        self.assertEqual(focused["question"], question)
        self.assertIn("focus", Path(focused["workspace"]).parts)
        manifest = load(focused["workspace"])[1]
        self.assertEqual(manifest["checklist"][0]["id"], "answer")
        self.assertEqual((self.source/"docs/architecture/current.json").read_bytes(),current)

    def test_finish_publishes_and_can_resume_after_receipt_failure(self):
        opened = start(self.source)
        self.ready(opened)
        result = finish(opened["workspace"])
        self.assertTrue(Path(result["html"]).is_file())
        path, data = load(opened["workspace"])
        data["status"] = "investigating"
        write_json(path,data)
        resumed = finish(opened["workspace"])
        self.assertTrue(resumed["already_published"])
        self.assertEqual(status(opened["workspace"])["status"],"complete")

    def test_unresolved_checklist_cannot_be_hidden_in_complete_report(self):
        opened = start(self.source)
        self.ready(opened)
        path,data = load(opened["workspace"])
        data["checklist"][0]["status"] = "unresolved"
        write_json(path,data)
        with self.assertRaises(ValueError):
            finish(opened["workspace"])
        with self.assertRaises(ValueError):
            finish(opened["workspace"],partial=True)

    def test_explicit_partial_report_preserves_gaps(self):
        opened = start(self.source)
        data = self.ready(opened)
        report = read_json(data["paths"]["report"])
        report["run"]["status"] = "partial"
        report["run"]["limitations"].append("The selected deployment was unavailable; runtime behavior remains unresolved.")
        write_json(data["paths"]["report"],report)
        path,data = load(opened["workspace"])
        data["checklist"][0]["status"] = "unresolved"
        write_json(path,data)
        with self.assertRaises(ValueError):
            finish(opened["workspace"])
        result = finish(opened["workspace"],partial=True)
        self.assertTrue(Path(result["html"]).is_file())
        self.assertEqual(status(opened["workspace"])["status"],"partial")

    def test_changed_collection_does_not_publish_as_complete(self):
        opened = start(self.source)
        self.ready(opened)
        (self.source/"new-feature.js").write_text("export const changed = true;",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"changed during collection"):
            finish(opened["workspace"])
        self.assertFalse((self.source/"docs/architecture/current.json").exists())
        self.assertEqual(read_json(opened["report"])["run"]["status"],"partial")

    def test_git_report_outputs_do_not_trigger_false_target_changes(self):
        subprocess.run(["git","init","-q",str(self.source)],check=True,capture_output=True)
        opened = start(self.source)
        self.ready(opened)
        result = finish(opened["workspace"])
        self.assertTrue(Path(result["html"]).is_file())
        self.assertEqual(status(opened["workspace"])["status"],"complete")

    def test_refresh_links_prior_matching_report(self):
        first = start(self.source)
        self.ready(first)
        result = finish(first["workspace"])
        next_run = start(self.source)
        self.assertEqual(next_run["previous_report"], str(Path(result["snapshot"])/"report.json"))

    def test_explicitly_selected_ignored_project_is_still_inventoried(self):
        subprocess.run(["git","init","-q",str(self.root)],check=True,capture_output=True)
        (self.root/".gitignore").write_text("project/\n",encoding="utf-8")
        opened = start(self.source)
        data = load(opened["workspace"])[1]
        before = read_json(data["paths"]["inventory_start"])
        self.assertEqual(before["selection_source"],"filesystem-ignored-root")
        self.assertEqual(len(before["files"]),4)
        self.ready(opened)
        self.assertTrue(Path(finish(opened["workspace"])["html"]).is_file())

    def test_bad_previous_pointer_has_no_new_workspace(self):
        output = self.root/"reports"
        output.mkdir()
        write_json(output/"current.json",{"snapshot":"../outside"})
        with self.assertRaisesRegex(ValueError,"escapes"):
            start(self.source,output=output)
        self.assertFalse((output/"investigations").exists())

    def test_remote_target_records_identity_without_fetching(self):
        opened = start("https://example.invalid/app",output=self.root/"reports",focus="How does the editor work?")
        self.assertIsNone(opened["inventory_summary"])
        self.assertEqual(load(opened["workspace"])[1]["target"]["locator"],"https://example.invalid/app")

    def test_invalid_target_or_blank_question_is_rejected(self):
        with self.assertRaises(FileNotFoundError):
            start(self.root/"missing")
        with self.assertRaises(ValueError):
            start(self.source,focus=" ")
        with self.assertRaises(ValueError):
            start(self.source,output=self.source)

    def test_manifest_cannot_redirect_working_report_outside_workspace(self):
        opened = start(self.source)
        path,data = load(opened["workspace"])
        data["paths"]["report"] = str(self.root/"unrelated.json")
        write_json(path,data)
        with self.assertRaisesRegex(ValueError,"escapes"):
            status(opened["workspace"])

    def test_cli_success_and_error_protocol(self):
        opened = self.cli("start",self.source)
        self.assertEqual(opened.returncode,0,opened.stderr)
        reply = json.loads(opened.stdout)
        self.assertTrue(reply["ok"])
        self.assertEqual(opened.stderr,"")
        invalid = self.cli("start",self.source,"--focus"," ")
        self.assertEqual(invalid.returncode,2)
        self.assertEqual(invalid.stdout,"")
        self.assertEqual(json.loads(invalid.stderr)["error"]["code"],"invalid_input")
        bad_flag = self.cli("start",self.source,"--not-a-flag")
        self.assertEqual(bad_flag.returncode,2)
        self.assertEqual(json.loads(bad_flag.stderr)["error"]["code"],"invalid_arguments")

    def test_cli_schemas_and_validation_exit(self):
        for subject in ("report","investigation","commands"):
            process = self.cli("schema",subject)
            self.assertEqual(process.returncode,0,process.stderr)
            self.assertTrue(json.loads(process.stdout)["ok"])
        path = self.root/"invalid.json"
        write_json(path,{"schema_version":1})
        process = self.cli("validate",path)
        self.assertEqual(process.returncode,1)
        self.assertEqual(json.loads(process.stderr)["error"]["code"],"validation_failed")

    def test_cli_reports_unavailable_rea_without_prompting(self):
        config = self.root/"rea.json"
        write_json(config,{"command":[str(self.root/"missing-rea")]})
        process = self.cli("rea","status","--config",config)
        self.assertEqual(process.returncode,4)
        self.assertEqual(process.stdout,"")
        self.assertEqual(json.loads(process.stderr)["error"]["code"],"rea_unavailable_or_failed")


if __name__ == "__main__":
    unittest.main()
