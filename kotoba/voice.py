"""Push-to-talk voice input for the CLI.

record_and_transcribe() -> STTResult
  Press Enter to start, Enter to stop. 16 kHz mono.
  Returns transcript + confidence values from whisper-large.
"""
from __future__ import annotations

import sys
import tempfile
import time
from dataclasses import dataclass, field

from kotoba import stt_config

SAMPLE_RATE = 16000
_LOW_LOGPROB_THRESHOLD = -0.7


@dataclass
class STTResult:
    text: str
    avg_logprob: float
    no_speech_prob: float
    low_confidence: bool  # True → skip confirm, ask character to repeat
    t_stt_ms: int = 0

    @classmethod
    def empty(cls) -> "STTResult":
        return cls(text="", avg_logprob=float("-inf"), no_speech_prob=1.0, low_confidence=True, t_stt_ms=0)


def transcribe_file(audio_path: str, language: str = "ko") -> STTResult:
    """Transcribe an existing WAV file without recording. Used for batch/test mode."""
    t0 = time.perf_counter()
    text, avg_logprob, no_speech_prob = stt_config.transcribe(audio_path, language=language)
    t_stt_ms = int((time.perf_counter() - t0) * 1000)
    low = not text or avg_logprob < _LOW_LOGPROB_THRESHOLD
    return STTResult(text=text, avg_logprob=avg_logprob, no_speech_prob=no_speech_prob, low_confidence=low, t_stt_ms=t_stt_ms)


def record_and_transcribe(language: str = "ko") -> STTResult:
    """Record until Enter, then transcribe. Returns STTResult."""
    import numpy as np
    import sounddevice as sd
    import soundfile as sf

    input("[Voice] Press Enter to start recording...")
    frames: list = []

    def _callback(indata, _frames, _time, status):
        if status:
            print(status, file=sys.stderr)
        frames.append(indata.copy())

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                        callback=_callback):
        input("[Voice] Recording… press Enter to stop.")

    if not frames:
        print("[Voice] Nothing captured.", file=sys.stderr)
        return STTResult.empty()

    audio = np.concatenate(frames)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        sf.write(tmp.name, audio, SAMPLE_RATE)
        tmp.close()
        print("[Transcribing…]", flush=True)
        t0 = time.perf_counter()
        text, avg_logprob, no_speech_prob = stt_config.transcribe(tmp.name, language=language)
        t_stt_ms = int((time.perf_counter() - t0) * 1000)
    finally:
        import os
        os.unlink(tmp.name)

    low = not text or avg_logprob < _LOW_LOGPROB_THRESHOLD
    return STTResult(
        text=text,
        avg_logprob=avg_logprob,
        no_speech_prob=no_speech_prob,
        low_confidence=low,
        t_stt_ms=t_stt_ms,
    )
