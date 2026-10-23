
# Changelog

## [1.2.0] 

### New Features

* **4 New Specialized Investigation Lenses (`--lens`)**:
* **`onboarding`**: 60-second mental model, entry points & boot sequence, "where to change X" codemap, local dev/test loop, and invariant landmines.
* **`delta`**: Breaking contract changes, data/persistence shifts, dependency boundary changes, and doc-vs-code drift.
* **`boundaries`**: External entry points, trust/isolation boundaries, untrusted input validation, outbound calls/IPC, and secrets handling.
* **`operations`**: Startup/shutdown draining, configuration precedence, state concurrency, timeouts/retries/backpressure, observability, and crash recovery.
* *All 4 new lenses work in both `catch-up` and `focus` modes across `overview`, `standard`, and `deep` depths alongside `mechanism`.*


* **Optional Companion Report Packs (`--emit`)**:
* Pass `--emit <pack>` (repeatable, comma-separated, or `all`) to `start`, `finish`, or `render` (and MCP tools `aa_start`, `aa_finish`, `aa_render`):
* **`mermaid`**: Exports `diagrams/<id>.mmd` and embeds fenced `mermaid` blocks in `report.md`.
* **`adr`**: Generates `packs/adr-summary.md` synthesizing architectural decisions, tradeoffs, and evidence locators.
* **`onboarding`**: Generates `packs/onboarding-codemap.md` indexing sections, contract tables, and cited files.
* **`delta`**: Generates `packs/architecture-delta.md` with automated claim-level diffing against `previous_report`.
* **`llms-txt`**: Generates `packs/llms-architecture.txt` as a compact, token-efficient summary with `path:line` citations for coding agents.




* **Structured Report Authoring Tools (MCP & CLI)**:
* Added MCP tools `aa_upsert_claim`, `aa_upsert_section`, `aa_upsert_diagram`, and `aa_set_run_meta` (alongside CLI equivalents `upsert-claim`, `upsert-section`, `upsert-diagram`, and `set-meta`).
* Eliminates manual `report.json` file editing during MCP runs, validates references on write, automatically prunes replaced `*-unknown` scaffold claims, and clears `SCAFFOLD_LIMITATION` once all scaffold sections are authored.


* **First-Class MCP Primitives (`annotations`, `resources`, `prompts`)**:
* **Tool Annotations**: Every tool advertises `readOnlyHint`, `destructiveHint`, `idempotentHint`, and `openWorldHint` so MCP clients can auto-approve read-only queries (`aa_status`, `aa_validate`, `aa_compare`, `aa_schema`, `aa_rea_status`).
* **MCP Resources**: `aa://schema/report`, `aa://schema/investigation`, `aa://guide/lenses-and-packs`, `aa://workspace/{workspace}/status`, and `aa://workspace/{workspace}/report`.
* **MCP Prompts**: `catch-up`, `explain-feature`, and `extract-mechanism`.


* **Standard Python Packaging**:
* `pip install .` now cleanly installs both `architect-anything` and `architect-anything-mcp` console scripts.



### Polish & Fixes

* **Direct MCP Domain Dispatch & Protocol Hardening**: Replaced string-flag round-tripping (`argv_for` → `argparse`) in the MCP server with direct Python function dispatch and JSON Schema validation via `schema_errors()`. Added JSON-RPC 2.0 batch support and preserved request `id` on `-32603` internal error responses.
* **2D Layered SVG Diagrams**: Upgraded diagram rendering logic to compute topological rank for multi-node `context`, `component`, `data`, and `state` diagrams, rendering multi-column layouts with smooth cubic Bézier curves.
* **Typography & Interactive Claim Previews**: Added XSS-safe inline ``code`` and `**bold**` rendering alongside floating claim preview tooltips on hover/focus.
* **Stale Lock Recovery**: Publication workflows now automatically recover from leftover `.architect-publish.lock` files when the holder PID is dead or the lock is stale.

---

## [1.1.0]

### Agent Workflow

* **Mechanism Lens** (`start --focus ... --lens mechanism`, MCP `lens`): Extract the portable *formula* behind something in product-neutral terms so you can build your own version. Swaps the focused checklist for core idea, trace, contract, essentials versus incidental, host assumptions, choices left to the builder, and limits.
* **Citations (`cite` / `aa_cite`)**: Builds a schema-valid, SHA-256-hashed evidence record for a local file and line range (`--append` adds it to the working report; repeated citations are idempotent).
* **Checklist Management (`checklist` / `aa_checklist`)**: Records one checklist answer with its note, replacing hand edits to `investigation.json`, and warns early when a deep-run note is too short.
* **Status Updates**: Now reports `remaining` checklist items and a clear `next` step.
* **Finish Refusals**: Explicitly name unresolved checklist items by ID, clarifying how `status` (is work finished?) differs from `coverage` (how much was inspected).
* **Documentation & Skills**: Updated `SKILL.md` with trigger-oriented descriptions, quickstarts, and rules treating inspected content strictly as data, never instructions. Added complete JSON snippets and error-mapping tables to `report-authoring.md`.

### Depth, MCP, and Hosts

* **Depth Control**: `start --depth overview|standard|deep` selects owner-level answers, full walkthroughs, or verbose technical references. Deep runs require concrete notes. Manifests from 1.0.0 load as `standard`.
* **Architect Anything MCP Server**: Standard library only, stdio-based server exposing start, status, finish, validate, render, inventory, compare, schema, and optional REA bridge tools.
* **Installer Enhancements**: `install-skill --host` and `install.py --host` choose personal configuration directories while respecting environment variables (`$CLAUDE_CONFIG_DIR`, `$CODEX_HOME`). Installer upgrades now store backups in `.architect-anything-backups/` beside the skills directory rather than inside it.
* **Version Alignment**: Enforced a single version constant shared by CLI, reports, package, and skills; release checks fail if discrepancies are detected.

### Repository

* **Documentation Overhaul**: Rewritten README with per-agent quick start, architecture diagram, supported targets, safety notes, FAQ, and dedicated installation/troubleshooting guides.
* **Governance & Standards**: Added `SECURITY.md`, `CODE_OF_CONDUCT.md`, issue/PR templates, Dependabot for GitHub Actions, and a tag-driven release workflow alongside rich package metadata.
* **Testing**: Expanded behavioral test suite covering depth, MCP protocol, error paths, installer hosts, citations, checklists, and helpers-only end-to-end workflows (83 total tests).

---

## [1.0.0] — Baseline

* Baseline release establishing core investigation workflows:
* Catch-up reports for projects that have outgrown owner documentation.
* Focused explanations of selected features, mechanisms, and design questions.
* Installable agent CLI with investigation workspaces, schemas, JSON results, resume/status, and checked publication.
* Source-project and finished-product workflows with REA target routing and CLI/MCP integration guidance.
* Offline HTML and Markdown reports, evidence indexes, and editable SVG diagrams.
* Fingerprint inventories, evidence validation, findings comparisons, snapshots, mobile navigation, search, themes, and print styling.
* Idempotent skill installation with protection for independent edits.