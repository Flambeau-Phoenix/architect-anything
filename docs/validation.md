# Validation scope

The initial implementation was validated on Windows x64 on October 20, 2026.
All investigation examples used synthetic fixtures.

## Core checks

Sixty-two behavioral tests passed using Python 3.14 (version 1.1.0; the first 35
were validated on October 20, 2026 for 1.0.0). Public Python sources are
also checked for Python 3.10 syntax compatibility.

The tests cover source fingerprints and line bounds, broken references, stale
findings, diagram endpoints and cycles, HTML/Markdown escaping, immutable
snapshots, manual edits, interrupted publication and rollback, dirty/non-Git
inventories, collection changes, findings comparisons, missing CLI configuration,
partial reports and installation behavior.
The workflow tests additionally cover catch-up versus focused questions, refusal
to publish a scaffold, partial findings, unresolved checklist entries, target
changes during collection, ignored report outputs in Git repositories,
prior-report selection, resume after publication, workspace containment,
record-only remote identity, JSON errors and unavailable REA handling.
The 1.1.0 tests cover depth checklists and the deep-note guard, legacy manifests
without depth, installer host destinations, and the MCP server over a real stdio
subprocess: handshake, tool listing, a start/status workflow, parse errors, tool
errors that keep the server running, and CLI-equivalent refusal of scaffolds.
The `cite` and `checklist` tests cover relative and absolute paths, line bounds,
idempotent appends, duplicate IDs, URL targets, note rules, the deep-note
warning, the CLI error envelope, the MCP tools, a helpers-only investigation from
`start` through `finish`, and that the authoring-cookbook JSON snippets compose
into a valid report. Installer tests cover the Claude Code and `~/.agents`
destinations, idempotence and protection of edited files.
The MCP server was not exercised against a live agent client in this release, and
the skill was not run end to end inside Claude Code or Antigravity; only Codex
was used as a live host during development.

The public repository adds release-structure checks and a reproducible source
demo, focused explanation demo and installable CLI. GitHub Actions is configured
for Windows/Linux and Python 3.10/3.12/3.14;
remote CI results are not asserted before the workflow has run.

The Python wheel was built and installed into an isolated environment. Its
console command was exercised from outside the checkout, including bundled
schemas, catch-up publication, focused questions, scaffold refusal, resume,
whole-project report preservation and structured REA failures. The installed
command also retained a real REA managed-artifact result. All 33 portable skill
files were compared byte-for-byte with the built wheel payload.

The focused explanation demo was reviewed for its direct answer, mechanism,
source claims and design limits. Desktop/mobile browser checks passed for search,
layout, mobile contents and offline operation.

## REA integration

REA 6.7.0 was built from its supplied source and lockfile using Node 24.18.0 and
npm 11.16.0. No upstream Git revision was available in that distribution.

| Route | Executed validation |
| --- | --- |
| Packaged JavaScript | ASAR analysis and summary from saved canonical Evidence |
| Feature tracing | Outgoing server.js graph trace: 18 nodes and 23 edges |
| Managed code | PE/CLI classification, members and CIL inspection without assembly execution |
| Native code | Native x64 PE overview through Ghidra 12.1.4 with JDK 21 |

The sandboxed native attempt reached Ghidra analysis but timed out at REA bridge
startup. The run outside that sandbox completed. That result validates the tested
host context, not general sandbox availability.

Canonical integration results were reviewed during development. They remain
outside the public repository because runtime captures and command receipts
contain machine coordinates. The public repository does not redistribute REA,
Ghidra, its fixture binaries or those local outputs.

## Presentation

Hidden-browser checks passed for desktop and 390-pixel mobile layouts, mobile
contents navigation, search, deep citations, themes, unique IDs, internal links,
print expansion, escaped hostile text, zero external requests and zero browser
JavaScript errors. Desktop, mobile, dark-theme, diagram and print views were
visually inspected.

The screenshots in this repository show a synthetic source fixture. Generate
the demo to obtain fresh report files and citations on your machine.

## Limits

Other target families are documented routes, not independently verified
platform/provider integrations in this release. Android/JADX, Apple/Harmony,
firmware, Flutter/Dart, IL2CPP, Godot packs, WASM, EVM, databases, network/signal
captures, recorded crashes, other native providers, devices and instrumentation
were not separately exercised here.

The native example tested inventory, not a complete native feature investigation.
The managed example tested static structure, not deployment behavior.
Structural validation cannot prove prose semantics, inferred rationale,
coverage, provider authenticity or runtime reproducibility.
