"""Text-to-speech output.

speak(text, voice_id, slow=False) -> None          # synthesise + play (blocking)
synthesize(text, voice_id, slow=False) -> str|None # write temp WAV, return path
play(wav_path) -> None                             # afplay a WAV file

Engine: MeloTTS (Korean neural TTS). voice_id = "KR".
Device: MPS (Apple Silicon Metal) if available, else CPU.
"""
import os
import subprocess
import tempfile
import warnings

_NORMAL_SPEED = 1.0
_SLOW_SPEED = 0.7

_tts_instance = None


def _get_tts(language: str):
    global _tts_instance
    if _tts_instance is None:
        from melo.api import TTS
        try:
            import torch
            dev = "mps" if torch.backends.mps.is_available() else "cpu"
        except Exception:
            dev = "cpu"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _tts_instance = TTS(language=language, device=dev)
    return _tts_instance


def synthesize(text: str, voice_id: str, slow: bool = False) -> str | None:
    """Synthesise text to a temp WAV. Returns path; caller must delete it. None on empty input."""
    if not voice_id or not text or not text.strip():
        return None
    tts = _get_tts(voice_id)
    try:
        speaker_id = tts.hps.data.spk2id[voice_id]
    except (KeyError, TypeError):
        return None
    speed = _SLOW_SPEED if slow else _NORMAL_SPEED
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        out_path = f.name
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tts.tts_to_file(text, speaker_id, out_path, speed=speed)
        return out_path
    except Exception:
        if os.path.exists(out_path):
            os.unlink(out_path)
        return None


def play(wav_path: str) -> None:
    """Play a WAV file via afplay (macOS). Blocking."""
    subprocess.run(["afplay", wav_path], check=False)


def speak(text: str, voice_id: str, slow: bool = False) -> None:
    """Synthesise and play. Blocking. No-op if voice_id or text is empty."""
    path = synthesize(text, voice_id, slow)
    if path:
        try:
            play(path)
        finally:
            os.unlink(path)


def warmup(voice_id: str) -> None:
    """Pre-load the TTS model so the first synthesis call isn't delayed by model init."""
    if voice_id:
        _get_tts(voice_id)
