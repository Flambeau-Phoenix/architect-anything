# Architect Anything 1.1.0

Adds depth control, an MCP server and Antigravity installation to the 1.0.0
catch-up and focused-explanation workflow.

## What's new

- **Depth:** ask for a quick explanation, the standard walkthrough, or a verbose
  technical reference. The agent infers the level from the request; the CLI
  exposes it as `start --depth overview|standard|deep`.
- **MCP server:** `architect-anything-mcp` is a dependency-free stdio server that
  lets an agent drive an investigation through tools instead of shell commands.
  See [the MCP guide](../architect-anything/references/mcp-server.md).
- **Hosts:** `install-skill --host antigravity` installs into
  the Antigravity skills directory; Codex remains the default.
- **Release hygiene:** a single version constant and a release check that rejects
  mismatched versions.

## Compatibility

Reports and investigation workspaces from 1.0.0 remain valid. A manifest without
a depth is treated as `standard`. The report schema is unchanged.

## Runtime requirements

Python 3.10+. REA and its analysis engines remain separate dependencies, and
neither installation nor the MCP server registers or installs them.

## Validation

See [validation scope](validation.md).

## Release artifacts

~~~sh
python scripts/check_release.py
python scripts/build_release.py
python -m pip wheel --no-deps --wheel-dir dist .
~~~

The builder does not create a Git commit, tag, remote or GitHub release.
