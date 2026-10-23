# Changelog — Architect Anything

## v1.2.0 (Second Edition) — 2026-10-23

### Added
- **Four New Specialized Investigation Lenses (`--lens`)**:
  - `onboarding`: Orients new maintainers with a 60-second mental model, entry points & boot sequence, "where to change X" codemap, local dev/test loop, and invariant landmines.
  - `delta`: Audits breaking contract changes, data/persistence shifts, dependency boundary changes, and doc-vs-code drift.
  - `boundaries`: Maps external entry points, trust/isolation boundaries, untrusted input validation, outbound calls/IPC, and secrets handling.
  - `operations`: Documents production startup/shutdown draining, configuration precedence, state concurrency, timeouts/retries/backpressure, observability, and crash recovery.
  - *(All four new lenses work in both `catch-up` and `focus` modes across `overview`, `standard`, and `deep` depths alongside the existing `mechanism` lens).*
- **Optional Companion Report Packs (`--emit`)**:
  - Pass `--emit <pack>` (repeatable, comma-separated, or `all`) to `start`, `finish`, or `render` (and MCP `aa_start`, `aa_finish`, `aa_render`):
    - `mermaid`: Exports `diagrams/<id>.mmd` files and embeds fenced `mermaid` blocks directly in `report.md`.
    - `adr`: Generates `packs/adr-summary.md` synthesizing architectural decisions, tradeoffs, and evidence locators.
    - `onboarding`: Generates `packs/onboarding-codemap.md` indexing sections, contract tables, and cited files.
    - `delta`: Generates `packs/architecture-delta.md` with automated claim-level diffing against `previous_report` when available.
    - `llms-txt`: Generates `packs/llms-architecture.txt` as a compact, token-efficient summary with `path:line` citations for coding agents.
- **Structured Report Authoring Tools (MCP & CLI)**:
  - Added MCP tools `aa_upsert_claim`, `aa_upsert_section`, `aa_upsert_diagram`, and `aa_set_run_meta` (and matching CLI subcommands `upsert-claim`, `upsert-section`, `upsert-diagram`, `set-meta`).
  - Eliminates manual `report.json` file editing during MCP runs, validates references on write, and automatically prunes replaced `*-unknown` scaffold claims and clears `SCAFFOLD_LIMITATION` once all scaffold sections are authored.
- **First-Class MCP Primitives (`resources`, `prompts`, `annotations`)**:
  - Added MCP tool `annotations` (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) so MCP hosts can auto-approve read-only calls (`aa_status`, `aa_validate`, `aa_compare`, `aa_schema`, `aa_rea_status`).
  - Added MCP `resources/list`, `resources/templates/list`, and `resources/read` (`aa://schema/report`, `aa://schema/investigation`, `aa://guide/lenses-and-packs`, `aa://workspace/{workspace}/status`, `aa://workspace/{workspace}/report`).
  - Added MCP `prompts/list` and `prompts/get` (`catch-up`, `explain-feature`, `extract-mechanism`).
- **Python Packaging (`pyproject.toml`)**:
  - Added `pyproject.toml` so `pip install .` cleanly installs the `architect-anything` and `architect-anything-mcp` entry points.

### Improved & Fixed
- **MCP Direct Dispatch & Protocol Hardening**:
  - Replaced `argv_for` → `argparse` string round-tripping in `aa_mcp.py` with direct domain function dispatch and full JSON Schema input validation via `schema_errors()`.
  - Added JSON-RPC 2.0 batch request support and preserved request `id` on `-32603` internal error responses.
- **2D Layered SVG Diagrams**:
  - Upgraded `diagram_svg()` in `aa_render.py` to compute topological rank for multi-node `context`, `component`, `data`, and `state` diagrams, rendering multi-column layouts with smooth cubic Bézier curves instead of a single tall vertical column.
- **HTML Typography & Interactive Claim Previews**:
  - Added XSS-safe inline `` `code` `` and `**bold**` rendering in `aa_render.py` (`rich_html()`) while preserving strict HTML escaping and the SHA-256 Content-Security-Policy.
  - Added floating claim preview tooltips in `report.js` and `report.css` when hovering or focusing claim links.
- **Stale Publish Lock Recovery**:
  - `publish()` in `aa_render.py` now checks whether an existing `.architect-publish.lock` belongs to a dead PID (handling Windows `SystemError`/`OSError` edge cases) or has exceeded the staleness timeout and recovers automatically.
