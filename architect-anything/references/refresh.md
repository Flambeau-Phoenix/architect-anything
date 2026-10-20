# Refresh, snapshots and continuation

Refresh on invocation; this skill does not schedule itself.

## Artifact layout

```text
OUTPUT/
  index.html                 latest-run landing page
  README.md                  latest-run Markdown link
  current.json               machine-readable current snapshot pointer
  snapshots/RUN-ID/
    report.json              authored model
    report.html
    report.md
    evidence.json
    diagrams/*.svg
    diagrams/*.json
    manifest.json            generated-file hashes
  evidence/                  canonical raw evidence, managed by the investigator
  notes/                     optional human-authored notes; never overwritten
```

Run IDs must be unique, for example `run-20261020T153000Z-product-v2`. Render into a
staging directory and publish only after validation. Existing snapshots cannot be
overwritten. An interrupted render does not advance the current pointer.
Concurrent publication is refused with a lock; a leftover lock requires checking
that no writer is still active before removing it.

Reports and the evidence index preserve citations. For portable sharing, copy
appropriate non-sensitive evidence into `OUTPUT/evidence/`, cite it with a stable
path, and keep this directory with the report. Source links to the original
checkout require that checkout; do not call them portable source archives.

## Compare accurately

1. Resolve and read the last report and its inventory; validate target identity.
2. Inventory the selected target before analysis. `diff` compares selected files,
   exclusions, errors, and scope. Different target roots are not silently paired.
3. Reinspect changed components and their dependents. Record additions, removals,
   interface/data changes and consequences, not just a list of changed files.
4. Compare normalized claim text, authority and evidence content signatures with
   `compare`. Stable claim IDs enable matching; new IDs are additions, not guessed
   renames. Evidence relocation alone is not a product change.
5. Classify deltas as observed findings changes, analysis/evidence changes or
   coverage changes. The helper's findings delta is a lead; the investigator
   decides which changes are actually architectural.
6. Revalidate retained claims. If not rechecked, mark them stale/unverified.
7. Compare start/end inventories and disclose changes during collection. Re-run
   affected reads or mark the report partial, with the affected scope.
8. Render a new snapshot and advance the current pointer only after success.

An unchanged file inventory does not establish unchanged remote services, runtime
configuration or dependency resolution outside the inspected tree. Different
exclusion policies make comparisons partial. Non-Git targets use hashes and
explicit collection timestamps, never a fabricated revision.

## Interrupted or unavailable investigation

Save a partial/interrupted model with verified findings, unavailable areas,
tool/provider failure reasons and a continuation checklist in the assessment.
Do not mark unchecked prior content current. Preserve complete canonical evidence
already collected. A future run resumes from matching identities and current
capabilities, not from stale session IDs.

## Human edits

Snapshots are generated artifacts. Never re-render over one. Keep manual notes in
separate files and reference them with their provenance. If current pointer/index
files were edited outside the helper, publication refuses to replace them; inspect
and reconcile their content first. Installation follows the same rule for modified
skill files.
