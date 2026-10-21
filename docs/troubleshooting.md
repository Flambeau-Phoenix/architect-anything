# Troubleshooting

Every CLI command prints one JSON object. Failures print JSON on stderr, leave
stdout empty and exit nonzero: `1` report validation failed, `2` invalid
arguments or input, `3` filesystem/process failure, `4` REA unavailable or failed.
The `error.message` names the cause.

## Install and run

| Symptom | Fix |
| --- | --- |
| `python: command not found` (Windows) | Use `py -3`, or install Python 3.10+ and tick "Add to PATH". |
| `Destination must be the exact architect-anything skill directory` | `--destination` must end in `architect-anything`. |
| `Installed file has independent changes` | You edited an installed file. Copy your edit somewhere, delete the installed folder (or the named file), and re-run the installer. |
| Agent does not offer the skill | Restart the agent after installing; confirm `.../skills/architect-anything/SKILL.md` exists in the directory your agent reads. |
| `aa_*` tools missing | Registering the MCP server needs an agent restart or reconnect. |

## While investigating

| Symptom | Fix |
| --- | --- |
| `still an uninvestigated scaffold` | `start` only prepares work. Author real findings and remove the scaffold limitation; do not publish the scaffold. |
| `Investigation is unfinished` | Record every checklist item with `checklist`, or publish honestly with `finish --partial`. |
| `Cited file does not exist` | `cite` resolves relative paths against the target root. Use an absolute path or fix the path. |
| `Line range ... is outside the file` | Re-read the file; cite the lines that exist. |
| `fingerprint changed` | The file changed after you cited it. Re-inspect and re-cite, or mark the claim `stale`. |
| `target changed during collection` | Files changed between `start` and `finish`. Recheck what changed, or finish `--partial`. |
| `Published investigation changed; start a new run` | Snapshots are immutable. Run `start` again for new findings. |
| Output folder is inside the target | Fine for source projects (`docs/architecture/` is excluded from inventories). It must not be the target root or its parent. |

## Finished products and REA

| Symptom | Fix |
| --- | --- |
| `No REA CLI found` | Connect an REA MCP server, put `rea` on PATH, or pass `--config` / set `ARCHITECT_ANYTHING_REA_CONFIG`. The skill never installs REA. |
| Native analysis times out or provider missing | Native routes need a provider (for example Ghidra) and a JDK on a supported host. Static JavaScript and managed analysis may still work; the report should name the unavailable boundary. |
| Oversized or truncated REA result | Project it with a saved view; do not rerun the producer. See [REA integration](../architect-anything/references/rea-integration.md). |
| `Evidence output/sidecar already exists` | `rea run --out` never overwrites. Choose a new filename. |

## Publishing

| Symptom | Fix |
| --- | --- |
| Publication refused because of a lock | Another writer may be active. Confirm none is, then remove the stale lock the message names. |
| Index or pointer was edited by hand | Publication refuses to replace files it did not write. Reconcile your edit, then retry. |
| Report links to source do not open | Citations point at the original checkout. Copy shareable evidence into `evidence/` beside the report for a portable bundle. |

Still stuck? Open an
[issue](https://github.com/Flambeau-Phoenix/architect-anything/issues) with the
command, the JSON error and your Python and agent versions. Do not attach private
source or raw evidence.
