# Installation

Architect Anything is a folder of instructions and scripts (`architect-anything/`)
that an AI coding agent loads as a **skill**. It needs Python 3.10 or newer and
nothing else; the helpers use only the standard library.

Three pieces are optional and independent of each other:

| Piece | What it is | Needed for |
| --- | --- | --- |
| The skill folder | `SKILL.md`, references, scripts, report assets | Everything |
| The `architect-anything` command | A pip-installed wrapper around the same scripts | Convenience; the skill also runs without it |
| The MCP server | `architect-anything-mcp`, a stdio server exposing the same operations as tools | Agents that prefer tools to shell commands |

[REA](https://github.com/morluto/rea) is a **separate** dependency, needed only to
investigate finished products (binaries, packages, apps with no source). See
[REA setup](#rea-for-finished-products).

## 1. Install the skill

Clone or download this repository, then run the installer from its root. It copies
the skill to your agent's personal skills directory, is safe to re-run, and refuses
to overwrite a file you edited.

~~~sh
python architect-anything/scripts/install.py --host claude
~~~

| Agent | Command | Installs to | Invoke with |
| --- | --- | --- | --- |
| Claude Code | `--host claude` | `~/.claude/skills/architect-anything` (or `$CLAUDE_CONFIG_DIR/skills/...`) | `/architect-anything` or ask naturally |
| Codex | `--host codex` (default) | `~/.codex/skills/architect-anything` (or `$CODEX_HOME/skills/...`) | `$architect-anything` |
| Antigravity | `--host antigravity` | `~/.gemini/config/skills/architect-anything` | ask naturally |
| Other agents that read `~/.agents/skills` | `--host agents` | `~/.agents/skills/architect-anything` | per your agent |

On Windows use `py -3` in place of `python` if `python` is not on your PATH.

### Project-local install

To give one repository its own copy (for example so teammates get the skill when
they clone), choose the destination yourself. It must end in `architect-anything`:

~~~sh
python architect-anything/scripts/install.py --destination /path/to/your/project/.claude/skills/architect-anything
~~~

### Without cloning

Download `architect-anything-<version>.zip` from the
[releases page](https://github.com/Flambeau-Phoenix/architect-anything/releases),
check it against the published `.sha256`, and unzip it into your agent's skills
directory so that `.../skills/architect-anything/SKILL.md` exists.

### Another agent

Any agent that can load a `SKILL.md` folder and run Python can use the
[architect-anything directory](../architect-anything/SKILL.md) as is. Point it at
that folder. `agents/openai.yaml` carries optional display metadata for hosts that
read it.

### Updating and removing

Re-run the installer from a newer checkout. If you changed installed files it stops
and names them; reconcile or remove those edits first. The previous version is kept in
`.architect-anything-backups/` next to your skills directory (for example
`~/.claude/.architect-anything-backups/`), deliberately outside it so agents do not
discover it as a second copy of the skill; delete old backups whenever you like. Machine settings
(`local.json`) are preserved. To uninstall, delete the
`architect-anything` skills folder.

## 2. Optional: the command

~~~sh
python -m pip install .
architect-anything --version
architect-anything install-skill --host claude   # install the skill from the package
~~~

This adds `architect-anything` and `architect-anything-mcp` to your environment.
Agents normally call the scripts inside the skill folder directly, so this step is
for people who want the command on their PATH.

## 3. Optional: the MCP server

Registration is opt-in; installing the skill never edits your agent configuration.

Claude Code:

~~~sh
claude mcp add architect-anything -- architect-anything-mcp
# without pip: claude mcp add architect-anything -- python /path/to/skills/architect-anything/scripts/aa_mcp.py
~~~

Codex (`config.toml`):

~~~toml
[mcp_servers.architect-anything]
command = "architect-anything-mcp"
~~~

Any MCP client (JSON):

~~~json
{ "mcpServers": { "architect-anything": { "command": "architect-anything-mcp" } } }
~~~

Restart or reconnect the agent and confirm the `aa_*` tools are listed. The server
organizes and publishes the investigation; it does not analyze targets itself.

## REA for finished products

A source repository needs no extra tools. To investigate an executable, package,
Electron/web app, mobile build, firmware image or capture, the agent uses REA:

- an **already connected REA MCP server**, or
- an **existing REA CLI**, found on `PATH` or named in a small JSON config kept
  outside the skill (`ARCHITECT_ANYTHING_REA_CONFIG` or `--config`).

REA's native analysis additionally needs a provider such as Ghidra and a JDK. These
are installed and licensed separately from this project; follow REA's own
documentation. See [REA integration](../architect-anything/references/rea-integration.md)
and [target routing](../architect-anything/references/target-routing.md).

## Verify the install

Ask your agent: *"Use architect-anything to give me a quick rundown of this
project."* It should say which depth it chose, create a workspace, investigate,
and give you links to an HTML report. To check the scripts directly:

~~~sh
python ~/.claude/skills/architect-anything/scripts/aa_cli.py --version
~~~
