# Architect Anything MCP server

`architect-anything-mcp` lets an MCP-capable agent drive an investigation through
tools. It speaks MCP over stdio, uses only the Python standard library, and wraps
the same functions as the CLI, so results and error codes are identical.

Registration is opt-in. Installing the skill or package never edits an agent's
MCP configuration. The server does not analyze a target for you, run anything
found in a target, or install REA or its engines.

## How it composes with REA

| Server | Role |
| --- | --- |
| REA MCP (or CLI) | Gathers evidence from binaries, packages and runtimes |
| Architect Anything MCP | Opens the investigation, tracks the checklist, validates and publishes the report |
| Normal repo tools | Read and search source for source investigations |

## Registration

Use the installed command, or the portable script when only the skill folder
exists. Replace the placeholder paths.

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

| Tool | Equivalent CLI | Purpose |
| --- | --- | --- |
| `aa_start` | `start` | Prepare a catch-up or focused workspace; accepts `depth`, `focus`, `kind`, `output`, `exclude` |
| `aa_status` | `status` | Read the checklist, depth and report state |
| `aa_cite` | `cite` | Build a hashed evidence record for a local file; `append` adds it to the working report |
| `aa_checklist` | `checklist` | Record one checklist answer with its note |
| `aa_finish` | `finish` | Check freshness and publish the authored report |
| `aa_validate` | `validate` | Validate a report model and optionally its cited files |
| `aa_render` | `render` | Publish an authored model without a workspace |
| `aa_inventory` | `inventory` | Fingerprint local files into a new file |
| `aa_compare` | `diff` / `compare` | Compare inventories or reports |
| `aa_schema` | `schema` | Report, investigation or command contracts |
| `aa_rea_status` | `rea status` | Probe an existing REA CLI |
| `aa_rea_run` | `rea run` | Run one REA CLI operation; output goes to a new path with a receipt |

Every tool returns the CLI envelope (`ok`, `command`, `result` or `error`) as
text and as `structuredContent`. Failures set `isError` and carry the stable
codes `invalid_input`, `invalid_arguments`, `validation_failed`,
`operation_failed` or `rea_unavailable_or_failed`. A failed call does not stop the
server.

## Workflow

1. `aa_start` with the target and, for a focused explanation, `focus`. Choose
   `depth` from the request.
2. Investigate with repository tools or REA. Record evidence with `aa_cite`
   (`append: true`), author claims and sections in the working `report.json`, and
   record each answer with `aa_checklist`. `aa_status` shows what remains.
3. `aa_validate` with `check_files`, then `aa_finish` (use `partial` only with
   honest limitations).

A scaffold is not a finding: `aa_finish` refuses an uninvestigated report.
