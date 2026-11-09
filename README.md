# kotoba (言葉 / 말)

A voice app for practicing Korean and Japanese with characters who remember how you treat them. Mistakes change the relationship instead of triggering a correction card.

**One-liner:** practice being someone in Korea or Japan, with characters who notice whether you got the register right.

---

## The core idea

Language learning apps teach you vocabulary and grammar. What they don't teach is the social layer — who gets formal speech, when you can drop it, what happens if you get it wrong. In Korean and Japanese, register (how formal you sound) is not a stylistic choice. It encodes the relationship. Use the wrong level with your boss and it lands.

kotoba makes the relationship itself the thing you train. Each character has a state — closeness, respect, whether you've offended them — that changes based on how you speak, and persists across sessions. Earn enough trust and 박서연 will offer to drop formalities. Use 반말 too early and she goes cold.

The app never tells you what you said wrong. The character reacts to it.

---

## Characters (v1)

The shared premise: **you've just moved to Seoul or Japan for work.**

### 박서연 (Park Seo-yeon) — your 선배 at a Seoul startup

Marketing, two years older than you, assigned to show you the ropes. Sharp, a little overworked, quietly ambitious. Her first real question is "몇 년생이에요?"

- Starts in 해요체 (polite). Both of you do.
- As closeness and respect grow, she may offer 반말. Use it before she offers and she notices.
- Teaches: age decides register, honorifics matter when talking *about* the team lead, not just *to* him.
- Future channel: KakaoTalk. ㅋㅋ, ㅠㅠ, leaving her on read costs you.

### 中村健二 (Nakamura Kenji) — the owner of a small izakaya near your apartment

Mid-50s, runs an eight-seat izakaya alone. Gruff at first, proud of his food. Full service keigo to new customers; casual with regulars.

- Asymmetric arc: he goes casual as you become a 常連 (regular). You aim for warm です/ます and never go plain with him.
- Teaches: uchi/soto (in-group vs. out-group) experienced by crossing it.
- Future channel: LINE. He adds you mid-season once you've earned it.

---

## Relationship state

Each character carries a small state that the judge updates every turn.

| Variable | Range | Goes up when | Goes down when |
|---|---|---|---|
| Closeness | 0–100 | Regular conversation, recalling their details | Long absence (slowly, never punishing) |
| Respect | 0–100 | Correct register, good repair after a slip | Too casual, rude content |
| Offense | none / mild / serious | — | One serious breach |
| Register | per language | They offer a change and you accept | Serious offense resets it |

Consequences scale from mild (shorter, cooler replies) to serious (the scene waits until you repair in the right register).

**Absence is noticed in the story, never punished.** Come back after a week and Seo-yeon says "오랜만이에요!" No streak shame, no guilt messages.

---

## Story system

The app runs in seasons, like a K-drama. Each episode is a short YAML file with beats — the LLM only improvises dialogue *inside* the current beat. The shape of the story stays authored.

```yaml
episode: seoyeon_s1e03_hoesik
beats:
  - id: arrive
    goal: Seo-yeon briefs you on who sits where at the team dinner
  - id: pour
    goal: Team lead raises his glass; you're expected to pour for him
    pass_if: user uses honorifics with the team lead
    on_fail: Seo-yeon covers for you; respect -3
  - id: after
    goal: Walking to the subway, Seo-yeon reacts to how it went
    variants: [proud, embarrassed]   # chosen by state
```

**Seo-yeon, Season 1:** introductions and the age question → your first mistake at work → the team dinner (회식) → the promotion competition → the register offer → the finale.

---

## Architecture

Each turn forks after speech-to-text: one path produces the character's spoken reply, the other judges your turn and updates state. The character reads state but never writes it.

```
Push-to-talk ──> Speech-to-text ──> Character LLM ──> TTS voice
                 (raw, never           ^
                  normalized)          | state + memories
                      |                |
                      v                |
                  Judge LLM ──────> State store ──> Session summary
                  (JSON only)
```

The judge runs in parallel with the reply; its changes apply from the next turn.

**Stack (all local, all free):**
- STT: `mlx-whisper` with Whisper large-v3 (raw transcription, errors preserved)
- LLM: Qwen3 8B via Ollama — one model, two prompts (character + judge)
- TTS: MeloTTS → CosyVoice 2 later (for emotion control)
- Storage: SQLite for state; YAML in git for characters and episodes

---

## What's been built (Day 7)

| Milestone | Status |
|---|---|
| STT check: does it preserve your mistakes? | Done. Whisper large chosen: 0 silent corrections in Japanese, 7/14 error rows preserved in Korean (clear speech: 14/14). |
| Data layer: player, character state, memories, turns, state events | Done. SQLite schema + db.py + YAML character files. |
| LLM wrapper | Done. `chat()` and `chat_json()` via Ollama. Median ~1.5 s (thinking off). |
| Character chat: Seo-yeon responds in 해요체, stays in register | Done. Scripted 10-turn test passes. |
| Judge: scores register, offenses, grammar, updates state | Done. 90% register accuracy on 40-row eval set. |
| Wire judge into the turn loop | Next. |

---

## Design vision

**What it should feel like:**

A slow burn, not a game. You're not scoring points or clearing levels — you're building a relationship through how you talk. The interface should reflect that: quiet, attentive, unhurried. Closer to a voice memo than a language drill.

**Interface principles:**

1. **The character is present, not the UI.** When you're in a conversation, there's nothing to look at except who you're talking to. No score counters, no feedback overlays mid-turn. The reaction is the feedback.

2. **State is visible after, not during.** After a session there's a brief summary: what shifted, why. During the conversation, the only signal is how they're talking to you.

3. **Register matters visually too.** The transcript on screen should show which register you used — 해요체 and 반말 feel different and should look slightly different, perhaps through typography weight or color temperature, not labels.

4. **Warmth scales with closeness.** The UI should feel warmer as a relationship deepens — not through explicit decoration but through small ambient shifts (background warmth, character illustration mood, text color temperature). Early sessions are cooler. Close ones feel lived-in.

5. **Korean and Japanese have different register shapes.** The visual language for each should reflect this. Korean register is more explicit and social — the app's Korean side can be slightly more expressive. Japanese register is about distance and context — the Japanese side should feel quieter, more contained.

**Character illustration:**

Characters should feel specific, not generic. Seo-yeon looks like she's been at the office since 9 and has a half-finished coffee on her desk. Kenji looks like someone who's been wiping down the same counter for 25 years. Neither is idealized.

Style reference: editorial illustration, not anime or avatar. Think *the person you'd actually meet*, rendered with enough warmth that you'd want to come back.

**Relationship screen:**

There should be somewhere to see the current state of a relationship outside of an active session — something between a contact card and a journal entry. Not numbers. Mood, posture, the last thing they said. A visual sense of where things stand.

**Push-to-talk:**

Holding to speak should feel like picking up a phone call, not pressing an arcade button. The visual treatment of recording should be minimal and focused — a breathing indicator, not a waveform meter.

**What to avoid:**

- Gamification patterns (streaks, XP, badges). They produce the wrong behavior and the wrong user.
- Correction popups mid-turn. The character reacts; that's the correction.
- Generic "AI chat" aesthetics (bubble chat, robot icons).
- Romance or parasocial design patterns that make the character feel like a companion app.

---

## Target users

People who are moving to Korea or Japan, not visiting. Register is a daily, high-stakes problem for people who study, work, or live there. In order: students heading abroad (exchange, language school, programs like IJP), people moving for a job (JET, EPIK, corporate transfers), long-term learners who care about the culture.

---

## Stack details for contributors

```
kotoba/           Python package (db, llm, character, judge, cli)
characters/       YAML character definitions
episodes/         YAML episode files (coming)
prompts/          LLM system prompts
tests/            pytest unit tests + judge eval set
tools/            dev scripts (STT check, chat test)
notes/            decisions.md, tuning.md
```

Python 3.12, venv at `.venv`. Run `pip install -r requirements.txt` to install dependencies. Ollama must be running locally on port 11434 with Qwen3 8B pulled.

```bash
python -m kotoba.cli        # start a session with Seo-yeon
pytest tests/               # unit tests
python tests/eval_judge.py  # judge accuracy eval (needs Ollama)
```
