#!/usr/bin/env python3
"""
tare.tools Graph Ops — Standalone deterministic Work Graph & DAG Backlog CLI.
"""
from __future__ import annotations
import sys
from pathlib import Path

# Ensure src/ is on python path when running script directly
_src_dir = Path(__file__).resolve().parent / "src"
_src_text = str(_src_dir)
if _src_text in sys.path:
    sys.path.remove(_src_text)
sys.path.insert(0, _src_text)

from graph_backlog.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
