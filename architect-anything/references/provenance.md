# Provenance

Architect Anything 1.0.0 was developed from the supplied Reverse Engineer Anything
6.7.0 source distribution (`rea-agents`, upstream `morluto/rea`).
The supplied folder had no Git metadata, so no upstream commit is asserted.

Upstream: https://github.com/morluto/rea

REA's MIT license is preserved at `assets/REA-LICENSE.txt`. Its target routing,
CLI/MCP evidence semantics, provider/lifecycle limitations and investigation
guidance informed this skill. The engine is used as a separately installed or
locally built dependency; its source, native providers and third-party binaries
are not redistributed inside the skill.

Primary inspected sources:

- `.agents/skills/reverse-engineer-anything/SKILL.md`
- `src/contracts/` tool contracts and effect metadata
- `docs/mcp-contracts.md`, `docs/cli.md`
- `docs/javascript-application-workflows.md`
- `docs/javascript-application-graph.md`
- Format/provider guides named in `target-routing.md`

The report schema, deterministic helper scripts and offline presentation are
Architect Anything additions. The existing project-blueprint skill informed the
owner/maintainer documentation goals; its patent-disclosure and reconstruction
goals are not part of this skill.

The package's routing is a baseline, not an assertion that every REA capability
has been exercised here. The public repository's docs/validation.md records
executed tests, real-provider results and platform-dependent gaps.
