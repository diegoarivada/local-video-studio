"""B-roll: stock video from Pixabay (free key, commercial use OK, no attribution required) and generated title cards.

Pixabay asks API users to cache searches for 24 hours and download what they use instead of hotlinking. Both happen here.
"""

import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://pixabay.com/api/videos/"
UA = {"User-Agent": "local-video-studio/0.1 (+https://github.com/diegoarivada/local-video-studio)"}
ALLOWED_HOSTS = ("pixabay.com", "cdn.pixabay.com")
MAX_DOWNLOAD = 200 * 1024 * 1024
DAY = 24 * 3600


class Pixabay:
    def __init__(self, key: str, cache: Path, log=print):
        self.key, self.cache, self.log = key, Path(cache), log
        self.cache.mkdir(parents=True, exist_ok=True)
        self.used: set[int] = set()
        self.credits: dict[int, str] = {}

    def _get(self, url: str, timeout=30) -> bytes:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            n = int(r.headers.get("Content-Length") or 0)
            if n > MAX_DOWNLOAD:
                raise ValueError("file too large")
            return r.read(MAX_DOWNLOAD + 1)

    def search(self, query: str) -> list[dict]:
        cached = self.cache / f"q-{hashlib.sha1(query.lower().encode()).hexdigest()[:16]}.json"
        if cached.exists() and time.time() - cached.stat().st_mtime < DAY:
            return json.loads(cached.read_text(encoding="utf-8"))
        qs = urllib.parse.urlencode({"key": self.key, "q": query[:100], "per_page": 20, "safesearch": "true",
                                     "min_width": 1280})
        try:
            hits = json.loads(self._get(f"{API}?{qs}"))["hits"]
        except Exception as e:  # never print the URL: it contains the key
            self.log(f"  Pixabay search failed for '{query}': {type(e).__name__}")
            return []
        time.sleep(0.7)   # stay far below 100 requests/minute
        cached.write_text(json.dumps(hits), encoding="utf-8")
        return hits

    def clip(self, queries: list[str], min_seconds=3.0):
        """First unused clip for any of the queries, downloaded to the cache. Returns a path or None."""
        for q in queries:
            for h in self.search(q):
                if h["id"] in self.used or h.get("duration", 0) < min_seconds:
                    continue
                v = h["videos"].get("large") or {}
                if not v.get("url") or v.get("width", 0) < 1920:
                    v = h["videos"].get("medium") or {}
                url = v.get("url", "")
                if urllib.parse.urlparse(url).hostname not in ALLOWED_HOSTS:
                    continue
                path = self.cache / f"pixabay-{h['id']}.mp4"
                if not path.exists():
                    try:
                        data = self._get(url, timeout=120)
                    except Exception as e:
                        self.log(f"  download failed ({type(e).__name__}), trying another clip")
                        continue
                    path.write_bytes(data)
                self.used.add(h["id"])
                self.credits[h["id"]] = h.get("user", "Pixabay")
                return path
        return None


def _font(size: int):
    from PIL import ImageFont
    for name in ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf", "Helvetica.ttc", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _wrap(draw, text, font, width):
    lines, cur = [], ""
    for w in text.split():
        cand = f"{cur} {w}".strip()
        if draw.textlength(cand, font=font) <= width:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])


def card(text: str, path: Path, size=(1920, 1080), colors=("#0a66c2", "#e63946"), sub=""):
    """A gradient title card. Used for chapter titles and whenever no stock clip fits."""
    import numpy as np
    from PIL import Image, ImageDraw
    w, h = size
    c1 = np.array([int(colors[0][i:i + 2], 16) for i in (1, 3, 5)], float)
    c2 = np.array([int(colors[1][i:i + 2], 16) for i in (1, 3, 5)], float)
    t = np.linspace(0, 1, w)[None, :] * 0.7 + np.linspace(0, 1, h)[:, None] * 0.3
    img = Image.fromarray((c1 + (c2 - c1) * t[..., None]).astype(np.uint8))
    d = ImageDraw.Draw(img)
    font = _font(int(h * 0.09))
    lines = _wrap(d, text, font, int(w * 0.8))[:4]
    lh = int(h * 0.11)
    y = (h - lh * len(lines)) // 2 - (lh // 3 if sub else 0)
    for line in lines:
        d.text(((w - d.textlength(line, font=font)) / 2 + 4, y + 4), line, font=font, fill=(0, 0, 0))
        d.text(((w - d.textlength(line, font=font)) / 2, y), line, font=font, fill=(255, 255, 255))
        y += lh
    if sub:
        f2 = _font(int(h * 0.04))
        d.text(((w - d.textlength(sub, font=f2)) / 2, y + lh // 4), sub, font=f2, fill=(255, 255, 255))
    img.save(path)
    return path


def thumbnail(title: str, frame: Path | None, path: Path, colors=("#0a66c2", "#e63946")):
    """1280x720: a darkened frame from the video (or a gradient) with big title text."""
    from PIL import Image, ImageDraw, ImageEnhance
    size = (1280, 720)
    if frame and Path(frame).exists():
        img = ImageEnhance.Brightness(Image.open(frame).convert("RGB").resize(size)).enhance(0.45)
    else:
        card("", path, size, colors)
        img = Image.open(path)
    d = ImageDraw.Draw(img)
    font = _font(92)
    lines = _wrap(d, title.upper(), font, 1150)[:3]
    y = 720 - 70 - 105 * len(lines)
    d.rectangle([0, y - 30, 22, 720 - 50], fill=colors[1])
    for line in lines:
        d.text((58, y + 5), line, font=font, fill=(0, 0, 0))
        d.text((54, y), line, font=font, fill=(255, 255, 255))
        y += 105
    img.save(path, quality=92)
    return path


def pixabay_key() -> str:
    return os.environ.get("PIXABAY_API_KEY", "").strip()
