"""Architect Anything's portable skill and agent-facing command."""
__version__ = "1.2.0"


def _run(module):
    import sys
    from pathlib import Path
    scripts = str(Path(__file__).resolve().parent/"scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    return __import__(module).main()


def main():
    return _run("aa_cli")


def mcp_main():
    return _run("aa_mcp")
