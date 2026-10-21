## What and why

<!-- The concrete change and the problem it solves. -->

## Checks

- [ ] `python scripts/check_release.py`
- [ ] `python -m unittest discover -s architect-anything/tests -v`
- [ ] Docs, schema, validator and renderer agree if the report model changed
- [ ] CLI JSON and exit-code contract preserved (or the change is called out below)
- [ ] CHANGELOG updated for user-visible changes
- [ ] No private paths, credentials, raw evidence or generated reports in the diff

## Evidence

<!-- State what you actually ran and what you could not. Real-engine (REA) support
needs real tool output; a simulated provider does not establish it. -->
