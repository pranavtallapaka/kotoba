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

---

## Judge (prompts/judge_ko.md — Day 7, post-fixes Day 8/11)

### Design
- Separate LLM call (Qwen3 8B, temperature 0.1) on every player turn.
- Returns structured JSON validated by Pydantic (JudgeResult).
- Never writes dialogue; character model reads state only.

### Accuracy on 40-row eval set (after Day 8 validator override)
- **Register accuracy: 100%** (40/40) across all five categories:
  - correct_haeyo 15/15, banmal_before_offer 8/8, hapsyo_stiff 5/5,
    honorific_error 6/6, grammar_only 6/6
- **Offense detection: 100% precision / 90% recall**
  - 4 misses are in honorific_error rows — model sometimes omits
    missing_honorifics_about_superiors offense_id while still listing the
    error in honorific_errors. Accepted for now.
- Before Day 8 validator: 90% register (36/40); banmal rows 20–23 were
  misclassified. Validator override raised to 100%.

### Known live-session issues (Day 11)
- Medial -어/아 morphemes (e.g. -어도, -아서) in haeyo sentences can trigger
  false banmal_before_offer. Guarded in code: strip the offense if
  register_used ≠ "banmal". (judge.py)
- Address terms (선배님 etc.) sometimes appear in honorific_errors with no
  → correction. Guarded in code: drop entries without →. (judge.py)
- Grammar error detection is stochastic; a known error (future+past adverb)
  was missed in one live session.
- Respect deltas for honorific errors vary (-1 to -4); prompt suggests -4
  but model does not always honour it.

---

## Korean register validator (kotoba/validator_ko.py — Day 8)

### Design
- Pure rule-based; no LLM. Runs after every judge call.
- Scans words right-to-left within each sentence.
- Priority: hapsyo suffixes (니다/니까/십시오) → 요 → banmal set.
- Multi-sentence: returns most casual register found.
- Confidence: high for hapsyo and 요-endings; medium for banmal set.

### Accuracy: 100% (40/40) on judge eval set
- All five categories perfect.
- High-confidence overrides used: hapsyo and 요 cases only.

### Integration with judge
- When validator confidence == "high" and disagrees with judge: register_used,
  register_match, and register_expected are overridden.
- Medium-confidence (banmal) does not override — avoids over-riding on
  ambiguous cases where the judge may have context the validator lacks.

---

## State delta bounds (kotoba/judge.py + kotoba/state.py — Day 7/9)

### Per-turn caps enforced in code (JudgeResult._clamp_deltas)
- closeness: −3 … +3
- respect: −10 … +3

### Typical judge-suggested values
| Situation | closeness | respect |
|---|---|---|
| Correct register, no errors | +1 | +1 |
| Hapsyo (stiff, not rude) | 0 | 0 |
| Banmal before offer | 0 | −6 |
| Honorific error | 0 | −4 |
| Grammar error only | 0 | −1 (or 0) |

### relationship_speed (player.yaml)
- Multiplies **positive** closeness deltas only. Negatives unaffected.
- Default: 2.0 (halves turns-to-반말-offer vs 1.0).
- Note: not in DB schema yet; state.py uses 2.0 as the hardcoded default.
- 반말 offer thresholds: closeness ≥ 60, respect ≥ 55.
  At +2/turn (speed 2.0): ~16 clean turns from start to closeness threshold.

---

## Beginner tolerance (kotoba/state.py — Day 9)

### Active when: player.support_level_ko ≤ 2 (default: 2)
- **Grammar-only errors** (grammar_errors non-empty, offense_ids empty,
  honorific_errors empty, register_match True): respect delta zeroed.
- **Register or honorific slip** (register_match False or honorific_errors
  non-empty): respect penalty capped at −3, regardless of judge delta.
- Register/honorific detection correct turn to turn; grammar-only misses are
  stochastic but benign (player gets +1 instead of 0, minor).

---

## TTS engine (kotoba/tts.py — Day 14, updated Day 15/16)

### Default engine: macOS `say` (Day 15)
- Zero model memory; uses macOS built-in speech synthesis via `say -v Yuna -o file.aiff`.
- `voice_id = "KR"` in character YAML maps to macOS voice `Yuna` (Korean, female).
- `synthesize()` writes a temp AIFF, `play()` uses `afplay`. Streaming pipeline unchanged.
- Emoji and non-Korean/non-Latin symbols stripped from input before synthesis (Day 16).
- Use `--tts melo` or `KOTOBA_TTS=melo` for MeloTTS neural synthesis (demo/recording quality).
- `/repeat` and `/slow` (0.7× speed) work with both engines.

### MeloTTS (neural, `--tts melo`)
- `voice_id = "KR"`, synthesis via `melo.api.TTS(language="KR", device="mps"|"cpu")`.
- Lazy-loaded and cached; `tts.warmup()` runs a dummy synthesis to pre-JIT the Metal path.
- Installation: see Day 14 entry in tuning.md.

---

## Voice confirm-step design (kotoba/cli.py — Day 13)

### Flow after each recording
```
I heard: <transcript>  (logprob=X.XX)
[Enter] accept  [r] re-record  [e] edit
>
```
- **Accept**: transcript goes to judge + reply pipeline unchanged.
- **Re-record**: loops back to push-to-talk; re-records and re-transcribes.
- **Edit**: player types a correction; `stt_corrected=True` logged to DB, judge scores the corrected text.

### Rationale
- STT errors on Korean are common (pronunciation, ambient noise). The confirm step lets the player fix transcriptions without breaking the judge.
- Corrections are flagged in the DB so accuracy analysis can exclude them.
- Quality warnings (clipping, too quiet) fire before transcription and prompt re-record immediately (Day 16).

---

## STT confidence threshold (voice.py)

- `avg_logprob < -0.7` → `low_confidence = True` → character asks to repeat (no judge call, no state change).
- Threshold chosen Day 3: catches worst outliers (ko_11 at -1.026, ko_22 at -1.381) without false-flagging valid preserved rows. Do not raise above -0.5.
- Low confidence triggers Seo-yeon's repeat prompt, not a system message, to stay in character.

---

## First-audio latency (Day 15)

### Pre-optimisation baseline (streaming disabled, MeloTTS, full reply synthesised as one chunk)
- tts1 ≈ 14–20 s from accept to first audio.

### Post-optimisation (Day 15–16: say engine, streaming sentences, deferred judge, turbo STT)
- Sentence-streaming pipeline: LLM tokens → sentence queue → TTS consumer thread.
- Judge deferred until first sentence queued (no GPU contention at t=0).
- `say` engine eliminates MeloTTS model load (~15 s cold, ~2 s warm synthesis per sentence).
- Target: tts1 < 3 s. Measure with `python -m kotoba.cli seoyeon --bench tests/voice_samples/ --debug`.

---

## Slip explanation format (kotoba/state.py explain_slip — Day 9)

### Trigger condition
- Fires when: `register_match == False` OR `honorific_errors` non-empty
  (after fix #2: entries without → are stripped, so bare address terms
  no longer trigger a false explanation).

### Format by case
| Case | Message |
|---|---|
| Banmal → haeyo expected | "You used 반말 ({word}) with your senior. She expected 해요체: {word}요." |
| Hapsyo → haeyo expected | "You used 하십시오체 (too formal). She expected 해요체." |
| Other register mismatch | "You used {register} ({word}). She expected {expected}." |
| Honorific error | "Honorific slip: {error[0]}. Use honorific forms when talking about superiors." |

### Word extraction
- `find_register_word(text, register)` in validator_ko.py: scans right-to-left
  per sentence using _check_word(); returns the first word matching the register.
- Correction for banmal→haeyo: appends 요 to the matched word (고마워 → 고마워요,
  먹어 → 먹어요, 가 → 가요). Works for the vast majority of -어/아 endings.
