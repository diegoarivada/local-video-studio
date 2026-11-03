"""Narration with Chatterbox (MIT). Uses its built-in voice, or clones YOUR voice from a short clean recording."""

import os

import numpy as np

os.environ.setdefault("TQDM_DISABLE", "1")   # one progress bar per line of narration is just noise
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


def pick_device(prefer="auto") -> str:
    import torch
    if prefer != "auto":
        return prefer
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def synthesize(chunks: list[str], voice_ref=None, exaggeration=0.5, cfg_weight=0.5, device="auto", seed=7, log=print):
    """Read each chunk separately (keeps long reads from drifting). Returns (list of float32 arrays, sample_rate)."""
    import torch
    from chatterbox.tts import ChatterboxTTS
    torch.manual_seed(seed)
    dev = pick_device(device)
    log(f"Loading Chatterbox on {dev}...")
    model = ChatterboxTTS.from_pretrained(device=dev)
    if voice_ref:
        model.prepare_conditionals(str(voice_ref), exaggeration=exaggeration)
    out = []
    for i, text in enumerate(chunks, 1):
        wav = model.generate(text, exaggeration=exaggeration, cfg_weight=cfg_weight)
        out.append(wav.squeeze(0).detach().cpu().numpy().astype(np.float32))
        if i % 10 == 0 or i == len(chunks):
            log(f"  voiced {i}/{len(chunks)}")
    sr = model.sr
    del model
    if dev == "cuda":
        torch.cuda.empty_cache()
    return out, sr


def trim_silence(a: np.ndarray, sr: int, threshold=0.01, pad=0.05) -> np.ndarray:
    """Cut leading/trailing silence so pauses between chunks are the ones we choose."""
    loud = np.where(np.abs(a) > threshold)[0]
    if not len(loud):
        return a
    p = int(pad * sr)
    return a[max(0, loud[0] - p): loud[-1] + p]
