"""python -m studio <command>

  make TOPIC        write the script, voice it, and render the video (all steps)
  script TOPIC      only write the script (edit out/<project>/script.json, then run `render`)
  render PROJECT    voice and render an existing project folder (after you edit script.json)

Examples:
  python -m studio make "Why you should back up your photos" --minutes 3
  python -m studio make "Budget travel in Japan" --voice me.wav --i-own-this-voice --music music/track.mp3
"""

import argparse
import json
import os
import sys
from pathlib import Path

from . import pipeline
from .script import DEFAULT_STYLE, Ollama, ScriptError, write_script


def load_env(path=Path(".env")):
    """Tiny .env reader (KEY=value lines). Real environment variables win."""
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def read_opt(path):
    return Path(path).read_text(encoding="utf-8") if path else ""


def main():
    load_env()
    p = argparse.ArgumentParser(prog="python -m studio", description="Topic in, narrated video draft out.")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common_voice(sp):
        sp.add_argument("--voice", help="a 10-60 s clean WAV/MP3 of YOUR voice to clone (default: built-in voice)")
        sp.add_argument("--i-own-this-voice", action="store_true", help="confirm the --voice recording is you, or you have consent")
        sp.add_argument("--exaggeration", type=float, default=0.5, help="0.3 calm ... 0.8 energetic")
        sp.add_argument("--cfg", type=float, default=0.5, help="lower (0.3) = slower, more deliberate pacing")
        sp.add_argument("--music", help="background track (you must have the rights; YouTube Audio Library works)")
        sp.add_argument("--no-captions", action="store_true")
        sp.add_argument("--device", default="auto", help="auto | cuda | mps | cpu")

    for name in ("make", "script"):
        sp = sub.add_parser(name)
        sp.add_argument("topic")
        sp.add_argument("--minutes", type=float, default=3)
        sp.add_argument("--notes", help="text file with your take, facts, and links to use")
        sp.add_argument("--style", help="text file describing how you talk (replaces the default style)")
        sp.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", "qwen3:8b"))
        sp.add_argument("--out", default="out")
        if name == "make":
            common_voice(sp)
    sp = sub.add_parser("render")
    sp.add_argument("project")
    common_voice(sp)
    a = p.parse_args()

    if getattr(a, "voice", None) and not a.i_own_this_voice:
        sys.exit("Cloning a voice needs --i-own-this-voice: only clone your own voice, or one you have written consent for.")
    if getattr(a, "voice", None) and not Path(a.voice).is_file():
        sys.exit(f"Voice file not found: {a.voice}")
    if getattr(a, "music", None) and not Path(a.music).is_file():
        sys.exit(f"Music file not found: {a.music}")

    try:
        if a.cmd in ("make", "script"):
            llm = Ollama(os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"), a.model)
            plan = write_script(llm, a.topic, a.minutes, read_opt(a.notes), read_opt(a.style) or DEFAULT_STYLE)
            project = pipeline.new_project(Path(a.out), plan["title"])
            pipeline.save_script(project, plan)
            print(f"Script: {project / 'script.md'}")
            if a.cmd == "script":
                print(f"Edit {project / 'script.json'} if you like, then: python -m studio render \"{project}\"")
                return
        else:
            project = Path(a.project)
            plan = json.loads((project / "script.json").read_text(encoding="utf-8"))
            pipeline.save_script(project, plan)
            for old in list((project / "segments").glob("*")) if (project / "segments").exists() else []:
                old.unlink()   # narration changes shift every shot, so rebuild them
        shots = pipeline.plan_shots(plan)
        print(f"Voicing {len(shots)} lines...")
        shots = pipeline.narrate(project, shots, a.voice, a.exaggeration, a.cfg, a.device)
        print(f"Narration: {shots[-1]['end'] / 60:.1f} min. Building shots...")
        final = pipeline.build_video(project, plan, shots, a.music, not a.no_captions)
        print(f"\nDone: {final}\nAlso in {project}: thumbnail.jpg, description.txt (with chapters), tags.txt, captions.srt")
    except ScriptError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
