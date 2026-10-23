import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from aa_investigation import (
    LENSES,
    cite,
    finish,
    load,
    questions_for,
    set_checklist,
    set_run_meta,
    start,
    status,
    upsert_claim,
    upsert_diagram,
    upsert_section,
)
from aa_model import read_json
from aa_render import diagram_mermaid, diagram_svg, publish, render_documents
from fixture_factory import create_source, sample_report

SKILL = Path(__file__).resolve().parents[1]
CLI = SKILL / "scripts/aa_cli.py"
MCP = SKILL / "scripts/aa_mcp.py"


class SecondEditionLensesAndPacks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = create_source(self.root / "project")

    def tearDown(self):
        self.temp.cleanup()

    def test_all_new_lenses_work_in_catchup_and_focus_across_depths(self):
        for lens in ("onboarding", "delta", "boundaries", "operations"):
            for mode in ("catch-up", "focus"):
                ov = questions_for(mode, "overview", lens)
                std = questions_for(mode, "standard", lens)
                deep = questions_for(mode, "deep", lens)
                self.assertLess(len(ov), len(std), (lens, mode))
                self.assertLess(len(std), len(deep), (lens, mode))
                opened = start(self.source, output=self.root / f"out-{lens}-{mode}",
                               focus="How are writes handled?" if mode == "focus" else None, lens=lens)
                self.assertEqual(opened["lens"], lens)

    def test_emit_companion_packs_end_to_end(self):
        opened = start(self.source, lens="onboarding", depth="overview", emit=["all"])
        self.assertEqual(set(opened["emit"]), {"mermaid", "adr", "onboarding", "delta", "llms-txt"})
        ws = opened["workspace"]
        ev = cite(ws, "service.js", lines="1-12", note="Write queue", append=True)["evidence"]
        upsert_claim(ws, "serial-queue", "Writes are serialized on a promise chain.", "derived", "verified", [ev["id"]])
        _, data = load(ws)
        for row in data["checklist"]:
            upsert_section(ws, row["id"], body=["The `addNote` function chains promises in **process-local** state."],
                           claims=["serial-queue"])
            set_checklist(ws, row["id"], "answered", "Verified in service.js.")
        upsert_diagram(
            ws,
            "flow",
            "Write Flow",
            "component",
            nodes=[
                {"id": "http", "label": "HTTP Server", "claims": ["serial-queue"]},
                {"id": "svc", "label": "Note Service", "claims": ["serial-queue"]},
                {"id": "store", "label": "File Store", "claims": ["serial-queue"]},
                {"id": "disk", "label": "Disk JSON", "claims": ["serial-queue"]},
            ],
            edges=[
                {"from": "http", "to": "svc", "label": "Call addNote", "claims": ["serial-queue"]},
                {"from": "svc", "to": "store", "label": "Persist array", "claims": ["serial-queue"]},
                {"from": "store", "to": "disk", "label": "Atomic rename", "claims": ["serial-queue"]},
            ],
        )
        set_run_meta(ws, title="Field Notes Onboarding", subtitle="Maintainer guide",
                     run_status="complete", coverage="partial",
                     limitations=["Static source inspection only."],
                     changes=["Initial onboarding baseline."])
        pub = finish(ws)
        self.assertIn("emitted", pub)
        emitted = pub["emitted"]
        for expected_rel in (
            "diagrams/flow.mmd",
            "packs/adr-summary.md",
            "packs/onboarding-codemap.md",
            "packs/architecture-delta.md",
            "packs/llms-architecture.txt",
        ):
            self.assertIn(expected_rel, emitted)
            self.assertTrue(Path(emitted[expected_rel]).is_file(), expected_rel)
        html_text = Path(pub["html"]).read_text(encoding="utf-8")
        self.assertIn("<code>addNote</code>", html_text)
        self.assertIn("<strong>process-local</strong>", html_text)
        self.assertIn('id="claim-popover"', html_text)
        md_text = Path(pub["markdown"]).read_text(encoding="utf-8")
        self.assertIn("```mermaid", md_text)


class McpAuthoringResourcesPromptsBatch(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = create_source(self.root / "project")

    def tearDown(self):
        self.temp.cleanup()

    def session(self, messages):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        payload = "\n".join(json.dumps(m) for m in messages) + "\n"
        process = subprocess.run([sys.executable, str(MCP)], input=payload,
                                 capture_output=True, text=True, env=env, timeout=120, check=False)
        self.assertEqual(process.returncode, 0, process.stderr)
        return [json.loads(line) for line in process.stdout.splitlines()]

    def call(self, ident, name, arguments):
        return {"jsonrpc": "2.0", "id": ident, "method": "tools/call", "params": {"name": name, "arguments": arguments}}

    def test_full_mcp_zero_file_edit_workflow(self):
        replies = self.session([
            self.call(1, "aa_start", {"target": str(self.source), "depth": "overview", "lens": "operations", "emit": ["llms-txt", "mermaid"]}),
        ])
        started = replies[0]["result"]["structuredContent"]["result"]
        ws = started["workspace"]
        status_reply = self.session([self.call(2, "aa_status", {"workspace": ws})])[0]["result"]["structuredContent"]["result"]
        checklist_ids = [r["id"] for r in status_reply["checklist"]]

        cite_reply = self.session([
            self.call(3, "aa_cite", {"workspace": ws, "path": "server.js", "lines": "1-24", "note": "HTTP server", "append": True}),
        ])[0]["result"]["structuredContent"]["result"]
        ev_id = cite_reply["evidence"]["id"]

        ops = [
            self.call(4, "aa_upsert_claim", {
                "workspace": ws, "id": "http-loopback",
                "text": "The server listens on `127.0.0.1` and closes on `SIGTERM`.",
                "authority": "observation", "freshness": "verified", "evidence": [ev_id],
            }),
        ]
        req_id = 10
        for item_id in checklist_ids:
            ops.append(self.call(req_id, "aa_upsert_section", {
                "workspace": ws, "id": item_id,
                "body": [f"Operational finding for `{item_id}`."],
                "claims": ["http-loopback"],
            }))
            req_id += 1
            ops.append(self.call(req_id, "aa_checklist", {
                "workspace": ws, "item": item_id, "status": "answered", "note": "Verified from server.js.",
            }))
            req_id += 1
        ops.append(self.call(req_id + 1, "aa_set_run_meta", {
            "workspace": ws, "title": "Field Notes Operations", "subtitle": "Operational runbook",
            "run_status": "complete", "coverage": "partial", "limitations": ["Static source inspection only."],
        }))
        ops.append(self.call(req_id + 2, "aa_finish", {"workspace": ws}))
        batch_replies = self.session(ops)
        for r in batch_replies:
            self.assertFalse(r["result"]["isError"], r)
        published = batch_replies[-1]["result"]["structuredContent"]["result"]
        self.assertTrue(Path(published["html"]).is_file())
        self.assertIn("packs/llms-architecture.txt", published["emitted"])

    def test_resources_prompts_and_jsonrpc_batch(self):
        opened = start(self.source, depth="overview")
        ws = opened["workspace"]
        batch = [
            {"jsonrpc": "2.0", "id": 1, "method": "resources/list"},
            {"jsonrpc": "2.0", "id": 2, "method": "resources/templates/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "resources/read", "params": {"uri": "aa://schema/report"}},
            {"jsonrpc": "2.0", "id": 4, "method": "resources/read", "params": {"uri": f"aa://workspace/{ws}/status"}},
            {"jsonrpc": "2.0", "id": 5, "method": "prompts/list"},
            {"jsonrpc": "2.0", "id": 6, "method": "prompts/get", "params": {"name": "catch-up", "arguments": {"target": str(self.source), "lens": "onboarding"}}},
        ]
        # Send as a single JSON-RPC batch array
        replies = self.session([batch])[0]
        self.assertIsInstance(replies, list)
        by_id = {r["id"]: r for r in replies}
        self.assertTrue(len(by_id[1]["result"]["resources"]) >= 3)
        self.assertTrue(len(by_id[2]["result"]["resourceTemplates"]) >= 2)
        self.assertEqual(json.loads(by_id[3]["result"]["contents"][0]["text"])["schema_version"] if "schema_version" in json.loads(by_id[3]["result"]["contents"][0]["text"]) else json.loads(by_id[3]["result"]["contents"][0]["text"])["title"], "Architect Anything report v1")
        ws_status = json.loads(by_id[4]["result"]["contents"][0]["text"])
        self.assertEqual(ws_status["mode"], "catch-up")
        self.assertTrue(len(by_id[5]["result"]["prompts"]) >= 3)
        self.assertIn("onboarding", by_id[6]["result"]["messages"][0]["content"]["text"])


class RendererAndLockPolish(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = create_source(self.root / "project")
        self.report = sample_report(self.source)

    def tearDown(self):
        self.temp.cleanup()

    def test_layered_svg_with_many_nodes_is_valid_xml(self):
        nodes = [{"id": f"n{i}", "label": f"Component {i}", "claims": ["http-boundary"]} for i in range(8)]
        edges = [
            {"from": "n0", "to": "n1", "label": "step 1", "claims": ["http-boundary"]},
            {"from": "n1", "to": "n2", "label": "step 2", "claims": ["http-boundary"]},
            {"from": "n2", "to": "n3", "label": "step 3", "claims": ["http-boundary"]},
            {"from": "n0", "to": "n4", "label": "branch", "claims": ["http-boundary"]},
            {"from": "n4", "to": "n5", "label": "forward", "claims": ["http-boundary"]},
            {"from": "n5", "to": "n1", "label": "feedback", "claims": ["http-boundary"]},
            {"from": "n6", "to": "n7", "label": "side", "claims": ["http-boundary"]},
            {"from": "n3", "to": "n3", "label": "self-loop", "claims": ["http-boundary"]},
        ]
        diag = {"id": "big", "title": "Layered Graph", "kind": "component", "freshness": "verified",
                "nodes": nodes, "edges": edges}
        svg = diagram_svg(diag)
        ET.fromstring(svg)
        mmd = diagram_mermaid(diag)
        self.assertIn("flowchart LR", mmd)

    def test_stale_lock_with_dead_pid_is_recovered_automatically(self):
        output = self.root / "reports"
        output.mkdir(parents=True)
        lock = output / ".architect-publish.lock"
        # Write a non-existent PID and backdate mtime
        lock.write_text("99999999", encoding="utf-8")
        old_time = time.time() - 600
        os.utime(lock, (old_time, old_time))
        res = publish(self.report, output)
        self.assertTrue(Path(res["html"]).is_file())
        self.assertFalse(lock.exists())


if __name__ == "__main__":
    unittest.main()
