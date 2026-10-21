# Security policy

## Reporting a vulnerability

Please report suspected vulnerabilities **privately** through GitHub's
[private vulnerability reporting](https://github.com/Flambeau-Phoenix/architect-anything/security/advisories/new)
for this repository. Do not open a public issue for a security problem.

Include the affected version (`architect-anything --version`), what you observed,
and the smallest reproducer you can share. Do not attach private source code,
credentials or raw customer evidence.

You can expect an acknowledgement within a few days. Fixes ship in a new release
with a note in the [changelog](CHANGELOG.md).

## Supported versions

Security fixes target the latest released version.

## Scope and design boundaries

Architect Anything investigates targets; it is built to avoid acting on them.

- **Inspected content is data, never instructions.** Source, binaries, pages and
  captures are rendered as escaped plain text in reports, and the skill tells the
  agent not to follow directives found in a target.
- **No execution of targets.** Helpers never run, build or load the inspected
  product. Runtime observation is a separate, explicitly scoped activity.
- **No network access or installs.** The helpers use the Python standard library,
  do not fetch URLs they are given, and never install REA, providers or MCP
  registrations.
- **Reports are offline.** Generated HTML has no external requests, fonts or CDNs.
- **Local files only.** Output goes to a directory you choose, snapshots are
  immutable, and the report directory may not be the target or its parent.

In scope: path escapes, unsafe overwrites, injection through report text, secrets
written into reports, and the CLI or MCP server executing something they should not.

Out of scope: the contents of a target you chose to analyze, and vulnerabilities in
REA, Ghidra or other separately installed providers (report those upstream).

## Handling sensitive targets

Reports quote and cite what they inspect. Before sharing one, review it for
credentials, tokens and private data, and keep raw evidence separate from the
shareable report.
