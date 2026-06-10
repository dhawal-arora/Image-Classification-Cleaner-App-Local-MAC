# Image Sorter

A local desktop tool that lets you swipe through images one by one and sort them into folders. Images are renamed and categorised using AI (via Ollama) entirely on your machine — nothing leaves your device.

---

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) installed with the `qwen2.5vl` model
- The following Python packages:

```
pip install pillow requests
```

---

## Setup

### 1. Install Ollama

Download and install Ollama from https://ollama.com (use the official installer, not Homebrew), then pull the vision model:

```
ollama pull qwen2.5vl
```

### 2. Ollama runs automatically

The official Ollama app starts itself in the background. You do not need to run `ollama serve` manually.

### 3. Install Python dependencies

```
pip install pillow requests
```

---

## Running

```
python rename_images.py
```

On first launch two folder pickers appear:

1. **Source folder** — the folder containing your images (all subfolders are scanned recursively)
2. **Destination folder** — where sorted images will be moved to

On subsequent launches the app remembers your last folders and asks if you want to reuse them.

---

## Controls

Each image is shown one at a time. Use swipe/drag or keyboard:

| Action | Gesture | Key |
|---|---|---|
| **Trash** | Drag left | `←` |
| **Keep & rename** | Drag right | `→` |
| **Private** | — | `Space` |

### Drag right — Keep & rename
- The screen dims and two options appear
- Press `↑` or click **Important** to move to the Important folder
- Press `↓` or click **Others** to move to the Others folder
- AI generates a descriptive filename in the background — you do not need to wait, just keep swiping
- Images are auto-categorised into `faces`, `screenshot`, or `unknown` subfolders

### Drag left — Trash
- The image is sent to the macOS Trash

### Space — Private
- The image is moved into a password-protected encrypted folder (`Private.sparseimage`)
- First press: you set a password — this creates the encrypted file
- Subsequent presses: password is asked once per session then cached
- To browse private images: double-click `Private.sparseimage` in Finder, enter your password, it opens like a regular folder

---

## AI Classification

When you keep an image, the AI (running locally via Ollama) does two things:

1. **Generates a filename** — a 3–6 word descriptive slug, e.g. `two-people-laughing-outside.jpg`
2. **Picks a subcategory** — using this priority order:
   - `faces` — any human face is visible (even inside a screenshot)
   - `screenshot` — looks like a phone/computer screen with no faces
   - `unknown` — everything else, or if AI fails

All of this happens in a background queue. A counter in the top-right (`⏳ N renaming in background`) shows pending items.

---

## Output Folder Structure

```
destination/
├── Important/
│   ├── faces/
│   ├── screenshot/
│   └── unknown/
├── Others/
│   ├── faces/
│   ├── screenshot/
│   └── unknown/
└── Private.sparseimage   ← password-protected encrypted folder
```

---

## Summary

At the end of the session a summary screen shows totals for trashed, renamed, and moved to Private.
