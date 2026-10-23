# Lenses and Companion Report Packs

Architect Anything supports **specialized investigation lenses** (`--lens`) that shape *what* questions the investigation asks, and **optional companion report packs** (`--emit`) that generate specialized supplementary files alongside the default HTML and Markdown reports.

---

## 1. Investigation Lenses (`--lens`)

Pass `--lens <name>` to `start` (or `aa_start` in MCP). Each lens provides a tailored checklist and default section layout suited to the user's goal, and works across all three depths (`overview`, `standard`, `deep`).

| Lens | Mode support | When to use | Checklist IDs (`standard`) |
| --- | --- | --- | --- |
| `mechanism` | `focus` only (requires `--focus`) | Extract a portable, product-neutral formula of how a mechanism works without cloning the product | `answer`, `trace`, `contract`, `essentials`, `assumptions`, `choices`, `limits` |
| `onboarding` | `catch-up` or `focus` | Orient a new engineer or maintainer with a 60-second mental model, entry points, edit map, dev loop, and invariant landmines | `briefing`, `entrypoints`, `codemap`, `devloop`, `invariants`, `limits` |
| `delta` | `catch-up` or `focus` | Audit architectural drift, breaking contract changes, data migrations, dependency shifts, and doc-vs-code discrepancies | `summary`, `contracts`, `data`, `dependencies`, `drift`, `risks` |
| `boundaries` | `catch-up` or `focus` | Map external entry points, trust/isolation boundaries, input validation, outbound calls/IPC, secrets handling, and host assumptions | `surface`, `trust`, `validation`, `egress`, `secrets`, `assumptions`, `limits` |
| `operations` | `catch-up` or `focus` | Document production lifecycle, startup/shutdown draining, configuration precedence, state concurrency, resilience/retries, observability, and recovery | `lifecycle`, `config`, `state`, `resilience`, `observability`, `recovery`, `limits` |

### Choosing a lens

- Default `catch-up` (no lens) is best when the owner wants a holistic briefing and technical reference of the whole project.
- Default `focus` (no lens) is best when answering a specific "how does feature X work in this codebase?" question.
- Use `--lens mechanism` when the user says *"how do they do X so I can build my own"*; see [Mechanism lens](mechanism-lens.md).
- Use `--lens onboarding` when the user says *"onboard me"*, *"where do I start contributing"*, or *"build a maintainer guide"*.
- Use `--lens delta` when the user says *"what drifted from the docs"*, *"audit breaking architectural changes"*, or *"compare this release"*.
- Use `--lens boundaries` when the user says *"map the trust boundaries"*, *"what external services or IPC does this touch"*, or *"what is the input surface"*.
- Use `--lens operations` when the user says *"write an operational runbook"*, *"how does this fail and recover"*, or *"how is it configured and deployed"*.

---

## 2. Optional Companion Report Packs (`--emit`)

Every published snapshot always produces `report.html`, `report.md`, `report.json`, `evidence.json`, `manifest.json`, and `diagrams/*.svg` + `diagrams/*.json`.

When you want additional portable outputs, pass `--emit <pack>` (repeatable, comma-separated, or `--emit all`) to `start`, `finish`, or `render` (or `emit: [...]` in `aa_start`, `aa_finish`, `aa_render`).

| Pack | Generated files inside snapshot | Purpose |
| --- | --- | --- |
| `mermaid` | `diagrams/<id>.mmd` + inline fenced `mermaid` blocks in `report.md` | Native Mermaid diagrams (`flowchart LR`, `sequenceDiagram`, `stateDiagram-v2`) for GitHub/GitLab Markdown rendering and diagram editors |
| `adr` | `packs/adr-summary.md` | Architecture Decision Record log synthesized from `derived`, `inference`, and `contradiction` claims with supporting evidence locators |
| `onboarding` | `packs/onboarding-codemap.md` | Standalone maintainer onboarding guide and codemap indexing every section, table, and cited source/artifact location |
| `delta` | `packs/architecture-delta.md` | Standalone architectural change & claim-diff report (automatically compares against `previous_report` when available) |
| `llms-txt` | `packs/llms-architecture.txt` | Compact, token-efficient architecture context file with verified claims and `path:line` citations for coding agents |

All emitted files are hashed into `manifest.json` and returned under the `emitted` key in the `finish` / `render` response.
