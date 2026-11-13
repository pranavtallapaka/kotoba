"""STT configuration: whisper-large-v3-mlx via mlx-whisper.

Model chosen Day 3: large over turbo for Korean accuracy (7/14 vs 4/14 preserved).
0.23s latency difference is negligible. See notes/decisions.md.
"""
import math

MODEL = "mlx-community/whisper-large-v3-mlx"


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
