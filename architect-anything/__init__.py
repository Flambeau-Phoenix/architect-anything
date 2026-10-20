"""Architect Anything's portable skill and agent-facing command."""
__version__ = "1.0.0"


def main():
    import sys
    from pathlib import Path
    scripts = str(Path(__file__).resolve().parent/"scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from aa_cli import main as run
    return run()
