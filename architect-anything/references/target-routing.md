# REA target routing

Baseline: supplied REA 6.7.0 source. This is a routing map, not a frozen API
catalog. Discover the connected server's actual tools/schemas, then use
`binary_session` availability when a route depends on an active target.
CLI equivalents generally use hyphens; consult CLI help for arguments.
Tool names below were checked against the supplied contracts.

All upstream guide paths are relative to the REA checkout's `docs/` directory.
If no checkout is available, use the matching version's documentation at
`https://github.com/morluto/rea/tree/main/docs`; main may differ from the installed
version. Never invent an unavailable tool based on a guide.

| Target / question | Initial route and useful follow-ups | Requirements and architectural limits | Guide |
| --- | --- | --- | --- |
| Installed desktop product | `inspect_desktop_application`; inspect returned candidate artifacts | Resolve the intended installation/version; candidate discovery is not runtime verification | `desktop-applications.md` |
| JavaScript tree / ASAR / Electron | `analyze_javascript_application`; `inspect_analysis_view`; `trace_application_feature`; `trace_javascript_semantics` | No native engine. Use summary, exact source selections and returned module IDs. Dynamic dispatch remains unknown | `javascript-application-workflows.md`, `javascript-application-graph.md` |
| JavaScript versions / source versus bundle | `compare_application_versions`; `compare_source_to_bundle`; `compare_javascript_export_shapes` | Authenticate inputs; preserve ambiguous matching and compilation/source-map limits | `javascript-application-workflows.md` |
| Browser application | `list_browser_targets`, `inspect_web_page`, `analyze_web_bundle`; selected scenario/runtime tools | Selected CDP endpoint and target; frontend evidence does not reveal unseen backend internals | `browser-observation.md`, `web-runtime.md`, `website-module-trace.md` |
| Electron runtime | `list_electron_targets`, `inspect_electron_page`; `inspect_electron_fuses`; advertised active capture and reconciliation | Inspect actual fuses before main-process debugger attempts; preserve process boundaries | `electron-observation.md`, `electron-fuses.md`, `javascript-runtime-reconciliation.md` |
| ZIP/APK/IPA/MSIX/AppX/DMG and other admitted containers | `open_binary` for active-target archive route, then `inspect_artifact`; selected `extract_artifact` | Inventory first. Extraction writes to a new selected directory and does not imply executable understanding | `cli.md`, `apple-application-analysis.md` |
| Native executable/library/database | `open_binary`; available inventory, `analyze_function`, pseudocode, xrefs, call paths, feature traces | Bring-your-own Ghidra, Hopper, IDA, Kuna or other advertised provider; do not promise cross-provider parity | `native-investigation.md`, `ghidra-provider.md`, `ida-provider.md`, `kuna-provider.md`, `jeb-analysis.md` |
| PE resources / native image metadata | `inspect_pe_resources`; format-appropriate native inspection | PE resource parsing is target-free and portable; payload ranges and hashes do not explain behavior | `binary-diagnostics.md` |
| Mach-O / Apple application | `inspect_macho`, `inspect_signature`, `inspect_plist`, framework/resource tools when advertised | Host/tool prerequisites vary. Signature metadata is not a whole-product trust judgment | `apple-application-analysis.md` |
| .NET PE/CLI | `inspect_managed_artifact`, `inspect_managed_members`, `inspect_managed_native_boundaries`, `project_managed_application_graph` | Built-in static parser; no assembly execution. Metadata tokens are not native addresses | `managed-code-analysis.md` |
| .NET NativeAOT | Native Ghidra route; admitted load-image/type metadata inspection | Do not route as an ordinary managed assembly; rehydration and platform limits remain explicit | `ghidra-nativeaot.md`, `windows-ghidra-p0.md` |
| Android APK | `inspect_android_package`, class/method inspection, `trace_android_references`; resource decoding when useful | Caller-supplied JADX/Java for code route; Apktool is separate. No implicit app installation | `android-analysis.md`, `apktool-resource-analysis.md` |
| Android device | `inspect_adb_client`, device/package discovery; explicitly selected acquisition or runtime tools | ADB/device authorization; acquisition, launch and mutation have distinct effects | `adb-device-analysis.md` |
| Harmony / Apple mobile packages | Container inventory and advertised application-graph projection | Graph projection uses matching authenticated facts; it does not recover absent code | `harmony-analysis.md`, `apple-application-analysis.md` |
| Flutter / Dart AOT | `identify_flutter_build`, `inspect_dart_aot`; selected native follow-up | APK/build identity first; recovered snapshot semantics depend on supported SDK/layout | `flutter-analysis.md` |
| Unity IL2CPP | `inspect_il2cpp_metadata`, then selected native code analysis | Metadata names do not by themselves map to executable bodies | `il2cpp-metadata.md` |
| Godot PCK / embedded packs | Artifact inventory/extraction through advertised Godot support | Assets/scripts/native engine are distinct layers; inventory does not imply script decompilation | `godot-pck.md` |
| Firmware | `inspect_firmware_regions`, selected `extract_firmware`, then each recovered format's route | Binwalk/Unblob on supported Linux hosts; record partitions, compression and unresolved regions | `firmware-analysis.md` |
| Raw bytes / DOS / embedded ISAs | Explicit native provider, loader profile, architecture/base/entry supplied from evidence | Never guess load addresses or ISA. Ghidra host/admission limits apply | `raw-binary.md`, `ghidra-dos.md`, `ghidra-mips.md`, `ghidra-ppc.md`, `ghidra-riscv.md`, `ghidra-psp.md` |
| Go executable | `inspect_go_binary` then native analysis if needed | Built-in metadata inspection needs no Go/compiler/decompiler. Missing metadata does not prove non-Go | `go-binaries.md` |
| Rust executable | `inspect_rust_binary` then native analysis if needed | Embedded cargo-auditable dependencies only where present; inferred rustc identity remains inference | `rust-binaries.md` |
| WebAssembly | `inspect_wasm_artifact`, `compare_wasm_interfaces` | WABT/profile availability; imports/exports, memories and host glue have separate evidence | `wasm-artifacts.md` |
| EVM bytecode | `inspect_evm_interface` with explicit carrier encoding | Linux/prlimit and bundled EVMole profile; selector candidates are not recovered source or proof of live contract behavior | `evm-bytecode.md`, `solidity-metadata.md` |
| SQLite snapshot | `inspect_sqlite_database` schema first, selected table/columns only as needed | Native SQLite-capable Node version; preserve DB/WAL identity and snapshot consistency | `sqlite-databases.md` |
| HAR/SAZ/mitmproxy/qlog | `inspect_web_network_capture` | Saved observations only; do not fetch recorded URLs. Preserve producer and format limits | `web-network-captures.md` |
| PCAP and protocol fields | `inspect_packet_fields`, `inspect_packet_capture` | Caller-supplied TShark and supported Linux/prlimit; filtering/paging scope is explicit | `packet-captures.md`, `pcap-analysis.md` |
| Logic/signal recordings | `inspect_signal_decoders`, `decode_signal_recording` | Caller-supplied decoder tooling and channel mapping; captured signals are not a complete hardware design | `signal-recordings.md` |
| ELF layout / recorded core | `inspect_binary_layout`, `inspect_recorded_crash` | pwntools and supported layouts/hosts; historical PIDs do not select live processes | `binary-diagnostics.md`, `recorded-crashes.md` |
| Process / native UI / calls | Advertised process capture, `observe_native_ui`, `capture_native_ui_scenario`, `observe_native_calls` | Scope the actual launch/actions; platform-specific ownership and cleanup | `process-capture.md`, `native-investigation.md` |
| Instrumentation / debugger / external RE tools | Advertised Frida, GDB, Rizin, Cutter or objdump tools | Tool effects can include execution/mutation. Use only to answer a scoped architecture question | `frida-instrumentation.md`, `reverse-engineering-tools.md` |

## Extending coverage as REA evolves

Inspect newly advertised tools and their owning contracts/effects. Route by the
analyst question and actual artifact, not by an assumed universal graph. Record
the runtime version and selected provider in the report. Update this reference
only after checking the new tool's interface and limits.

Use extraction, recovery and decompilation for understanding when justified.
Reconstruction builders, target patches, annotations and unrelated device
administration are not required merely because REA exposes them. The skill covers
REA's target families without indiscriminately running every available operation.
