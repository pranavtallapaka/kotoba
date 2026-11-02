# kotoba — tools

Small utilities for checking the local stack.

## stt_check.py

Smoke-test the mlx-whisper pipeline.

```
# List practice sentences
python tools/stt_check.py --list

# Record 5 seconds and transcribe
python tools/stt_check.py --record 5

# Transcribe an existing file
python tools/stt_check.py --file path/to/audio.wav
```

Paths resolve relative to this `tools/` directory, so `sentences.csv` must
sit alongside `stt_check.py`.
