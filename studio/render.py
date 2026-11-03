"""FFmpeg assembly: one segment per shot, concat, burned-in captions, music ducked under the voice, -14 LUFS."""

import subprocess
from pathlib import Path

W, H, FPS = 1920, 1080, 30
X264 = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p"]


def ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(args, cwd=None):
    r = subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", *map(str, args)],
                       cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"ffmpeg failed: {r.stderr.strip()[-600:]}")


def clip_segment(src: Path, seconds: float, out: Path, offset=0.0):
    """Stock clip -> exactly `seconds` of 1080p30, cropped to fill, looped if the clip is short."""
    run(["-stream_loop", "-1", "-ss", f"{offset:.2f}", "-i", src, "-t", f"{seconds:.3f}", "-an",
         "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1", *X264, out])


def still_segment(img: Path, seconds: float, out: Path):
    """Still image -> slow push-in (Ken Burns) for `seconds`."""
    frames = max(1, int(seconds * FPS))
    run(["-loop", "1", "-framerate", FPS, "-i", img, "-t", f"{seconds:.3f}", "-an",
         "-vf", f"scale={W * 2}:{H * 2},zoompan=z='min(zoom+0.0007,1.12)':d={frames}:x='iw/2-(iw/zoom/2)':"
                f"y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},setsar=1", *X264, out])


def concat(segments: list[Path], out: Path):
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{Path(s).resolve().as_posix()}'\n" for s in segments), encoding="utf-8")
    run(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out])


def final(video: Path, narration: Path, out: Path, captions_ass: Path | None = None, music: Path | None = None,
          music_volume=0.18):
    """Mux picture + voice (+ looped music ducked under the voice), burn captions, normalize to YouTube's -14 LUFS."""
    work = Path(out).parent
    args = ["-i", Path(video).resolve(), "-i", Path(narration).resolve()]
    if music:
        args += ["-stream_loop", "-1", "-i", Path(music).resolve()]
        audio = (f"[1:a]asplit=2[voice][sc];[2:a]volume={music_volume}[m];"
                 "[m][sc]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=350[duck];"
                 "[voice][duck]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    else:
        audio = "[1:a]loudnorm=I=-14:TP=-1.5:LRA=11[a]"
    # Relative path: the subtitles filter's own escaping of Windows drive letters is fragile.
    vf = f"[0:v]subtitles={Path(captions_ass).name}[v]" if captions_ass else "[0:v]null[v]"
    run([*args, "-filter_complex", f"{vf};{audio}", "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", Path(out).resolve()],
        cwd=work)


def frame(video: Path, at: float, out: Path):
    run(["-ss", f"{at:.2f}", "-i", video, "-frames:v", "1", "-q:v", "2", out])
