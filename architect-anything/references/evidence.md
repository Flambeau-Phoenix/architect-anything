# Evidence and confidence

Read this when authoring claims, importing REA results or reusing previous work.

## Authority

| Authority | Meaning | Example |
| --- | --- | --- |
| observation | Directly inspected source/artifact or recorded behavior | A handler registers a route; a capture contains a request |
| derived | Deterministic conclusion from cited facts | Two declarations share a schema; a graph has a recovered dependency |
| inference | Reasoned interpretation with a stated basis | This queue likely isolates slow work |
| contradiction | Evidence disagrees and is not yet reconciled | Docs name one store while the active adapter selects another |
| unknown | Not established within the investigation | Server persistence behind an observed endpoint |

Use separate freshness labels: `verified`, `stale`, `unverified`. Authority and
freshness answer different questions. Avoid percentage confidence scores that
cannot be calibrated.

## Citation records

Each evidence record has a stable report-local ID, kind, locator and note.
For local files, include a path relative to `target.locator` (or an explicit
absolute path), SHA-256 and optional 1-based inclusive line range. For a file
target, relative paths resolve beside the file. For REA, also retain its actual
Evidence ID and operation/profile in the note; point to a saved canonical result
or bundle. A volatile same-session ID alone is not a durable citation.

Claims link to evidence IDs. Diagram nodes and relationships link to claim IDs.
Every substantive architectural assertion needs a supporting claim, including
assertions in prose and tables. A validator checks structural links and hashes;
human/agent review must check whether the cited evidence supports the assertion.
Unknown claims may have no evidence; explain the investigation boundary.

Path/line citations are meaningful only with the matching content fingerprint.
Do not substitute a version string for a binary digest. Use byte offsets, native
addresses, metadata tokens and graph node IDs where source lines do not apply.

## REA evidence handling

Read `normalized_result`, coverage and limitations. Preserve the canonical
Evidence record unchanged; never fabricate IDs or repair evidence hashes.
Returned `raw_result` can be null without making the normalized facts invalid.

Prefer `detail: "summary"` where advertised. Follow returned parent IDs through
`inspect_analysis_view`; select actual node IDs, because paths can name several
graph roles. Page results until the relevant scope is examined. Page exhaustion
does not prove full target coverage.

Session-retained IDs are valid only in that server session. Export needed bundles
or use complete file Evidence for later CLI invocations. For oversized delivery,
use retained views or export; do not rerun the producer or parse a truncated JSON
preview. `retention: complete-record` does not remove analysis limitations.

## Negative findings and secrecy

State the search domain: "No matching export in the inspected x64 library" is
stronger and more honest than "the product has no such feature." Unsupported
providers, omitted sources and unresolved dynamic calls are unknown, not empty.

Keep passwords, session tokens and private customer payloads out of shareable
reports. Preserve useful non-sensitive paths and identifiers. Do not erase
arbitrary evidence merely because a field name looks sensitive. Canonical raw
evidence stays separate; a redacted presentation is not the original Evidence.

## Freshness validation

`validate --check-files` verifies local evidence hashes and line bounds. Changes
fail validation while a claim is marked verified. A stale/unverified claim may
retain its historical evidence with a warning and visible freshness badge.
Remote locators, native semantic interpretation, runtime reproducibility and
provider authenticity still require investigation; the helper cannot prove them.
