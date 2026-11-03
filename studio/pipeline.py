"""Topic -> script.json -> narration -> shots -> video. Each stage writes files into one project folder, so you can
edit script.json and re-render without rewriting, or swap the voice without re-downloading footage."""

import json
import time
from pathlib import Path

from . import render, text, visuals

SECTION_PAUSE, SENTENCE_PAUSE = 0.7, 0.25


def new_project(out_root: Path, title: str) -> Path:
    d = Path(out_root) / f"{time.strftime('%Y%m%d-%H%M')}-{text.slugify(title, 40)}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_script(project: Path, plan: dict):
    (project / "script.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    md = [f"# {plan['title']}", "", plan.get("description", ""), ""]
    for s in plan["sections"]:
        md += [f"## {s['heading']}", "", s.get("narration", ""), ""]
    (project / "script.md").write_text("\n".join(md), encoding="utf-8")


def plan_shots(plan: dict) -> list[dict]:
    """One shot per spoken chunk: [{"section", "text", "queries", "first"}]. The first chunk of a section is marked
    so a chapter card can open it."""
    shots = []
    for si, sec in enumerate(plan["sections"]):
        chunks = text.group_sentences(text.split_sentences(sec.get("narration", "")))
        q = sec.get("stock_queries") or [sec["heading"]]
        for ci, c in enumerate(chunks):
            shots.append({"section": si, "text": c, "queries": q[ci % len(q):] + q[:ci % len(q)], "first": ci == 0})
    if not shots:
        raise ValueError("script.json has no narration to read.")
    return shots


def narrate(project: Path, shots: list[dict], voice_ref=None, exaggeration=0.5, cfg_weight=0.5, device="auto", log=print):
    """Voice every shot, stitch with pauses, and record each shot's start/end in the narration."""
    import numpy as np
    import soundfile as sf
    from . import voice
    clips, sr = voice.synthesize([s["text"] for s in shots], voice_ref, exaggeration, cfg_weight, device, log=log)
    parts, t = [], 0.0
    for i, (shot, a) in enumerate(zip(shots, clips)):
        a = voice.trim_silence(a, sr)
        shot["start"], shot["end"] = t, t + len(a) / sr
        t = shot["end"]
        parts.append(a)
        if i + 1 < len(shots):
            gap = SECTION_PAUSE if shots[i + 1]["first"] else SENTENCE_PAUSE
            parts.append(np.zeros(int(gap * sr), np.float32))
            t += gap
    sf.write(str(project / "narration.wav"), np.concatenate(parts), sr, subtype="PCM_16")
    (project / "shots.json").write_text(json.dumps(shots, indent=2), encoding="utf-8")
    return shots


def build_video(project: Path, plan: dict, shots: list[dict], music=None, captions=True, log=print) -> Path:
    seg_dir = project / "segments"
    seg_dir.mkdir(exist_ok=True)
    key = visuals.pixabay_key()
    stock = visuals.Pixabay(key, project.parent / ".cache" / "pixabay", log) if key else None
    if not stock:
        log("No PIXABAY_API_KEY set: using title cards instead of stock footage.")
    segments = []
    for i, s in enumerate(shots):
        # Each shot lasts until the next one starts, so pauses are covered by picture too.
        dur = (shots[i + 1]["start"] if i + 1 < len(shots) else s["end"] + 0.5) - s["start"]
        out = seg_dir / f"{i:04}.mp4"
        if not out.exists():
            heading = plan["sections"][s["section"]]["heading"]
            chapter_card = s["first"] and s["section"] > 0   # each new chapter opens on its title; the hook opens on footage
            src = stock.clip(s["queries"], min_seconds=min(dur, 4)) if stock and not chapter_card else None
            if src:
                render.clip_segment(src, dur, out)
            else:
                img = visuals.card(heading, seg_dir / f"{i:04}.png", sub=plan["title"] if i == 0 else "")
                render.still_segment(img, dur, out)
        segments.append(out)
        if (i + 1) % 10 == 0 or i + 1 == len(shots):
            log(f"  shots {i + 1}/{len(shots)}")
    video = project / "picture.mp4"
    render.concat(segments, video)
    events = [e for s in shots for e in text.caption_events(s["text"], s["start"], s["end"])]
    (project / "captions.srt").write_text(text.to_srt(events), encoding="utf-8")
    ass = project / "captions.ass"
    ass.write_text(text.to_ass(events), encoding="utf-8")
    final = project / f"{text.slugify(plan['title'])}.mp4"
    log("Rendering the final video...")
    render.final(video, project / "narration.wav", final, ass if captions else None, music)
    write_metadata(project, plan, shots, stock, music)
    try:
        render.frame(final, min(3.0, shots[-1]["end"] / 2), project / "frame.jpg")
        visuals.thumbnail(plan["title"], project / "frame.jpg", project / "thumbnail.jpg")
    except Exception as e:
        log(f"Thumbnail skipped: {e}")
    return final


def write_metadata(project: Path, plan: dict, shots: list[dict], stock, music):
    starts = []
    for s in shots:
        if s["first"]:
            starts.append((s["start"], plan["sections"][s["section"]]["heading"]))
    lines = [plan.get("description", ""), ""]
    ch = text.chapters(starts)
    if ch:
        lines += ["Chapters", *ch, ""]
    lines += ["Credits"]
    if stock and stock.credits:
        lines.append("Stock footage from Pixabay: " + ", ".join(sorted(set(stock.credits.values()))))
    if music:
        lines.append(f"Music: {Path(music).stem} (check its license and credit line)")
    lines += ["Narration voice generated with Chatterbox (Resemble AI).", "",
              "Reminder: in YouTube Studio, tick \"Altered or synthetic content\" if the voice is a clone of a real person."]
    (project / "description.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (project / "tags.txt").write_text(", ".join(plan.get("tags", [])) + "\n", encoding="utf-8")
