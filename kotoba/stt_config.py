"""STT configuration: whisper via mlx-whisper.

Model chosen Day 3: large over turbo for Korean accuracy (7/14 vs 4/14 preserved).
Set KOTOBA_STT=turbo to use whisper-large-v3-turbo (0.67 s, less memory, 4/14 preserved).
See notes/decisions.md.
"""
import math
import os

SAMPLE_RATE = 16000

_MODELS = {
    "large": "mlx-community/whisper-large-v3-mlx",
    "turbo": "mlx-community/whisper-large-v3-turbo",
}

_model_key = os.environ.get("KOTOBA_STT", "large").lower()
MODEL = _MODELS.get(_model_key, _MODELS["large"])


def transcribe(audio_path: str, language: str = "ko") -> tuple[str, float, float]:
    """Transcribe audio file. Returns (text, avg_logprob, no_speech_prob).

    avg_logprob < -0.7 indicates likely mishearing; treat as low confidence.
    """
    import mlx_whisper

    out = mlx_whisper.transcribe(
        audio_path,
        path_or_hf_repo=MODEL,
        language=language,
        temperature=0.0,
        condition_on_previous_text=False,
        verbose=None,
    )
    text = out["text"].strip()
    segs = out.get("segments") or []
    if segs:
        avg_logprob = sum(s["avg_logprob"] for s in segs) / len(segs)
        no_speech_prob = sum(s["no_speech_prob"] for s in segs) / len(segs)
    else:
        avg_logprob = math.nan
        no_speech_prob = math.nan
    return text, avg_logprob, no_speech_prob


def warmup() -> None:
    """Load the Whisper model by transcribing a tiny silent clip."""
    import numpy as np
    import soundfile as sf
    import tempfile

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        silence = np.zeros(SAMPLE_RATE // 10, dtype=np.float32)  # 0.1 s
        sf.write(tmp.name, silence, SAMPLE_RATE)
        tmp.close()
        transcribe(tmp.name)
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass
