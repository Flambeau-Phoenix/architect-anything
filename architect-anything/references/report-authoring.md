# Report authoring

The agent authors the interpretation; deterministic helpers validate and present
it. Reports should explain the system to an owner returning after a month away,
then let an engineer follow the details and citations.

## Recommended reading order

1. Owner briefing: product purpose, users, capabilities, main system shape,
   important changes, and attention needed.
2. Architecture: boundaries, major components, deployment topology, dependencies.
3. Behavior: meaningful feature walkthroughs, data ownership and state lifecycles.
4. Technical reference: interfaces, schemas, storage, algorithms, configuration,
   build/release, observability and failure/recovery.
5. Assessment: evidenced risks, documentation drift, coupling, gaps and next checks.

Use more sections when it improves navigation. Small products can combine topics.
No fixed word count or mandatory padding. Explain "what happens" in connected
prose, then use tables for comparisons and contracts. Describe consequences:
"writes are serialized by the worker" is more useful than "there is a worker."

Do not claim novelty, patents, security assurance or performance measurements
unless those are separately investigated. Distinguish observed risks from
hypothetical improvements.

## Model and helper commands

`assets/report.schema.json` is the v1 contract. An executable example is at
`examples/minimal-report.json`; it intentionally contains an unknown claim so
that example wording cannot masquerade as findings.

```text
python scripts/aa_cli.py upsert-claim WORKSPACE CLAIM_ID --text "..." --authority observation --evidence EV_ID
python scripts/aa_cli.py upsert-section WORKSPACE SEC_ID --body "..." --claim CLAIM_ID
python scripts/aa_cli.py upsert-diagram WORKSPACE DIAG_ID --title "..." --kind component --nodes-json "[...]" --edges-json "[...]"
python scripts/aa_cli.py set-meta WORKSPACE --title "..." --subtitle "..." --run-status complete --coverage partial --limitation "..."
python scripts/architect.py validate report.json --check-files
python scripts/architect.py render report.json --output OUTPUT
```

Core helpers require only Python 3.10+. Validation is strict: unknown fields,
duplicate IDs, missing citations, invalid diagram endpoints, unsupported enums,
and inconsistent freshness are rejected.

### Required report records

- `schema_version: 1`, `title`, `subtitle`.
- `target`: `name`, `kind` (`source`, `product`, `hybrid`, `capture`), absolute local
  root or URL in `locator`, and `revision` (string or null).
- `run`: unique alphabetic-leading `id`, ISO `captured_at` with timezone,
  `status` (`complete`, `partial`, `interrupted`), `coverage`
  (`complete`, `partial`, `unknown`), `tools`, `limitations`, `exclusions`.
  Optional `changes` holds the owner-facing change summary. Optional absolute
  `inventory_start`/`inventory_end` paths must be provided together.
  **`status` and `coverage` answer different questions.** `status` says whether the
  investigation is *finished*; `coverage` says how much of the target it *inspected*. A
  focused, static or sampled investigation that you completed and that has honest limits is
  `status: complete` with `coverage: partial` (and the limits in `limitations`). Use
  `status: partial` or `interrupted` only when the work itself is unfinished (blocked,
  out of time, checklist items genuinely unanswered); publish that with `finish --partial`.
  A `complete` run needs every claim, section and diagram `verified`.
- `evidence`: ID, kind, human-readable locator and note; local records also have
  `path`, SHA-256 and optional line range. REA records also have actual `evidence_id`.
- `claims`: ID, plain-text assertion, authority, freshness and evidence IDs.
- `sections`: ID, title, plain-text body paragraphs, claim IDs, `detail` boolean
  and freshness. Optional table contains `columns` and same-width `rows`.
- `diagrams`: ID, title, kind, freshness, nodes and directed edges. Both nodes
  and edges cite claims.

Use stable IDs like `storage-ownership`, not positional IDs that change whenever
sections are reordered. Keep facts in claims; make the prose explain their
relationship. Every factual assertion in a section must be supported by one of
its cited claims. The helper cannot semantically verify this relationship.

All user/target strings are **plain text** (with safe inline `` `code` `` and
`**bold**` formatting rendered in HTML after strict escaping). Raw HTML and
script tags are always escaped. Generated Markdown and HTML contain the same
findings, tables, evidence and diagrams.

## Authoring cookbook

Prefer the structured authoring helpers (`upsert-claim`, `upsert-section`,
`upsert-diagram`, `set-meta` or MCP `aa_upsert_*` / `aa_set_run_meta`), which
validate references on write and automatically prune replaced `*-unknown` scaffold
claims and clear the scaffold limitation once all scaffold sections are replaced.
You can also edit the working `report.json` directly. Get evidence records from
`cite ... --append` rather than computing hashes by hand.

Evidence (local file, hashed; the CLI produces this record):

```json
{"id": "ev-src-sync-py-L40-72", "kind": "source", "locator": "src/sync.py:40-72",
 "note": "Retry loop and backoff", "path": "src/sync.py", "sha256": "<64 hex chars>",
 "line_start": 40, "line_end": 72}
```

REA evidence additionally needs a durable saved result and the real Evidence ID:
`{"id": "ev-rea-main", "kind": "rea", "locator": "analyze_javascript_application",
"note": "Provider and profile used", "path": "evidence/app-analysis.json",
"sha256": "...", "evidence_id": "<actual id from the saved result>"}`.

Claim. One fact each; `authority` is `observation`, `derived`, `inference`,
`contradiction` or `unknown`; only `unknown` may have no evidence:

```json
{"id": "retry-backoff", "text": "Failed pushes retry up to five times with exponential backoff.",
 "authority": "observation", "freshness": "verified", "evidence": ["ev-src-sync-py-L40-72"]}
```

Section. Prose explains how the cited claims relate; `detail: true` hides it from
the owner-level reading path; the optional table rows must match `columns` in width:

```json
{"id": "sync-behavior", "title": "How offline sync recovers", "detail": false, "freshness": "verified",
 "body": ["Pushes queue locally and retry with backoff, so a dropped connection delays but does not lose edits."],
 "claims": ["retry-backoff"],
 "table": {"columns": ["Step", "Owner"], "rows": [["Queue edit", "client store"], ["Retry push", "sync worker"]]}}
```

Component diagram (at most 12 nodes; every node and edge cites claims):

```json
{"id": "sync-components", "title": "Sync components", "kind": "component", "freshness": "verified",
 "nodes": [{"id": "client", "label": "Client store", "claims": ["retry-backoff"]},
           {"id": "worker", "label": "Sync worker", "claims": ["retry-backoff"]}],
 "edges": [{"from": "client", "to": "worker", "label": "Hand over queued edits", "claims": ["retry-backoff"]}]}
```

Sequence diagram: same fields with `"kind": "sequence"`. Node order sets the
participants left to right and edge order sets the message order, so list edges
chronologically, including the return messages.

### Fixing validation and finish messages

| Message contains | Cause and fix |
| --- | --- |
| `missing reference X` | A claim, section or diagram cites an ID that does not exist. Add the record or correct the ID. |
| `duplicate IDs` / `duplicate node IDs` | IDs must be unique within their group. Rename one. |
| `factual/inferred claims require evidence` | Add evidence IDs, or change the authority to `unknown` and explain the boundary. |
| `local evidence requires sha256` | Create the record with `cite`. |
| `fingerprint changed` / `file unavailable` | The file changed or moved after citing. Re-inspect, re-cite, and mark dependent claims `stale` if not rechecked. |
| `line range outside file` / `reversed line range` | Correct `line_start`/`line_end`; use `cite --lines A-B`. |
| `REA citation requires durable file and actual Evidence ID` | Save the REA result to a file and cite its real ID. |
| `complete run contains unchecked ...` | A complete run needs every claim, section and diagram `verified`. Verify them, or set `run.status` to `partial` with limitations. |
| `verified presentation contains stale/unverified claims` | A verified section or diagram cites a non-verified claim. Re-verify the claim or lower the presentation's freshness. |
| `explain section findings or gaps with claims` | Every section cites at least one claim; use an `unknown` claim to state a gap. |
| `every node/relationship needs claims` / `dangling edge` | Cite claims on each node and edge; edge endpoints must be node IDs. |
| `table row width mismatch` | Make each row as wide as `columns`. |
| `incomplete coverage requires explicit limitations` | Add what was not inspected to `run.limitations`. |
| `target changed during collection` | Files changed between start and finish. Recheck affected findings or finish `--partial`. |
| `still an uninvestigated scaffold` | Remove the scaffold limitation only after authoring real findings. |
| `Investigation is unfinished: unresolved checklist items` | Answer each named item with `checklist`, or use `finish --partial`. |
| `Every checklist item is resolved, but run.status ... is 'partial'` | If you finished and only the scope is limited, set `run.status` to `complete` and `run.coverage` to `partial`. Keep `partial` only for unfinished work, published with `finish --partial`. |
| `explanatory note` / `Deep investigation notes` | Give each non-unresolved item a concrete note (40+ characters for deep-only items). |

Warnings such as `claim not used in a section or diagram` do not block publication;
either use the claim or delete it.

## Diagrams

Supported types: `context`, `component`, `sequence`, `data`, `state`.
The first, second, fourth and fifth use a layered directed relationship map; sequence
uses ordered messages between lifelines. Each output includes an SVG, the
editable diagram JSON, and (when `--emit mermaid` is enabled) `.mmd` Mermaid sources.

Keep each view focused, with at most 12 nodes; use several diagrams for larger
systems. Edges have numbered labels tied to a readable relationship list so long
labels do not collide with paths. Node order and topological rank control placement;
edge order controls sequence chronology. Back edges and self-loops are preserved.
Mark inferred or stale relationships through the supporting claims and appropriate
diagram freshness.

Use a context view for external boundaries, a component view for responsibilities,
a sequence for a concrete feature, a data view for ownership/transfers, and a
state view only when the transitions are established. Do not invent a synchronous
call when the implementation uses an event.

An optional external diagram renderer can be used when explicitly requested, but
the default report is self-contained and has no dependency on another skill,
network fonts, CDNs or Mermaid services.

## Visual and semantic acceptance

- Read the opening briefing without opening technical details: does it explain
  the actual product and significant changes?
- Follow a feature from prose to diagram to claim to source evidence.
- Verify every important boundary/relationship against its cited evidence.
- Open desktop and narrow layouts; check text, table scrolling and diagrams.
- Search a distinctive term; clear search and follow a deep citation.
- Switch themes and check readable contrast.
- Inspect print view: technical details and evidence must be present.
- Confirm no unexpected network requests and no script execution from inspected
  text. Local file citations may be blocked by some browsers' hosting policies;
  the exact locator and hash remain readable.

Structural validation is necessary, not proof of a professional or correct report.
