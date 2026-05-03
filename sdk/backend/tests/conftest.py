"""Shared pytest fixtures."""

import sys
from pathlib import Path

# Ensure the backend package root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
