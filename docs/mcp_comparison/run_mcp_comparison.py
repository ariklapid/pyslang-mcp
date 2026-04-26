"""Regenerate the docs-hosted MCP comparison benchmark report."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
REPO = THIS_DIR.parents[1]
SCRIPT = REPO / "scripts" / "run_mcp_comparison.py"

if "--output-dir" not in sys.argv:
    sys.argv.extend(["--output-dir", str(THIS_DIR)])

runpy.run_path(str(SCRIPT), run_name="__main__")
