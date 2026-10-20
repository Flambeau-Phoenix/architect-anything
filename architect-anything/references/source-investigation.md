# Source investigation

Use ordinary repository tools for complete source projects, irrespective of
language. REA complements this route when shipped behavior matters; it is not a
universal source-language parser.

## Survey and coverage

Read manifests, entry points, build/CI/deployment definitions, schema/migrations,
tests, and existing documentation. Use `rg --files`, targeted searches and bounded
reads. Exclude generated dependencies from first-party walkthroughs, but record
dependencies and their architectural role. Generated code that runs in production
is still relevant when source cannot explain the resulting behavior.

Build a checklist connecting **user capabilities → entry points → components →
data/interfaces → deployment units**. Every major capability needs either an
evidenced walkthrough or an explicit gap. An import tree is not a feature map.
For a monorepo, establish deployable boundaries before documenting packages.

## Follow real paths

Trace the concrete functions behind UI actions, routes, CLI commands, workers,
schedulers, plugins and event handlers. Explain:

- Inputs, validation, permissions, dispatch and outputs.
- State ownership, persistence, migrations, caches and invalidation.
- External calls, protocol/data shapes, trust boundaries and failure semantics.
- Concurrency, transactions, cancellation, retries, cleanup and idempotency.
- Extension points, feature flags, configuration precedence and cross-component
  contracts that must change together.

Use tests to corroborate contracts; tests are not proof of deployment or observed
runtime behavior. Read actual implementation behind names. Describe important
algorithms with inputs, steps, outputs, invariants and meaningful edge cases.
Claim complexity only where the inspected algorithm supports it.

## Rationale and operations

Consult comments, ADRs and focused commit history for why choices were made.
Separate the observed choice, recorded rationale, and your inferred tradeoff.
Do not manufacture an ADR as if it were a historical decision.

Trace build → package → release → deploy. Identify configuration sources,
observability, backup/recovery, rollback and service dependencies. Distinguish
documented commands, inspected commands and commands actually executed.
Avoid running an unknown build just to make the report seem more verified.

## Source and product disagreement

Do not identify a built app with the current source revision solely because names
or version strings match. Record both fingerprints. Compare source and shipped
bundles with REA when applicable, then describe discrepancies and matching limits.
Keep local-development, test and production configurations distinct.

## Scalable depth

For large systems, first map every top-level subsystem. Deeply inspect important
and highly coupled flows, then follow remaining capabilities in bounded passes.
Report the exact sampled scope. Do not claim exhaustive understanding from a
handful of representative files. A narrower accurate report is useful when its
coverage is visible.
