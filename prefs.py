import json
from pathlib import Path

from config import PREFS_FILE


def load_prefs() -> dict:
    try:
        return json.loads(PREFS_FILE.read_text())
    except Exception:
        return {}


def save_prefs(src: Path, dest: Path):
    PREFS_FILE.write_text(json.dumps({"src": str(src), "dest": str(dest)}, indent=2))
