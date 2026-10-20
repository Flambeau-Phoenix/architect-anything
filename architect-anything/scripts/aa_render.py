"""Offline HTML/Markdown/SVG renderer and immutable snapshot publisher."""
from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import shutil
import tempfile
import textwrap
from pathlib import Path
from urllib.parse import quote, urlparse

from aa_model import PACKAGE, digest, evidence_path, json_text, validate


def esc(value):
    return html.escape(str(value), quote=True)


def md(value):
    # Model prose is plain text, not executable Markdown/HTML.
    result = html.escape(str(value), quote=False)
    for char in "\\`*_{}[]()#+!|":
        result = result.replace(char, "\\" + char)
    return result.replace("\n", " ")


def badge(value):
    return f'<span class="tag {esc(value)}">{esc(value)}</span>'


def claim_links(ids):
    return " ".join(f'<a href="#claim-{esc(c)}">{esc(c)}</a>' for c in ids)


def text_lines(label, x, y, width=28):
    lines = textwrap.wrap(label, width=width, break_long_words=True) or [""]
    return "".join(f'<text x="{x}" y="{y+i*19}" text-anchor="middle" font-size="13">{esc(line)}</text>'
                   for i, line in enumerate(lines))


def diagram_svg(diagram):
    """A vertical relationship map or chronological sequence, never guessed edges."""
    nodes, edges = diagram["nodes"], diagram["edges"]
    positions = {n["id"]: i for i, n in enumerate(nodes)}
    sequence = diagram["kind"] == "sequence"
    width = max(620, len(nodes) * 190 + 60) if sequence else max(540, 360 + len(edges) * 24)
    header_height = max(90, max(len(textwrap.wrap(n["label"], width=20)) for n in nodes)*19+30) if sequence else 90
    height = (header_height + 100 + len(edges) * 100) if sequence else max(210, len(nodes) * 150 + 60)
    marker = f'arrow-{diagram["id"]}'
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title-{esc(diagram["id"])}" viewBox="0 0 {width} {height}">',
             f'<title id="title-{esc(diagram["id"])}">{esc(diagram["title"])}</title>',
             '<desc>Evidence-linked nodes and directed relationships. Numbered arrows correspond to the relationship list.</desc>',
             '<style>.node{fill:var(--paper,#fff);stroke:var(--accent,#126b69);stroke-width:1.5}text{fill:var(--ink,#172b42);font-family:system-ui,sans-serif}.edge{fill:none;stroke:var(--muted,#52657b);stroke-width:1.6}.lifeline{stroke:var(--line,#a8b7c9);stroke-dasharray:5 5}.edge-marker{fill:var(--muted,#52657b)}</style>',
             f'<defs><marker id="{marker}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="edge-marker" d="M 0 0 L 10 5 L 0 10 z"/></marker></defs>']
    for node in nodes:
        i = positions[node["id"]]
        x, y = (30 + i*190, 25) if sequence else (32, 30+i*150)
        w = 160 if sequence else 260
        if sequence:
            parts.append(f'<path class="lifeline" d="M {x+w/2} {25+header_height} V {height-20}"/>')
        parts.append(f'<a href="#claim-{esc(node["claims"][0])}"><rect class="node" x="{x}" y="{y}" width="{w}" height="{header_height}" rx="10"/>')
        parts.append(text_lines(node["label"], x+w/2, y+28, 20 if sequence else 32))
        parts.append('</a>')
    for i, edge in enumerate(edges):
        a, b = positions[edge["from"]], positions[edge["to"]]
        if sequence:
            x1, x2, y = 110+a*190, 110+b*190, header_height+80+i*100
            if a == b:
                path = f"M {x1} {y} h 50 v 32 h -50"
                lx = x1 + 50
            else:
                path = f"M {x1} {y} H {x2}"
                lx = (x1+x2)/2
            parts.append(f'<path class="edge" marker-end="url(#{marker})" d="{path}"/>')
            parts.append(f'<text x="{lx}" y="{y-12}" text-anchor="middle" font-size="12">{i+1}</text>')
        else:
            # Give every relationship its own routing lane; labels live in the legend.
            lane, y1, y2 = 330+i*24, 68+a*150, 80+b*150
            if a == b:
                y2 += 24
            path = f"M 292 {y1} H {lane} V {y2} H 292"
            parts.append(f'<path class="edge" marker-end="url(#{marker})" d="{path}"/>')
            parts.append(f'<circle cx="{lane}" cy="{(y1+y2)/2}" r="10" style="fill:var(--bg,#f4f6f9)"/>')
            parts.append(f'<text x="{lane}" y="{(y1+y2)/2+4}" text-anchor="middle" font-size="10">{i+1}</text>')
    parts.append("</svg>")
    return "".join(parts)


def evidence_href(report, evidence):
    if "path" in evidence:
        return evidence_path(report, evidence).as_uri()
    parsed = urlparse(evidence["locator"])
    return evidence["locator"] if parsed.scheme in ("https", "http") and parsed.netloc else None


def render_documents(report):
    claims = {c["id"]: c for c in report["claims"]}
    sections, markdown = [], [f'# {md(report["title"])}', "", md(report["subtitle"]), "",
        f'**Target:** {md(report["target"]["name"])} · **As of:** {md(report["run"]["captured_at"])}',
        f'**Status:** {report["run"]["status"]} · **Coverage:** {report["run"]["coverage"]}',
        f'**Revision:** {md(report["target"]["revision"] or "No Git revision; see evidence fingerprints")}', ""]
    nav = []
    changes = report["run"].get("changes", [])
    if changes:
        sections.append('<section class="card searchable" id="changes"><h2>What changed</h2><ul>' +
                        "".join(f"<li>{esc(c)}</li>" for c in changes) + "</ul></section>")
        markdown += ["## What changed", ""] + [f"- {md(c)}" for c in changes] + [""]
        nav.append('<a href="#changes">What changed</a>')
    if report["run"]["limitations"]:
        sections.append('<section class="card notice searchable" id="coverage"><h2>Investigation boundaries</h2><ul>' +
                        "".join(f"<li>{esc(c)}</li>" for c in report["run"]["limitations"]) + "</ul></section>")
        markdown += ["## Investigation boundaries", ""] + [f"- {md(c)}" for c in report["run"]["limitations"]] + [""]
        nav.append('<a href="#coverage">Investigation boundaries</a>')
    for section in report["sections"]:
        sid = "section-" + section["id"]
        nav.append(f'<a href="#{esc(sid)}">{esc(section["title"])}</a>')
        body = "".join(f"<p>{esc(p)}</p>" for p in section["body"])
        markdown += [f'<a id="{sid}"></a>', f'## {md(section["title"])}', "",
                     f'Freshness: **{section["freshness"]}**', ""] + [md(p)+"\n" for p in section["body"]]
        table = section.get("table")
        if table:
            body += '<div class="table-scroll"><table><thead><tr>' + "".join(
                f"<th>{esc(v)}</th>" for v in table["columns"]) + "</tr></thead><tbody>"
            body += "".join("<tr>" + "".join(f"<td>{esc(v)}</td>" for v in row) + "</tr>" for row in table["rows"])
            body += "</tbody></table></div>"
            markdown += ["| " + " | ".join(md(c) for c in table["columns"]) + " |",
                         "| " + " | ".join("---" for _ in table["columns"]) + " |"]
            markdown += ["| " + " | ".join(md(c) for c in row) + " |" for row in table["rows"]] + [""]
        body += '<div class="citations">Supporting claims: ' + claim_links(section["claims"]) + "</div>"
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
        for i, edge in enumerate(diagram["edges"]):
            label = f'{node_labels[edge["from"]]} → {node_labels[edge["to"]]}: {edge["label"]}'
            body += f'<li><span class="edge-number">{i+1}</span>{esc(label)} <span class="citations">{claim_links(edge["claims"])}</span></li>'
            markdown += [f'{i+1}. {md(label)} — ' + ", ".join(f"[{c}](#claim-{c})" for c in edge["claims"])]
        body += f'</ol><p class="small download"><a href="diagrams/{esc(diagram["id"])}.svg">SVG</a> · <a href="diagrams/{esc(diagram["id"])}.json">Editable diagram model</a></p>'
        sections.append(f'<section class="card searchable" id="diagram-{esc(diagram["id"])}"><div class="section-top"><h2>{esc(diagram["title"])}</h2>{badge(diagram["freshness"])}</div>{body}</section>')
        markdown += [""]
    nav += ['<a href="#claims">Claim ledger</a>', '<a href="#evidence">Evidence index</a>', '<a href="#method">Method & scope</a>']
    ledger = '<section class="card searchable" id="claims"><h2>Claim ledger</h2><p class="small">Authority describes how a conclusion was reached. Freshness describes whether its basis was rechecked.</p>'
    markdown += ["## Claim ledger", ""]
    for claim in report["claims"]:
        cites = "".join(f'<a href="#evidence-{esc(e)}">{esc(e)}</a>' for e in claim["evidence"])
        ledger += f'<article class="claim" id="claim-{esc(claim["id"])}"><span class="claim-label">{esc(claim["id"])}</span>{badge(claim["authority"])} {badge(claim["freshness"])}<p>{esc(claim["text"])}</p><div class="citations">{cites or "Evidence not established within scope."}</div></article>'
        markdown += [f'<a id="claim-{claim["id"]}"></a>',
                     f'**{claim["id"]} · {claim["authority"]} · {claim["freshness"]}**', "", md(claim["text"]), "",
                     "Evidence: " + (", ".join(f"[{e}](#evidence-{e})" for e in claim["evidence"]) or "Not established"), ""]
    sections.append(ledger + "</section>")
    evidence_html = '<section class="card searchable" id="evidence"><h2>Evidence index</h2><p class="small">Raw evidence stays outside this page. Local file links require the cited checkout or evidence directory.</p>'
    markdown += ["## Evidence index", ""]
    for ev in report["evidence"]:
        href = evidence_href(report, ev)
        source = f'<a href="{esc(href)}">{esc(ev["locator"])}</a>' if href else esc(ev["locator"])
        location = ""
        if "line_start" in ev:
            location = f' · lines {ev["line_start"]}–{ev.get("line_end",ev["line_start"])}'
        evidence_html += f'<article class="evidence" id="evidence-{esc(ev["id"])}"><strong>{esc(ev["id"])}</strong> {badge(ev["kind"])}<p>{source}{location}</p><p>{esc(ev["note"])}</p>'
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
<label for="search" class="small"><br>Find in report</label><input id="search" type="search" placeholder="Components, flows, evidence…">
<div id="search-status" role="status" aria-live="polite"></div><button id="contents" class="contents-toggle" type="button" aria-expanded="false" aria-controls="contents-nav">Contents</button><nav id="contents-nav" aria-label="Report sections">{"".join(nav)}</nav>
<div class="tools"><button id="theme" type="button">Light / dark</button><button id="print" type="button">Print</button></div>
<p class="small download"><a href="report.md">Markdown</a> · <a href="report.json">Report model</a></p></aside>
<main id="main"><header><div class="eyebrow">Architecture intelligence · {esc(report["target"]["kind"])}</div>
<h1>{esc(report["title"])}</h1><p class="subtitle">{esc(report["subtitle"])}</p>
<div class="meta"><span>As of {esc(report["run"]["captured_at"])}</span><span>Coverage: {esc(report["run"]["coverage"])}</span>
<span>Revision: {esc(report["target"]["revision"] or "content fingerprints")}</span></div></header>
<div class="stats">{"".join(f'<div class="stat"><strong>{number}</strong><span>{label}</span></div>' for number,label in stats)}</div>
{"".join(sections)}<footer>Architect Anything · Evidence-backed investigation · Run {esc(report["run"]["id"])}<br>Static findings do not establish unobserved runtime behavior.</footer></main>
<script>{js}</script></body></html>'''
    return document, "\n".join(markdown), diagram_assets


def publish(report, output, check_files=True):
    result = validate(report, check_files=check_files)
    if not result["valid"]:
        raise ValueError("\n".join(result["errors"]))
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    lock = output / ".architect-publish.lock"
    lock_fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    stage = None
    try:
        os.write(lock_fd, str(os.getpid()).encode())
        os.close(lock_fd)
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
        page, markdown, diagrams = render_documents(report)
        (stage / "report.html").write_text(page, encoding="utf-8")
        (stage / "report.md").write_text(markdown, encoding="utf-8")
        (stage / "report.json").write_text(json_text(report), encoding="utf-8")
        (stage / "evidence.json").write_text(json_text(report["evidence"]), encoding="utf-8")
        (stage / "diagrams").mkdir()
        for diagram in report["diagrams"]:
            name = diagram["id"]
            (stage / "diagrams" / f"{name}.svg").write_text(diagrams[name].replace('href="#claim-', 'href="../report.html#claim-'), encoding="utf-8")
            (stage / "diagrams" / f"{name}.json").write_text(json_text(diagram), encoding="utf-8")
        manifest = {p.relative_to(stage).as_posix(): digest(p) for p in sorted(stage.rglob("*")) if p.is_file()}
        (stage / "manifest.json").write_text(json_text(manifest), encoding="utf-8")
        rel = f'snapshots/{report["run"]["id"]}'
        index = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={rel}/report.html"><title>{esc(report["title"])}</title></head><body><p><a href="{rel}/report.html">Open the current architecture report</a></p></body></html>'
        readme = f'# {md(report["title"])}\n\n[Current HTML report]({rel}/report.html) · [Markdown]({rel}/report.md)\n\nRun: {report["run"]["id"]}\n\nOlder reports are preserved in `snapshots/`. Keep human notes outside generated snapshots.\n'
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
        return {"snapshot": str(final), "html": str(final/"report.html"), "markdown": str(final/"report.md"),
                "warnings": result["warnings"]}
    finally:
        if stage and stage.exists():
            if not stage.resolve().is_relative_to(output):
                raise ValueError("Refusing cleanup outside the selected output directory")
            shutil.rmtree(stage)  # Own freshly created staging directory, under selected output.
        lock.unlink(missing_ok=True)
