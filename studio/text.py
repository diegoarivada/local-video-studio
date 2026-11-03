"""Pure text and timing helpers: sentences, caption timing, SRT/ASS, chapters. No heavy imports (tested in CI)."""

import re
import unicodedata

WORDS_PER_MIN = 150


def clean(text: str) -> str:
    """Make model text safe to read aloud: no markdown, list markers, or dashes that TTS reads badly."""
    text = re.sub(r"^\s*#+\s.*$", "", str(text), flags=re.M)
    text = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", text, flags=re.M)
    text = re.sub(r"\*\*|__|`", "", text)
    text = re.sub(r"\s*[—–]\s*", ", ", text)
    return " ".join(text.split()).strip().strip('"')


def split_sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", " ".join(str(text).split())) if s]


def group_sentences(sentences: list[str], min_chars=60, max_chars=280) -> list[str]:
    """Merge very short sentences with the next one so each TTS call (and each shot) has natural length.
    Sentences longer than max_chars are split at commas first (TTS models drift on very long inputs)."""
    pieces = []
    for s in sentences:
        while len(s) > max_chars and ", " in s[:max_chars]:
            cut = s[:max_chars].rindex(", ") + 1
            pieces.append(s[:cut])
            s = s[cut:].strip()
        pieces.append(s)
    out, cur = [], ""
    for s in pieces:
        cand = f"{cur} {s}".strip()
        if cur and len(cand) > max_chars:
            out.append(cur)
            cur = s
        else:
            cur = cand
        if len(cur) >= min_chars:
            out.append(cur)
            cur = ""
    if cur:
        if out and len(out[-1]) + len(cur) < max_chars:
            out[-1] = f"{out[-1]} {cur}"
        else:
            out.append(cur)
    return out


def caption_events(text: str, start: float, end: float, words_per=3) -> list[tuple[float, float, str]]:
    """Split a spoken chunk into short caption groups, timed by character share of the chunk's real duration."""
    words = text.split()
    if not words or end <= start:
        return []
    groups = [" ".join(words[i:i + words_per]) for i in range(0, len(words), words_per)]
    total = sum(len(g) + 1 for g in groups)
    out, t = [], start
    for g in groups:
        d = (end - start) * (len(g) + 1) / total
        out.append((t, t + d, g))
        t += d
    return out


def _hms(t: float):
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return int(h), int(m), s


def ts_srt(t: float) -> str:
    h, m, s = _hms(t)
    return f"{h:02}:{m:02}:{int(s):02},{int(round((s % 1) * 1000)) % 1000:03}"


def ts_ass(t: float) -> str:
    h, m, s = _hms(t)
    return f"{h}:{m:02}:{s:05.2f}"


def to_srt(events) -> str:
    return "\n".join(f"{i}\n{ts_srt(a)} --> {ts_srt(b)}\n{txt}\n" for i, (a, b, txt) in enumerate(events, 1))


ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font},76,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,5,2,2,80,80,110,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def to_ass(events, font="Arial") -> str:
    def esc(s):
        return s.replace("\\", "").replace("{", "(").replace("}", ")")
    lines = [f"Dialogue: 0,{ts_ass(a)},{ts_ass(b)},Caption,,0,0,0,,{esc(t)}" for a, b, t in events]
    return ASS_HEADER.format(font=font) + "\n".join(lines) + "\n"


def chapters(starts: list[tuple[float, str]], min_gap=10.0) -> list[str]:
    """YouTube chapters: first at 0:00, at least 3, each at least 10 s apart. Returns [] if that isn't possible."""
    kept = []
    for t, title in starts:
        t = 0.0 if not kept else t
        if kept and t - kept[-1][0] < min_gap:
            continue
        kept.append((t, title))
    if len(kept) < 3:
        return []

    def fmt(t):
        h, m, s = _hms(t)
        return f"{h}:{m:02}:{int(s):02}" if h else f"{m}:{int(s):02}"
    return [f"{fmt(t)} {title}" for t, title in kept]


def slugify(s: str, n=60) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:n].strip("-") or "video"


def words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text))
