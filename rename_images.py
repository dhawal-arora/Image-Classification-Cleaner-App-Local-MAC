"""
Image Sorter
  ← / drag left   → Trash
  → / drag right  → Keep (then ↑ Important  ↓ Others)
  Space            → Move to password-protected Private DMG
"""
import base64
import io
import json
import queue
import re
import shutil
import sys
import subprocess
import threading
from pathlib import Path

import requests
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import messagebox, filedialog

MODEL = "qwen2.5vl"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif"}
SWIPE_THRESHOLD = 130
BG = "#111118"
PREFS_FILE = Path.home() / ".image_sorter_prefs.json"
PRIV_SPARSE = "Private.sparseimage"
PRIV_MOUNT  = "/tmp/image_sorter_private"


# ── Prefs ─────────────────────────────────────────────────────────────────────

def load_prefs() -> dict:
    try:
        return json.loads(PREFS_FILE.read_text())
    except Exception:
        return {}


def save_prefs(src: Path, dest: Path):
    PREFS_FILE.write_text(json.dumps({"src": str(src), "dest": str(dest)}, indent=2))



# ── Private DMG ───────────────────────────────────────────────────────────────

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


# ── Password dialog ───────────────────────────────────────────────────────────

def ask_password(root: tk.Tk, title: str, prompt: str,
                 confirm: bool = False) -> str | None:
    dialog = tk.Toplevel(root)
    dialog.title(title)
    dialog.configure(bg=BG)
    dialog.geometry("420x230" if confirm else "420x165")
    dialog.resizable(False, False)
    dialog.grab_set()
    dialog.lift()

    result = [None]

    tk.Label(dialog, text=prompt, bg=BG, fg="#ccc",
             font=("Helvetica Neue", 13), wraplength=380).pack(pady=(18, 6), padx=20)

    e1 = tk.Entry(dialog, show="*", font=("Helvetica Neue", 13),
                  bg="#222", fg="white", insertbackground="white",
                  relief="flat", width=28)
    e1.pack(pady=4)
    e1.focus_set()

    e2 = None
    if confirm:
        tk.Label(dialog, text="Confirm password", bg=BG, fg="#666",
                 font=("Helvetica Neue", 11)).pack(pady=(8, 2))
        e2 = tk.Entry(dialog, show="*", font=("Helvetica Neue", 13),
                      bg="#222", fg="white", insertbackground="white",
                      relief="flat", width=28)
        e2.pack(pady=4)

    err_lbl = tk.Label(dialog, text="", bg=BG, fg="#e05555",
                       font=("Helvetica Neue", 11))
    err_lbl.pack()

    def ok(e=None):
        pw = e1.get()
        if not pw:
            return
        if e2 is not None and pw != e2.get():
            err_lbl.config(text="Passwords do not match")
            return
        result[0] = pw
        dialog.destroy()

    e1.bind("<Return>", ok)
    if e2:
        e2.bind("<Return>", ok)
    dialog.bind("<Escape>", lambda e: dialog.destroy())

    tk.Label(dialog, text="  OK  ", bg="#333", fg="#ccc",
             font=("Helvetica Neue", 12), padx=16, pady=6,
             cursor="hand2").pack(pady=6)
    dialog.children[list(dialog.children)[-1]].bind("<Button-1>", ok)

    dialog.wait_window()
    return result[0]


# ── Helpers ───────────────────────────────────────────────────────────────────

def send_to_trash(path: Path):
    script = f'tell application "Finder" to delete POSIX file "{path}"'
    subprocess.run(["osascript", "-e", script], check=True)


VALID_CATEGORIES = {"faces", "screenshot", "unknown"}


def ai_classify(image_path: Path) -> tuple[str, str]:
    """Returns (slug, category). category is one of: faces | screenshot | unknown."""
    img = Image.open(image_path).convert("RGB")
    img.thumbnail((768, 768), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    data = base64.b64encode(buf.getvalue()).decode()
    r = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": MODEL,
            "stream": False,
            "prompt": (
                "Analyze this image. Reply with exactly two lines and nothing else.\n"
                "Line 1: describe the image in 3-6 words as a filename slug "
                "(lowercase English letters, numbers, hyphens only). "
                "Example: two-people-laughing-outside\n"
                "Line 2: category. Follow these steps in order and stop at the first match:\n"
                "  STEP 1 — Do you see any human face, even partially, even inside a screenshot? "
                "If YES output: faces\n"
                "  STEP 2 — Is this a screenshot of a phone or computer screen with NO human faces at all? "
                "If YES output: screenshot\n"
                "  STEP 3 — output: unknown\n"
                "A screenshot containing a face must be classified as faces, never as screenshot. "
                "Output only the two lines. No explanation."
            ),
            "images": [data],
        },
        timeout=90,
    )
    print(f"[AI status] {r.status_code}")
    print(f"[AI body]   {r.text[:300]}")
    r.raise_for_status()

    lines = [l.strip().lower() for l in r.json()["response"].strip().splitlines() if l.strip()]
    print(f"[AI lines] {lines}")

    slug = re.sub(r"[^a-z0-9]+", "-", lines[0]).strip("-") if lines else ""
    slug = slug or image_path.stem.lower()

    category = "unknown"
    if len(lines) >= 2:
        cat = re.sub(r"[^a-z]", "", lines[1])
        if cat in VALID_CATEGORIES:
            category = cat

    return slug, category


def safe_dest(folder: Path, stem: str, suffix: str) -> Path:
    dest = folder / (stem + suffix)
    n = 1
    while dest.exists():
        dest = folder / f"{stem}-{n}{suffix}"
        n += 1
    return dest


# ── App ───────────────────────────────────────────────────────────────────────

class ImageSorter:
    def __init__(self, root: tk.Tk, images: list, dest: Path):
        self.root = root
        self.images = images
        self.dest = dest
        self.important = dest / "Important"
        self.others = dest / "Others"
        for parent in (self.important, self.others):
            for sub in ("faces", "screenshot", "unknown"):
                (parent / sub).mkdir(parents=True, exist_ok=True)

        self.idx = 0
        self.drag_x0 = 0
        self.offset = 0.0
        self.locked = False
        self._absorb_release = False
        self.stats = dict(trashed=0, renamed=0, private=0)
        self._priv_password: str | None = None

        self._pil_orig: Image.Image | None = None
        self._tk_img: ImageTk.PhotoImage | None = None
        self._cat_widgets: list = []

        self._q: queue.Queue = queue.Queue()
        self._q_count = 0
        self._q_lock = threading.Lock()
        threading.Thread(target=self._queue_worker, daemon=True).start()

        self._build_ui()
        self._show_image()

    # ── Background worker ─────────────────────────────────────────────────

    def _queue_worker(self):
        while True:
            path, folder = self._q.get()
            try:
                slug, category = ai_classify(path)
            except Exception as ex:
                print(f"[AI error] {ex}")
                slug, category = path.stem.lower(), "unknown"

            subfolder = folder / category
            subfolder.mkdir(parents=True, exist_ok=True)
            dest = safe_dest(subfolder, slug, path.suffix.lower())
            try:
                path.rename(dest)
                print(f"[Done] {path.name} → {folder.name}/{category}/{dest.name}")
            except Exception as ex:
                print(f"[Move error] {ex}")

            with self._q_lock:
                self._q_count -= 1
                remaining = self._q_count

            self.root.after(0, lambda r=remaining: self._update_queue_label(r))
            self._q.task_done()

    def _enqueue(self, path: Path, folder: Path):
        with self._q_lock:
            self._q_count += 1
        self._q.put((path, folder))
        self._update_queue_label(self._q_count)

    def _update_queue_label(self, count: int):
        if count > 0:
            self.queue_lbl.config(text=f"⏳ {count} renaming in background", fg="#888")
        else:
            self.queue_lbl.config(text="")

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.root.title("Image Sorter")
        self.root.configure(bg=BG)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = min(sw, 1080), min(sh, 820)
        self.root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        top_bar = tk.Frame(self.root, bg=BG)
        top_bar.pack(fill=tk.X, pady=(14, 0))

        self.top_lbl = tk.Label(top_bar, bg=BG, fg="#555",
                                font=("Helvetica Neue", 12))
        self.top_lbl.pack(side=tk.LEFT, expand=True)

        self.queue_lbl = tk.Label(top_bar, bg=BG, fg="#888",
                                  font=("Helvetica Neue", 11))
        self.queue_lbl.pack(side=tk.RIGHT, padx=20)

        self.cv = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        self.cv.pack(fill=tk.BOTH, expand=True, padx=24, pady=10)

        self.footer = tk.Frame(self.root, bg=BG)
        self.footer.pack(fill=tk.X, pady=(0, 14))
        self._set_footer_swipe()

        self.cv.bind("<ButtonPress-1>",   self._on_press)
        self.cv.bind("<B1-Motion>",       self._on_drag)
        self.cv.bind("<ButtonRelease-1>", self._on_release)

        self.root.bind("<Left>",  lambda _: self._kb("trash"))
        self.root.bind("<Right>", lambda _: self._kb("rename"))
        self.root.bind("<space>", lambda _: self._kb("private"))

    def _set_footer_swipe(self):
        for w in self.footer.winfo_children():
            w.destroy()
        for text, color in [("←  Trash", "#e05555"),
                             ("Space  Private", "#9b59b6"),
                             ("Keep & rename  →", "#4caf7d")]:
            tk.Label(self.footer, text=text, bg=BG, fg=color,
                     font=("Helvetica Neue", 11, "bold")).pack(side=tk.LEFT, expand=True)

    def _set_footer_category(self):
        for w in self.footer.winfo_children():
            w.destroy()
        for text, color in [("↑  Important", "#c0932a"), ("↓  Others", "#2a72c0")]:
            tk.Label(self.footer, text=text, bg=BG, fg=color,
                     font=("Helvetica Neue", 11, "bold")).pack(side=tk.LEFT, expand=True)

    # ── Image loading & rendering ─────────────────────────────────────────

    def _canvas_wh(self):
        self.cv.update_idletasks()
        return self.cv.winfo_width() or 960, self.cv.winfo_height() or 600

    def _load_pil(self):
        cw, ch = self._canvas_wh()
        try:
            img = Image.open(self.images[self.idx]).convert("RGBA")
            img.thumbnail((cw - 60, ch - 60), Image.LANCZOS)
            self._pil_orig = img
        except Exception:
            self._pil_orig = None

    def _render(self, offset: float):
        self.cv.delete("all")
        cw, ch = self._canvas_wh()
        cx, cy = cw // 2 + int(offset), ch // 2

        if self._pil_orig is None:
            self.cv.create_text(cx, cy, text="Could not load image",
                                fill="#444", font=("Helvetica Neue", 16))
            return

        angle = max(-20, min(20, offset / 11))
        rotated = self._pil_orig.rotate(-angle, resample=Image.BICUBIC, expand=False)
        iw, ih = rotated.size

        self._tk_img = ImageTk.PhotoImage(rotated)
        self.cv.create_image(cx, cy, image=self._tk_img)

        if offset < -25:
            strength = min(abs(offset) / SWIPE_THRESHOLD, 1.0)
            stipple = "gray75" if strength > 0.55 else ("gray50" if strength > 0.3 else "gray25")
            self.cv.create_rectangle(cx - iw // 2, cy - ih // 2,
                                     cx + iw // 2, cy + ih // 2,
                                     fill="#c0392b", stipple=stipple, outline="")
            if strength > 0.35:
                self.cv.create_text(cx, cy, text="TRASH", fill="white",
                                    font=("Helvetica Neue", 40, "bold"))
        elif offset > 25:
            strength = min(offset / SWIPE_THRESHOLD, 1.0)
            stipple = "gray75" if strength > 0.55 else ("gray50" if strength > 0.3 else "gray25")
            self.cv.create_rectangle(cx - iw // 2, cy - ih // 2,
                                     cx + iw // 2, cy + ih // 2,
                                     fill="#27ae60", stipple=stipple, outline="")
            if strength > 0.35:
                self.cv.create_text(cx, cy, text="KEEP", fill="white",
                                    font=("Helvetica Neue", 40, "bold"))

        p = self.images[self.idx]
        try:
            caption = str(p.relative_to(p.parents[1]))
        except Exception:
            caption = p.name
        self.cv.create_text(cw // 2, cy + ih // 2 + 16,
                            text=caption, fill="#444",
                            font=("Helvetica Neue", 10))

    def _show_image(self):
        if self.idx >= len(self.images):
            self._summary()
            return
        self.top_lbl.config(text=f"{self.idx + 1} / {len(self.images)}")
        self.locked = False
        self.offset = 0.0
        self._set_footer_swipe()
        self._load_pil()
        self._render(0)

    # ── Drag ─────────────────────────────────────────────────────────────

    def _on_press(self, e):
        if not self.locked:
            self.drag_x0 = e.x

    def _on_drag(self, e):
        if self.locked:
            return
        self.offset = float(e.x - self.drag_x0)
        self._render(self.offset)

    def _on_release(self, e):
        if self.locked:
            return
        if self._absorb_release:
            self._absorb_release = False
            return
        off = float(e.x - self.drag_x0)
        if abs(off) >= SWIPE_THRESHOLD:
            self._fly_out("trash" if off < 0 else "rename", off)
        else:
            self._spring_back(self.offset)

    # ── Keyboard ─────────────────────────────────────────────────────────

    def _kb(self, action: str):
        if self.locked:
            return
        if action == "trash":
            self._fly_out("trash", -SWIPE_THRESHOLD - 10)
        elif action == "rename":
            self._fly_out("rename", SWIPE_THRESHOLD + 10)
        elif action == "private":
            self._do_private(self.images[self.idx])

    # ── Animations ────────────────────────────────────────────────────────

    def _spring_back(self, start: float, step: int = 0, steps: int = 7):
        if step >= steps:
            self.offset = 0.0
            self._render(0)
            return
        pos = start * (1 - step / steps) ** 1.8
        self._render(pos)
        self.root.after(16, lambda: self._spring_back(start, step + 1, steps))

    def _fly_out(self, action: str, direction: float, step: int = 0, steps: int = 8):
        self.locked = True
        cw, _ = self._canvas_wh()
        target = (cw + 300) * (1 if direction > 0 else -1)
        if step >= steps:
            self._do_action(action)
            return
        t = (step / steps) ** 0.55
        pos = self.offset + (target - self.offset) * t
        self._render(pos)
        self.root.after(16, lambda: self._fly_out(action, direction, step + 1, steps))

    # ── Actions ───────────────────────────────────────────────────────────

    def _do_action(self, action: str):
        path = self.images[self.idx]
        if action == "trash":
            try:
                send_to_trash(path)
                self.stats["trashed"] += 1
            except Exception as ex:
                messagebox.showerror("Trash failed", str(ex))
            self.idx += 1
            self._show_image()
        elif action == "rename":
            self._category_screen(path)

    def _do_private(self, path: Path):
        self.locked = True

        # First time: create the encrypted DMG
        if not (self.dest / PRIV_SPARSE).exists():
            pw = ask_password(self.root, "Create Private folder",
                              "Set a password for your Private folder:",
                              confirm=True)
            if not pw:
                self.locked = False
                return
            try:
                create_private_dmg(self.dest, pw)
                self._priv_password = pw
            except Exception as ex:
                messagebox.showerror("Failed to create Private folder", str(ex))
                self.locked = False
                return

        # Ask for password once per session
        if not self._priv_password:
            pw = ask_password(self.root, "Unlock Private folder",
                              "Enter password to unlock Private folder:")
            if not pw:
                self.locked = False
                return
            self._priv_password = pw

        # Mount → copy → unmount
        try:
            mount = mount_private_dmg(self.dest, self._priv_password)
            dest_file = safe_dest(mount, path.stem, path.suffix.lower())
            shutil.copy2(str(path), str(dest_file))
            path.unlink()
            unmount_private_dmg()
            self.stats["private"] += 1
            print(f"[Private] {path.name} → Private folder")
        except Exception as ex:
            unmount_private_dmg()
            self._priv_password = None  # wrong password — ask again next time
            messagebox.showerror("Private folder failed", str(ex))
            self.locked = False
            return

        self.idx += 1
        self._show_image()

    # ── Category screen ───────────────────────────────────────────────────

    def _category_screen(self, path: Path):
        self.locked = True
        cw, ch = self._canvas_wh()
        self.cv.delete("all")

        if self._pil_orig:
            dim = self._pil_orig.copy()
            overlay = Image.new("RGBA", dim.size, (17, 17, 24, 190))
            dim = Image.alpha_composite(dim, overlay)
            self._tk_img = ImageTk.PhotoImage(dim)
            self.cv.create_image(cw // 2, ch // 2, image=self._tk_img)

        imp_lbl = tk.Label(self.root, text="↑   Important",
                           bg="#c0932a", fg="#ffffff",
                           font=("Helvetica Neue", 17, "bold"),
                           padx=40, pady=14, cursor="hand2")
        imp_lbl.place(relx=0.5, rely=0.2, anchor="center")
        imp_lbl.bind("<Button-1>", lambda _: self._pick_category(path, "important"))

        oth_lbl = tk.Label(self.root, text="↓   Others",
                           bg="#2a72c0", fg="#ffffff",
                           font=("Helvetica Neue", 17, "bold"),
                           padx=40, pady=14, cursor="hand2")
        oth_lbl.place(relx=0.5, rely=0.8, anchor="center")
        oth_lbl.bind("<Button-1>", lambda _: self._pick_category(path, "others"))

        self._cat_widgets = [imp_lbl, oth_lbl]
        self._set_footer_category()

        self.root.bind("<Up>",   lambda _: self._pick_category(path, "important"))
        self.root.bind("<Down>", lambda _: self._pick_category(path, "others"))

    def _pick_category(self, path: Path, category: str):
        if not self._cat_widgets:
            return

        folder = self.important if category == "important" else self.others
        self._enqueue(path, folder)
        self.stats["renamed"] += 1

        for w in self._cat_widgets:
            w.destroy()
        self._cat_widgets = []

        self.root.unbind("<Up>")
        self.root.unbind("<Down>")

        self._absorb_release = True
        self.locked = False
        self.idx += 1
        self._show_image()

    # ── Summary ───────────────────────────────────────────────────────────

    def _summary(self):
        self.cv.delete("all")
        for seq in ("<ButtonPress-1>", "<B1-Motion>", "<ButtonRelease-1>"):
            self.cv.unbind(seq)
        cw, ch = self._canvas_wh()
        self.top_lbl.config(text="Done!")

        entries = [
            ("All done!", "#ffffff", 30, "bold", 0),
            (f"🗑   {self.stats['trashed']} sent to Trash", "#e05555", 15, "normal", 56),
            (f"✅  {self.stats['renamed']} renamed & moved", "#4caf7d", 15, "normal", 92),
            (f"🔒  {self.stats['private']} moved to Private DMG", "#9b59b6", 15, "normal", 128),
        ]
        for text, color, size, weight, dy in entries:
            self.cv.create_text(cw // 2, ch // 2 - 90 + dy,
                                text=text, fill=color,
                                font=("Helvetica Neue", size, weight))

        tk.Button(self.cv, text="  Close  ", bg="#222", fg="#aaa",
                  relief="flat", font=("Helvetica Neue", 13),
                  padx=16, pady=8, cursor="hand2",
                  command=self.root.quit).place(relx=0.5, rely=0.78, anchor="center")


# ── Entry ─────────────────────────────────────────────────────────────────────

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
