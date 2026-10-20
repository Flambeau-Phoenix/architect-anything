# REA integration and recovery

Use an already connected REA MCP server when available. Discover canonical tools
and schemas, route the selected target, and inspect session availability for an
observed missing capability. Do not run setup/doctor before every investigation.

## CLI and local configuration

The skill's optional bridge locates a configured command or an existing `rea` on
PATH. It never downloads packages, registers MCP, or installs providers.

Store machine-specific settings **outside** the portable skill, for example:

```json
{
  "command": ["C:/tools/node.exe", "C:/tools/rea/scripts/rea.mjs"],
  "cwd": "C:/tools/rea",
  "env": {
    "GHIDRA_INSTALL_DIR": "C:/tools/ghidra",
    "JAVA_HOME": "C:/tools/jdk"
  },
  "version": "6.7.0"
}
```

Pass `--config FILE` or set `ARCHITECT_ANYTHING_REA_CONFIG` to that file. Do not
store credentials or a copy of the ambient environment here. An installed skill
may have a small `local.json` pointing to this external file; the installer treats
that file as machine configuration, not portable package content.

```text
python scripts/rea_bridge.py status --config CONFIG.json
python scripts/rea_bridge.py run --config CONFIG.json --out EVIDENCE.json -- analyze-javascript-application ABSOLUTE_APP_PATH --json
```

`status` checks executable/script paths and performs a bounded `--version` probe.
It does not claim a provider is ready or MCP is connected. `run` passes an argument
array without shell interpolation, streams stdout to the selected file and saves
stderr separately. It records success/failure and does not reinterpret REA output.
It is a CLI convenience, **not a read-only sandbox**: operation authorization and
provider lifecycle rules still apply.

Large CLI results should be written to files and projected:

```json
{
  "source": {"kind": "evidence-file", "path": "ABSOLUTE_EVIDENCE_PATH"},
  "view": {"kind": "summary"}
}
```

Save that request as JSON; use `rea inspect-analysis-view REQUEST.json --json`
where advertised. CLI commands run in separate processes; same-session retained
IDs cannot be reused across them.

Do not generalize the view's `evidence-file` selector to every CLI command. In the
tested 6.7.0 CLI, `trace-application-feature` consumes a request file whose
`application` is the **complete canonical Evidence object**. Load the saved JSON
into that field without changing it, supply the seed/direction, and write the
request file. MCP request references can differ; inspect that adapter's schema.

## Build the supplied source

Inspect the checkout's `AGENTS.md`, `.nvmrc` and `package.json#packageManager`.
Use its pinned toolchain and lockfile:

```text
npm ci
npm run build:cached
node scripts/rea.mjs --version
```

A source checkout may lack the packaged Windows native addon. Static JavaScript
and managed parsing can still work. Native Ghidra on Windows needs REA's matching
native controls as well as Ghidra and a supported full JDK. Follow the checkout's
documented build/verification lane if native compilation is appropriate.
Never silently substitute an unverified or mismatched binary.

## Distinguish blockers

| Symptom | Response |
| --- | --- |
| No MCP tools, usable CLI | Continue with CLI; no registration needed |
| Missing compiled source runtime | Build from the supplied lockfile or use an already installed matching release |
| Client registration aligned but tools absent | Reconnect/restart that client; setup cannot attach tools to the active session |
| Missing native engine or host support | Continue built-in/static routes and disclose the exact unavailable boundary |
| Oversized/truncated result | Use saved/retained evidence views; do not rerun the producer |
| Target integrity mismatch | Investigate identity; do not suppress the mismatch to force a clean report |
| Client permission rejection | Respect the actual rejection; continue unaffected work and explain the blocker |

MCP registration is optional. If specifically requested, inspect the current
client configuration and REA setup dry-run first, preserve unrelated settings,
then apply the authorized concrete change. Do not install engines or overwrite
the existing REA skill as an incidental consequence of report generation.
