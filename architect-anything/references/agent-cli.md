# Agent CLI

The user asks for documents or an explanation in natural language. The agent uses
this command interface to organize and validate its work. It is not an LLM runner
and does not invent architecture from an inventory.

## Installation and portable invocation

Install the named command from a repository checkout with Python 3.10+:

~~~text
python -m pip install .
architect-anything --help
~~~

An installed Python package also supports Python -m architect_anything.
When only the skill folder is available, invoke Python scripts/aa_cli.py relative
to the skill. The portable path requires no package installation or third-party
Python libraries.

## Workflow

~~~text
architect-anything start TARGET
architect-anything start TARGET --focus "How does offline sync work?"
architect-anything status WORKSPACE
architect-anything validate WORKING_REPORT.json --check-files
architect-anything finish WORKSPACE
~~~

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
| schema commands | Discover command help, streams and exit contracts |
| schema report | Full report JSON Schema |
| schema investigation | Investigation manifest JSON Schema |
| inventory TARGET --out FILE | Hash selected local files |
| diff BEFORE AFTER | Compare inventory selection and content |
| compare BEFORE AFTER | Compare report findings/evidence/coverage |
| render REPORT --output DIR | Publish an existing authored report model |
| rea status --config FILE | Probe an existing REA CLI |
| rea run --config FILE --out FILE -- OPERATION ARGS | Run a selected REA operation and retain output/receipt |
| install-skill | Install the portable skill for the local agent |

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

Exit codes: 0 success; 1 report validation failed; 2 invalid arguments/input;
3 filesystem/process failure; 4 REA unavailable/failed. Error details may contain
the validation result or a retained REA receipt. Help and version are plain text.
No command prompts interactively or acquires an LLM/provider subscription.

Older scripts/architect.py and scripts/rea_bridge.py remain available for existing
callers. Their historical output shapes differ; the stable envelope above applies
to architect-anything and scripts/aa_cli.py.
