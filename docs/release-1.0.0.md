# Architect Anything 1.0.0

Prepared for the first public release; not yet published.

Architect Anything turns source projects and finished products into navigable
architecture reports. It explains purpose, structure, important behavior and
change history while retaining the evidence and limits behind its findings.

## Included

- Catch-up reports for owners and focused explanations of selected app behavior.
- An installable agent CLI with resumable investigation workspaces and JSON contracts.
- Portable agent skill, routing references and REA integration guidance.
- Standard-library Python helpers for inventory, validation, rendering,
  comparisons, snapshots and installation.
- Offline HTML and Markdown with evidence-linked diagrams.
- Reproducible whole-project/focused demos, preview images, behavioral tests and CI.

## Runtime requirements

Python 3.10+. REA and applicable analysis engines are separate dependencies for
investigations that require them. Installation does not provision MCP or engines.
Source investigation does not require a native decompiler.

## Validation

See [validation scope](validation.md). Core tests and local REA integration have
passed in the documented environment. GitHub Actions is prepared; hosted CI is
pending publication of the repository.

## Release artifacts

Use the release builder after reviewing the source:

~~~sh
python scripts/build_release.py
~~~

It validates the repository and builds the portable skill ZIP, SHA-256 checksum
and file manifest under dist/. Personal settings and provider/runtime binaries
are excluded. The builder does not create a Git commit, tag, remote or GitHub
release.

For an installable Python wheel, build it separately:

~~~sh
python -m pip wheel --no-deps --wheel-dir dist .
~~~

The wheel installs the architect-anything console command and bundled skill data.
The ZIP supports direct skill installation and portable Python invocation.
