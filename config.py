from pathlib import Path

MODEL = "qwen2.5vl"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif"}
SWIPE_THRESHOLD = 130
BG = "#111118"
PREFS_FILE = Path.home() / ".image_sorter_prefs.json"
PRIV_SPARSE = "Private.sparseimage"
PRIV_MOUNT  = "/tmp/image_sorter_private"
