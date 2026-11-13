"""Push-to-talk voice input for the CLI.

record_and_transcribe() -> STTResult
  Press Enter to start, Enter to stop. 16 kHz mono.
  Trims silence, checks for clipping / too-quiet before transcribing.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from dataclasses import dataclass

from kotoba import stt_config

SAMPLE_RATE = 16000
_LOW_LOGPROB_THRESHOLD = -0.7

# Silence trimming
_SILENCE_THRESHOLD = 0.01   # amplitude below this is silence
_SILENCE_PAD_MS = 80        # ms of padding to keep around speech

# Quality checks
_CLIP_THRESHOLD = 0.99      # any sample above this = clipped
_QUIET_RMS_THRESHOLD = 0.01 # RMS below this = too quiet


@dataclass
class STTResult:
    text: str
    avg_logprob: float
    no_speech_prob: float
    low_confidence: bool
    t_stt_ms: int = 0
    quality_warning: str = ""  # non-empty → ask user to re-record before transcribing

    @classmethod
    def empty(cls) -> "STTResult":
        return cls(text="", avg_logprob=float("-inf"), no_speech_prob=1.0,
                   low_confidence=True, t_stt_ms=0)


def _trim_silence(audio: "np.ndarray") -> "np.ndarray":
    """Remove leading/trailing silence, keeping a short pad around speech."""
    import numpy as np
    mask = (abs(audio) > _SILENCE_THRESHOLD).flatten()
    if not mask.any():
        return audio
    pad = int(SAMPLE_RATE * _SILENCE_PAD_MS / 1000)
    start = max(0, int(mask.argmax()) - pad)
    end = min(len(audio), int(len(mask) - mask[::-1].argmax()) + pad)
    return audio[start:end]


def _check_quality(audio: "np.ndarray") -> str:
    """Return a warning string if the audio is clipped or too quiet, else ''."""
    import numpy as np
    if np.max(np.abs(audio)) > _CLIP_THRESHOLD:
        return "Recording clipped — speak a bit farther from the mic or more quietly."
    rms = float(np.sqrt(np.mean(audio ** 2)))
    if rms < _QUIET_RMS_THRESHOLD:
        return "Recording was too quiet — speak up or move closer to the mic."
    return ""


def transcribe_file(audio_path: str, language: str = "ko") -> STTResult:
    """Transcribe an existing WAV file without recording. Used for batch/test mode."""
    t0 = time.perf_counter()
    text, avg_logprob, no_speech_prob = stt_config.transcribe(audio_path, language=language)
    t_stt_ms = int((time.perf_counter() - t0) * 1000)
    low = not text or avg_logprob < _LOW_LOGPROB_THRESHOLD
    return STTResult(text=text, avg_logprob=avg_logprob, no_speech_prob=no_speech_prob,
                     low_confidence=low, t_stt_ms=t_stt_ms)


def record_and_transcribe(language: str = "ko") -> STTResult:
    """Record until Enter, trim silence, quality-check, then transcribe."""
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

    warning = _check_quality(audio)
    if warning:
        return STTResult(text="", avg_logprob=float("-inf"), no_speech_prob=1.0,
                         low_confidence=True, quality_warning=warning)

    audio = _trim_silence(audio)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        sf.write(tmp.name, audio, SAMPLE_RATE)
        tmp.close()
        print("[Transcribing…]", flush=True)
        t0 = time.perf_counter()
        text, avg_logprob, no_speech_prob = stt_config.transcribe(tmp.name, language=language)
        t_stt_ms = int((time.perf_counter() - t0) * 1000)
    finally:
        os.unlink(tmp.name)

    low = not text or avg_logprob < _LOW_LOGPROB_THRESHOLD
    return STTResult(text=text, avg_logprob=avg_logprob, no_speech_prob=no_speech_prob,
                     low_confidence=low, t_stt_ms=t_stt_ms)
