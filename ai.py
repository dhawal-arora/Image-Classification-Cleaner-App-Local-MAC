import base64
import io
import re
from pathlib import Path

import requests
from PIL import Image

from config import MODEL

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
