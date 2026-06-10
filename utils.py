import subprocess
from pathlib import Path


def send_to_trash(path: Path):
    script = f'tell application "Finder" to delete POSIX file "{path}"'
    subprocess.run(["osascript", "-e", script], check=True)


def safe_dest(folder: Path, stem: str, suffix: str) -> Path:
    dest = folder / (stem + suffix)
    n = 1
    while dest.exists():
        dest = folder / f"{stem}-{n}{suffix}"
        n += 1
    return dest
