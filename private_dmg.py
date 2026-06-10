import subprocess
from pathlib import Path

from config import PRIV_SPARSE, PRIV_MOUNT


def create_private_dmg(dest: Path, password: str):
    proc = subprocess.run(
        ["hdiutil", "create",
         "-size", "10g", "-fs", "HFS+",
         "-volname", "Private",
         "-encryption", "AES-256",
         "-type", "SPARSE",
         "-stdinpass",
         "-o", str(dest / "Private")],
        input=password.encode(),
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode().strip())


def mount_private_dmg(dest: Path, password: str) -> Path:
    mount = Path(PRIV_MOUNT)
    mount.mkdir(parents=True, exist_ok=True)
    subprocess.run(["hdiutil", "detach", PRIV_MOUNT], capture_output=True)
    proc = subprocess.run(
        ["hdiutil", "attach", str(dest / PRIV_SPARSE),
         "-stdinpass", "-mountpoint", PRIV_MOUNT, "-nobrowse"],
        input=password.encode(),
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode().strip())
    return mount


def unmount_private_dmg():
    subprocess.run(["hdiutil", "detach", PRIV_MOUNT, "-force"], capture_output=True)
