"""Text-to-speech output.

speak(text, voice_id, slow=False) -> None          # synthesise + play (blocking)
synthesize(text, voice_id, slow=False) -> str|None # write temp file, return path
play(file_path) -> None                            # afplay a file
warmup(voice_id) -> None                          # pre-load model (melo only; no-op for say)
set_engine(engine) -> None                         # "say" or "melo"

Engine default: "say" (macOS built-in, zero model memory).
Use --tts melo (or KOTOBA_TTS=melo) for MeloTTS neural synthesis.
"""
import os
import subprocess
import tempfile
import warnings

_NORMAL_SPEED = 1.0
_SLOW_SPEED = 0.7
_NORMAL_RATE = 175   # say words-per-minute
_SLOW_RATE = 120

# MeloTTS voice_id → macOS say voice name
_SAY_VOICES = {
    "KR": "Yuna",
    "EN": "Samantha",
    "JA": "Kyoko",
}

_ENGINE: str = os.environ.get("KOTOBA_TTS", "say").lower()
_tts_instance = None


def set_engine(engine: str) -> None:
    global _ENGINE
    _ENGINE = engine.lower()


def _get_melo(language: str):
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
    """Synthesise text to a temp file. Returns path; caller must delete it. None on empty input."""
    if not voice_id or not text or not text.strip():
        return None
    if _ENGINE == "say":
        voice = _SAY_VOICES.get(voice_id, "Yuna")
        rate = str(_SLOW_RATE if slow else _NORMAL_RATE)
        with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as f:
            out_path = f.name
        result = subprocess.run(
            ["say", "-v", voice, "-r", rate, "-o", out_path, text],
            check=False, capture_output=True,
        )
        if result.returncode == 0 and os.path.exists(out_path):
            return out_path
        if os.path.exists(out_path):
            os.unlink(out_path)
        return None
    else:  # melo
        tts = _get_melo(voice_id)
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


def play(file_path: str) -> None:
    """Play a WAV or AIFF file via afplay (macOS). Blocking."""
    subprocess.run(["afplay", file_path], check=False)


def speak(text: str, voice_id: str, slow: bool = False) -> None:
    """Synthesise and play. Blocking. No-op if voice_id or text is empty."""
    path = synthesize(text, voice_id, slow)
    if path:
        try:
            play(path)
        finally:
            os.unlink(path)


def warmup(voice_id: str) -> None:
    """Pre-load TTS model. No-op for say engine."""
    if _ENGINE != "melo" or not voice_id:
        return
    _get_melo(voice_id)
    wav = synthesize("안녕", voice_id)
    if wav and os.path.exists(wav):
        os.unlink(wav)
