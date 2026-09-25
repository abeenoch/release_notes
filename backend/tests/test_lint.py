"""Lint gate that runs inside the existing CI test step.

.github/workflows/* can't be edited from this machine — the deploy key is
denied by GitHub for workflow files without the `workflow` scope — so the
ruff gate lives here instead: CI's "Run backend tests" step executes it like
any other test, and ruff ships in requirements.txt. Same enforcement, no
workflow edit needed. (Move it into the workflow proper if a token with the
workflow scope ever becomes available.)
"""
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent


def test_ruff_is_clean():
    proc = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "app", "tests"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        "ruff found issues (fix locally with `ruff check app tests --fix`):\n"
        f"{proc.stdout}{proc.stderr}"
    )
