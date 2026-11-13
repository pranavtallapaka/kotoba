"""Text-to-speech output.

speak(text, voice_id, slow=False) -> None

Engine: MeloTTS (Korean neural TTS). voice_id must be a MeloTTS language code
("KR" for Korean). slow=True reduces synthesis speed by 30%.
Playback via afplay (macOS); audio is synthesised to a temp WAV then played.
"""
import subprocess
import tempfile
import os

_NORMAL_SPEED = 1.0
_SLOW_SPEED = 0.7

_tts_instance: object = None   # lazy-loaded on first call


def _get_tts(language: str):
    """Return a cached MeloTTS instance for the given language."""
    global _tts_instance
    if _tts_instance is None:
        from melo.api import TTS  # deferred import — slow on first call
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _tts_instance = TTS(language=language, device="cpu")
    return _tts_instance


def speak(text: str, voice_id: str, slow: bool = False) -> None:
    """Synthesise text with MeloTTS and play it. Blocks until audio finishes.
    No-op if voice_id is empty or text is empty."""
    if not voice_id or not text:
        return
    tts = _get_tts(voice_id)
    try:
        speaker_id = tts.hps.data.spk2id[voice_id]
    except (KeyError, TypeError):
        return
    speed = _SLOW_SPEED if slow else _NORMAL_SPEED
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        out_path = f.name
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tts.tts_to_file(text, speaker_id, out_path, speed=speed)
        subprocess.run(["afplay", out_path], check=False)
    finally:
        os.unlink(out_path)
