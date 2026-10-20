"""Strict report contract and referential/freshness validation. No dependencies."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((PACKAGE / "assets/report.schema.json").read_text(encoding="utf-8"))


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def json_text(value):
    return json.dumps(value, ensure_ascii=True, indent=2) + "\n"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def schema_errors(value, spec=None, at="$"):
    """Validate the intentionally bounded JSON Schema vocabulary used by v1."""
    spec = SCHEMA if spec is None else spec
    if "$ref" in spec:
        target = SCHEMA
        for key in spec["$ref"][2:].split("/"):
            target = target[key]
        return schema_errors(value, target, at)
    errors = []
    types = {"object": dict, "array": list, "string": str, "integer": int,
             "boolean": bool, "null": type(None)}
    expected = spec.get("type")
    if expected:
        names = expected if isinstance(expected, list) else [expected]
        if not any(type(value) is types[name] for name in names):
            return [f"{at}: expected {expected}"]
    if "const" in spec and (type(value) is not type(spec["const"]) or value != spec["const"]):
        errors.append(f"{at}: expected constant {spec['const']}")
    if "enum" in spec and value not in spec["enum"]:
        errors.append(f"{at}: expected one of {spec['enum']}")
    if isinstance(value, dict):
        props = spec.get("properties", {})
        for key in spec.get("required", []):
            if key not in value:
                errors.append(f"{at}: missing {key}")
        for key, item in value.items():
            if key in props:
                errors += schema_errors(item, props[key], f"{at}.{key}")
            elif spec.get("additionalProperties") is False:
                errors.append(f"{at}: unknown property {key}")
    if isinstance(value, list):
        if len(value) < spec.get("minItems", 0) or len(value) > spec.get("maxItems", float("inf")):
            errors.append(f"{at}: invalid item count")
        if spec.get("uniqueItems") and len({json.dumps(v, sort_keys=True) for v in value}) != len(value):
            errors.append(f"{at}: duplicate values")
        if "items" in spec:
            for i, item in enumerate(value):
                errors += schema_errors(item, spec["items"], f"{at}[{i}]")
    if isinstance(value, str):
        if len(value) < spec.get("minLength", 0) or len(value) > spec.get("maxLength", float("inf")):
            errors.append(f"{at}: invalid string length")
        if "pattern" in spec and not re.search(spec["pattern"], value):
            errors.append(f"{at}: invalid format")
        if spec.get("format") == "date-time":
            try:
                stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    raise ValueError("timezone required")
            except ValueError:
                errors.append(f"{at}: use an ISO timestamp with timezone")
    if type(value) is int and value < spec.get("minimum", value):
        errors.append(f"{at}: below minimum")
    return errors


def evidence_path(report, evidence):
    p = Path(evidence["path"])
    if p.is_absolute():
        return p.resolve()
    root = Path(report["target"]["locator"]).resolve()
    return ((root.parent if root.is_file() else root) / p).resolve()


def validate(report, check_files=False):
    errors, warnings = schema_errors(report), []
    if errors:
        return {"valid": False, "errors": errors, "warnings": warnings}
    groups = {name: report[name] for name in ("evidence", "claims", "sections", "diagrams")}
    indexes = {}
    for name, records in groups.items():
        indexes[name] = {r["id"]: r for r in records}
        if len(indexes[name]) != len(records):
            errors.append(f"{name}: duplicate IDs")
    claims, evidence = indexes["claims"], indexes["evidence"]

    def check_refs(refs, index, context):
        for ref in refs:
            if ref not in index:
                errors.append(f"{context}: missing reference {ref}")

    def check_freshness(freshness, refs, context):
        if freshness == "verified" and any(claims[c]["freshness"] != "verified" for c in refs if c in claims):
            errors.append(f"{context}: verified presentation contains stale/unverified claims")

    for claim in report["claims"]:
        check_refs(claim["evidence"], evidence, claim["id"])
        if claim["authority"] != "unknown" and not claim["evidence"]:
            errors.append(f"{claim['id']}: factual/inferred claims require evidence")
        if report["run"]["status"] == "complete" and claim["freshness"] != "verified":
            errors.append(f"{claim['id']}: complete run contains unchecked claims")
    used_claims = set()
    for section in report["sections"]:
        if report["run"]["status"] == "complete" and section["freshness"] != "verified":
            errors.append(f"{section['id']}: complete run contains an unchecked section")
        check_refs(section["claims"], claims, section["id"])
        check_freshness(section["freshness"], section["claims"], section["id"])
        used_claims.update(section["claims"])
        if not section["claims"]:
            errors.append(f"{section['id']}: explain section findings or gaps with claims")
        table = section.get("table")
        if table and any(len(row) != len(table["columns"]) for row in table["rows"]):
            errors.append(f"{section['id']}: table row width mismatch")
    for diagram in report["diagrams"]:
        if report["run"]["status"] == "complete" and diagram["freshness"] != "verified":
            errors.append(f"{diagram['id']}: complete run contains an unchecked diagram")
        nodes = {n["id"] for n in diagram["nodes"]}
        if len(nodes) != len(diagram["nodes"]):
            errors.append(f"{diagram['id']}: duplicate node IDs")
        for item in diagram["nodes"] + diagram["edges"]:
            check_refs(item["claims"], claims, diagram["id"])
            check_freshness(diagram["freshness"], item["claims"], diagram["id"])
            used_claims.update(item["claims"])
            if not item["claims"]:
                errors.append(f"{diagram['id']}: every node/relationship needs claims")
        for edge in diagram["edges"]:
            if edge["from"] not in nodes or edge["to"] not in nodes:
                errors.append(f"{diagram['id']}: dangling edge")
    for claim_id in claims.keys() - used_claims:
        warnings.append(f"{claim_id}: claim not used in a section or diagram")
    for ev in report["evidence"]:
        if "path" in ev and "sha256" not in ev:
            errors.append(f"{ev['id']}: local evidence requires sha256")
        if ev["kind"] == "rea" and ("evidence_id" not in ev or "path" not in ev):
            errors.append(f"{ev['id']}: REA citation requires durable file and actual Evidence ID")
        if ("line_start" in ev or "line_end" in ev) and "path" not in ev:
            errors.append(f"{ev['id']}: line citations require a file")
        if "line_end" in ev and "line_start" not in ev:
            errors.append(f"{ev['id']}: line_end requires line_start")
        if ev.get("line_end", ev.get("line_start", 1)) < ev.get("line_start", 1):
            errors.append(f"{ev['id']}: reversed line range")
        if not check_files or "path" not in ev:
            continue
        issue = None
        try:
            p = evidence_path(report, ev)
            if not p.is_file():
                issue = "file unavailable"
            elif digest(p) != ev.get("sha256"):
                issue = "fingerprint changed"
            elif "line_start" in ev:
                with p.open("r", encoding="utf-8") as stream:
                    count = sum(1 for _ in stream)
                if ev.get("line_end", ev["line_start"]) > count:
                    issue = "line range outside file"
        except (OSError, UnicodeError) as exc:
            issue = f"cannot verify file: {exc}"
        if issue:
            consumers = [c for c in report["claims"] if ev["id"] in c["evidence"]]
            verified = not consumers or any(c["freshness"] == "verified" for c in consumers)
            (errors if verified else warnings).append(f"{ev['id']}: {issue}")
    if report["run"]["coverage"] != "complete" and not report["run"]["limitations"]:
        errors.append("run: incomplete coverage requires explicit limitations")
    if report["run"]["status"] != "complete" and not report["run"]["limitations"]:
        errors.append("run: partial/interrupted report requires limitations and continuation details")
    if check_files:
        start, end = report["run"].get("inventory_start"), report["run"].get("inventory_end")
        if bool(start) != bool(end):
            errors.append("run: provide both start and end inventories")
        if start and end:
            try:
                from aa_inventory import compare_inventory
                delta = compare_inventory(read_json(start), read_json(end))
                changed = any(delta[k] for k in ("added", "removed", "changed")) or delta["coverage_changed"]
                if changed and (report["run"]["status"] == "complete" or not report["run"]["limitations"]):
                    errors.append("run: target changed during collection; investigate or mark partial with limitations")
            except (OSError, ValueError, KeyError) as exc:
                errors.append(f"run: cannot compare collection inventories: {exc}")
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def compare_reports(old, new):
    for report in (old, new):
        if not validate(report)["valid"]:
            raise ValueError("Cannot compare structurally invalid reports")
    if old["target"]["name"] != new["target"]["name"] or old["target"]["kind"] != new["target"]["kind"]:
        raise ValueError("Reports identify different targets")
    before = {c["id"]: c for c in old["claims"]}
    after = {c["id"]: c for c in new["claims"]}
    delta = {"added": sorted(after.keys() - before.keys()), "removed": sorted(before.keys() - after.keys()),
             "findings_changed": [], "evidence_changed": [], "coverage_changed": [], "unchanged": []}
    def signature(report, claim):
        records = {e["id"]: e for e in report["evidence"]}
        return sorted(json.dumps({k: v for k, v in records[e].items() if k not in ("id", "path")},
                                 sort_keys=True) for e in claim["evidence"])
    for key in sorted(before.keys() & after.keys()):
        a, b = before[key], after[key]
        changed = False
        for field, category in (("text", "findings_changed"), ("authority", "coverage_changed"),
                                ("freshness", "coverage_changed")):
            if a[field] != b[field]:
                if key not in delta[category]:
                    delta[category].append(key)
                changed = True
        if signature(old, a) != signature(new, b):
            delta["evidence_changed"].append(key)
            changed = True
        if not changed:
            delta["unchanged"].append(key)
    delta["run_coverage_changed"] = old["run"]["coverage"] != new["run"]["coverage"]
    delta["notice"] = "Finding changes are investigation leads, not automatic proof of architectural change."
    return delta
