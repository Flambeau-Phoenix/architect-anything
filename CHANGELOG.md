# Changelog

## 1.1.0

- Depth control: `start --depth overview|standard|deep` selects an owner-level
  answer, the full walkthrough, or a verbose technical reference. The depth is
  recorded in the investigation manifest and drives its checklist; deep runs
  require concrete notes. Manifests from 1.0.0 load as `standard`.
- Architect Anything MCP server (`architect-anything-mcp`, standard library only,
  stdio) exposing start, status, finish, validate, render, inventory, compare,
  schema and the optional REA bridge as tools with the CLI's stable error codes.
- `install-skill --host codex|antigravity` and `install.py --host` choose the
  personal skills directory; `--destination` still overrides.
- One version constant shared by the CLI, reports, package and skill; the release
  check now fails when SKILL.md, the package or the changelog disagree.
- Behavioral tests for depth, the MCP protocol/error paths and installer hosts.

## 1.0.0 — prepared for first release

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

No publication date is asserted while the first release remains unpublished.
