#!/usr/bin/env python3
"""Run the operator launch QA smoke test.

This wraps the automated checklist in tests/test_operator_manual_qa_smoke.py so
operators can run the same smoke flow without remembering the pytest path.
"""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = "." + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    return subprocess.call([sys.executable, "-m", "pytest", "-q", "tests/test_operator_manual_qa_smoke.py"], env=env)


if __name__ == "__main__":
    raise SystemExit(main())
