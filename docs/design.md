# Voice Language Tool — Design Doc

Exported Nov 13, 2026 from the shared design doc. The shared doc is the source of truth; re-export after big changes.

## Overview

A voice app for practicing Korean and Japanese with persistent characters whose way of speaking to you is earned or lost through how you treat them. Mistakes change the scene instead of triggering a correction card.

**One-liner:** practice being someone in Korea or Japan, with characters who remember how you treated them, in conversation and in your texts.

**Name:** not final. Shortlist: Kotomal (言葉 kotoba + 말 mal, both meaning "words"), Enishi (縁, the bond between people), Goma. Working name in code: kotoba.

**Differentiator: social consequences that persist over time.** Role-play of real-life scenarios is standard (Speak, Praktika, Talkpal, Noonchi). What no app does is make the relationship itself the thing you train: use the wrong speech level and the character goes cold, earn trust and they offer 반말, leave them on read and they notice.

**Lock-in vs. moat**

- **Short-term lock-in:** each user's relationships. Two months of earning Seo-yeon's trust is a reason not to switch. This protects against churn, not against copying.
- **Long-term moat (doesn't exist yet):** authored characters and story seasons with native-checked cultural rules (IP a competitor can't copy), plus labeled data on learner speech and social appropriateness, which can train a judge nobody else can build.

**Goals for v1**

- One Korean and one Japanese character you'd actually come back to
- Register choice judged in live conversation, not just grammar
- Mistakes land as consequences inside the scene, with a short explanation
- A state model clean enough to scale to more characters, languages and users

**Non-goals for v1:** pronunciation scoring, avatars, accounts and hosting, curriculum content, full keigo production, romance of any kind.

## Positioning

**For people moving to Korea or Japan, not visiting.** Register is a daily, high-stakes problem for people who study, work or live there. Tourists rarely face it: their exchanges are short and scripted, locals forgive foreigners, and a translation app covers most of a trip. Travel motivation also ends on a date, which drives churn.

**Target users, in order**

1. Students heading abroad (exchange, language school, study-abroad programs)
2. People moving for a job (JET, EPIK, corporate transfers)
3. Long-term learners who care about the culture (including many beginners)
4. Later, B2B: study-abroad offices, exchange programs, relocation firms

**Competitors**

| Product | What it does | Gap vs. this product |
| --- | --- | --- |
| Speak | Structured voice lessons, AI tutor, Korean and Japanese | Tutor, not a relationship; no social consequences |
| Praktika | Avatar tutors with long-term memory | Memory makes it personalized, not consequential |
| Langua, Practice Me | AI conversation partners that remember you | Same: remembering you is not judging you |
| Noonchi | Korean AI role-play with feedback on honorifics and tone | Closest competitor; no visible persistent relationships; Korean only |
| LangBuddy | AI buddy who texts you on WhatsApp/iMessage, with voice notes | Has the texting channel; texts don't carry relationship state or register |
| HelloTalk, Tandem | Human language exchange (HelloTalk: 70M+ registered) | Partners are peers; they can't be your boss or landlord, and rarely correct register |

The defensible claim is narrow: nobody makes the *relationship* the thing you train. Re-check Noonchi and LangBuddy before the beta.

**Market signal:** Japanese is the 4th and Korean the 6th most-studied language on Duolingo. JLPT had 1.65M examinees in 2025; TOPIK had 550K+ from Jan–Sep 2025. International students: 408K in Japan, 274K in Korea. Realistic outcome if retention works: a paid niche product with thousands to tens of thousands of subscribers. Most people moving to Japan/Korea are not English speakers, so more interface languages may matter more than new target languages.

**Early research (Instagram outreach, Nov 2026):** ~25% reply rate on DMs, most repliers fill in the form. Early stories are about *uncertainty* in choosing register (which form is safe, when switching is okay) more than grammar, and real reactions to slips were mild (laughter), which supports gentle, explained consequences.

## Core mechanic: relationship state

Each character carries a small state that updates every turn and persists across sessions. The character's reply reads that state; only the judge writes it.

| Variable | Range | Goes up when | Goes down when | Controls |
| --- | --- | --- | --- | --- |
| Closeness | 0–100 | Regular conversation, recalling their details, fitting small talk | Long absence (slow, never punishing), ignoring what they said | Unlocks milestones past thresholds |
| Respect | 0–100 | Correct register, good repair after a slip | Too casual, 반말 before the offer, rude content | Warmth, willingness to help, how smoothly scenes go |
| Offense | none / mild / serious | — | One serious breach | Scene branches; repair may be required |
| Register (theirs → you, yours → them) | per language | They offer a change and you accept | Serious offense resets it | What they use with you, and what they expect back |

**Social facts** are fixed per character and define what's *correct*: age relative to the player (set relative, not as a number), role, in-group vs. out-group, and a register ceiling.

**Consequences, from mild to serious**

1. Tone: shorter, more formal replies
2. Friction: the character asks what you meant, or corrects you in character
3. Branch: the scene takes a worse path (no favor, colder walk to the subway)
4. Repair required: the scene waits until you recover in the language, at the right level

**Register changes are offered, never taken.** In Korean this is the "말 편하게 해도 돼요" moment. Accepting unlocks the new level; using it early costs respect. Some relationships are **asymmetric**: the other person goes casual while you stay polite (e.g. an older shop owner). Some **cap out** and never go casual.

**Absence is noticed in the story, never punished.** Come back after a week and Seo-yeon says "오랜만이에요!" No streak shame, no guilt messages.

**Relationship milestones.** Progress shows through several signals, not one switch, so a slow arc still visibly moves every week: how they address you (name + 씨 → name), topics that open up, invitations (lunch, team dinner, festival), adding you on KakaoTalk or LINE, and finally the speech-level offer. Each character file lists its milestones with conditions; a short line marks each one ("★ Seo-yeon started calling you by name").

**Player moves.** The player can make social moves too. Inviting a senior to speak casually to you ("선배님, 말 편하게 하세요") is polite and adds closeness; asking to use 반말 yourself before the offer is presumptuous unless closeness is already high. (To be checked by a Korean reviewer.)

**Slip explanations.** After a slip, the player sees one short English line: what they said, why it landed that way, and the better version. Learners feel confusion more than punishment, so explaining matters as much as the reaction.

## Beginners and support levels

Many people moving to Korea or Japan are beginners, so support fades as the learner improves:

| Level | What the learner does |
| --- | --- |
| 0. Choose and say | Pick one of 2–3 replies (differing mainly in speech level) and say it aloud |
| 1. Sentence frames | Say a template with one blank, e.g. "저는 ___에서 왔어요" |
| 2. Help on demand | Free speech with /hint, /en, /frames and English subtitles |
| 3. Free conversation | No help |

Characters speak simply at low levels (Seo-yeon is helping a new foreign hire), and expectations rise with level: at support level 2 or below, grammar-only errors cost nothing and register slips cost at most −3 with a gentle reaction. Repeated slips in one session make the character noticeably cooler even when the cost is capped.

## Register rules

Korean gates register mostly on age and hierarchy; Japanese mostly on in-group vs. out-group (uchi/soto). These are v1 simplifications: hand-check them, and have a native speaker review them before the beta.

**Korean**

| Level | Example ending | Used when |
| --- | --- | --- |
| 하십시오체 (formal) | -습니다 / -십시오 | Team leads, formal meetings, presentations |
| 해요체 (polite) | -아요 / -어요 | Default with most adults, including Seo-yeon at first |
| 반말 (casual) | -아 / -어, -야 | Only after an offer; older people may use it with you first |

Also judged: -(으)시- when talking about someone senior (missing 께서 alone is not an error), honorific vocabulary (드시다, 계시다), and address terms (선배, 팀장님; never a senior's bare name, and name + 씨 to a senior sounds too familiar). Kinship terms (형, 누나, 오빠, 언니) depend on the player's gender too, so onboarding asks, or lets the player choose how to be addressed.

**Japanese**

| Level | Example | Used when |
| --- | --- | --- |
| Keigo (尊敬語 / 謙譲語) | 何になさいますか / 伺います | Service staff, business; learners mostly need to *understand* it |
| です / ます | 行きます / そうです | Default with acquaintances, including Ren for a long time |
| Plain form | 行く / そうだよ | In-group only; with Ren after "タメ口でいいよ" |

**Japanese judge scope for v1:** です/ます vs plain form, common set phrases (失礼します, お願いします, お疲れ様です), address terms (さん, 先輩), "too stiff" (correct but socially distant, e.g. heavy keigo with a neighbor), and an indirectness score on request and complaint beats only. Full sonkeigo/kenjōgo production waits for a later business-Japanese track. This also removes the 8B judge's weakest area.

**Validation layer.** Korean sentence endings are regular enough for a rule-based check that confirms or vetoes the judge's register label. Japanese uses fugashi (MeCab) to tell です/ます from plain form.

**Texting has its own register** (for the texting layer later): ㅋ vs. ㅋㅋㅋ, leaving someone on read (읽씹, 既読スルー), stickers and emoji with seniors.

## Characters

The two leads cover the two halves of a new life, **work and home**, and teach different lessons: Seo-yeon's arc *equalizes* through age and hierarchy (you earn casual speech with a senior), Ren's arc moves slowly from strangers to friends between peers, and teaches indirectness. Both progress through several visible milestones, not just a speech-level switch.

**Korean lead: 박서연 (Park Seo-yeon), your 선배 at a Seoul startup**

| | |
| --- | --- |
| Who | Marketing, two years older than you, assigned to show you the ropes. Sharp, a little overworked, quietly ambitious |
| Core lesson | Age and hierarchy decide register. Her first real question is "몇 년생이에요?" |
| Register arc | Both in 해요체 → she may slip into 반말 first (she's older) → "말 편하게 해도 돼요." You keep calling her 선배, and stay polite in front of the team lead |
| Offenses | 반말 before the offer, calling her name + 씨 (name_ssi_to_senior), missing honorifics about superiors, dropping 선배님 in front of the team lead |
| Texting | KakaoTalk: ㅋㅋ, ㅠㅠ, late-night complaints about the team lead |

**Japanese lead: 中島蓮 (Nakajima Ren), your next-door neighbor**

| | |
| --- | --- |
| Who | Same age as you. Grad student who plays guitar in a small band. Polite, a little shy, quietly funny once you know him |
| Core lesson | Becoming part of someone's circle slowly, plus **indirectness**: raising a problem without complaining directly |
| Why it's slow | Neighbors in Japan keep a polite distance for a long time, so a drawn-out progression is realistic |
| Register arc | です/ます for a long time → he starts using casual speech around his friends → "タメ口でいいよ" → first names and LINE |
| Offenses | Plain form before the offer, sounding too stiff (heavy keigo with a neighbor), complaining bluntly |
| Texting | LINE, once earned. Stickers matter |

**Supporting cast**

- **오 팀장 (Team lead Oh):** mid-40s, strictly formal; the honorifics test in Seo-yeon's story
- **中村健二 (Kenji):** owner of the izakaya Ren takes you to; warms up fast, a contrast to Ren; you hear service keigo there
- **Later:** 高橋健太 (Kenta), a workplace 先輩 for a future business-Japanese track; 한지우 (Ji-woo) for the share-house track

**The player:** a foreigner who just moved there, the same in both languages. Onboarding sets name (in Hangul or kana), age, gender or preferred address terms, and level.

**Character rules:** no romance, even if a user pushes. Characters have their own lives and other friends, never guilt-trip, and are clearly fictional.

## Story system

The app runs in seasons, like a K-drama: episodes with their own plot, so people return for the story, not a streak. **The LLM never invents the plot.** You write each episode as a short series of beats with conditions; the model improvises dialogue only inside the current beat.

```yaml
episode: seoyeon_s1e03_hoesik
characters: [seoyeon, team_lead_oh]
beats:
  - id: arrive
    speaker: seoyeon
    goal: Seo-yeon briefs you on who sits where at the team dinner
  - id: pour
    speaker: team_lead_oh
    goal: Team lead raises his glass; you're expected to offer to pour
    pass_if: user uses honorifics with the team lead
    on_fail: Seo-yeon covers for you; respect -3
  - id: after
    speaker: seoyeon
    goal: Walking to the subway, Seo-yeon reacts to how it went
    variants: [proud, embarrassed]   # chosen by state
```

This keeps the story's shape in your hands, keeps branching to a few written variants, and makes each episode testable.

Each beat can also carry `beginner_frames`: 2 suggested replies with English glosses, shown at support level 1 or below. Beats advance when the goal is met or after a set number of turns, so a struggling beginner never gets stuck.

**Seo-yeon, Season 1 (Episodes 1–3 are beat-level; 4–7 are outlines)**

1. **첫 주 (First week):** greet (she introduces herself, 해요체) → age ("몇 년생이에요?"; she's two years older, so you should call her 선배/선배님 from now on) → cafeteria (small talk about where you're from, saved as a memory) → hook (tomorrow's first meeting with 오 팀장님)
2. **첫 실수 (The first mistake):** reminder (a report is due) → report (the team lead asks through her; explain or apologize politely; on fail, she covers for you, respect −2) → advice (thanking her properly adds closeness; warm or tired variant) → hook (invitation to Friday's team dinner)
3. **회식 (Team dinner),** with 오 팀장: arrive (who sits where) → pour (offer to pour with honorifics; on fail, she covers, respect −3) → question (the team lead asks something personal; answer with honorifics) → after (walking to the subway: proud or embarrassed variant) → hook (she's competing for a promotion)
4. The promotion race heats up
5. She asks you a favor
6. The register offer, if closeness and respect allow it
7. Finale: the promotion result

**Ren, Season 1**

1. Moving-in greeting: you bring a small gift; formal です/ます, surname + さん
2. Garbage day: you sort the trash wrong; he quietly helps; first small talk
3. The noise problem: his guitar late at night; raise it indirectly or bluntly, and the relationship branches
4. Sharing food (お裾分け): he brings extra; you return the favor
5. Festival with his friends: he starts using casual speech; you juggle speech levels with strangers
6. "タメ口でいいよ": first names, LINE
7. Trust: he asks you to water his plants while he's away

## Architecture and stack

Each turn splits after speech-to-text: one path produces the character's spoken reply, the other judges your turn and updates the relationship. The character reads state but never writes it.

```text
Push-to-talk ──> Speech-to-text ──> "I heard" ──> Character LLM ──> TTS voice
                 (raw, not          confirm          ^
                  normalized)          |             | state + memories + beat
                                       v             |
                                   Judge LLM ──> State store ──> Session summary
                                   (JSON + rule   (bounded
                                    checks)        deltas)
```

The judge runs after the reply's first sentence has gone to TTS; its changes apply from the next turn.

**Per turn**

1. Push-to-talk records audio
2. Speech-to-text returns a raw transcript, settings chosen so mistakes aren't "fixed"
3. "I heard: …" — accept, re-record or type a correction; low confidence (avg_logprob < −0.7) → the character asks you to repeat, in character, with no judge call
4. The character replies (streamed sentence by sentence to TTS), conditioned on persona, register, state, memories and the beat goal
5. The judge scores the accepted text against social facts, state and the current beat; rule checks confirm or veto; changes are written with reasons
6. A slip explanation is shown to the player if needed

**Stack on the M2 Pro (16 GB), all free and local**

| Layer | Choice | Memory |
| --- | --- | --- |
| Speech-to-text | Whisper large-v3-turbo via `mlx-whisper` (large is more accurate on Korean but heavier); SenseVoice as a backup | ~1.6 GB |
| Character + judge | Qwen3 8B via Ollama, num_ctx 4096, keep_alive 30m, thinking off; judge model configurable (qwen3:4b to test) | ~5 GB |
| Text-to-speech | macOS `say` during development (testing only, per Apple's license); MeloTTS for demo clips; CosyVoice 2 later | ~0 / ~1–2 GB |
| Japanese parsing | fugashi (MeCab) + unidic-lite | small |
| Storage | SQLite + YAML files in git; tests use test.db | — |
| Interface | Python CLI, then FastAPI backend for the iPhone app | — |

**Measured on the M2 Pro (Nov 12):** speech-to-text ~1.0 s, first reply sentence ~2.5 s, first audio ~4–5 s after confirming the transcript. Memory is the main constraint: with whisper large, MeloTTS and other apps open, the Mac used 16 GB of swap and everything slowed about 10×. The judge takes ~13.6 s (it runs after the reply starts; to be optimized).

**Voice output rules:** only the character's reply text reaches TTS, with emoji and non-Korean text stripped (emoji stay on screen). Check licenses before any public release: Whisper and MeCab allow commercial use; SenseVoice's license is unclear on commercial use.

## Data model

Static content (characters, episodes) lives in YAML files in git; everything that changes lives in SQLite. That split is what lets this scale: new characters and episodes are content, not code.

**Character file**

```yaml
id: seoyeon
language: ko
name: 박서연
role: senior_coworker        # 선배
age_offset: +2               # relative to the player
group: in
register_to_player_default: haeyo
register_expected_default: haeyo
register_ceiling: banmal     # she may offer 반말
asymmetric_first: true       # she may go casual before you
beginner_tolerance: true
offer_threshold: {closeness: 60, respect: 55}
address_terms: [선배, 선배님]
offenses:
  - banmal_before_offer
  - name_ssi_to_senior
  - bare_name_or_no_title_in_front_of_boss
  - missing_honorifics_about_superiors
milestones:
  - {id: drops_ssi, conditions: {closeness: 40}, effect: calls you by name without 씨}
  - {id: lunch_invite, conditions: {closeness: 45, episodes_done: 2}, effect: invites you to lunch}
  - {id: kakao_add, conditions: {closeness: 50}, effect: adds you on KakaoTalk}
  - {id: she_goes_casual, conditions: {closeness: 55}, effect: uses 반말 with you first}
  - {id: banmal_offer, conditions: {closeness: 60, respect: 55}, effect: offers 반말 both ways (private)}
persona: >
  Marketing at a Seoul startup, two years ahead of you. Sharp, a
  little overworked, quietly ambitious. Covers for people she likes.
voice_id: <tts voice>
channel: kakaotalk            # for the texting layer later
```

**Player file (`player.yaml`)**

```yaml
name: 프라나브
age: <age>
gender: <gender>             # or address-term preference
level_ko: beginner
level_ja: <level>
support_level_ko: 1
support_level_ja: 2
relationship_speed: 2.0      # testing only; 1.0 for real use
debug: true                  # testing only
```

**Tables**

| Table | Key columns | Purpose |
| --- | --- | --- |
| `player` | name, age, address_prefs, levels, support levels | Onboarding facts the judge needs |
| `character_state` | character_id, closeness, respect, offense, register_to_player, register_expected, address_form, milestones_reached, updated_at | One row per character |
| `memories` | character_id, about (player/character), fact, source_quote, source_turn_id | Facts retrieved into the reply prompt |
| `episode_progress` | episode_id, current_beat, variant, status | Where you are in each story |
| `sessions` | character_id, episode_id, started_at, summary | One conversation; summary shown at the end |
| `turns` | session_id, user_text_raw, user_text_accepted, corrected, avg_logprob, user_register, reply_text, judge_json, stage timings | Full log, judge output as JSON |
| `state_events` | turn_id, variable, delta, reason | Every change with its reason: tuning trail and future training data |

**Memory rule:** new memories come only from the player's own turns, and each one's `source_quote` must appear in one of those turns. Facts the character states about herself are stored separately as character facts, so she never mistakes her own statements for facts about you. Summaries' "she'll remember" lines come only from validated memories.

## Judge

A separate, low-temperature LLM call that returns structured JSON only and never writes dialogue. Keeping it separate stops the character from grading itself generously. On an 8B local model the judge is the weakest link, so rule-based checks matter most here.

**Inputs:** accepted transcript, character file, current state, current beat and its `pass_if`, last 4 turns (speaker-labeled PLAYER: / character), the register the character expects.

**Output**

```json
{
  "subject": "팀장님",
  "subject_is_senior": true,
  "verb_has_honorific": false,
  "register_used": "banmal",
  "register_expected": "haeyo",
  "register_match": false,
  "offense_ids": ["banmal_before_offer"],
  "grammar_errors": [
    {"span": "어제 갈 거예요", "fix": "어제 갔어요", "type": "tense", "severity": "minor"}
  ],
  "beat_passed": false,
  "new_memories": [{"about": "player", "fact": "going hiking this weekend", "source_quote": "주말에 등산 가요"}],
  "state_deltas": {"closeness": 0, "respect": -3},
  "offense": "mild",
  "repair_required": false,
  "reason": "Used 반말 before Seo-yeon offered; content was friendly."
}
```

**Rules enforced in code and prompt**

- Per-turn bounds (closeness −3 to +3, respect −10 to +3), so one turn can't swing the relationship; positive closeness multiplied by `relationship_speed`
- Any slip means no closeness gain that turn
- Beginner tolerance at support level ≤ 2: grammar-only errors cost 0 respect; register/honorific slips cost at most −3
- Grammar lowers respect only if it would cause misunderstanding; register errors always count
- `repair_required` only for serious offense; the next turn is judged on whether it repairs
- `reason` is mandatory; it goes into `state_events` and the session summary

**Korean rule checks:** the sentence-ending validator; an honorific check for senior subjects (missing 께서 alone is not an error, since 이/가 is normal in everyday 해요체); and an address-term check (name + 씨 to a senior). When a rule check is high-confidence and disagrees with the judge, the rule wins and both are recorded.

**Measured (Nov 12):** register accuracy 100%, offense precision 100%, offense recall 90%. The misses were honorifics, fixed on build-plan Day 21. The test labels still need review by a Korean speaker.

**Evals:** `tests/eval_judge.py` and `tests/eval_validator.py` print a short summary and write details to `tests/eval_results.csv`. Run them yourself in a separate terminal rather than through Claude Code, to save tokens.

## Build plan

**Status (Nov 13):** Milestones 1–3 done. Next: Milestone 4 (beat runner, Seo-yeon Episodes 1–3, the honorific check, relationship milestones). The day-by-day plan is in the separate "Build Plan: Day by Day" doc.

1. **Milestone 1 — STT check:** done. Turbo chosen; no register/honorific corrections; Korean misrecognition is high for a beginner speaker, handled by the "I heard" confirm step
2. **Milestone 2 — text loop with Seo-yeon:** done. Judge, rule checks, consequences, memory, summaries
3. **Milestone 3 — voice on the Mac:** done. ~4–5 s to first audio
4. **Milestone 4 — stories and consequences:** beat runner, Episodes 1–3, honorific check, team lead, relationship milestones, repair, episode summaries
5. **Milestone 5 — Ren:** ren.yaml, fugashi です/ます check, indirectness judging, episodes 1–3

**Then the iPhone path:** FastAPI backend on the Mac over Tailscale; SwiftUI app with WhisperKit; relationship screens and SwiftData state; 4–6 weeks of daily personal use; TestFlight beta with 30–50 learners on a hosted model; go / no-go in June 2027.

**Known follow-ups:** judge speed (~13.6 s; shorten output, check retries, test qwen3:4b for the judge); more natural voice (MeloTTS / CosyVoice 2) before demo clips; awkward replies to short phrases (add example exchanges to the character prompt); native review of the Korean test labels.

## Later features

**Texting layer: characters in your real phone.** Between sessions, characters message you in the language, tied to the story. Your replies go through the same judge. Channels: KakaoTalk (ko) / LINE (ja) official accounts for immersion; message-style notifications from the app as the easiest; a Telegram bot for personal testing. Guardrails: opt-in, quiet hours, user-set frequency, no guilt-tripping, no romance.

**Share-house storyline (Korean, second track).** 한지우 (Han Ji-woo), a same-age housemate trying to break into webtoons, plus an older house manager and a younger student. The lesson shifts from *earning* 반말 to *managing* register across a group, with the house KakaoTalk group chat as the centerpiece.

**Business-Japanese track.** 高橋健太 (Kenta), a workplace 先輩, with full keigo.

**Mirrored worlds.** The same scenario in both languages, then a comparison of where the right move differed.

## Go-to-market and retention (summary)

- Acquisition: blunder clips, relationship share cards, "tell us your worst register mistake" scenes, expat and language creators, build in public on X, Instagram DMs + a 2-minute form, launches timed to departures (Japan April, Korea March/September, JET summer)
- Retention: seasons with cliffhangers, characters texting about their own lives, absence noticed warmly, reputation spreading between characters, visible relationship milestones
- Exchange-app users: position as rehearsal before real exchange; target people frustrated with flaky partners or dating behavior
- Measure: 30-day retention by user motivation, and shares per user
- Early supporters: a 350K-follower language creator interested in early access; a UI/UX design student helping with name, brand, character art, landing page and app design (credit + portfolio case study; revisit pay if it grows)

## Scaling path (summary)

0. Prove retention in a beta → 1. Own one group (people moving there) → 2. Institutions → 3. More languages (du/Sie, tu/vous, tú/usted, Hindi, Thai, Vietnamese) and interface languages → 4. Platform (authoring tool, fine-tuned judge, licensing). Bottlenecks: native-speaker review per language, LLM cost per user, your time.

## Risks and open questions

| Risk | Mitigation |
| --- | --- |
| STT misrecognizes learner speech | "I heard" confirm step; low-confidence → ask to repeat; beginners use choose-and-say |
| Weak judge on 8B | Rule checks, bounded deltas, narrow Japanese scope; hosted judge for the beta if needed |
| Memory pressure on 16 GB | Turbo STT, `say` in development, num_ctx 4096, close other apps |
| Pacing | Tune from `state_events` over weeks of your own use; reset relationship_speed to 1.0 |
| Story sprawl | Beat-based episodes, a few written variants only |
| Latency | Streaming, judge after first sentence, a thinking sound ("음…") |
| Flat voices | MeloTTS / CosyVoice 2 before the marketing push |
| Close competitors | Move fast; build content and data, not just the mechanic |
| Attachment design | No romance, no guilt, characters with their own lives |

**Open questions:** closeness decay with absence or story-only? Can a serious offense permanently cap a relationship? Final app name? Which native speakers will review the Korean and Japanese rules?
