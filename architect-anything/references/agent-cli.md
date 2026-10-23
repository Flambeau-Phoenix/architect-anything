# Agent CLI

The user asks for documents or an explanation in natural language. The agent uses
this command interface to organize and validate its work. It is not an LLM runner
and does not invent architecture from an inventory.

## Installation and portable invocation

Install the named command from a repository or skill checkout with Python 3.10+:

~~~text
python -m pip install .
architect-anything --help
architect-anything-mcp
~~~

An installed Python package also supports `python -m architect_anything`.
When only the skill folder is available, invoke `python scripts/aa_cli.py` relative
to the skill. The portable path requires no package installation or third-party
Python libraries.

## Workflow

~~~text
architect-anything start TARGET
architect-anything start TARGET --focus "How does offline sync work?"
architect-anything start TARGET --focus "How does offline sync resolve conflicts?" --lens mechanism
architect-anything start TARGET --lens onboarding --emit onboarding --emit mermaid
architect-anything start TARGET --depth deep
architect-anything status WORKSPACE
architect-anything cite WORKSPACE src/sync.py --lines 40-72 --note "Retry loop" --append
architect-anything upsert-claim WORKSPACE retry-backoff --text "Failed pushes retry up to 5 times." --authority observation --evidence ev-src-sync-py-L40-72
architect-anything upsert-section WORKSPACE behavior --body "Pushes queue locally and retry." --claim retry-backoff
architect-anything set-meta WORKSPACE --title "Offline Sync Architecture" --run-status complete --coverage partial --limitation "Static source only"
architect-anything checklist WORKSPACE behavior --status answered --note "Traced push and pull paths"
architect-anything validate WORKING_REPORT.json --check-files
architect-anything finish WORKSPACE [--emit mermaid,adr,llms-txt]
~~~

`--lens` supports five specialized lenses (see [Lenses and packs](lenses-and-packs.md)):
- `mechanism` (requires `--focus`): extracts a portable formula (core idea, trace, contract, essentials, assumptions, choices, limits). See [Mechanism lens](mechanism-lens.md).
- `onboarding`: maintainer onboarding and edit map (`briefing`, `entrypoints`, `codemap`, `devloop`, `invariants`, `limits`).
- `delta`: architectural drift and contract changes (`summary`, `contracts`, `data`, `dependencies`, `drift`, `risks`).
- `boundaries`: trust boundaries, input validation, outbound calls, and secrets (`surface`, `trust`, `validation`, `egress`, `secrets`, `assumptions`, `limits`).
- `operations`: production lifecycle, configuration precedence, state concurrency, resilience, observability, and recovery (`lifecycle`, `config`, `state`, `resilience`, `observability`, `recovery`, `limits`).

`--emit` accepts optional companion report packs (`mermaid`, `adr`, `onboarding`, `delta`, `llms-txt`, or `all`) on `start`, `finish`, or `render`.

`status` returns `remaining` (unresolved checklist IDs), a `next` sentence, `lens`, and `emit` (when configured).

`cite` resolves PATH against the target (absolute paths are accepted), checks
that it exists and that `--lines` lies inside it, and returns a schema-valid
evidence record: relative POSIX path, SHA-256, line range and a generated unique
ID (override with `--id`). It is idempotent: citing the same file and lines again
returns the existing record. Without `--append` it only prints the record, so it
can be pasted into the report; with `--append` it adds the record to the working
`report.json` and changes nothing else. `--kind` is `source` (default),
`artifact` or `document`; REA and runtime evidence need their own records with a
durable file and actual Evidence ID.

`upsert-claim`, `upsert-section`, `upsert-diagram`, and `set-meta` let the agent
author and update the working `report.json` safely with immediate schema and
reference validation. When `upsert-section` replaces the last scaffold section,
unused `*-unknown` scaffold claims and the scaffold limitation are pruned automatically.

`checklist` sets one item to `unresolved`, `answered`, `partial` or
`not-applicable`. A note is required except when reopening an item. In a deep
run it warns when a note is shorter than the 40 characters that `finish` needs.
Use it instead of editing `investigation.json` by hand.

`--depth` is `overview`, `standard` (default) or `deep`. It is stored in the
manifest, shown by status and selects the checklist: overview keeps the
owner-level questions, deep adds interfaces, algorithms, failure paths, module
reference and build/release (catch-up) or signatures, failure paths and related
configuration (focus). A deep finish requires each answered or partial added row
to carry a concrete note of at least 40 characters. A manifest without depth is
treated as standard.

Start returns an investigation manifest, report scaffold and evidence directory.
Directory targets default to source unless they are recognized application
bundles. Use --kind product for a finished-product directory. File targets
default to product. URLs are recorded without fetching or running them.

Read the mode-specific checklist. Investigate it with source tools or REA and
author the report and checklist notes. A starter model is explicitly incomplete;
finish rejects an uninvestigated scaffold.

Finish requires a complete authored report and no unresolved checklist items.
Partial or not-applicable checklist answers need an explanatory note. For a
report with genuine remaining gaps, set its status to partial/interrupted and
use --partial explicitly. Changed collection state cannot be published as complete.

The workspace remains readable after interruption. Repeating finish after a
successful publication returns its existing snapshot if the authored model is
unchanged. New findings require a new investigation/snapshot.

## Other commands

| Command | Result |
| --- | --- |
| cite WORKSPACE PATH | Build (and optionally append) a hashed evidence record |
| upsert-claim WORKSPACE ID | Add or update a validated claim in the working report |
| upsert-section WORKSPACE ID | Add or update a validated section and prune replaced scaffold claims |
| upsert-diagram WORKSPACE ID | Add or update a validated diagram in the working report |
| set-meta WORKSPACE | Update report title, subtitle, target name, status, coverage, limitations, or changes |
| checklist WORKSPACE ID | Record a checklist answer with its note |
| schema commands | Discover command help, streams and exit contracts |
| schema report | Full report JSON Schema |
| schema investigation | Investigation manifest JSON Schema |
| inventory TARGET --out FILE | Hash selected local files |
| diff BEFORE AFTER | Compare inventory selection and content |
| compare BEFORE AFTER | Compare report findings/evidence/coverage |
| render REPORT --output DIR [--emit ...] | Publish an existing authored report model |
| rea status --config FILE | Probe an existing REA CLI |
| rea run --config FILE --out FILE -- OPERATION ARGS | Run a selected REA operation and retain output/receipt |
| install-skill [--host codex\|claude\|agents\|antigravity] | Install the portable skill for the local agent |

The REA bridge preserves operation scope and actual host requirements. A CLI
probe does not prove a provider is ready or an MCP server is connected.

## Machine protocol

Successful operations write one JSON object on stdout:

~~~json
{"ok": true, "command": "start", "result": {}}
~~~

Failures write JSON on stderr, leave stdout empty, and exit nonzero:

~~~json
{"ok": false, "command": "validate", "error": {"code": "validation_failed", "message": "Report validation failed"}}
~~~

Hosts install into: `codex` (`$CODEX_HOME` or `~/.codex`) `/skills`, `claude`
(`$CLAUDE_CONFIG_DIR` or `~/.claude`) `/skills`, `agents` `~/.agents/skills`, and
`antigravity` `~/.gemini/config/skills`. `--destination` overrides them and must
end in `architect-anything`. For a project-local Claude Code skill use
`--destination PROJECT/.claude/skills/architect-anything`.

Exit codes: 0 success; 1 report validation failed; 2 invalid arguments/input;
3 filesystem/process failure; 4 REA unavailable/failed. Error details may contain
the validation result or a retained REA receipt. Help and version are plain text.
No command prompts interactively or acquires an LLM/provider subscription.

Older scripts/architect.py and scripts/rea_bridge.py remain available for existing
callers. Their historical output shapes differ; the stable envelope above applies
to architect-anything and scripts/aa_cli.py.
