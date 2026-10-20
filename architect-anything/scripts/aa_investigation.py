"""Question-driven investigation workspaces. These scaffold agent work, not findings."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import uuid
from pathlib import Path
from urllib.parse import urlparse

from aa_inventory import compare_inventory, inventory
from aa_model import PACKAGE, VERSION, json_text, read_json, schema_errors, validate
from aa_render import publish

CATCH_UP = [
    ("briefing", "What is this project now, who uses it, and what can it do?"),
    ("components", "What are the major components, boundaries and dependencies?"),
    ("behavior", "How do its important user features work end to end?"),
    ("data", "Who owns the data, where does it live, and how does it move?"),
    ("operations", "How is it configured, built, run, deployed and recovered?"),
    ("changes", "What changed since the last verified architecture report?"),
    ("assessment", "What coupling, discrepancies, risks and unknowns deserve attention?")
]
FOCUS = [
    ("answer", "What is the direct answer to the user's question?"),
    ("trigger", "What user action, API, event or input starts this behavior?"),
    ("trace", "What exact path connects that trigger to the result and state changes?"),
    ("mechanism", "Which implementation mechanism, algorithm and invariants make it work?"),
    ("design", "Which boundaries and tradeoffs explain the design, and is rationale recorded or inferred?"),
    ("limits", "What is established, what remains unknown, and what would resolve it?")
]
DEEP_CATCH_UP = [
    ("interfaces", "What are the public interfaces (APIs, CLIs, events, file formats) and their contracts?"),
    ("algorithms", "Which non-trivial algorithms and state machines exist, and what are their invariants?"),
    ("failure", "How do errors, retries, timeouts, partial failure and recovery behave?"),
    ("modules", "For each major module: what are its responsibility, public surface, dependencies and owned state?"),
    ("build", "How are build, packaging, configuration precedence and release produced?")
]
DEEP_FOCUS = [
    ("interfaces", "Which exact functions, messages or schemas carry the behavior, with their signatures?"),
    ("failure", "What happens on each evidenced failure path, including concurrency and ordering?"),
    ("alternatives", "Which adjacent code paths or configuration change the behavior?")
]
OVERVIEW_CATCH_UP = ("briefing", "components", "behavior", "changes", "assessment")
OVERVIEW_FOCUS = ("answer", "trace", "limits")
DEPTHS = ("overview", "standard", "deep")
DEFAULT_DEPTH = "standard"
DEEP_NOTE_MINIMUM = 40
TITLES = {
    "briefing": "Your project, as it stands", "components": "How the pieces fit",
    "behavior": "How the important features work", "data": "Data and ownership",
    "operations": "Running and changing the system", "changes": "What changed",
    "assessment": "What deserves attention", "answer": "The direct answer",
    "trigger": "Where the behavior starts", "trace": "The path from input to result",
    "mechanism": "How the mechanism works", "design": "Why the design works this way",
    "limits": "Evidence and remaining questions", "interfaces": "Interfaces and contracts",
    "algorithms": "Algorithms and state", "failure": "Failure, retry and recovery",
    "modules": "Module reference", "build": "Build, configuration and release",
    "alternatives": "Related paths and configuration"
}


def questions_for(mode, depth):
    """Return the (id, question) checklist for a mode and depth."""
    if depth not in DEPTHS:
        raise ValueError(f"Depth must be one of: {', '.join(DEPTHS)}")
    base = FOCUS if mode == "focus" else CATCH_UP
    if depth == "overview":
        keep = OVERVIEW_FOCUS if mode == "focus" else OVERVIEW_CATCH_UP
        return [item for item in base if item[0] in keep]
    if depth == "deep":
        return base + (DEEP_FOCUS if mode == "focus" else DEEP_CATCH_UP)
    return list(base)


SCAFFOLD_LIMITATION = "Investigation scaffold only. The agent must inspect the target, replace working sections with evidenced findings, and complete the coverage checklist before publishing."


def write_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name+".tmp")
    temp.write_text(json_text(value), encoding="utf-8", newline="\n")
    temp.replace(path)


def slug(value):
    readable = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:48] or "feature"
    return readable+"-"+hashlib.sha256(value.encode()).hexdigest()[:8]


def prior_report(output, locator):
    pointer = output/"current.json"
    if not pointer.is_file():
        return None
    current = read_json(pointer)
    prior = (output/current["snapshot"]/"report.json").resolve()
    if not prior.is_relative_to(output):
        raise ValueError("Previous report pointer escapes the selected report output")
    return str(prior) if prior.is_file() and read_json(prior)["target"]["locator"] == locator else None


def start(target, output=None, focus=None, kind="auto", excludes=(), max_files=100000, max_bytes=268435456,
          depth=DEFAULT_DEPTH):
    if depth not in DEPTHS:
        raise ValueError(f"Depth must be one of: {', '.join(DEPTHS)}")
    if focus is not None and not focus.strip():
        raise ValueError("A focus question cannot be blank")
    if max_files < 1 or max_bytes < 0:
        raise ValueError("Inventory limits must be positive; max-bytes=0 permits unlimited streaming hashes")
    remote = urlparse(str(target)).scheme in ("http", "https")
    if remote:
        if not urlparse(str(target)).netloc or kind == "source":
            raise ValueError("Use a valid product URL, or select a local source directory")
        root, name = None, urlparse(str(target)).netloc
        selected_kind = "product" if kind == "auto" else kind
        locator = str(target)
    else:
        root = Path(target).resolve(strict=True)
        if not root.is_file() and not root.is_dir():
            raise ValueError("Target must be a regular file or directory")
        name, locator = root.stem if root.is_file() else root.name, str(root)
        selected_kind = kind if kind != "auto" else (
            "source" if root.is_dir() and root.suffix.lower() not in (".app", ".framework") else "product")
    mode = "focus" if focus is not None else "catch-up"
    if output is None:
        default = root/"docs/architecture" if root is not None and selected_kind == "source" and root.is_dir() else Path.cwd()/"architecture"/slug(name)
        output = default/"focus"/slug(focus.strip()) if mode == "focus" else default
    output = Path(output).resolve()
    if root is not None and root.is_dir() and (output == root or root.is_relative_to(output)):
        raise ValueError("The report output must not be the target root or its ancestor")
    patterns = list(excludes)
    if root is not None and root.is_dir() and output.is_relative_to(root):
        patterns.append(output.relative_to(root).as_posix())
    previous = prior_report(output, locator)
    now = dt.datetime.now(dt.timezone.utc)
    run_id = "run-"+now.strftime("%Y%m%dT%H%M%SZ")+"-"+uuid.uuid4().hex[:8]
    work = output/"investigations"/run_id
    work.mkdir(parents=True, exist_ok=False)
    (work/"evidence").mkdir()
    # Create the excluded output before inventory, so later end inventory has the same scope.
    first = inventory(root, patterns, max_files, max_bytes) if root is not None else None
    if first:
        write_json(work/"inventory-start.json", first)
    identity = {"name": name, "kind": selected_kind, "locator": locator,
                "revision": first["git"]["revision"] if first and first["git"] else None}
    questions = questions_for(mode, depth)
    report = {
        "schema_version": 1, "title": f"{name}: {focus.strip() if focus else 'project catch-up'}",
        "subtitle": "Working investigation. Findings have not yet been established.",
        "target": identity,
        "run": {"id": run_id, "captured_at": now.isoformat(), "status": "partial", "coverage": "unknown",
                "tools": [f"Architect Anything {VERSION}"], "limitations": [SCAFFOLD_LIMITATION],
                "exclusions": patterns},
        "evidence": [],
        "claims": [{"id": key+"-unknown", "text": question+" Not established yet.",
                    "authority": "unknown", "freshness": "unverified", "evidence": []}
                   for key, question in questions],
        "sections": [{"id": key, "title": TITLES[key], "body": ["This topic has not been investigated."],
                      "claims": [key+"-unknown"], "detail": key not in ("briefing", "answer", "assessment", "limits"),
                      "freshness": "unverified"} for key, _ in questions],
        "diagrams": []
    }
    write_json(work/"report.json", report)
    manifest = {
        "schema_version": 1, "id": run_id, "mode": mode, "depth": depth,
        "question": focus.strip() if focus else None,
        "target": identity, "created_at": now.isoformat(), "status": "investigating",
        "paths": {"report": str(work/"report.json"), "evidence": str(work/"evidence"),
                  "output": str(output), "inventory_start": str(work/"inventory-start.json") if first else None,
                  "inventory_end": str(work/"inventory-end.json") if first else None},
        "checklist": [{"id": key, "question": q, "status": "unresolved", "note": ""} for key,q in questions],
        "inventory_options": {"excludes": patterns, "max_files": max_files, "max_bytes": max_bytes},
        "previous_report": previous
    }
    write_json(work/"investigation.json", manifest)
    return {"workspace": str(work), "manifest": str(work/"investigation.json"), "report": str(work/"report.json"),
            "mode": mode, "depth": depth, "question": manifest["question"], "previous_report": previous,
            "inventory_summary": {"files": len(first["files"]), "coverage": first["coverage"]} if first else None,
            "next": "Investigate the checklist using the skill; author claims/sections and evidence, then run finish. This command has not analyzed architectural behavior or published a report."}


def load(workspace):
    p = Path(workspace).resolve(strict=True)
    path = p/"investigation.json" if p.is_dir() else p
    data = read_json(path)
    errors = schema_errors(data, read_json(PACKAGE/"assets/investigation.schema.json"))
    if errors:
        raise ValueError("Invalid investigation manifest: "+"; ".join(errors))
    if data.get("schema_version") != 1 or data.get("mode") not in ("focus", "catch-up"):
        raise ValueError("Unsupported investigation manifest")
    data.setdefault("depth", DEFAULT_DEPTH)  # 1.0.0 manifests predate depth control
    work = path.parent
    if data["mode"] == "focus" and (not isinstance(data["question"], str) or not data["question"].strip()):
        raise ValueError("A focused investigation requires its question")
    for key in ("report", "evidence", "inventory_start", "inventory_end"):
        value = data["paths"][key]
        if value and not Path(value).resolve().is_relative_to(work):
            raise ValueError(f"Investigation {key} escapes its workspace")
    rows = data["checklist"]
    if not rows or len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Investigation checklist must have unique IDs")
    if any(r["status"] not in ("unresolved", "answered", "partial", "not-applicable") for r in rows):
        raise ValueError("Invalid checklist status")
    return path, data


def status(workspace):
    _, data = load(workspace)
    report = read_json(data["paths"]["report"])
    return {"workspace": str(Path(data["paths"]["report"]).parent), "mode": data["mode"], "depth": data["depth"],
            "question": data["question"], "status": data["status"], "checklist": data["checklist"],
            "report_validation": validate(report), "previous_report": data["previous_report"],
            "notice": "This reads saved investigation state, not live target freshness. A valid model does not establish completeness; validate local evidence or start a new run to refresh."}


def finish(workspace, partial=False):
    manifest_path, data = load(workspace)
    report = read_json(data["paths"]["report"])
    if SCAFFOLD_LIMITATION in report["run"]["limitations"]:
        raise ValueError("The working report is still an uninvestigated scaffold. Author actual findings or an explicit blocked/interrupted account before publishing.")
    if report["run"]["id"] != data["id"] or any(
            report["target"][key] != data["target"][key] for key in ("kind", "locator")):
        raise ValueError("Report identity differs from its investigation")
    if not partial and (report["run"]["status"] != "complete" or any(
            row["status"] == "unresolved" for row in data["checklist"])):
        raise ValueError("Investigation is unfinished. Resolve the checklist and author verified findings, or explicitly use --partial to publish the stated gaps.")
    if partial and report["run"]["status"] == "complete" and any(
            row["status"] == "unresolved" for row in data["checklist"]):
        raise ValueError("A complete report cannot contain unresolved investigation questions")
    if any(row["status"] != "unresolved" and not row["note"].strip() for row in data["checklist"]):
        raise ValueError("Answered, partial and not-applicable checklist entries require an explanatory note")
    if data["depth"] == "deep":
        deep_ids = {key for key, _ in DEEP_FOCUS + DEEP_CATCH_UP}
        thin = [row["id"] for row in data["checklist"] if row["id"] in deep_ids
                and row["status"] in ("answered", "partial") and len(row["note"].strip()) < DEEP_NOTE_MINIMUM]
        if thin:
            raise ValueError("Deep investigation notes need at least "+str(DEEP_NOTE_MINIMUM)
                             +" characters of concrete explanation: "+", ".join(thin))
    output = Path(data["paths"]["output"])
    snapshot = output/"snapshots"/data["id"]
    if (snapshot/"report.json").is_file():
        if read_json(snapshot/"report.json") != report:
            raise ValueError("Published investigation changed; start a new run")
        data["status"] = report["run"]["status"]
        write_json(manifest_path, data)
        return {"snapshot": str(snapshot), "html": str(snapshot/"report.html"), "already_published": True,
                "notice": "Existing historical snapshot; no new target verification was performed."}
    if data["paths"]["inventory_start"]:
        options = data["inventory_options"]
        end = inventory(data["target"]["locator"], options["excludes"], options["max_files"], options["max_bytes"])
        write_json(data["paths"]["inventory_end"], end)
        report["run"]["inventory_start"] = data["paths"]["inventory_start"]
        report["run"]["inventory_end"] = data["paths"]["inventory_end"]
        delta = compare_inventory(read_json(data["paths"]["inventory_start"]), end)
        mixed = any(delta[key] for key in ("added", "removed", "changed")) or delta["coverage_changed"]
        if mixed:
            report["run"]["status"] = "partial"
            notice = "Target files or selected coverage changed during collection. Recheck affected findings before calling the investigation complete."
            if notice not in report["run"]["limitations"]:
                report["run"]["limitations"].append(notice)
            write_json(data["paths"]["report"], report)
            if not partial:
                raise ValueError(notice+" The working report was marked partial; no snapshot was published.")
    write_json(data["paths"]["report"], report)
    result = publish(report, output, check_files=True)
    data["status"] = report["run"]["status"]
    write_json(manifest_path, data)
    return result
