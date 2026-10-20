# Finished products

Start from the user-selected product: executable, application bundle, installation
directory, archive, URL, device artifact, or saved capture. Resolve an app name to
one clear installation; ask if identity is ambiguous. Do not pick a test fixture.

## Identify before interpreting

Inventory package/container contents, architecture, signatures/version metadata,
entry points, resources, configuration and embedded runtimes. A file extension
does not identify its implementation: PE can be native, managed or a host; an
Electron package may contain native add-ons; a mobile app can mix several engines.
Keep artifact SHA-256, package member paths, offsets and provider profiles.

Use [target routing](target-routing.md) for each layer. Follow runtime boundaries
explicitly: renderer/preload/main, managed/native, host/WASM, app/service, or
firmware/filesystem/boot regions. Do not flatten different evidence authorities
into a fictitious whole-program call graph.

## Recover the useful architecture

1. Establish visible capabilities from resources, manifests, entry points and
   authorized observation. Treat text labels as leads, not proof.
2. Map executables, libraries, modules, services, IPC channels and storage.
3. Trace representative capabilities using recovered functions, references,
   application graphs and resources. Preserve address spaces, metadata tokens,
   source locations and symbol ambiguity.
4. Describe protocol and data structures only to the extent they are recovered.
   A network string is not proof of a request; an import is not proof of use.
5. Explain resource ownership, initialization and failure behavior where evidence
   exists. Missing symbols, indirect dispatch, packing and unavailable providers
   become explicit unresolved boundaries.
6. If a specific gap requires runtime evidence, use the runtime reference.

Decompilation is useful for understanding. Pseudocode, guessed types and inferred
names are interpretations, not recovered original source. Do not emit a
reconstruction implementation or turn the report into a cloning checklist.

## Product-specific emphasis

- Desktop: processes, UI/resources, filesystem ownership, IPC, update mechanism.
- Web: browser boundaries, loaded assets, routes, storage and observed endpoints.
  Client evidence cannot establish an unseen server's internal architecture.
- Mobile: manifest components, permissions, lifecycle, services, bridges and data.
- Firmware: memory/partition layout, boot chain, services and update boundaries.
- Libraries/runtimes: exported surfaces, calling conventions, consumers and ABI.
- Games: engine/package identity, assets, scripts/native boundaries and lifecycle.
- Captures: explain the recorded interaction and its scope; do not claim a full
  product architecture from traffic or a crash snapshot alone.

## Version comparisons

Use REA comparisons supported by the evidence type: application graphs, artifacts,
managed members, functions or WASM interfaces. Match by actual identities and
preserve ambiguous correspondences. A provider change can change recovered
structure without a product change. Artifact equality cannot prove unchanged
remote services, configuration or runtime behavior.
