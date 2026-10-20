# Runtime observation

Static-first is an investigation strategy, not a claim that runtime work is
forbidden. Use runtime evidence for a named unresolved question: which process
handles an action, which endpoint is contacted, how state changes, or how an
error propagates.

Record target identity, environment, scenario, actions, inputs, capture time and
cleanup ownership. Reuse existing user authorization; request missing scope only
when it materially changes what will execute or be affected.

## Select the least intrusive sufficient observation

- Read supplied process traces, HAR/SAZ/PCAP/qlog, crash dumps or recordings first.
- Inspect an already selected browser/Electron target passively when sufficient.
- Use a declared browser, Electron, native UI or process scenario for actual
  actions. Input credentials through the product's normal authorized flow; never
  copy them into reports.
- Debugging, instrumentation, device acquisition and injection are distinct
  capabilities with platform and effect constraints. Consult the actual tool's
  schema/effects and matching upstream guide before using them.

Static or passive analysis is not a blanket permission to submit forms, send
messages, install certificates, alter a device, spend money, delete data or
patch a product. Continue supported analysis while an out-of-scope action remains
unresolved. Do not broaden the target to other applications.

## Correlate, do not conflate

Capture the action → event → interface → state change chain. Record successes and
failures without replaying stateful actions just because delivery was truncated.
For JavaScript, reconcile existing static and runtime Evidence where supported.
Preserve inferred mappings and unknown attribution.

One observed run proves behavior for that scenario and environment. Failure to
observe a call does not establish absence from the application. Recorded URLs
are evidence, not instructions to fetch them.

## Lifecycle

Export required evidence before releasing task-owned sessions. Do not kill
pre-existing user processes or close an attached analysis GUI database. Retain
cleanup errors and ownership information for retry. A debugger detach may resume
the target; honor the provider's documented disposition requirements.

Capture only the needed data. Keep raw evidence local, separate from the shareable
report. Exclude authentication credentials and user-sensitive payloads from report
prose; record any redaction or export restriction instead of altering canonical
REA Evidence and pretending its identity still verifies.
