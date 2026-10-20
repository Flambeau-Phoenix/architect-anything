import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from aa_investigation import DEEP_CATCH_UP, DEEP_FOCUS, finish, load, start, status, write_json
from aa_model import VERSION, read_json
from fixture_factory import create_source, sample_report
from install import default_destination

SKILL = Path(__file__).resolve().parents[1]
CLI = SKILL/"scripts/aa_cli.py"
MCP = SKILL/"scripts/aa_mcp.py"


class Depth(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = create_source(self.root/"project")

    def tearDown(self):
        self.temp.cleanup()

    def ids(self, **options):
        self.runs = getattr(self, "runs", 0) + 1
        opened = start(self.source, output=self.root/f"out-{self.runs}", **options)
        return [row["id"] for row in load(opened["workspace"])[1]["checklist"]]

    def test_default_depth_is_standard_and_recorded(self):
        opened = start(self.source)
        self.assertEqual(opened["depth"], "standard")
        self.assertEqual(load(opened["workspace"])[1]["depth"], "standard")
        self.assertEqual(status(opened["workspace"])["depth"], "standard")
        self.assertEqual(len(load(opened["workspace"])[1]["checklist"]), 7)

    def test_overview_is_a_subset_and_deep_extends_standard(self):
        overview = self.ids(depth="overview")
        standard = self.ids(depth="standard")
        deep = self.ids(depth="deep")
        self.assertLess(len(overview), len(standard))
        self.assertTrue(set(overview) <= set(standard))
        self.assertEqual(deep[:len(standard)], standard)
        self.assertEqual(deep[len(standard):], [key for key, _ in DEEP_CATCH_UP])
        focus = [row["id"] for row in load(start(self.source, focus="How are writes serialized?", depth="deep")["workspace"])[1]["checklist"]]
        self.assertEqual(focus[-len(DEEP_FOCUS):], [key for key, _ in DEEP_FOCUS])

    def test_invalid_depth_is_rejected_without_a_workspace(self):
        output = self.root/"reports"
        with self.assertRaisesRegex(ValueError, "Depth"):
            start(self.source, output=output, depth="exhaustive")
        self.assertFalse(output.exists())

    def test_legacy_manifest_without_depth_loads_as_standard(self):
        opened = start(self.source)
        path, data = load(opened["workspace"])
        del data["depth"]
        write_json(path, data)
        self.assertEqual(load(opened["workspace"])[1]["depth"], "standard")

    def test_deep_requires_concrete_notes(self):
        opened = start(self.source, depth="deep")
        path, data = load(opened["workspace"])
        report = sample_report(self.source, data["id"])
        report["target"] = data["target"]
        for row in data["checklist"]:
            row["status"] = "answered" if row["id"] != "changes" else "not-applicable"
            row["note"] = "Fixture source inspected; source citations are in the authored report." if row["id"] != "changes" else "First report; no verified prior record."
        data["checklist"][-1]["note"] = "ok"
        write_json(data["paths"]["report"], report)
        write_json(path, data)
        with self.assertRaisesRegex(ValueError, "Deep investigation notes"):
            finish(opened["workspace"])
        data["checklist"][-1]["note"] = "Build and release steps traced through the packaging scripts."
        write_json(path, data)
        self.assertTrue(Path(finish(opened["workspace"])["html"]).is_file())


class Installer(unittest.TestCase):
    def test_host_destinations(self):
        self.assertTrue(default_destination("antigravity").replace("\\", "/").endswith(".gemini/config/skills/architect-anything"))
        self.assertTrue(default_destination("codex").replace("\\", "/").endswith("skills/architect-anything"))
        with self.assertRaises(ValueError):
            default_destination("unknown")


class McpServer(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = create_source(self.root/"project")

    def tearDown(self):
        self.temp.cleanup()

    def session(self, messages):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        process = subprocess.run([sys.executable, str(MCP)], input="".join(json.dumps(m)+"\n" for m in messages),
                                 capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(process.returncode, 0, process.stderr)
        lines = process.stdout.splitlines()
        return [json.loads(line) for line in lines]  # every stdout line must be a JSON-RPC frame

    def call(self, ident, name, arguments):
        return {"jsonrpc": "2.0", "id": ident, "method": "tools/call", "params": {"name": name, "arguments": arguments}}

    def test_handshake_listing_and_workflow(self):
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}}
        replies = self.session([
            init, {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            self.call(3, "aa_start", {"target": str(self.source), "depth": "overview"}),
            self.call(4, "aa_schema", {"subject": "investigation"}),
            {"jsonrpc": "2.0", "id": 5, "method": "ping"},
        ])
        by_id = {r["id"]: r for r in replies}
        self.assertEqual(len(replies), 5)  # the notification gets no response
        self.assertEqual(by_id[1]["result"]["protocolVersion"], "2025-03-26")
        self.assertEqual(by_id[1]["result"]["serverInfo"]["version"], VERSION)
        names = {t["name"] for t in by_id[2]["result"]["tools"]}
        self.assertEqual(names, {"aa_start", "aa_status", "aa_finish", "aa_validate", "aa_render", "aa_inventory",
                                 "aa_compare", "aa_schema", "aa_rea_status", "aa_rea_run"})
        for tool in by_id[2]["result"]["tools"]:
            self.assertEqual(tool["inputSchema"]["type"], "object")
        started = by_id[3]["result"]
        self.assertFalse(started["isError"])
        self.assertEqual(started["structuredContent"]["result"]["depth"], "overview")
        self.assertTrue(by_id[4]["result"]["structuredContent"]["ok"])
        self.assertEqual(by_id[5]["result"], {})
        workspace = started["structuredContent"]["result"]["workspace"]
        again = self.session([self.call(1, "aa_status", {"workspace": workspace})])
        self.assertEqual(again[0]["result"]["structuredContent"]["result"]["mode"], "catch-up")

    def test_tool_errors_do_not_stop_the_server(self):
        replies = self.session([
            self.call(1, "aa_status", {"workspace": str(self.root/"missing")}),
            self.call(2, "aa_start", {"target": str(self.source), "depth": "exhaustive"}),
            self.call(3, "aa_start", {"target": str(self.source), "surprise": True}),
            self.call(4, "aa_finish", {}),
            self.call(5, "no_such_tool", {}),
            self.call(6, "aa_validate", {"report": str(self.root/"nope.json")}),
            {"jsonrpc": "2.0", "id": 7, "method": "unknown/method"},
            self.call(8, "aa_schema", {}),
        ])
        by_id = {r["id"]: r for r in replies}
        for ident in (1, 2, 3, 4, 5, 6):
            self.assertTrue(by_id[ident]["result"]["isError"], ident)
            self.assertIn("code", by_id[ident]["result"]["structuredContent"]["error"])
        self.assertEqual(by_id[7]["error"]["code"], -32601)
        self.assertTrue(by_id[8]["result"]["structuredContent"]["ok"])  # still serving after failures

    def test_invalid_json_gets_parse_error_and_server_continues(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        process = subprocess.run([sys.executable, str(MCP)], input='not json\n{"jsonrpc":"2.0","id":1,"method":"ping"}\n',
                                 capture_output=True, text=True, env=env, timeout=60)
        frames = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual(frames[0]["error"]["code"], -32700)
        self.assertEqual(frames[1]["result"], {})

    def test_mcp_publication_matches_cli_contract(self):
        opened = self.session([self.call(1, "aa_start", {"target": str(self.source), "focus": "How are writes serialized?"})])
        data = opened[0]["result"]["structuredContent"]["result"]
        self.assertEqual(data["mode"], "focus")
        refused = self.session([self.call(1, "aa_finish", {"workspace": data["workspace"]})])
        error = refused[0]["result"]["structuredContent"]["error"]
        self.assertEqual(error["code"], "invalid_input")
        self.assertIn("scaffold", error["message"])


if __name__ == "__main__":
    unittest.main()
