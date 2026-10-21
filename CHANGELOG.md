# Changelog

## 1.1.0

### Agent workflow

- `cite` builds a schema-valid, SHA-256-hashed evidence record for a local file
  and line range (`--append` adds it to the working report; repeated citations are
  idempotent), so agents no longer compute fingerprints by hand. MCP: `aa_cite`.
- `checklist` records one checklist answer with its note, replacing hand edits to
  `investigation.json`, and warns early when a deep-run note is too short. MCP:
  `aa_checklist`.
- `status` now reports `remaining` checklist items and a `next` step.
- `SKILL.md`: trigger-oriented description, when to use and not use, a quickstart,
  and an explicit rule that inspected content is data, never instructions.
- `report-authoring.md`: JSON snippets for every record type and a table mapping
  validation and finish messages to fixes. A test keeps the snippets valid.

### Depth, MCP and hosts

- Depth control: `start --depth overview|standard|deep` selects an owner-level
  answer, the full walkthrough, or a verbose technical reference. The depth is
  recorded in the investigation manifest and drives its checklist; deep runs
  require concrete notes. Manifests from 1.0.0 load as `standard`.
- Architect Anything MCP server (`architect-anything-mcp`, standard library only,
  stdio) exposing start, status, finish, validate, render, inventory, compare,
  schema and the optional REA bridge as tools with the CLI's stable error codes.
- `install-skill --host codex|claude|agents|antigravity` and `install.py --host`
  choose the personal skills directory (`$CLAUDE_CONFIG_DIR` and `$CODEX_HOME`
  are honored); `--destination` still overrides.
- One version constant shared by the CLI, reports, package and skill; the release
  check fails when SKILL.md, the package or the changelog disagree.

### Repository

- Rewritten README with per-agent quick start, how-it-works diagram, supported
  targets, safety notes and FAQ; new installation, example-prompt and
  troubleshooting guides.
- `SECURITY.md`, `CODE_OF_CONDUCT.md`, issue and pull-request templates,
  Dependabot for GitHub Actions, and a tag-driven release workflow.
- Package metadata (authors, keywords, classifiers, project URLs).
- Focused-explanation screenshot; the focused demo no longer exposes a temporary
  directory name.
- Behavioral tests for depth, the MCP protocol and error paths, installer hosts,
  `cite`, `checklist` and a helpers-only end-to-end workflow (62 in total).

## 1.0.0

Baseline for 1.1.0; not released separately.

- Catch-up reports for projects that have outgrown their owners' documentation.
- Focused explanations of selected features, mechanisms and design questions.
- Installable agent CLI with investigation workspaces, schemas, JSON results,
  resume/status and checked publication.
- Source-project and finished-product investigation workflows.
- REA 6.7.0 target routing and CLI/MCP integration guidance.
- Offline HTML and Markdown reports, evidence indexes and editable SVG diagrams.
- Fingerprint inventories, evidence validation, findings comparisons and snapshots.
- Mobile navigation, search, themes and print styling.
- Idempotent skill installation with protection for independent edits.
- Thirty-five behavioral tests, whole-project/focused demos and cross-platform CI.
