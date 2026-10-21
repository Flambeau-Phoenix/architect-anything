"""Question-driven investigation workspaces. These scaffold agent work, not findings."""
from __future__ import annotations

import datetime as dt
import hashlib
import re
import uuid
from pathlib import Path
from urllib.parse import urlparse

from aa_inventory import compare_inventory, inventory
from aa_model import (
    PACKAGE,
    VERSION,
    json_text,
    read_json,
    schema_errors,
    text_digest,
    validate,
)
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
# The "mechanism" lens: extract a portable formula (how it works, in product-neutral terms) instead
# of documenting the product. It replaces the focused checklist; it never asks for a rebuild plan.
MECHANISM = [
    ("answer", "What is the mechanism's core idea, stated in product-neutral terms?"),
    ("trace", "What is the shortest evidenced path from trigger to result that supports that account?"),
    ("contract", "What does it take in and produce, including side effects, timing and ordering?"),
    ("essentials", "Which parts are essential to the mechanism, and which are incidental to this product (UI, naming, engine quirks)?"),
    ("assumptions", "What does it assume from its host: state, ordering, timing, platform or data shape?"),
    ("choices", "What would someone building their own version have to decide for themselves?"),
    ("limits", "Where does it fail or stop being valid, and what remains unknown?")
]
OVERVIEW_CATCH_UP = ("briefing", "components", "behavior", "changes", "assessment")
OVERVIEW_FOCUS = ("answer", "trace", "limits")
OVERVIEW_MECHANISM = ("answer", "essentials", "choices", "limits")
LENSES = ("mechanism",)
# Sections on the owner-level reading path; every other section is collapsed technical detail.
OWNER_LEVEL = ("briefing", "answer", "assessment", "limits", "essentials", "choices")
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
    "alternatives": "Related paths and configuration",
    "contract": "What goes in and what comes out", "essentials": "The essential part, and what is incidental",
    "assumptions": "What it assumes from its host", "choices": "What you would decide for yourself"
}


def questions_for(mode, depth, lens=None):
    """Return the (id, question) checklist for a mode, depth and optional lens."""
    if depth not in DEPTHS:
        raise ValueError(f"Depth must be one of: {', '.join(DEPTHS)}")
    if lens is not None and lens not in LENSES:
        raise ValueError(f"Lens must be one of: {', '.join(LENSES)}")
    if lens and mode != "focus":
        raise ValueError("A lens needs a focus: name the mechanism you want to understand")
    base = MECHANISM if lens == "mechanism" else FOCUS if mode == "focus" else CATCH_UP
    if depth == "overview":
        keep = OVERVIEW_MECHANISM if lens == "mechanism" else OVERVIEW_FOCUS if mode == "focus" else OVERVIEW_CATCH_UP
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
          depth=DEFAULT_DEPTH, lens=None):
    if depth not in DEPTHS:
        raise ValueError(f"Depth must be one of: {', '.join(DEPTHS)}")
    if focus is not None and not focus.strip():
        raise ValueError("A focus question cannot be blank")
    if lens is not None and lens not in LENSES:
        raise ValueError(f"Lens must be one of: {', '.join(LENSES)}")
    if lens and focus is None:
        raise ValueError("A lens needs a focus: name the mechanism you want to understand")
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
    questions = questions_for(mode, depth, lens)
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
                      "claims": [key+"-unknown"], "detail": key not in OWNER_LEVEL,
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
    if lens:
        manifest["lens"] = lens
    write_json(work/"investigation.json", manifest)
    return {"workspace": str(work), "manifest": str(work/"investigation.json"), "report": str(work/"report.json"),
            "mode": mode, "depth": depth, "lens": lens, "question": manifest["question"], "previous_report": previous,
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
    if data.get("lens") is not None and data["lens"] not in LENSES:
        raise ValueError(f"Unsupported investigation lens: {data['lens']!r}")
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


def next_step(data, report):
    """One-sentence pointer to the next unfinished piece of the workflow."""
    remaining = [row["id"] for row in data["checklist"] if row["status"] == "unresolved"]
    if remaining:
        return ("Investigate the unresolved checklist items ("+", ".join(remaining)+"). Record each with "
                "checklist, cite evidence with cite, and author the matching report sections.")
    if SCAFFOLD_LIMITATION in report["run"]["limitations"]:
        return "Replace the scaffold sections and its limitation with evidenced findings, then validate."
    return "Run validate --check-files on the working report, then finish (or finish --partial with honest limitations)."


def status(workspace):
    _, data = load(workspace)
    report = read_json(data["paths"]["report"])
    return {"workspace": str(Path(data["paths"]["report"]).parent), "mode": data["mode"], "depth": data["depth"],
            "lens": data.get("lens"), "question": data["question"], "status": data["status"], "checklist": data["checklist"],
            "remaining": [row["id"] for row in data["checklist"] if row["status"] == "unresolved"],
            "report_validation": validate(report), "previous_report": data["previous_report"],
            "next": next_step(data, report),
            "notice": "This reads saved investigation state, not live target freshness. A valid model does not establish completeness; validate local evidence or start a new run to refresh."}


CHECKLIST_STATUSES = ("unresolved", "answered", "partial", "not-applicable")
CITE_KINDS = ("source", "artifact", "document")


def set_checklist(workspace, item, new_status, note=""):
    """Record the answer to one checklist row without hand-editing the manifest."""
    if new_status not in CHECKLIST_STATUSES:
        raise ValueError("Status must be one of: "+", ".join(CHECKLIST_STATUSES))
    manifest_path, data = load(workspace)
    row = next((r for r in data["checklist"] if r["id"] == item), None)
    if row is None:
        raise ValueError(f"Unknown checklist item {item!r}; choose from: "+", ".join(r["id"] for r in data["checklist"]))
    note = (note or "").strip()
    if new_status != "unresolved" and not note:
        raise ValueError("Answered, partial and not-applicable checklist entries require an explanatory note")
    row["status"], row["note"] = new_status, note if new_status != "unresolved" else ""
    write_json(manifest_path, data)
    remaining = [r["id"] for r in data["checklist"] if r["status"] == "unresolved"]
    result = {"item": dict(row), "remaining": remaining}
    deep = {key for key, _ in DEEP_FOCUS + DEEP_CATCH_UP}
    if data["depth"] == "deep" and item in deep and new_status in ("answered", "partial") and len(note) < DEEP_NOTE_MINIMUM:
        result["warning"] = f"Deep investigations need at least {DEEP_NOTE_MINIMUM} characters of concrete explanation for {item}; finish will refuse this note."
    return result


def parse_lines(lines):
    """Parse 'N' or 'N-M' into a 1-based inclusive range."""
    if lines is None:
        return None, None
    match = re.fullmatch(r"(\d+)(?:-(\d+))?", str(lines).strip())
    if not match:
        raise ValueError("Lines must look like 12 or 12-40")
    start = int(match.group(1))
    end = int(match.group(2) or start)
    if start < 1 or end < start:
        raise ValueError("Lines must be 1-based with the end at or after the start")
    return start, end


def cite(workspace, path, lines=None, ident=None, kind="source", note="", append=False):
    """Build a schema-valid, hashed evidence record for a local file; optionally add it to the working report."""
    if kind not in CITE_KINDS:
        raise ValueError("cite supports kinds: "+", ".join(CITE_KINDS)+". REA and runtime evidence need their own records.")
    _, data = load(workspace)
    locator = data["target"]["locator"]
    requested = Path(path).expanduser()
    remote = urlparse(locator).scheme in ("http", "https")
    base = None if remote else (Path(locator).parent if Path(locator).is_file() else Path(locator)).resolve()
    if base is None and not requested.is_absolute():
        raise ValueError("This target is a URL; cite a local evidence file by absolute path")
    file = (requested if requested.is_absolute() else base/requested).resolve()
    if not file.is_file():
        raise ValueError(f"Cited file does not exist: {file}")
    start, end = parse_lines(lines)
    if start is not None:
        try:
            with file.open("r", encoding="utf-8") as stream:
                count = sum(1 for _ in stream)
        except UnicodeError:
            raise ValueError("Line citations need a UTF-8 text file; omit --lines for binary evidence")
        if end > count:
            raise ValueError(f"Line range {start}-{end} is outside the file, which has {count} lines")
    shown = file.relative_to(base).as_posix() if base is not None and file.is_relative_to(base) else str(file)
    sha = text_digest(file)
    record = {"kind": kind, "locator": shown+(f":{start}" if start and start == end else f":{start}-{end}" if start else ""),
              "note": note or "", "path": shown, "sha256": sha}
    if start is not None:
        record["line_start"], record["line_end"] = start, end
    report_path = Path(data["paths"]["report"])
    report = read_json(report_path)
    existing = {e["id"]: e for e in report["evidence"]}
    same = lambda e: all(e.get(k) == record.get(k) for k in ("path", "sha256", "line_start", "line_end"))
    if ident is None:
        stem = re.sub(r"[^A-Za-z0-9]+", "-", shown).strip("-")[-50:].strip("-") or "file"
        base_id = "ev-"+stem+(f"-L{start}" if start == end and start else f"-L{start}-{end}" if start else "")
        match = next((e for e in report["evidence"] if same(e)), None)
        if match:
            return {"evidence": match, "appended": False, "already_present": True, "report": str(report_path)}
        ident, n = base_id, 2
        while ident in existing:
            ident, n = f"{base_id}-{n}", n+1
    elif not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,79}", ident):
        raise ValueError("Evidence ID must start with a letter and use letters, digits, underscore or hyphen (max 80)")
    elif ident in existing:
        raise ValueError(f"Evidence ID {ident!r} already exists in the working report")
    record = {"id": ident, **record}
    if append:
        report["evidence"].append(record)
        write_json(report_path, report)
    return {"evidence": record, "appended": append, "already_present": False, "report": str(report_path)}


def finish(workspace, partial=False):
    manifest_path, data = load(workspace)
    report = read_json(data["paths"]["report"])
    if SCAFFOLD_LIMITATION in report["run"]["limitations"]:
        raise ValueError("The working report is still an uninvestigated scaffold. Author actual findings or an explicit blocked/interrupted account before publishing.")
    if report["run"]["id"] != data["id"] or any(
            report["target"][key] != data["target"][key] for key in ("kind", "locator")):
        raise ValueError("Report identity differs from its investigation")
    unresolved = [row["id"] for row in data["checklist"] if row["status"] == "unresolved"]
    if not partial and unresolved:
        raise ValueError("Investigation is unfinished: unresolved checklist items: "+", ".join(unresolved)
                         +". Answer each with checklist (answered, partial or not-applicable plus a note), "
                         "or publish the stated gaps explicitly with --partial.")
    if not partial and report["run"]["status"] != "complete":
        raise ValueError(f"Every checklist item is resolved, but run.status in the report is "
                         f"{report['run']['status']!r}. If the investigation is finished and only its scope is limited, "
                         "set run.status to 'complete' and run.coverage to 'partial' (and list what was not inspected "
                         "in run.limitations). Keep run.status 'partial' or 'interrupted' only for an unfinished "
                         "investigation, and then publish it with --partial.")
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
