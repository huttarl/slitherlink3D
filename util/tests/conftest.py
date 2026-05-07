"""Make util/ importable from the tests subdirectory.

Without this, `from slisolver import is_valid_loop` would fail because
util/ has no __init__.py and isn't on sys.path when pytest runs from the
repo root.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
