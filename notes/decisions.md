# Decisions

## STT model (PROVISIONAL — Day 3)

### Japanese: whisper large — settled
- whisper-large-v3-mlx via mlx-whisper
- 13/14 error rows preserved on real recordings; 0 register/honorific CORRECTED
- Only failure: ja_07 (高いくない→高くない, conjugation). Both turbo and large
  silently correct this. Accepted limitation: impossible phoneme sequences like
  高いく are indistinguishable from 高く in speech and the model normalises them.
  The judge must not rely on STT catching this class of error.

### Korean: whisper large — provisional, pending pronunciation work
- large: 7/14 error rows preserved on real recordings; 0 CORRECTED
- TTS reference test (macOS Yuna voice): 14/14 preserved
- Conclusion: the model handles Korean correctly when the input is clear.
  Errors (7 "other" rows) are pronunciation, not model failure.
- Specific issues: 부 vs 루, 선생님 vs 선산님, 커피가 vs 고기가, 날씨가 춥어요 vs
  나르시가 초보요, 선배 오늘 뭐 해 → Chinese characters (low logprob: -1.026).
  ko_22 잘 지내셨어요 is a persistent misrecognition across re-records.
- Action: re-record problem sentences with cleaner articulation before finalising.

### Confidence threshold
- avg_logprob does not cleanly separate "other" from "preserved".
- A threshold of -0.7 catches only the worst outliers (ko_11 at -1.026,
  ko_22 at -1.381). Do not go shallower than -0.5 or it will flag valid
  preserved rows. Use as a "ask to repeat" hint only, not a hard reject.

### Model choice rationale: large over turbo
- Turbo: median 0.67 s, Korean 4/14 preserved
- Large: median 0.90 s, Korean 7/14 preserved
- 0.23 s latency difference is negligible in a conversational turn.
  Large is worth it for the Korean accuracy improvement.
