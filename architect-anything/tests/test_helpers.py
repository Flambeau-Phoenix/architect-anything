import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from aa_inventory import compare_inventory, inventory
from aa_model import compare_reports, digest, read_json, schema_errors, validate
from aa_render import diagram_svg, publish, render_documents
from install import install
from rea_bridge import configuration
from fixture_factory import create_source, sample_report


class Helpers(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = create_source(self.root/"source")
        self.report = sample_report(self.source)

    def tearDown(self):
        self.temp.cleanup()

    def test_source_evidence_and_schema(self):
        self.assertEqual(validate(self.report, True), {"valid": True, "errors": [], "warnings": []})
        self.report["unexpected"] = True
        self.assertFalse(validate(self.report)["valid"])

    def test_broken_citation_and_dangling_graph(self):
        self.report["claims"][0]["evidence"] = ["missing"]
        self.report["diagrams"][0]["edges"][0]["to"] = "missing"
        errors = validate(self.report)["errors"]
        self.assertTrue(any("missing reference" in v for v in errors))
        self.assertTrue(any("dangling edge" in v for v in errors))

    def test_stale_hash_cannot_claim_verified(self):
        (self.source/"server.js").write_text("changed", encoding="utf-8")
        self.assertFalse(validate(self.report, True)["valid"])
        self.report["run"]["status"] = "partial"
        for claim in self.report["claims"]:
            if "server-source" in claim["evidence"]:
                claim["freshness"] = "stale"
        for item in self.report["sections"] + self.report["diagrams"]:
            item["freshness"] = "stale"
        result = validate(self.report, True)
        self.assertTrue(result["valid"], result)
        self.assertTrue(result["warnings"])

    def test_line_range(self):
        self.report["evidence"][0]["line_end"] = 999
        self.assertFalse(validate(self.report, True)["valid"])

    def test_missing_rea_file_and_identity(self):
        self.report["evidence"][0]["kind"] = "rea"
        self.assertFalse(validate(self.report)["valid"])

    def test_plain_text_cannot_execute(self):
        payload = '</script><script>globalThis.OWNED=true</script><img src=x onerror=alert(1)>'
        self.report["title"] = payload
        self.report["sections"][0]["body"] = [payload]
        self.report["claims"][0]["text"] = payload
        self.report["evidence"][0]["locator"] = "javascript:alert(1)"
        page, markdown, _ = render_documents(self.report)
        self.assertNotIn("<script>globalThis.OWNED", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn('href="javascript:', page)
        self.assertNotIn("<img src=x", markdown)
        self.assertIn("Content-Security-Policy", page)

    def test_markdown_evidence_values_cannot_inject_markup(self):
        self.report["evidence"][0]["evidence_id"] = "value</code><script>owned</script>"
        self.report["evidence"][0].pop("path")
        self.report["evidence"][0].pop("line_start")
        self.report["evidence"][0].pop("line_end")
        self.report["evidence"][0]["locator"] = "https://example.invalid/> <script>owned</script>"
        _, markdown, _ = render_documents(self.report)
        self.assertNotIn("<script>owned</script>", markdown)
        self.assertIn("%3E%20%3Cscript%3E", markdown)

    def test_complete_run_cannot_hide_stale_presentations(self):
        self.report["sections"][0]["freshness"] = "stale"
        self.report["diagrams"][0]["freshness"] = "unverified"
        result = validate(self.report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("unchecked section" in v for v in result["errors"]))
        self.assertTrue(any("unchecked diagram" in v for v in result["errors"]))

    def test_publish_snapshot_and_manual_note_preservation(self):
        output = self.root/"reports"
        result = publish(self.report, output)
        original = Path(result["html"]).read_bytes()
        (output/"notes").mkdir()
        (output/"notes"/"owner.md").write_text("Keep this", encoding="utf-8")
        newer = copy.deepcopy(self.report)
        newer["run"]["id"] = "example-v2"
        newer["run"]["changes"] = ["Rechecked source without architectural changes."]
        publish(newer, output)
        self.assertEqual(Path(result["html"]).read_bytes(), original)
        self.assertEqual((output/"notes"/"owner.md").read_text(), "Keep this")
        self.assertEqual(read_json(output/"current.json")["run_id"], "example-v2")
        with self.assertRaises(ValueError):
            publish(newer, output)

    def test_manual_pointer_edit_is_not_overwritten(self):
        output = self.root/"reports"
        publish(self.report, output)
        (output/"README.md").write_text("Owner notes", encoding="utf-8")
        self.report["run"]["id"] = "new"
        with self.assertRaises(ValueError):
            publish(self.report, output)
        self.assertEqual((output/"README.md").read_text(), "Owner notes")

    def test_interrupted_publish_preserves_current(self):
        output = self.root/"reports"
        publish(self.report, output)
        previous = (output/"current.json").read_bytes()
        self.report["run"]["id"] = "new"
        original_replace = os.replace
        def fail_pointer(source, destination):
            if str(destination).endswith("current.json"):
                raise OSError("simulated pointer failure")
            return original_replace(source, destination)
        with patch("aa_render.os.replace", side_effect=fail_pointer):
            with self.assertRaises(OSError):
                publish(self.report, output)
        self.assertEqual((output/"current.json").read_bytes(), previous)
        self.assertFalse((output/".architect-publish.lock").exists())

    def test_non_git_inventory_diff_and_limits(self):
        before = inventory(self.source)
        (self.source/"service.js").write_text("changed", encoding="utf-8")
        (self.source/"new.js").write_text("new", encoding="utf-8")
        (self.source/"store.js").unlink()
        after = inventory(self.source)
        change = compare_inventory(before, after)
        self.assertEqual(change["changed"], ["service.js"])
        self.assertEqual(change["added"], ["new.js"])
        self.assertEqual(change["removed"], ["store.js"])
        self.assertIn("server.js", change["unchanged"])
        self.assertIsNone(before["git"])
        self.assertEqual(inventory(self.source, max_files=1)["coverage"], "partial")
        self.assertFalse(compare_inventory(before, inventory(self.source, ["server.js"]))["comparable"])

    def test_dirty_working_tree(self):
        try:
            subprocess.run(["git", "init", "-q", str(self.source)], check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git unavailable")
        subprocess.run(["git", "-C", str(self.source), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.source), "-c", "user.name=Fixture", "-c",
                        "user.email=fixture@example.invalid", "commit", "-qm", "fixture"],
                       check=True, capture_output=True)
        before = inventory(self.source)
        (self.source/"service.js").write_text("changed", encoding="utf-8")
        after = inventory(self.source)
        self.assertIsNotNone(after["git"]["revision"])
        self.assertTrue(after["git"]["status_records"])
        self.assertEqual(compare_inventory(before, after)["changed"], ["service.js"])

    def test_mixed_collection_requires_partial(self):
        start = inventory(self.source)
        (self.source/"unrelated.txt").write_text("added", encoding="utf-8")
        end = inventory(self.source)
        for name, value in (("start", start), ("end", end)):
            p = self.root/f"{name}.json"
            p.write_text(json.dumps(value), encoding="utf-8")
            self.report["run"]["inventory_"+name] = str(p)
        self.assertFalse(validate(self.report, True)["valid"])
        self.report["run"]["status"] = "partial"
        self.report["run"]["limitations"].append("An unrelated file appeared during collection; recheck scope.")
        self.assertTrue(validate(self.report, True)["valid"])

    def test_report_comparison_separates_changes(self):
        newer = copy.deepcopy(self.report)
        newer["claims"][0]["text"] = "Changed behavior established by new evidence."
        newer["claims"][1]["authority"] = "inference"
        newer["claims"].pop(2)
        for section in newer["sections"]:
            section["claims"] = [c for c in section["claims"] if c != "serialized-writes"]
        for d in newer["diagrams"]:
            for item in d["nodes"] + d["edges"]:
                item["claims"] = ["write-flow"] if "serialized-writes" in item["claims"] else item["claims"]
        newer["claims"].append({"id": "new-finding", "text": "New finding unknown.", "authority": "unknown",
                                "freshness": "verified", "evidence": []})
        newer["sections"][0]["claims"].append("new-finding")
        delta = compare_reports(self.report, newer)
        self.assertIn("http-boundary", delta["findings_changed"])
        self.assertIn("write-flow", delta["coverage_changed"])
        self.assertEqual(delta["removed"], ["serialized-writes"])
        self.assertEqual(delta["added"], ["new-finding"])
        self.assertIn("file-store", delta["unchanged"])

    def test_all_diagram_types_valid_xml(self):
        for kind in ("context", "component", "sequence", "data", "state"):
            d = copy.deepcopy(self.report["diagrams"][0])
            d["kind"] = kind
            d["edges"].append({"from": "http", "to": "http", "label": "cycle", "claims": ["http-boundary"]})
            ET.fromstring(diagram_svg(d))

    def test_install_copy_and_local_edit_refusal(self):
        dest = self.root/"skills"/"architect-anything"
        result = install(dest)
        self.assertTrue(result["verified"])
        second = install(dest)
        self.assertTrue(second["unchanged"])
        self.assertIsNone(second["backup"])
        (dest/"SKILL.md").write_text("Local changes", encoding="utf-8")
        with self.assertRaises(ValueError):
            install(dest)
        self.assertEqual((dest/"SKILL.md").read_text(), "Local changes")

    def test_missing_provider_configuration(self):
        config = self.root/"rea.json"
        config.write_text(json.dumps({"command": [str(self.root/"missing.exe")]}))
        with self.assertRaises(ValueError):
            configuration(config)

    def test_partial_and_interrupted_reports_render(self):
        for status in ("partial", "interrupted"):
            self.report["run"]["id"] = "example-"+status
            self.report["run"]["status"] = status
            self.report["run"]["limitations"].append("Continue with uninspected runtime flows.")
            result = publish(self.report, self.root/"reports")
            self.assertTrue(Path(result["html"]).exists())


if __name__ == "__main__":
    unittest.main()
