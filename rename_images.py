"""
Image Sorter
  ← / drag left   → Trash
  → / drag right  → Keep (then ↑ Important  ↓ Others)
  Space            → Move to password-protected Private DMG
"""
import sys
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, filedialog

from config import IMAGE_EXTS
from prefs import load_prefs, save_prefs
from sorter import ImageSorter


def pick_folders() -> tuple[Path, Path]:
    probe = tk.Tk()
    probe.withdraw()
    probe.update()

    messagebox.showinfo("Step 1 of 2", "Select the folder that contains your images.")
    src_str = filedialog.askdirectory(title="Source — folder containing images")
    if not src_str:
        sys.exit(0)

    messagebox.showinfo("Step 2 of 2", "Select the destination folder.\nImportant/ and Others/ will be created inside it.")
    dest_str = filedialog.askdirectory(title="Destination — where sorted images will go")
    if not dest_str:
        sys.exit(0)

    probe.destroy()
    return Path(src_str).resolve(), Path(dest_str).resolve()


def main():
    prefs = load_prefs()
    src_str = prefs.get("src", "")
    dest_str = prefs.get("dest", "")

    if src_str and dest_str and Path(src_str).is_dir() and Path(dest_str).is_dir():
        probe = tk.Tk()
        probe.withdraw()
        probe.update()
        reuse = messagebox.askyesno(
            "Use last folders?",
            f"Source:\n{src_str}\n\nDestination:\n{dest_str}\n\nUse these again?"
        )
        probe.destroy()
        if reuse:
            src, dest = Path(src_str), Path(dest_str)
        else:
            src, dest = pick_folders()
    else:
        src, dest = pick_folders()

    save_prefs(src, dest)

    if not src.is_dir():
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("Error", f"Not a directory:\n{src}")
        sys.exit(1)

    images = sorted(p for p in src.rglob("*") if p.suffix.lower() in IMAGE_EXTS)
    if not images:
        root = tk.Tk(); root.withdraw()
        messagebox.showinfo("No images", f"No images found in:\n{src}")
        sys.exit(0)

    root = tk.Tk()
    ImageSorter(root, images, dest)
    root.mainloop()


if __name__ == "__main__":
    main()
