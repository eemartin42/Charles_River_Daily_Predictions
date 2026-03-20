"""Resolved paths for the backend package (independent of process cwd)."""

from pathlib import Path

# backend/src/paths.py -> backend/
BACKEND_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = BACKEND_ROOT / "models"
CACHE_DIR = BACKEND_ROOT / "cache_data"
