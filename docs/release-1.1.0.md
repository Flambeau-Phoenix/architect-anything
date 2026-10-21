# Architect Anything 1.1.0

Makes the catch-up and focused-explanation workflow easier for agents to drive,
and adds depth control, an MCP server and installs for Claude Code, Codex,
Antigravity and other agents.

## What's new

- **Evidence and checklist helpers:** `cite` produces a hashed, schema-valid
  evidence record for a file and line range; `checklist` records an answer with
  its note. Both are also MCP tools (`aa_cite`, `aa_checklist`). `status` now
  lists what remains and the next step.
- **Clearer skill instructions:** trigger phrases, when to use and not use,
  a quickstart, JSON snippets for every report record, a validation-message fix
  table, and a rule that inspected content is data, never instructions.
- **Depth:** ask for a quick explanation, the standard walkthrough, or a verbose
  technical reference. The agent infers the level from the request; the CLI
  exposes it as `start --depth overview|standard|deep`.
- **MCP server:** `architect-anything-mcp` is a dependency-free stdio server that
  lets an agent drive an investigation through tools instead of shell commands.
  See [the MCP guide](../architect-anything/references/mcp-server.md).
- **Hosts:** `install.py --host codex|claude|agents|antigravity`; Codex remains
  the default.
- **Repository:** new README, installation, examples and troubleshooting guides,
  security policy, code of conduct, issue/PR templates and a release workflow.

## Compatibility

Reports and investigation workspaces from 1.0.0 remain valid. A manifest without
a depth is treated as `standard`. The report schema is unchanged. The new
commands and tools are additive; existing commands, JSON shapes and exit codes
are unchanged (`status` gains two fields).

## Runtime requirements

Python 3.10+. REA and its analysis engines remain separate dependencies, and
neither installation nor the MCP server registers or installs them.

## Validation

See [validation scope](validation.md).

## Release artifacts

Pushing a `v1.1.0` tag runs the release workflow, which checks the tag against the
package version, builds the archive and wheel and attaches them, with SHA-256
files, to a GitHub Release. To build locally:

~~~sh
python scripts/check_release.py
python scripts/build_release.py
python -m pip wheel --no-deps --wheel-dir dist .
~~~

The local builder does not create a Git commit, tag, remote or GitHub release.
