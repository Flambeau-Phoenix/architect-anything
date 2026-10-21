#!/usr/bin/env python3
"""Demonstrate a focused, source-backed explanation through the investigation CLI helpers."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT/"architect-anything"
sys.path.insert(0,str(SKILL/"scripts"))
sys.path.insert(0,str(SKILL/"tests"))
from aa_investigation import finish, load, start, write_json
from fixture_factory import create_source, sample_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",default=".cli-demo")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    source = create_source(output/"fixture")
    question = "How are overlapping writes prevented?"
    opened = start(source,output=output/"reports",focus=question)
    manifest_path, manifest = load(opened["workspace"])
    report = sample_report(source,manifest["id"])
    report["target"] = dict(manifest["target"], name="Field Notes")
    report["title"] = "Field Notes: how are overlapping writes prevented?"
    report["subtitle"] = "The promise queue, the persistence boundary, and the limit of process-local coordination."
    selected = {"http-boundary","write-flow","serialized-writes","note-model","file-store",
                "replace-file","error-boundary","single-process","runtime-gap"}
    report["claims"] = [c for c in report["claims"] if c["id"] in selected]
    report["claims"].append({
        "id":"failure-propagation","authority":"derived","freshness":"verified",
        "text":"The caller receives the original operation promise and its failure, while pending stores a caught promise so a failed request does not poison the next queued write.",
        "evidence":["service-source","server-source"]})
    def section(id,title,body,claims,detail=False):
        return {"id":id,"title":title,"body":body,"claims":claims,"detail":detail,"freshness":"verified"}
    report["sections"] = [
        section("answer","One queue protects the whole read/modify/write operation",
                ["Within a single process, addNote chains each new write behind the previous operation. The queued callback validates the input, reads the collection, adds the note and waits for persistence before the next write begins.",
                 "That gives this service instance an ordered write path. It does not coordinate another process writing the same file."],
                ["serialized-writes","note-model","replace-file","single-process"]),
        section("trigger","The request that enters the queue",
                ["POST /notes collects and parses the request body, then awaits addNote. A successful operation returns the created note with HTTP 201; the catch boundary returns a failure as HTTP 400."],
                ["write-flow","error-boundary"]),
        section("trace","From request to replacement",
                ["The HTTP handler calls the note service. Inside the queue, the service reads the existing JSON array, creates a UUID record with trimmed text and an ISO timestamp, then invokes the store.",
                 "The store writes a temporary sibling file and renames it over the configured data file. The service waits for that sequence before resolving the operation."],
                ["write-flow","serialized-writes","note-model","file-store","replace-file"]),
        section("mechanism","Why a failed request does not block the next write",
                ["The service returns the original operation promise to its caller, preserving its success or failure. Separately, it sets pending to a caught version of that promise.",
                 "The next call therefore waits for the earlier operation to settle, while an earlier rejection is cleared from the queue tail. This explains both error propagation to the request and continued progress for later writes."],
                ["failure-propagation","serialized-writes","error-boundary"],True),
        section("design","The useful boundary—and the tradeoff",
                ["The queue surrounds the entire read/modify/write cycle, which is the coordination boundary visible in the code. A second process has its own in-memory queue and can still race over the shared file.",
                 "The design explanation is derived from the inspected ordering and ownership. No historical decision record or author rationale was supplied with this fixture."],
                ["serialized-writes","single-process","runtime-gap"],True),
        section("limits","What would require another investigation",
                ["This explanation establishes the source-level write path in the supplied fixture. It does not establish crash durability, filesystem guarantees, production access controls, or coordination between multiple instances.",
                 "To extend the explanation, exercise overlapping requests, a rejected write, multiple processes and termination during persistence in a controlled runtime scenario."],
                ["runtime-gap","single-process","failure-propagation"])
    ]
    report["diagrams"] = [report["diagrams"][1]]
    report["run"]["limitations"] = ["Synthetic source fixture, inspected statically. The server, concurrency and crash behavior were not executed.",
                                    "Design intent is inferred from implementation; no historical rationale was provided."]
    write_json(opened["report"],report)
    for row in manifest["checklist"]:
        row["status"] = "partial" if row["id"] == "design" else "answered"
        row["note"] = "Historical rationale was not provided; implementation tradeoffs are labeled." if row["id"] == "design" else "Explained in the authored report with source claims and explicit runtime limits."
    write_json(manifest_path,manifest)
    print(json.dumps(finish(opened["workspace"]),indent=2))


if __name__ == "__main__":
    main()
