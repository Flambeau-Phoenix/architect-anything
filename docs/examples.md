# Example prompts

You never need to name a mode, depth or command. Describe what you want to
understand; the agent chooses the approach, says which depth it picked, and
delivers the documents. Prefix a prompt with `/architect-anything` (Claude Code)
or `$architect-anything` (Codex) to invoke the skill explicitly.

## Catch up on a project

> This project has gotten ahead of me. Explain what it does now, how the pieces
> fit together, how the important features work, and what changed. Give me
> architecture documents I can keep up to date.

**You get:** an owner briefing first, then components and boundaries, feature
walkthroughs, data ownership, operations, and an assessment of coupling, drift
and unknowns. Source projects write to `docs/architecture/`.

## Explain one thing

> How does offline sync work? Trace it from the user's edit to the server, show
> where conflicts are resolved, and say what happens when a push fails.

> Explain how plugins are discovered and loaded in this app.

**You get:** the direct answer first, then the trigger, the path through the
code, the state it touches, failure behavior and the design tradeoffs, with a
sequence diagram and citations. Output goes to `docs/architecture/focus/<question>/`
and leaves any whole-project report untouched.

## Refresh after the code moves on

> Refresh the architecture report and tell me what changed since the last one.

**You get:** a new immutable snapshot, with changed components rechecked and
carried-over claims labeled stale unless revalidated, plus a delta against the
previous report. Old snapshots are preserved.

## Understand a finished product

> Investigate `C:\Program Files\Acme\Acme.exe` and explain how it works. Tell me
> what the evidence cannot establish.

> Here is a packaged Electron app (`/path/to/App.app`). How does it handle
> auto-update and where does it store user data?

**You get:** a report built from recovered structure (via REA) rather than source,
with every claim tied to a file hash, offset, address or saved REA evidence, and
explicit unresolved boundaries where analysis stopped. The skill is static-first;
runtime work (launching, capturing, interacting) happens only for a concrete
evidence gap and within the actions you have authorized.

## Control the depth

| Say something like | Depth | Result |
| --- | --- | --- |
| "Give me a quick rundown." | `overview` | Owner briefing, component map, one or two traces |
| "How does this work?" | `standard` | Adds data ownership, operations, changes, assessment |
| "Document every detail for the maintainers." | `deep` | Adds interface contracts, algorithms, failure paths, per-module reference, build and release |

Deeper means more precise, not longer: signatures, contract tables and concrete
walkthroughs, each cited.

## Good habits

- Name the target by absolute path or product name; say so if there is more than one version.
- Say where output should go if you do not want the default.
- Tell the agent which runtime actions, if any, are allowed (launching, network capture).
- For a focused question, include the symptom or decision behind it; it narrows the trace.
