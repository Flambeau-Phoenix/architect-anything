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

All user/target strings are **plain text**. HTML and Markdown metacharacters are
escaped. Do not insert HTML, Mermaid or Markdown syntax into body text and expect
it to execute/render. Generated Markdown and HTML contain the same findings,
tables, evidence and diagrams.

## Diagrams

Supported types: `context`, `component`, `sequence`, `data`, `state`.
The first, second, fourth and fifth use a directed relationship map; sequence
uses ordered messages between lifelines. Each output includes an SVG and the
editable diagram JSON.

Keep each view focused, with at most 12 nodes; use several diagrams for larger
systems. Edges have numbered labels tied to a readable relationship list so long
labels do not collide with paths. Node order controls vertical placement or
sequence participants; edge order controls sequence chronology. Back edges and
self-loops are preserved. Mark inferred or stale relationships through the
supporting claims and appropriate diagram freshness.

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
