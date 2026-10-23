"""Offline HTML/Markdown/SVG renderer, optional companion report packs, and immutable snapshot publisher."""
from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
import shutil
import tempfile
import textwrap
import time
from pathlib import Path
from urllib.parse import quote, urlparse

from aa_model import PACKAGE, compare_reports, digest, evidence_path, json_text, validate

EMIT_PACKS = ("mermaid", "adr", "onboarding", "delta", "llms-txt")


def normalize_emits(emit):
    """Validate and deduplicate optional companion report pack names."""
    if not emit:
        return []
    items = [emit] if isinstance(emit, str) else list(emit)
    cleaned = []
    for raw in items:
        for part in str(raw).split(","):
            val = part.strip()
            if not val:
                continue
            if val == "all":
                for p in EMIT_PACKS:
                    if p not in cleaned:
                        cleaned.append(p)
                continue
            if val not in EMIT_PACKS:
                raise ValueError(f"Emit pack must be one of: {', '.join(EMIT_PACKS)} (or 'all')")
            if val not in cleaned:
                cleaned.append(val)
    return cleaned


def esc(value):
    return html.escape(str(value), quote=True)


def rich_html(value):
    """Escape HTML metacharacters strictly, then render safe inline `code` and **bold** spans."""
    escaped = esc(value)
    escaped = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped


def md(value):
    # Model prose is plain text, not executable Markdown/HTML.
    result = html.escape(str(value), quote=False)
    for char in "\\`*_{}[]()#+!|":
        result = result.replace(char, "\\" + char)
    return result.replace("\n", " ")


def badge(value):
    return f'<span class="tag {esc(value)}">{esc(value)}</span>'


def claim_links(ids, claims_map=None):
    links = []
    for c in ids:
        tip = ""
        if claims_map and c in claims_map:
            claim = claims_map[c]
            ev_txt = ", ".join(claim["evidence"]) if claim["evidence"] else "unverified"
            summary = f"[{claim['authority']} · {claim['freshness']}] {claim['text']} (Evidence: {ev_txt})"
            tip = f' title="{esc(summary)}" data-claim-tip="{esc(summary)}"'
        links.append(f'<a href="#claim-{esc(c)}" class="claim-ref"{tip}>{esc(c)}</a>')
    return " ".join(links)


def text_lines(label, x, y, width=28):
    lines = textwrap.wrap(label, width=width, break_long_words=True) or [""]
    return "".join(f'<text x="{x}" y="{y+i*19}" text-anchor="middle" font-size="13">{esc(line)}</text>'
                   for i, line in enumerate(lines))


def _layered_positions(nodes, edges):
    """Assign (col, row) positions for non-sequence graphs using topological rank when multi-node."""
    n = len(nodes)
    if n <= 3 or not edges:
        return {node["id"]: (0, i) for i, node in enumerate(nodes)}, 1, n
    order = {node["id"]: i for i, node in enumerate(nodes)}
    indegree = {node["id"]: 0 for node in nodes}
    adj = {node["id"]: [] for node in nodes}
    for e in edges:
        u, v = e["from"], e["to"]
        if u != v and u in adj and v in indegree:
            adj[u].append(v)
            indegree[v] += 1
    rank = {node["id"]: 0 for node in nodes}
    queue = [nid for nid in order if indegree[nid] == 0]
    if not queue:
        queue = [nodes[0]["id"]]
    visited = set()
    while queue:
        curr = queue.pop(0)
        if curr in visited:
            continue
        visited.add(curr)
        for nxt in adj[curr]:
            if rank[nxt] <= rank[curr] and nxt not in visited:
                rank[nxt] = min(2, rank[curr] + 1)
            indegree[nxt] -= 1
            if indegree[nxt] <= 0 and nxt not in visited:
                queue.append(nxt)
    for nid in order:
        if nid not in visited:
            rank[nid] = 1 if len(set(rank.values())) > 1 else 0
    distinct_ranks = sorted(set(rank.values()))
    if len(distinct_ranks) == 1:
        # Split into 2 balanced columns when > 4 nodes
        if n > 4:
            cols = {0: [], 1: []}
            for i, node in enumerate(nodes):
                cols[i % 2].append(node["id"])
        else:
            return {node["id"]: (0, i) for i, node in enumerate(nodes)}, 1, n
    else:
        remap = {r: idx for idx, r in enumerate(distinct_ranks)}
        cols = {idx: [] for idx in range(len(distinct_ranks))}
        for node in nodes:
            cols[remap[rank[node["id"]]]].append(node["id"])
    coords = {}
    max_rows = 1
    for c_idx, nids in cols.items():
        max_rows = max(max_rows, len(nids))
        for r_idx, nid in enumerate(nids):
            coords[nid] = (c_idx, r_idx)
    return coords, len(cols), max_rows


def diagram_svg(diagram):
    """A layered relationship map or chronological sequence, never guessed edges."""
    nodes, edges = diagram["nodes"], diagram["edges"]
    positions = {n["id"]: i for i, n in enumerate(nodes)}
    sequence = diagram["kind"] == "sequence"
    marker = f'arrow-{diagram["id"]}'
    if sequence:
        width = max(620, len(nodes) * 190 + 60)
        header_height = max(90, max(len(textwrap.wrap(n["label"], width=20)) for n in nodes) * 19 + 30)
        height = header_height + 100 + len(edges) * 100
    else:
        coords, num_cols, max_rows = _layered_positions(nodes, edges)
        header_height = 90
        if num_cols == 1:
            width = max(540, 360 + len(edges) * 24)
            height = max(210, len(nodes) * 150 + 60)
        else:
            col_gap = 340
            width = max(680, 60 + num_cols * col_gap + len(edges) * 14)
            height = max(240, max_rows * 155 + 70)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title-{esc(diagram["id"])}" viewBox="0 0 {width} {height}">',
        f'<title id="title-{esc(diagram["id"])}">{esc(diagram["title"])}</title>',
        '<desc>Evidence-linked nodes and directed relationships. Numbered arrows correspond to the relationship list.</desc>',
        '<style>.node{fill:var(--paper,#fff);stroke:var(--accent,#126b69);stroke-width:1.6}text{fill:var(--ink,#172b42);font-family:system-ui,sans-serif}.edge{fill:none;stroke:var(--muted,#52657b);stroke-width:1.6}.lifeline{stroke:var(--line,#a8b7c9);stroke-dasharray:5 5}.edge-marker{fill:var(--muted,#52657b)}.badge-bg{fill:var(--bg,#f4f6f9);stroke:var(--accent,#126b69);stroke-width:1.2}</style>',
        f'<defs><marker id="{marker}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="edge-marker" d="M 0 0 L 10 5 L 0 10 z"/></marker></defs>'
    ]
    node_boxes = {}
    for node in nodes:
        i = positions[node["id"]]
        if sequence:
            x, y, w = 30 + i * 190, 25, 160
            parts.append(f'<path class="lifeline" d="M {x+w/2} {25+header_height} V {height-20}"/>')
        elif num_cols == 1:
            x, y, w = 32, 30 + i * 150, 260
        else:
            col, row = coords[node["id"]]
            w = 240
            x = 40 + col * 340
            y = 35 + row * 150
        node_boxes[node["id"]] = (x, y, w, header_height)
        parts.append(f'<a href="#claim-{esc(node["claims"][0])}"><rect class="node" x="{x}" y="{y}" width="{w}" height="{header_height}" rx="10"/>')
        parts.append(text_lines(node["label"], x + w / 2, y + 28, 20 if sequence else 28))
        parts.append('</a>')
    for i, edge in enumerate(edges):
        a, b = positions[edge["from"]], positions[edge["to"]]
        if sequence:
            x1, x2, y = 110 + a * 190, 110 + b * 190, header_height + 80 + i * 100
            if a == b:
                path = f"M {x1} {y} h 50 v 32 h -50"
                lx = x1 + 50
            else:
                path = f"M {x1} {y} H {x2}"
                lx = (x1 + x2) / 2
            parts.append(f'<path class="edge" marker-end="url(#{marker})" d="{path}"/>')
            parts.append(f'<text x="{lx}" y="{y-12}" text-anchor="middle" font-size="12">{i+1}</text>')
        elif num_cols == 1:
            lane, y1, y2 = 330 + i * 24, 68 + a * 150, 80 + b * 150
            if a == b:
                y2 += 24
            path = f"M 292 {y1} H {lane} V {y2} H 292"
            parts.append(f'<path class="edge" marker-end="url(#{marker})" d="{path}"/>')
            parts.append(f'<circle cx="{lane}" cy="{(y1+y2)/2}" r="10" class="badge-bg"/>')
            parts.append(f'<text x="{lane}" y="{(y1+y2)/2+4}" text-anchor="middle" font-size="10">{i+1}</text>')
        else:
            x1, y1, w1, h1 = node_boxes[edge["from"]]
            x2, y2, w2, h2 = node_boxes[edge["to"]]
            c1, _ = coords[edge["from"]]
            c2, _ = coords[edge["to"]]
            offset = (i % 5 - 2) * 8
            if edge["from"] == edge["to"]:
                sx, sy = x1 + w1, y1 + h1 / 2 - 10
                ex, ey = x1 + w1, y1 + h1 / 2 + 12
                path = f"M {sx} {sy} C {sx+45} {sy-20}, {ex+45} {ey+20}, {ex} {ey}"
                mx, my = sx + 36, (sy + ey) / 2
            elif c1 < c2:
                sx, sy = x1 + w1, y1 + h1 / 2 + offset
                ex, ey = x2, y2 + h2 / 2 + offset
                cx1, cx2 = sx + (ex - sx) * 0.45, sx + (ex - sx) * 0.55
                path = f"M {sx} {sy} C {cx1} {sy}, {cx2} {ey}, {ex} {ey}"
                mx, my = (sx + ex) / 2, (sy + ey) / 2
            elif c1 > c2:
                sx, sy = x1, y1 + h1 / 2 + offset
                ex, ey = x2 + w2, y2 + h2 / 2 + offset
                cx1, cx2 = sx - (sx - ex) * 0.45, sx - (sx - ex) * 0.55
                path = f"M {sx} {sy} C {cx1} {sy}, {cx2} {ey}, {ex} {ey}"
                mx, my = (sx + ex) / 2, (sy + ey) / 2
            else:
                lane = x1 + w1 + 26 + i * 16
                sy, ey = y1 + h1 / 2, y2 + h2 / 2
                path = f"M {x1+w1} {sy} H {lane} V {ey} H {x2+w2}"
                mx, my = lane, (sy + ey) / 2
            parts.append(f'<path class="edge" marker-end="url(#{marker})" d="{path}"/>')
            parts.append(f'<circle cx="{mx}" cy="{my}" r="11" class="badge-bg"/>')
            parts.append(f'<text x="{mx}" y="{my+4}" text-anchor="middle" font-size="10">{i+1}</text>')
    parts.append("</svg>")
    return "".join(parts)


def diagram_mermaid(diagram):
    """Export a diagram record to deterministic Mermaid syntax."""
    def clean(text):
        return str(text).replace('"', "'").replace("\n", " ")

    if diagram["kind"] == "sequence":
        lines = ["sequenceDiagram"]
        for node in diagram["nodes"]:
            lines.append(f'    participant {node["id"]} as "{clean(node["label"])}"')
        for i, edge in enumerate(diagram["edges"], 1):
            lines.append(f'    {edge["from"]}->>{edge["to"]}: {i}. {clean(edge["label"])}')
        return "\n".join(lines) + "\n"
    if diagram["kind"] == "state":
        lines = ["stateDiagram-v2"]
        for node in diagram["nodes"]:
            lines.append(f'    state "{clean(node["label"])}" as {node["id"]}')
        for i, edge in enumerate(diagram["edges"], 1):
            lines.append(f'    {edge["from"]} --> {edge["to"]}: {i}. {clean(edge["label"])}')
        return "\n".join(lines) + "\n"
    lines = ["flowchart LR"]
    for node in diagram["nodes"]:
        lines.append(f'    {node["id"]}["{clean(node["label"])}"]')
    for i, edge in enumerate(diagram["edges"], 1):
        lines.append(f'    {edge["from"]} -->|"{i}. {clean(edge["label"])}"| {edge["to"]}')
    return "\n".join(lines) + "\n"


def evidence_href(report, evidence):
    if "path" in evidence:
        return evidence_path(report, evidence).as_uri()
    parsed = urlparse(evidence["locator"])
    return evidence["locator"] if parsed.scheme in ("https", "http") and parsed.netloc else None


def render_companion_packs(report, emits, prior_report=None):
    """Build optional companion artifacts keyed by relative snapshot path."""
    files = {}
    claims = {c["id"]: c for c in report["claims"]}
    evidence = {e["id"]: e for e in report["evidence"]}

    if "mermaid" in emits:
        for diagram in report["diagrams"]:
            files[f"diagrams/{diagram['id']}.mmd"] = diagram_mermaid(diagram)
        if not report["diagrams"]:
            files["diagrams/README.mmd"] = "%% No diagrams authored in this run\n"

    if "adr" in emits:
        adr_lines = [
            f"# Architecture Decisions & Tradeoffs: {md(report['title'])}",
            "",
            f"**Target:** {md(report['target']['name'])} · **Run:** `{report['run']['id']}` · **Captured:** {report['run']['captured_at']}",
            "",
            "This companion pack synthesizes evidenced architectural decisions, inferred tradeoffs, and boundaries from the investigation.",
            "",
        ]
        decision_claims = [c for c in report["claims"] if c["authority"] in ("derived", "inference", "contradiction")]
        if not decision_claims:
            decision_claims = list(report["claims"])
        for idx, c in enumerate(decision_claims, 1):
            ev_locs = [evidence[e]["locator"] for e in c["evidence"] if e in evidence]
            adr_lines += [
                f"## ADR-{idx:03d}: {md(c['id'])}",
                "",
                f"- **Status / Freshness:** {c['freshness']}",
                f"- **Authority:** {c['authority']}",
                f"- **Decision / Finding:** {md(c['text'])}",
                f"- **Supporting Evidence:** {', '.join(f'`{l}`' for l in ev_locs) if ev_locs else 'None (open boundary)'}",
                "",
            ]
        files["packs/adr-summary.md"] = "\n".join(adr_lines)

    if "onboarding" in emits:
        onb_lines = [
            f"# Maintainer Onboarding & Codemap: {md(report['target']['name'])}",
            "",
            f"> {md(report['subtitle'])}",
            "",
            "## Key Sections",
            "",
        ]
        for s in report["sections"]:
            onb_lines.append(f"### {md(s['title'])}")
            onb_lines.append("")
            for p in s["body"]:
                onb_lines.append(md(p))
                onb_lines.append("")
            if s.get("table"):
                t = s["table"]
                onb_lines.append("| " + " | ".join(md(c) for c in t["columns"]) + " |")
                onb_lines.append("| " + " | ".join("---" for _ in t["columns"]) + " |")
                for row in t["rows"]:
                    onb_lines.append("| " + " | ".join(md(v) for v in row) + " |")
                onb_lines.append("")
        onb_lines += ["## Key Source & Artifact Locations", ""]
        for ev in report["evidence"]:
            onb_lines.append(f"- **`{ev['locator']}`** ({ev['kind']}): {md(ev['note'])}")
        onb_lines.append("")
        files["packs/onboarding-codemap.md"] = "\n".join(onb_lines)

    if "delta" in emits:
        delta_lines = [
            f"# Architecture Delta & Drift Report: {md(report['target']['name'])}",
            "",
            f"**Run:** `{report['run']['id']}` · **As of:** {report['run']['captured_at']}",
            "",
        ]
        if report["run"].get("changes"):
            delta_lines += ["## Reported Architectural Changes", ""]
            for ch in report["run"]["changes"]:
                delta_lines.append(f"- {md(ch)}")
            delta_lines.append("")
        if prior_report:
            try:
                diff = compare_reports(prior_report, report)
                delta_lines += [
                    f"## Claim Comparison vs Prior Run (`{prior_report['run']['id']}`)",
                    "",
                    f"- **Added claims ({len(diff['added'])}):** {', '.join(diff['added']) or 'None'}",
                    f"- **Removed claims ({len(diff['removed'])}):** {', '.join(diff['removed']) or 'None'}",
                    f"- **Modified findings ({len(diff['findings_changed'])}):** {', '.join(diff['findings_changed']) or 'None'}",
                    f"- **Modified evidence ({len(diff['evidence_changed'])}):** {', '.join(diff['evidence_changed']) or 'None'}",
                    f"- **Authority/freshness shifts ({len(diff['coverage_changed'])}):** {', '.join(diff['coverage_changed']) or 'None'}",
                    f"- **Unchanged claims ({len(diff['unchanged'])}):** {', '.join(diff['unchanged']) or 'None'}",
                    "",
                ]
            except ValueError as exc:
                delta_lines += [f"## Prior Report Comparison Unavailable", "", f"- {md(str(exc))}", ""]
        else:
            delta_lines += [
                "## Baseline Snapshot",
                "",
                "No prior verified report was linked to this workspace; this snapshot establishes the baseline.",
                "",
            ]
        files["packs/architecture-delta.md"] = "\n".join(delta_lines)

    if "llms-txt" in emits:
        llm_lines = [
            f"# {report['target']['name']}: {report['title']}",
            f"> {report['subtitle']}",
            "",
            f"Target: {report['target']['locator']} ({report['target']['kind']})",
            f"Run: {report['run']['id']} | Status: {report['run']['status']} | Coverage: {report['run']['coverage']}",
            "",
            "## Summary Sections",
        ]
        for s in report["sections"]:
            llm_lines.append(f"### {s['title']} [{s['id']}]")
            for p in s["body"]:
                llm_lines.append(p)
            llm_lines.append(f"Claims: {', '.join(s['claims'])}")
            llm_lines.append("")
        llm_lines.append("## Verified Claims & Citations")
        for c in report["claims"]:
            locs = [evidence[e]["locator"] for e in c["evidence"] if e in evidence]
            cite_str = f" (Sources: {', '.join(locs)})" if locs else ""
            llm_lines.append(f"- [{c['id']}] ({c['authority']}/{c['freshness']}): {c['text']}{cite_str}")
        llm_lines.append("")
        files["packs/llms-architecture.txt"] = "\n".join(llm_lines)

    return files


def render_documents(report, include_mermaid=False):
    claims = {c["id"]: c for c in report["claims"]}
    sections, markdown = [], [f'# {md(report["title"])}', "", md(report["subtitle"]), "",
        f'**Target:** {md(report["target"]["name"])} \u00b7 **As of:** {md(report["run"]["captured_at"])}',
        f'**Status:** {report["run"]["status"]} \u00b7 **Coverage:** {report["run"]["coverage"]}',
        f'**Revision:** {md(report["target"]["revision"] or "No Git revision; see evidence fingerprints")}', ""]
    nav = []
    changes = report["run"].get("changes", [])
    if changes:
        sections.append('<section class="card searchable" id="changes"><h2>What changed</h2><ul>' +
                        "".join(f"<li>{rich_html(c)}</li>" for c in changes) + "</ul></section>")
        markdown += ["## What changed", ""] + [f"- {md(c)}" for c in changes] + [""]
        nav.append('<a href="#changes">What changed</a>')
    if report["run"]["limitations"]:
        sections.append('<section class="card notice searchable" id="coverage"><h2>Investigation boundaries</h2><ul>' +
                        "".join(f"<li>{rich_html(c)}</li>" for c in report["run"]["limitations"]) + "</ul></section>")
        markdown += ["## Investigation boundaries", ""] + [f"- {md(c)}" for c in report["run"]["limitations"]] + [""]
        nav.append('<a href="#coverage">Investigation boundaries</a>')
    for section in report["sections"]:
        sid = "section-" + section["id"]
        nav.append(f'<a href="#{esc(sid)}">{esc(section["title"])}</a>')
        body = "".join(f"<p>{rich_html(p)}</p>" for p in section["body"])
        markdown += [f'<a id="{sid}"></a>', f'## {md(section["title"])}', "",
                     f'Freshness: **{section["freshness"]}**', ""] + [md(p)+"\n" for p in section["body"]]
        table = section.get("table")
        if table:
            body += '<div class="table-scroll"><table><thead><tr>' + "".join(
                f"<th>{rich_html(v)}</th>" for v in table["columns"]) + "</tr></thead><tbody>"
            body += "".join("<tr>" + "".join(f"<td>{rich_html(v)}</td>" for v in row) + "</tr>" for row in table["rows"])
            body += "</tbody></table></div>"
            markdown += ["| " + " | ".join(md(c) for c in table["columns"]) + " |",
                         "| " + " | ".join("---" for _ in table["columns"]) + " |"]
            markdown += ["| " + " | ".join(md(c) for c in row) + " |" for row in table["rows"]] + [""]
        body += '<div class="citations">Supporting claims: ' + claim_links(section["claims"], claims) + "</div>"
        markdown += ["Supporting claims: " + ", ".join(f"[{c}](#claim-{c})" for c in section["claims"]), ""]
        if section["detail"]:
            body = f"<details><summary>Read technical detail</summary><div>{body}</div></details>"
        sections.append(f'<section class="card searchable" id="{esc(sid)}"><div class="section-top"><h2>{esc(section["title"])}</h2>{badge(section["freshness"])}</div>{body}</section>')
    diagram_assets = {}
    for diagram in report["diagrams"]:
        svg = diagram_svg(diagram)
        diagram_assets[diagram["id"]] = svg
        nav.append(f'<a href="#diagram-{esc(diagram["id"])}">{esc(diagram["title"])}</a>')
        node_labels = {n["id"]: n["label"] for n in diagram["nodes"]}
        body = f'<div class="diagram-scroll">{svg}</div><ol class="edge-list">'
        markdown += [f'## {md(diagram["title"])}', "", f'![{md(diagram["title"])}](diagrams/{diagram["id"]}.svg)', "",
                     f'Freshness: **{diagram["freshness"]}**', ""]
        if include_mermaid:
            markdown += ["```mermaid", diagram_mermaid(diagram).rstrip("\n"), "```", ""]
        for i, edge in enumerate(diagram["edges"]):
            label = f'{node_labels[edge["from"]]} \u2192 {node_labels[edge["to"]]}: {edge["label"]}'
            body += f'<li><span class="edge-number">{i+1}</span>{rich_html(label)} <span class="citations">{claim_links(edge["claims"], claims)}</span></li>'
            markdown += [f'{i+1}. {md(label)} \u2014 ' + ", ".join(f"[{c}](#claim-{c})" for c in edge["claims"])]
        dl_links = f'<a href="diagrams/{esc(diagram["id"])}.svg">SVG</a> \u00b7 <a href="diagrams/{esc(diagram["id"])}.json">Editable diagram model</a>'
        if include_mermaid:
            dl_links += f' \u00b7 <a href="diagrams/{esc(diagram["id"])}.mmd">Mermaid</a>'
        body += f'</ol><p class="small download">{dl_links}</p>'
        sections.append(f'<section class="card searchable" id="diagram-{esc(diagram["id"])}"><div class="section-top"><h2>{esc(diagram["title"])}</h2>{badge(diagram["freshness"])}</div>{body}</section>')
        markdown += [""]
    nav += ['<a href="#claims">Claim ledger</a>', '<a href="#evidence">Evidence index</a>', '<a href="#method">Method & scope</a>']
    ledger = '<section class="card searchable" id="claims"><h2>Claim ledger</h2><p class="small">Authority describes how a conclusion was reached. Freshness describes whether its basis was rechecked.</p>'
    markdown += ["## Claim ledger", ""]
    for claim in report["claims"]:
        cites = "".join(f'<a href="#evidence-{esc(e)}">{esc(e)}</a>' for e in claim["evidence"])
        ledger += f'<article class="claim" id="claim-{esc(claim["id"])}"><span class="claim-label">{esc(claim["id"])}</span>{badge(claim["authority"])} {badge(claim["freshness"])}<p>{rich_html(claim["text"])}</p><div class="citations">{cites or "Evidence not established within scope."}</div></article>'
        markdown += [f'<a id="claim-{claim["id"]}"></a>',
                     f'**{claim["id"]} \u00b7 {claim["authority"]} \u00b7 {claim["freshness"]}**', "", md(claim["text"]), "",
                     "Evidence: " + (", ".join(f"[{e}](#evidence-{e})" for e in claim["evidence"]) or "Not established"), ""]
    sections.append(ledger + "</section>")
    evidence_html = '<section class="card searchable" id="evidence"><h2>Evidence index</h2><p class="small">Raw evidence stays outside this page. Local file links require the cited checkout or evidence directory.</p>'
    markdown += ["## Evidence index", ""]
    for ev in report["evidence"]:
        href = evidence_href(report, ev)
        source = f'<a href="{esc(href)}">{esc(ev["locator"])}</a>' if href else esc(ev["locator"])
        location = ""
        if "line_start" in ev:
            location = f' \u00b7 lines {ev["line_start"]}\u2013{ev.get("line_end",ev["line_start"])}'
        evidence_html += f'<article class="evidence" id="evidence-{esc(ev["id"])}"><strong>{esc(ev["id"])}</strong> {badge(ev["kind"])}<p>{source}{location}</p><p>{rich_html(ev["note"])}</p>'
        if ev.get("evidence_id"):
            evidence_html += f'<p><code>{esc(ev["evidence_id"])}</code></p>'
        if ev.get("sha256"):
            evidence_html += f'<p class="small">SHA-256 <code>{esc(ev["sha256"])}</code></p>'
        evidence_html += "</article>"
        markdown += [f'<a id="evidence-{ev["id"]}"></a>', f'### {ev["id"]}', "",
                     (f'[{md(ev["locator"])}](<{quote(href, safe=":/?#[]@!$&()*+,;=%")}>)' if href else md(ev["locator"])) + md(location),
                     "", md(ev["note"]), ""]
        for key in ("sha256", "evidence_id"):
            if key in ev:
                markdown += [f'{key}: {md(ev[key])}', ""]
    sections.append(evidence_html + "</section>")
    method = '<section class="card searchable" id="method"><h2>Method & scope</h2><h3>Tools recorded</h3><ul>' + "".join(
        f"<li>{esc(t)}</li>" for t in report["run"]["tools"]) + "</ul><h3>Excluded from investigation</h3><ul>" + "".join(
        f"<li>{esc(t)}</li>" for t in report["run"]["exclusions"]) + "</ul></section>"
    sections.append(method)
    markdown += ["## Method & scope", "", "Tools:"] + [f"- {md(t)}" for t in report["run"]["tools"]] + [
        "", "Exclusions:"] + [f"- {md(t)}" for t in report["run"]["exclusions"]] + [""]
    css = (PACKAGE / "assets/report.css").read_text(encoding="utf-8")
    js = (PACKAGE / "assets/report.js").read_text(encoding="utf-8")
    script_hash = base64.b64encode(hashlib.sha256(js.encode()).digest()).decode()
    csp = f"default-src 'none'; style-src 'unsafe-inline'; script-src 'sha256-{script_hash}'; img-src 'self' data:; base-uri 'none'; form-action 'none'"
    unknown = sum(c["authority"] == "unknown" for c in claims.values())
    stats = [(len(report["sections"]), "Report sections"), (len(claims), "Linked claims"),
             (len(report["evidence"]), "Evidence records"), (unknown, "Open questions")]
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{esc(csp)}"><title>{esc(report["title"])}</title>
<style>{css}</style></head><body><a class="skip" href="#main">Skip to report</a>
<aside><div class="brand"><span class="brand-mark" aria-hidden="true"></span>Architect Anything</div>
<h2>{esc(report["target"]["name"])}</h2><span class="tag">{esc(report["run"]["status"])} investigation</span>
<label for="search" class="small"><br>Find in report</label><input id="search" type="search" placeholder="Components, flows, evidence\u2026">
<div id="search-status" role="status" aria-live="polite"></div><button id="contents" class="contents-toggle" type="button" aria-expanded="false" aria-controls="contents-nav">Contents</button><nav id="contents-nav" aria-label="Report sections">{"".join(nav)}</nav>
<div class="tools"><button id="theme" type="button">Light / dark</button><button id="print" type="button">Print</button></div>
<p class="small download"><a href="report.md">Markdown</a> \u00b7 <a href="report.json">Report model</a></p></aside>
<main id="main"><header><div class="eyebrow">Architecture intelligence \u00b7 {esc(report["target"]["kind"])}</div>
<h1>{esc(report["title"])}</h1><p class="subtitle">{esc(report["subtitle"])}</p>
<div class="meta"><span>As of {esc(report["run"]["captured_at"])}</span><span>Coverage: {esc(report["run"]["coverage"])}</span>
<span>Revision: {esc(report["target"]["revision"] or "content fingerprints")}</span></div></header>
<div class="stats">{"".join(f'<div class="stat"><strong>{number}</strong><span>{label}</span></div>' for number,label in stats)}</div>
{"".join(sections)}<footer>Architect Anything \u00b7 Evidence-backed investigation \u00b7 Run {esc(report["run"]["id"])}<br>Static findings do not establish unobserved runtime behavior.</footer></main>
<div id="claim-popover" class="claim-popover" role="tooltip" hidden></div>
<script>{js}</script></body></html>'''
    return document, "\n".join(markdown), diagram_assets


def _acquire_lock(lock_path, stale_seconds=300):
    """Acquire publish lock, recovering automatically if the lock holder PID is gone or stale."""
    for _ in range(2):
        try:
            fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return
        except FileExistsError:
            try:
                stat = lock_path.stat()
                age = time.time() - stat.st_mtime
                raw = lock_path.read_text(encoding="utf-8", errors="ignore").strip()
                pid = int(raw) if raw.isdigit() else None
                dead = False
                if pid is not None and pid != os.getpid():
                    try:
                        os.kill(pid, 0)
                    except PermissionError:
                        dead = False
                    except (ProcessLookupError, OSError, SystemError):
                        dead = True
                if dead or age > stale_seconds:
                    lock_path.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            raise


def publish(report, output, check_files=True, emit=(), prior_report=None):
    selected_emits = normalize_emits(emit)
    result = validate(report, check_files=check_files)
    if not result["valid"]:
        raise ValueError("\n".join(result["errors"]))
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    lock = output / ".architect-publish.lock"
    _acquire_lock(lock)
    stage = None
    try:
        pointer = output / "current.json"
        old = json.loads(pointer.read_text(encoding="utf-8")) if pointer.exists() else None
        for name in ("index.html", "README.md"):
            path = output / name
            if path.exists() and (not old or digest(path) != old.get("pointer_hashes", {}).get(name)):
                raise ValueError(f"Refusing to overwrite independently edited {path}")
        snapshots = output / "snapshots"
        snapshots.mkdir(exist_ok=True)
        final = snapshots / report["run"]["id"]
        if final.exists():
            raise ValueError(f"Immutable snapshot already exists: {final}")
        stage = Path(tempfile.mkdtemp(prefix=".aa-stage-", dir=output))
        page, markdown, diagrams = render_documents(report, include_mermaid="mermaid" in selected_emits)
        (stage / "report.html").write_text(page, encoding="utf-8", newline="\n")
        (stage / "report.md").write_text(markdown, encoding="utf-8", newline="\n")
        (stage / "report.json").write_text(json_text(report), encoding="utf-8", newline="\n")
        (stage / "evidence.json").write_text(json_text(report["evidence"]), encoding="utf-8", newline="\n")
        (stage / "diagrams").mkdir()
        for diagram in report["diagrams"]:
            name = diagram["id"]
            (stage / "diagrams" / f"{name}.svg").write_text(diagrams[name].replace('href="#claim-', 'href="../report.html#claim-'), encoding="utf-8", newline="\n")
            (stage / "diagrams" / f"{name}.json").write_text(json_text(diagram), encoding="utf-8", newline="\n")
        companion_files = render_companion_packs(report, selected_emits, prior_report=prior_report)
        emitted_paths = {}
        for rel_path, content in companion_files.items():
            dest_file = stage / rel_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            dest_file.write_text(content, encoding="utf-8", newline="\n")
            emitted_paths[rel_path] = str(final / rel_path)
        manifest = {p.relative_to(stage).as_posix(): digest(p) for p in sorted(stage.rglob("*")) if p.is_file()}
        (stage / "manifest.json").write_text(json_text(manifest), encoding="utf-8", newline="\n")
        rel = f'snapshots/{report["run"]["id"]}'
        index = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={rel}/report.html"><title>{esc(report["title"])}</title></head><body><p><a href="{rel}/report.html">Open the current architecture report</a></p></body></html>'
        readme = f'# {md(report["title"])}\n\n[Current HTML report]({rel}/report.html) \u00b7 [Markdown]({rel}/report.md)\n\nRun: {report["run"]["id"]}\n\nOlder reports are preserved in `snapshots/`. Keep human notes outside generated snapshots.\n'
        new_pointer = {"schema_version": 1, "run_id": report["run"]["id"], "snapshot": rel,
                       "pointer_hashes": {name: hashlib.sha256(text.encode()).hexdigest()
                                         for name, text in (("index.html", index), ("README.md", readme))}}
        # Publish snapshot first. Roll back the three small pointers on write failure.
        stage.rename(final)
        stage = None
        previous = {name: (output/name).read_bytes() if (output/name).exists() else None
                    for name in ("index.html", "README.md", "current.json")}
        try:
            for name, text in (("index.html", index), ("README.md", readme), ("current.json", json_text(new_pointer))):
                temp = output / f".{name}.tmp"
                temp.write_text(text, encoding="utf-8", newline="\n")
                os.replace(temp, output / name)
        except OSError:
            for name, content in previous.items():
                if content is None:
                    (output/name).unlink(missing_ok=True)
                else:
                    (output/name).write_bytes(content)
            raise
        pub_res = {"snapshot": str(final), "html": str(final/"report.html"), "markdown": str(final/"report.md"),
                   "warnings": result["warnings"]}
        if emitted_paths:
            pub_res["emitted"] = emitted_paths
        return pub_res
    finally:
        if stage and stage.exists():
            if not stage.resolve().is_relative_to(output):
                raise ValueError("Refusing cleanup outside the selected output directory")
            shutil.rmtree(stage)  # Own freshly created staging directory, under selected output.
        lock.unlink(missing_ok=True)
