"""Small inspectable project used by behavioral tests and example generation."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from aa_model import digest

SOURCES = {
    "package.json": '{\n  "name": "field-notes",\n  "version": "1.0.0",\n  "type": "module",\n  "scripts": {"start": "node server.js"}\n}\n',
    "server.js": '''import http from "node:http";
import { listNotes, addNote } from "./service.js";
const port = Number(process.env.PORT || 8787);
const server = http.createServer(async (req, res) => {
  try {
    if (req.method === "GET" && req.url === "/notes") {
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify(await listNotes()));
    } else if (req.method === "POST" && req.url === "/notes") {
      let body = "";
      for await (const chunk of req) body += chunk;
      const note = await addNote(JSON.parse(body).text);
      res.writeHead(201, {"Content-Type": "application/json"});
      res.end(JSON.stringify(note));
    } else {
      res.writeHead(404); res.end();
    }
  } catch (error) {
    res.writeHead(400, {"Content-Type": "application/json"});
    res.end(JSON.stringify({error: error.message}));
  }
});
server.listen(port, "127.0.0.1");
process.on("SIGTERM", () => server.close());
''',
    "service.js": '''import { readNotes, writeNotes } from "./store.js";
import { randomUUID } from "node:crypto";
let pending = Promise.resolve();
export async function listNotes() { return readNotes(); }
export function addNote(text) {
  const operation = pending.then(async () => {
    if (typeof text !== "string" || !text.trim()) throw new Error("Text required");
    const notes = await readNotes();
    const note = {id: randomUUID(), text: text.trim(), createdAt: new Date().toISOString()};
    notes.push(note);
    await writeNotes(notes);
    return note;
  });
  pending = operation.catch(() => {});
  return operation;
}
''',
    "store.js": '''import { readFile, writeFile, rename } from "node:fs/promises";
import path from "node:path";
const file = path.resolve(process.env.NOTES_FILE || "notes.json");
export async function readNotes() {
  try { return JSON.parse(await readFile(file, "utf8")); }
  catch (error) { if (error.code === "ENOENT") return []; throw error; }
}
export async function writeNotes(notes) {
  await writeFile(file + ".tmp", JSON.stringify(notes), "utf8");
  await rename(file + ".tmp", file);
}
'''
}


def create_source(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for name, content in SOURCES.items():
        (root/name).write_text(content, encoding="utf-8", newline="\n")
    return root


def sample_report(root, run_id="example-source-v1"):
    root = Path(root).resolve()
    evidence = [{"id": name.split(".")[0]+"-source", "kind": "source", "locator": name,
                 "note": "Direct inspection of the generated Field Notes fixture; static source evidence.",
                 "path": name, "sha256": digest(root/name),
                 "line_start": 1, "line_end": len(content.splitlines())}
                for name, content in SOURCES.items()]
    facts = [
        ("http-boundary", "A Node HTTP server listens on loopback, dispatching GET and POST /notes; other paths return 404.", "observation", ["server-source"]),
        ("write-flow", "POST reads the request body, parses text, calls addNote, and returns the created note with HTTP 201.", "observation", ["server-source", "service-source"]),
        ("serialized-writes", "Within one process, addNote chains each write behind the preceding operation and resets the queue after failure.", "derived", ["service-source"]),
        ("note-model", "A note contains a random UUID, trimmed text and an ISO creation timestamp; empty/non-string text is rejected.", "observation", ["service-source"]),
        ("file-store", "The store reads a JSON array from NOTES_FILE (default notes.json); a missing file is treated as an empty collection.", "observation", ["store-source"]),
        ("replace-file", "Persistence writes a sibling .tmp file, then renames it over the selected data file.", "observation", ["store-source"]),
        ("error-boundary", "The request handler maps all caught errors to HTTP 400 and returns the exception message.", "observation", ["server-source"]),
        ("shutdown", "SIGTERM stops accepting new HTTP connections through server.close; the fixture declares no explicit pending-write drain.", "observation", ["server-source", "service-source"]),
        ("config", "PORT defaults to 8787; NOTES_FILE is resolved from the process working directory.", "observation", ["server-source", "store-source"]),
        ("single-process", "The promise queue coordinates one process only. Separate processes could overwrite updates because no cross-process lock is present in this fixture.", "inference", ["service-source", "store-source"]),
        ("body-limit", "The POST handler concatenates request chunks without an explicit body-size limit in the inspected handler.", "observation", ["server-source"]),
        ("runtime-gap", "Crash durability, filesystem rename semantics, deployed security controls and production behavior have not been tested.", "unknown", []),
    ]
    claims = [{"id": key, "text": text, "authority": authority, "freshness": "verified", "evidence": refs}
              for key, text, authority, refs in facts]
    def section(id, title, body, refs, detail=False, table=None):
        value = {"id": id, "title": title, "body": body, "claims": refs, "detail": detail, "freshness": "verified"}
        if table:
            value["table"] = table
        return value
    sections = [
        section("briefing", "A small service with a single persistence boundary",
                ["Field Notes exposes two local HTTP operations: list notes and add a note. The implementation separates request handling, note validation and sequencing, and JSON-file storage.",
                 "The important constraint is process-local write coordination. It prevents overlapping writes through this service instance, while leaving multi-process behavior outside that guarantee."],
                ["http-boundary", "write-flow", "serialized-writes", "file-store", "single-process"]),
        section("components", "Three components, three responsibilities",
                ["The HTTP layer owns dispatch and response formatting. The service layer owns note creation and write sequencing. The store owns file resolution, parsing and replacement."],
                ["http-boundary", "note-model", "serialized-writes", "file-store", "replace-file"], table={
                    "columns": ["Component", "Owns", "Depends on"],
                    "rows": [["server.js", "HTTP routes and errors", "service.js"],
                             ["service.js", "Validation, IDs, write queue", "store.js; node:crypto"],
                             ["store.js", "JSON reads and replacement", "node:fs/promises; node:path"]]}),
        section("behavior", "What happens when a note is created",
                ["The server collects and parses the request body. addNote queues the operation, validates text, reads existing notes, adds a timestamped UUID record, and waits for file replacement before returning.",
                 "A failure rejects that request, while the caught queue tail allows a subsequent write to run. The HTTP boundary returns the failure as a 400 response."],
                ["write-flow", "serialized-writes", "note-model", "replace-file", "error-boundary"]),
        section("data", "The file is the data model",
                ["Storage contains the note array directly. A missing file behaves like an empty database; malformed JSON and other filesystem errors propagate to the request boundary.",
                 "Writing uses a temporary sibling followed by rename. The source establishes that ordering, but it does not establish crash durability on a particular filesystem."],
                ["file-store", "replace-file", "runtime-gap"], True),
        section("interfaces", "A deliberately small HTTP surface",
                ["GET /notes returns the current collection as JSON. POST /notes creates a note from the text field and returns 201. The observed catch block does not distinguish validation errors from storage failures."],
                ["http-boundary", "write-flow", "error-boundary"], True),
        section("operations", "Configuration and shutdown boundaries",
                ["The process binds to 127.0.0.1. PORT changes the listener and NOTES_FILE chooses the data path relative to the working directory.",
                 "SIGTERM invokes server.close. The source does not declare a separate write-queue drain or backup/recovery procedure; operational guarantees beyond the inspected handler remain unverified."],
                ["http-boundary", "config", "shutdown", "runtime-gap"], True),
        section("assessment", "What deserves attention",
                ["The request body has no explicit size cap in the inspected POST handler. The single-process queue also means multi-process writers need separate investigation before sharing a data file.",
                 "Next checks: exercise concurrent writes, filesystem failures and SIGTERM during a write; establish the actual deployment and access controls. This report is a static architecture example, not a production certification."],
                ["body-limit", "single-process", "shutdown", "runtime-gap"])
    ]
    nodes = [{"id": "http", "label": "HTTP boundary", "claims": ["http-boundary"]},
             {"id": "service", "label": "Note service / write queue", "claims": ["serialized-writes"]},
             {"id": "store", "label": "JSON file store", "claims": ["file-store"]}]
    edges = [{"from": "http", "to": "service", "label": "Dispatch listNotes or addNote", "claims": ["write-flow", "http-boundary"]},
             {"from": "service", "to": "store", "label": "Read collection; persist a new note", "claims": ["serialized-writes", "replace-file"]}]
    return {"schema_version": 1, "title": "Field Notes, explained",
            "subtitle": "From local HTTP request to durable-file boundary: a source-backed architecture walkthrough.",
            "target": {"name": "Field Notes", "kind": "source", "locator": str(root), "revision": None},
            "run": {"id": run_id, "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "status": "complete", "coverage": "partial",
                    "tools": ["Architect Anything 1.0.0", "Direct source inspection", "SHA-256 file fingerprints"],
                    "limitations": ["Synthetic validation fixture. Static source inspected; runtime, deployment and crash durability were not exercised."],
                    "exclusions": ["No external services, authentication deployment or production environment supplied."]},
            "evidence": evidence, "claims": claims, "sections": sections,
            "diagrams": [
                {"id": "components", "title": "The request-to-storage boundary", "kind": "component",
                 "nodes": nodes, "edges": edges, "freshness": "verified"},
                {"id": "create-note", "title": "Creating a note", "kind": "sequence", "nodes": nodes,
                 "edges": [edges[0], edges[1], {"from": "store", "to": "service", "label": "Complete write and rename", "claims": ["replace-file"]},
                           {"from": "service", "to": "http", "label": "Return the created note for HTTP 201", "claims": ["write-flow"]}],
                 "freshness": "verified"}]}
