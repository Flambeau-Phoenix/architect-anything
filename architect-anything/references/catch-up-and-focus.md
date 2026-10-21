# Two ways to help the user understand a system

Read this for an owner catching up on a fast-moving project, or a specific
"how does this work?" request. Users should be able to ask in ordinary language.
Do the investigation and document generation; do not send the user a sequence
of internal helper commands to finish themselves.

## Catch me up on my project

Use this when the user wants to regain a reliable mental model of the system.
Start with the selected project and its current state. Do not require the user
to already know which modules or architectural patterns matter.

Deliver a readable owner briefing answering:

- What is the project now, who is it for, and what can it do?
- What are the major pieces, how do they fit, and where are the boundaries?
- How do important user actions reach their result and change state?
- What changed since the last verified record, and why does it matter?
- What design constraints, hidden coupling or discrepancies deserve attention?
- What remains uncertain, and how would someone check it?

Then provide the technical reference behind that briefing. Map the whole scoped
system before choosing representative deep traces. Keep uncovered areas visible.
The catch-up report must not be a directory listing or a recital of dependencies.

## Explain this part

Use this for a named feature, screen, endpoint, algorithm, protocol, subsystem or
concrete question such as "how are plugins loaded?" or "why does sync behave this way?"

Resolve the phrase to actual entry points. Search names, labels, routes, event
handlers and configuration as leads, then follow the implementation or REA
evidence. Ask for clarification only if several plausible targets remain.

Answer the question directly first. Trace:

1. Trigger and inputs.
2. Dispatch, component/process boundaries and important transformations.
3. Algorithm, state ownership, invariants, ordering and failure behavior.
4. Output, persistence or external effects.
5. The design choices and tradeoffs that explain the mechanism.

Use a compact sequence/data/state diagram and concrete evidence. Investigate
adjacent components only far enough to explain the selected behavior. Preserve
unresolved native, dynamic or remote handoffs rather than inventing internals.

Recorded rationale, your inferred tradeoff, and a proposed improvement are
different things. Describe the existing design; label any inference. Do not turn
the task into an unsolicited redesign.

The focused report should stand alone for a reader unfamiliar with the project.
It is a useful document, not just raw decompiled code or an unannotated call graph.
Default focused reports live under docs/architecture/focus/ and preserve the
whole-project report.

## Use the workflow CLI

An installed command is available as architect-anything. From a portable skill,
use Python with this skill's scripts/aa_cli.py instead. Both call the same helpers.

Start a catch-up investigation:

~~~text
architect-anything start ABSOLUTE_TARGET --kind source
~~~

Start a focused explanation:

~~~text
architect-anything start ABSOLUTE_TARGET --focus "How are plugins discovered and loaded?"
~~~

The JSON result gives the working report, investigation manifest, evidence
directory, inventory summary and prior report if present. This only prepares the
work; it does not produce an architectural analysis.

Read the checklist from status, collect evidence, and author report.json. Record
evidence with cite and each answer with checklist (answered, partial or
not-applicable, always with a concrete note); unresolved means no sufficient
answer yet. Use status to resume after interruption. Remove the scaffold
limitation only after actually investigating. Do not fill working sections with
guesses to satisfy the checklist.

Use finish WORKSPACE to capture the ending inventory, verify citations and
publish. A normal finish requires a complete authored report and resolved
checklist. To deliver useful work with explicit gaps, mark the report partial
or interrupted and use finish WORKSPACE --partial. Do not call partial work a
complete explanation. Changed targets force review or a partial result.

For a refresh, compare the prior report and current evidence, then explain
architectural consequences in the new briefing. Do not carry stale prose forward
as verified. For remote URLs the CLI records identity only; use the selected
browser/REA route to collect evidence.

## Delivery test

The user should be able to read the first page and say what their project does,
or explain the selected mechanism, without inspecting a JSON file or knowing REA.
An engineer should then be able to follow the report's evidence and technical
detail. Provide the report links, a concise explanation of what you learned,
and the few unresolved questions that materially limit understanding.
