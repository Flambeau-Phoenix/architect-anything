# Contributing

Keep the skill focused on explaining existing architecture from evidence.
Prefer a targeted workflow improvement over adding universal rules for one case.

## Local checks

Python 3.10+ is sufficient; no third-party Python packages are required.

~~~sh
python scripts/check_release.py
python -m unittest discover -s architect-anything/tests -v
python scripts/generate_demo.py --output .demo
python scripts/generate_focus_demo.py --output .cli-demo
~~~

Open .demo/reports/index.html to inspect the report. When changing presentation,
check desktop and narrow layouts, both themes, navigation/search, diagrams,
evidence links and print output.
Also inspect .cli-demo/reports/index.html for the focused-answer workflow.

Keep each report-model change consistent with its schema, validator, renderer,
documentation and meaningful behavioral tests.
Preserve the CLI's JSON/error contract and test the installed console entry point
when changing package metadata or command dispatch.

~~~sh
python -m pip install .
python scripts/smoke_installed_cli.py
~~~

## REA and evidence

Use actual tool contracts and provider results. Distinguish source-derived facts,
runtime observations, interpretations and unknowns. A simulated provider or a
passing report test does not establish real-engine support.

When adding a route, record the REA version, required provider/OS and remaining
limits. Do not add global setup or engine installations to the ordinary report
workflow.

## Public artifacts

Use synthetic or explicitly shareable fixtures. Keep credentials, machine
configuration, private paths, raw customer evidence, generated reports and
provider binaries out of commits. Review preview images as well as text.

Do not publish snapshots that point into a private checkout. Reproduce demos
locally instead.

## Issues and changes

Describe the concrete request, observed behavior, relevant versions, and the
smallest shareable reproducer. State which checks actually ran and which did not.
Preserve upstream attribution when adapting REA material.
