# Architect Anything MCP server

`architect-anything-mcp` lets an MCP-capable agent drive an entire architecture
investigation through structured tools, resources, and prompts. It speaks MCP over
stdio (JSON-RPC 2.0, including batch requests), uses only the Python standard
library, and executes the same domain functions as the CLI so results and error
codes are identical.

Registration is opt-in. Installing the skill or package never edits an agent's
MCP configuration. The server does not analyze a target for you, run anything
found in a target, or install REA or its engines.

## How it composes with REA

| Server | Role |
| --- | --- |
| REA MCP (or CLI) | Gathers evidence from binaries, packages and runtimes |
| Architect Anything MCP | Opens the investigation, records citations, authors claims/sections/diagrams, tracks the checklist, validates and publishes the report |
| Normal repo tools | Read and search source for source investigations |

## Registration

Use the installed command (`pip install .` provides `architect-anything-mcp`), or
the portable script when only the skill folder exists. Replace the placeholder paths.

~~~json
{
  "mcpServers": {
    "architect-anything": {
      "command": "architect-anything-mcp"
    }
  }
}
~~~

Portable form:

~~~json
{
  "mcpServers": {
    "architect-anything": {
      "command": "python",
      "args": ["/path/to/skills/architect-anything/scripts/aa_mcp.py"]
    }
  }
}
~~~

Claude Code:

~~~sh
claude mcp add architect-anything -- architect-anything-mcp
# portable: claude mcp add architect-anything -- python /path/to/skills/architect-anything/scripts/aa_mcp.py
~~~

Codex `config.toml`:

~~~toml
[mcp_servers.architect-anything]
command = "architect-anything-mcp"
~~~

Restart or reconnect the agent, then confirm that the `aa_*` tools are listed.

## Tools

Every tool advertises MCP `annotations` (`readOnlyHint`, `destructiveHint`,
`idempotentHint`, `openWorldHint`) so MCP hosts can auto-approve read-only queries.

| Tool | Equivalent CLI | Read-Only | Purpose |
| --- | --- | --- | --- |
| `aa_start` | `start` | No | Prepare a catch-up or focused workspace; accepts `depth`, `focus`, `lens` (`mechanism`, `onboarding`, `delta`, `boundaries`, `operations`), `emit`, `kind`, `output`, `exclude` |
| `aa_status` | `status` | Yes | Read the checklist, depth, lens, emit list, and report state |
| `aa_cite` | `cite` | No | Build a hashed evidence record for a local file; `append` adds it to the working report |
| `aa_upsert_claim` | `upsert-claim` | No | Add or update a claim (`id`, `text`, `authority`, `freshness`, `evidence[]`) with immediate reference checking |
| `aa_upsert_section` | `upsert-section` | No | Add or update a section (`id`, `title`, `body[]`, `claims[]`, `detail`, `freshness`, `table`) and auto-prune replaced scaffold claims |
| `aa_upsert_diagram` | `upsert-diagram` | No | Add or update a diagram (`id`, `title`, `kind`, `nodes[]`, `edges[]`, `freshness`) with immediate validation |
| `aa_set_run_meta` | `set-meta` | No | Update report `title`, `subtitle`, `target_name`, `run_status`, `coverage`, `limitations`, `changes`, or `tools` |
| `aa_checklist` | `checklist` | No | Record one checklist answer with its note |
| `aa_finish` | `finish` | No | Check freshness and publish the authored report and optional `emit` companion packs |
| `aa_validate` | `validate` | Yes | Validate a report model and optionally its cited files |
| `aa_render` | `render` | No | Publish an authored model and optional `emit` packs without a workspace |
| `aa_inventory` | `inventory` | No | Fingerprint local files into a new file |
| `aa_compare` | `diff` / `compare` | Yes | Compare inventories or reports |
| `aa_schema` | `schema` | Yes | Report, investigation or command contracts |
| `aa_rea_status` | `rea status` | Yes | Probe an existing REA CLI |
| `aa_rea_run` | `rea run` | No | Run one REA CLI operation; output goes to a new path with a receipt |

Every tool returns the CLI envelope (`ok`, `command`, `result` or `error`) as
text and as `structuredContent`. Failures set `isError` and carry the stable
codes `invalid_input`, `invalid_arguments`, `validation_failed`,
`operation_failed` or `rea_unavailable_or_failed`. A failed call does not stop the
server.

## Resources & Prompts

- **Resources (`resources/list`, `resources/templates/list`, `resources/read`)**:
  - `aa://schema/report`: Report JSON Schema v1.
  - `aa://schema/investigation`: Investigation manifest JSON Schema v1.
  - `aa://guide/lenses-and-packs`: Markdown reference for lenses and `--emit` packs.
  - `aa://workspace/{workspace}/status`: Live investigation status and checklist.
  - `aa://workspace/{workspace}/report`: Current working `report.json`.
- **Prompts (`prompts/list`, `prompts/get`)**:
  - `catch-up`: Guided catch-up investigation workflow (`target`, `depth`, `lens`).
  - `explain-feature`: Guided feature/subsystem trace (`target`, `focus`, `depth`).
  - `extract-mechanism`: Guided portable mechanism extraction (`target`, `focus`).

## Workflow

1. `aa_start` with the target and, for a focused explanation, `focus`. Choose
   `depth`, optional `lens`, and optional `emit` packs from the request.
2. Investigate with repository tools or REA. Record evidence with `aa_cite`
   (`append: true`), author claims, sections, diagrams, and run metadata with
   `aa_upsert_claim`, `aa_upsert_section`, `aa_upsert_diagram`, and `aa_set_run_meta`,
   and record each answer with `aa_checklist`. `aa_status` shows what remains.
3. `aa_validate` with `check_files`, then `aa_finish` (use `partial` only with
   honest limitations).

A scaffold is not a finding: `aa_finish` refuses an uninvestigated report.
