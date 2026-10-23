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
     SCHEMA,
    VERSION,
    json_text,
    read_json,
    schema_errors,
    text_digest,
    validate,
)
from aa_render import EMIT_PACKS, normalize_emits, publish

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
# The "onboarding" lens: orient a new maintainer or contributor rapidly with concrete entry points,
# edit maps, local dev/test loops, and invariant landmines.
ONBOARDING = [
    ("briefing", "What is the 60-second mental model of this system and its core vocabulary?"),
    ("entrypoints", "Where does execution start, and how is the system bootstrapped?"),
    ("codemap", "Where should a developer look to add or modify key features?"),
    ("devloop", "How is the project configured, run, tested and debugged locally?"),
    ("invariants", "Which architectural invariants, ordering rules or landmines must not be broken?"),
    ("limits", "What remains undocumented or requires live environment access to verify?")
]
# The "delta" lens: audit architectural drift, breaking changes, and migration impact.
DELTA = [
    ("summary", "What are the headline architectural and behavioral changes?"),
    ("contracts", "Which public APIs, schemas, CLI flags, events or wire formats changed?"),
    ("data", "How did state ownership, persistence formats or migration requirements change?"),
    ("dependencies", "Which internal boundaries, external services or third-party dependencies shifted?"),
    ("drift", "Where do existing docs, comments or configuration lag behind the current implementation?"),
    ("risks", "What regression risks, compatibility hazards or unverified paths remain?")
]
# The "boundaries" lens: map trust boundaries, untrusted inputs, external calls, and privilege assumptions.
BOUNDARIES = [
    ("surface", "What are all external entry points and untrusted input channels into this scope?"),
    ("trust", "Where are the trust, process, privilege and isolation boundaries?"),
    ("validation", "How are untrusted inputs parsed, validated, escaped or sandboxed before use?"),
    ("egress", "Which external network services, filesystems, subprocesses or IPC channels are invoked?"),
    ("secrets", "How are credentials, tokens, keys and sensitive configuration loaded and scoped?"),
    ("assumptions", "What security or isolation guarantees are assumed from the host environment?"),
    ("limits", "Which attack surfaces or runtime behaviors were not verified in this static/bounded pass?")
]
# The "operations" lens: production readiness, state lifecycle, failure recovery, and observability.
OPERATIONS_LENS = [
    ("lifecycle", "How does the system initialize, warm up, accept work and drain on shutdown?"),
    ("config", "Which environment variables, files and flags control runtime behavior, and in what precedence?"),
    ("state", "Where does durable and ephemeral state live, and what are the concurrency/locking guarantees?"),
    ("resilience", "How are timeouts, retries, backpressure, circuit breaking and partial failures handled?"),
    ("observability", "What logs, metrics, traces, health checks or receipts are emitted for operators?"),
    ("recovery", "How does the system recover from crashes, corrupt state or interrupted operations?"),
    ("limits", "Which operational failure modes or scale limits remain untested?")
]

OVERVIEW_CATCH_UP = ("briefing", "components", "behavior", "changes", "assessment")
OVERVIEW_FOCUS = ("answer", "trace", "limits")
OVERVIEW_MECHANISM = ("answer", "essentials", "choices", "limits")
OVERVIEW_ONBOARDING = ("briefing", "entrypoints", "codemap", "invariants", "limits")
OVERVIEW_DELTA = ("summary", "contracts", "drift", "risks")
OVERVIEW_BOUNDARIES = ("surface", "trust", "egress", "limits")
OVERVIEW_OPERATIONS = ("lifecycle", "config", "resilience", "recovery", "limits")

LENSES = ("mechanism", "onboarding", "delta", "boundaries", "operations")
FOCUS_ONLY_LENSES = ("mechanism",)
LENS_TABLES = {
    "mechanism": MECHANISM,
    "onboarding": ONBOARDING,
    "delta": DELTA,
    "boundaries": BOUNDARIES,
    "operations": OPERATIONS_LENS,
}
LENS_OVERVIEWS = {
    "mechanism": OVERVIEW_MECHANISM,
    "onboarding": OVERVIEW_ONBOARDING,
    "delta": OVERVIEW_DELTA,
    "boundaries": OVERVIEW_BOUNDARIES,
    "operations": OVERVIEW_OPERATIONS,
}
# Sections on the owner-level reading path; every other section is collapsed technical detail.
OWNER_LEVEL = (
    "briefing", "answer", "assessment", "limits", "essentials", "choices",
    "entrypoints", "codemap", "invariants",
    "summary", "contracts", "drift", "risks",
    "surface", "trust",
    "lifecycle", "resilience", "recovery",
)
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
    "assumptions": "What it assumes from its host", "choices": "What you would decide for yourself",
    "entrypoints": "Entry points and boot sequence", "codemap": "Where to find and change things",
    "devloop": "Local development and verification loop", "invariants": "Invariants and architectural landmines",
    "summary": "Headline architectural changes", "contracts": "Interface and contract changes",
    "dependencies": "Dependency and boundary shifts", "drift": "Documentation versus implementation drift",
    "risks": "Compatibility and regression risks",
    "surface": "External entry points and input surface", "trust": "Trust and isolation boundaries",
    "validation": "Input parsing, validation and escaping", "egress": "Outbound calls, subprocesses and IPC",
    "secrets": "Credentials, secrets and sensitive state",
    "lifecycle": "Startup, readiness and graceful shutdown", "config": "Configuration knobs and precedence",
    "state": "State durability and concurrency", "resilience": "Timeouts, retries and backpressure",
    "observability": "Logs, metrics, health and diagnostics", "recovery": "Crash recovery and state repair",
}


def questions_for(mode, depth, lens=None):
    """Return the (id, question) checklist for a mode, depth and optional lens."""
    if depth not in DEPTHS:
        raise ValueError(f"Depth must be one of: {', '.join(DEPTHS)}")
    if lens is not None and lens not in LENSES:
        raise ValueError(f"Lens must be one of: {', '.join(LENSES)}")
    if lens in FOCUS_ONLY_LENSES and mode != "focus":
        raise ValueError("A lens needs a focus: name the mechanism you want to understand")
    base = LENS_TABLES[lens] if lens else (FOCUS if mode == "focus" else CATCH_UP)
    if depth == "overview":
        keep = LENS_OVERVIEWS[lens] if lens else (OVERVIEW_FOCUS if mode == "focus" else OVERVIEW_CATCH_UP)
        return [item for item in base if item[0] in keep]
    if depth == "deep":
        extra = DEEP_FOCUS if mode == "focus" else DEEP_CATCH_UP
        existing_ids = {item[0] for item in base}
        return list(base) + [item for item in extra if item[0] not in existing_ids]
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
          depth=DEFAULT_DEPTH, lens=None, emit=()):
    if depth not in DEPTHS:
        raise ValueError(f"Depth must be one of: {', '.join(DEPTHS)}")
    if focus is not None and not focus.strip():
        raise ValueError("A focus question cannot be blank")
    if lens is not None and lens not in LENSES:
        raise ValueError(f"Lens must be one of: {', '.join(LENSES)}")
    if lens in FOCUS_ONLY_LENSES and focus is None:
        raise ValueError("A lens needs a focus: name the mechanism you want to understand")
    selected_emits = normalize_emits(emit)
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
    default_label = focus.strip() if focus else (f"{lens} investigation" if lens else "project catch-up")
    report = {
        "schema_version": 1, "title": f"{name}: {default_label}",
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
    if selected_emits:
        manifest["emit"] = selected_emits
    write_json(work/"investigation.json", manifest)
    res = {"workspace": str(work), "manifest": str(work/"investigation.json"), "report": str(work/"report.json"),
           "mode": mode, "depth": depth, "lens": lens, "question": manifest["question"], "previous_report": previous,
           "inventory_summary": {"files": len(first["files"]), "coverage": first["coverage"]} if first else None,
           "next": "Investigate the checklist using the skill; author claims/sections and evidence, then run finish. This command has not analyzed architectural behavior or published a report."}
    if selected_emits:
        res["emit"] = selected_emits
    return res


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
    res = {"workspace": str(Path(data["paths"]["report"]).parent), "mode": data["mode"], "depth": data["depth"],
           "lens": data.get("lens"), "question": data["question"], "status": data["status"], "checklist": data["checklist"],
           "remaining": [row["id"] for row in data["checklist"] if row["status"] == "unresolved"],
           "report_validation": validate(report), "previous_report": data["previous_report"],
           "next": next_step(data, report),
           "notice": "This reads saved investigation state, not live target freshness. A valid model does not establish completeness; validate local evidence or start a new run to refresh."}
    if data.get("emit"):
        res["emit"] = data["emit"]
    return res


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


def _prune_unused_scaffold(report):
    """Remove unused *-unknown scaffold claims and auto-clear SCAFFOLD_LIMITATION when all sections are authored."""
    used_claims = set()
    for s in report["sections"]:
        used_claims.update(s["claims"])
    for d in report["diagrams"]:
        for item in d["nodes"] + d["edges"]:
            used_claims.update(item["claims"])
    report["claims"] = [
        c for c in report["claims"]
        if not (c["id"].endswith("-unknown") and c["authority"] == "unknown"
                and c["text"].endswith("Not established yet.") and c["id"] not in used_claims)
    ]
    still_scaffold = any(
        s["body"] == ["This topic has not been investigated."]
        or any(c.endswith("-unknown") for c in s["claims"])
        for s in report["sections"]
    )
    if not still_scaffold and SCAFFOLD_LIMITATION in report["run"]["limitations"]:
        report["run"]["limitations"] = [l for l in report["run"]["limitations"] if l != SCAFFOLD_LIMITATION]


def upsert_claim(workspace, claim_id, text, authority="observation", freshness="verified", evidence=()):
    """Add or update one claim in the working report with immediate schema and evidence validation."""
    _, data = load(workspace)
    report_path = Path(data["paths"]["report"])
    report = read_json(report_path)
    ev_ids = {e["id"] for e in report["evidence"]}
    ev_list = list(evidence or ())
    for ref in ev_list:
        if ref not in ev_ids:
            raise ValueError(f"Claim {claim_id!r} references missing evidence ID {ref!r}")
    if authority != "unknown" and not ev_list:
        raise ValueError(f"Claim {claim_id!r} with authority {authority!r} requires at least one evidence ID")
    record = {"id": claim_id, "text": text, "authority": authority, "freshness": freshness, "evidence": ev_list}
    errors = schema_errors(record, SCHEMA["properties"]["claims"]["items"], f"$.claims[{claim_id}]")
    if errors:
        raise ValueError("Invalid claim: " + "; ".join(errors))
    idx = next((i for i, c in enumerate(report["claims"]) if c["id"] == claim_id), None)
    action = "updated" if idx is not None else "added"
    if idx is not None:
        report["claims"][idx] = record
    else:
        report["claims"].append(record)
    write_json(report_path, report)
    return {"action": action, "claim": record, "total_claims": len(report["claims"]), "report": str(report_path)}


def upsert_section(workspace, section_id, title=None, body=(), claims=(), detail=None, freshness="verified", table=None):
    """Add or update one section in the working report, pruning replaced scaffold placeholders automatically."""
    _, data = load(workspace)
    report_path = Path(data["paths"]["report"])
    report = read_json(report_path)
    claim_map = {c["id"]: c for c in report["claims"]}
    claim_list = list(claims or ())
    if not claim_list:
        raise ValueError(f"Section {section_id!r} must cite at least one claim ID")
    for ref in claim_list:
        if ref not in claim_map:
            raise ValueError(f"Section {section_id!r} references missing claim ID {ref!r}")
    if freshness == "verified" and any(claim_map[c]["freshness"] != "verified" for c in claim_list):
        raise ValueError(f"Verified section {section_id!r} cannot cite stale or unverified claims")
    idx = next((i for i, s in enumerate(report["sections"]) if s["id"] == section_id), None)
    existing = report["sections"][idx] if idx is not None else None
    resolved_title = title if title is not None else (existing["title"] if existing else TITLES.get(section_id, section_id))
    resolved_detail = detail if detail is not None else (existing["detail"] if existing else (section_id not in OWNER_LEVEL))
    body_list = [body] if isinstance(body, str) else list(body or ())
    if not body_list:
        raise ValueError(f"Section {section_id!r} requires at least one body paragraph")
    record = {"id": section_id, "title": resolved_title, "body": body_list, "claims": claim_list,
              "detail": bool(resolved_detail), "freshness": freshness}
    if table is not None:
        if not isinstance(table, dict) or "columns" not in table or "rows" not in table:
            raise ValueError("Section table must be an object with 'columns' and 'rows'")
        if any(len(r) != len(table["columns"]) for r in table["rows"]):
            raise ValueError(f"Section {section_id!r}: table row width mismatch")
        record["table"] = table
    errors = schema_errors(record, SCHEMA["properties"]["sections"]["items"], f"$.sections[{section_id}]")
    if errors:
        raise ValueError("Invalid section: " + "; ".join(errors))
    action = "updated" if idx is not None else "added"
    if idx is not None:
        report["sections"][idx] = record
    else:
        report["sections"].append(record)
    _prune_unused_scaffold(report)
    write_json(report_path, report)
    return {"action": action, "section": record, "scaffold_cleared": SCAFFOLD_LIMITATION not in report["run"]["limitations"],
            "report": str(report_path)}


def upsert_diagram(workspace, diagram_id, title, kind, nodes, edges, freshness="verified"):
    """Add or update one diagram in the working report with immediate structural validation."""
    _, data = load(workspace)
    report_path = Path(data["paths"]["report"])
    report = read_json(report_path)
    claim_map = {c["id"]: c for c in report["claims"]}
    record = {"id": diagram_id, "title": title, "kind": kind, "freshness": freshness,
              "nodes": list(nodes or ()), "edges": list(edges or ())}
    errors = schema_errors(record, SCHEMA["properties"]["diagrams"]["items"], f"$.diagrams[{diagram_id}]")
    if errors:
        raise ValueError("Invalid diagram: " + "; ".join(errors))
    node_ids = {n["id"] for n in record["nodes"]}
    if len(node_ids) != len(record["nodes"]):
        raise ValueError(f"Diagram {diagram_id!r} has duplicate node IDs")
    for item in record["nodes"] + record["edges"]:
        if not item.get("claims"):
            raise ValueError(f"Diagram {diagram_id!r}: every node and edge must cite at least one claim")
        for ref in item["claims"]:
            if ref not in claim_map:
                raise ValueError(f"Diagram {diagram_id!r} references missing claim ID {ref!r}")
        if freshness == "verified" and any(claim_map[c]["freshness"] != "verified" for c in item["claims"]):
            raise ValueError(f"Verified diagram {diagram_id!r} cannot cite stale or unverified claims")
    for edge in record["edges"]:
        if edge["from"] not in node_ids or edge["to"] not in node_ids:
            raise ValueError(f"Diagram {diagram_id!r} has dangling edge {edge['from']!r} -> {edge['to']!r}")
    idx = next((i for i, d in enumerate(report["diagrams"]) if d["id"] == diagram_id), None)
    action = "updated" if idx is not None else "added"
    if idx is not None:
        report["diagrams"][idx] = record
    else:
        report["diagrams"].append(record)
    _prune_unused_scaffold(report)
    write_json(report_path, report)
    return {"action": action, "diagram": record, "total_diagrams": len(report["diagrams"]), "report": str(report_path)}


def set_run_meta(workspace, title=None, subtitle=None, target_name=None, run_status=None,
                 coverage=None, limitations=None, changes=None, tools=None):
    """Update top-level report metadata and run status/coverage/limitations safely."""
    _, data = load(workspace)
    report_path = Path(data["paths"]["report"])
    report = read_json(report_path)
    if title is not None:
        if not str(title).strip():
            raise ValueError("Report title cannot be blank")
        report["title"] = str(title).strip()
    if subtitle is not None:
        report["subtitle"] = str(subtitle).strip()
    if target_name is not None:
        if not str(target_name).strip():
            raise ValueError("Target name cannot be blank")
        report["target"]["name"] = str(target_name).strip()
    if run_status is not None:
        if run_status not in ("complete", "partial", "interrupted"):
            raise ValueError("run_status must be complete, partial, or interrupted")
        report["run"]["status"] = run_status
    if coverage is not None:
        if coverage not in ("complete", "partial", "unknown"):
            raise ValueError("coverage must be complete, partial, or unknown")
        report["run"]["coverage"] = coverage
    if limitations is not None:
        report["run"]["limitations"] = [str(x).strip() for x in limitations if str(x).strip()]
    if changes is not None:
        clean_changes = [str(x).strip() for x in changes if str(x).strip()]
        if clean_changes:
            report["run"]["changes"] = clean_changes
        else:
            report["run"].pop("changes", None)
    if tools is not None:
        clean_tools = [str(x).strip() for x in tools if str(x).strip()]
        if clean_tools:
            report["run"]["tools"] = clean_tools
    _prune_unused_scaffold(report)
    errors = schema_errors(report)
    if errors:
        raise ValueError("Invalid report metadata: " + "; ".join(errors))
    write_json(report_path, report)
    return {"title": report["title"], "subtitle": report["subtitle"], "target": report["target"],
            "run": report["run"], "report": str(report_path)}


def finish(workspace, partial=False, emit=()):
    manifest_path, data = load(workspace)
    report = read_json(data["paths"]["report"])
    selected_emits = normalize_emits(list(data.get("emit", ())) + list(emit or ()))
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
    prior = read_json(data["previous_report"]) if data.get("previous_report") and Path(data["previous_report"]).is_file() else None
    result = publish(report, output, check_files=True, emit=selected_emits, prior_report=prior)
    data["status"] = report["run"]["status"]
    if selected_emits:
        data["emit"] = selected_emits
    write_json(manifest_path, data)
    return result
