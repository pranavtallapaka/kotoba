# Voice Language Tool — Design Doc

Exported Oct 28, 2026 from the shared design doc. The shared doc is the source of truth; re-export after big changes.

## Overview

A voice app for practicing Korean and Japanese with persistent characters whose way of speaking to you is earned or lost through how you treat them. Mistakes change the scene instead of triggering a correction card.

**One-liner:** practice being someone in Korea or Japan, with characters who remember how you treated them, in conversation and in your texts.

**Differentiator: social consequences that persist over time.** Role-play of real-life scenarios is standard (Speak, Praktika, Talkpal, Noonchi). What no app does is make the relationship itself the thing you train: use the wrong speech level and the character goes cold, earn trust and they offer 반말, leave them on read and they notice.

**Lock-in vs. moat**

- **Short-term lock-in:** each user's relationships. Two months of earning Seo-yeon's trust is a reason not to switch. This protects against churn, not against copying.
- **Long-term moat (doesn't exist yet):** authored characters and story seasons with native-checked cultural rules (IP a competitor can't copy), plus labeled data on learner speech and social appropriateness, which can train a judge nobody else can build.

**Goals for v1**

- One Korean and one Japanese character you'd actually come back to
- Register choice judged in live conversation, not just grammar
- Mistakes land as consequences inside the scene
- A state model clean enough to scale to more characters, languages and users

**Non-goals for v1:** pronunciation scoring, avatars, accounts and hosting, curriculum content, romance of any kind.

## Positioning

**For people moving to Korea or Japan, not visiting.** Register is a daily, high-stakes problem for people who study, work or live there. Tourists rarely face it: their exchanges are short and scripted, locals forgive foreigners, and a translation app covers most of a trip. Travel motivation also ends on a date, which drives churn.

**Target users, in order**

1. Students heading abroad (exchange, language school, programs like IJP)
2. People moving for a job (JET, EPIK, corporate transfers)
3. Long-term learners who care about the culture
4. Later, B2B: study-abroad offices, exchange programs, relocation firms

**Competitors**

| Product | What it does | Gap vs. this product |
| --- | --- | --- |
| Speak | Structured voice lessons, AI tutor, Korean and Japanese | Tutor, not a relationship; no social consequences |
| Praktika | Avatar tutors with long-term memory | Memory makes it personalized, not consequential |
| Langua, Practice Me | AI conversation partners that remember you | Same: remembering you is not judging you |
| Noonchi | Korean AI role-play with feedback on honorifics and tone | Closest competitor; no visible persistent relationships; Korean only |
| LangBuddy | AI buddy who texts you on WhatsApp/iMessage, with voice notes | Has the texting channel; texts don't carry relationship state or register |
| HelloTalk, Tandem | Human language exchange (HelloTalk: 70M+ registered) | Partners are peers; they can't be your boss or landlord, and they rarely correct register |

The defensible claim is narrow: nobody makes the *relationship* the thing you train. Re-check Noonchi and LangBuddy before the beta.

**Market signal:** Japanese is the 4th and Korean the 6th most-studied language on Duolingo. JLPT had 1.65M examinees in 2025; TOPIK had 550K+ from Jan–Sep 2025. International students: 408K in Japan, 274K in Korea. Realistic outcome if retention works: a paid niche product with thousands to tens of thousands of subscribers. Note: most people moving to Japan/Korea are not English speakers, so additional interface languages (Chinese, Vietnamese, Nepali) may matter more than new target languages.

## Core mechanic: relationship state

Each character carries a small state that updates every turn and persists across sessions. The character's reply reads that state; only the judge writes it.

| Variable | Range | Goes up when | Goes down when | Controls |
| --- | --- | --- | --- | --- |
| Closeness | 0–100 | Regular conversation, recalling their details, fitting small talk | Long absence (slow, never punishing), ignoring what they said | Unlocks register changes past a threshold |
| Respect | 0–100 | Correct register, good repair after a slip | Too casual, 반말 before the offer, rude content | Warmth, willingness to help, how smoothly scenes go |
| Offense | none / mild / serious | — | One serious breach | Scene branches; repair may be required |
| Register (theirs → you, yours → them) | per language | They offer a change and you accept | Serious offense resets it | What they use with you, and what they expect back |

**Social facts** are fixed per character and define what's *correct*: age relative to the player (set relative, not as a number), role, in-group vs. out-group, and a register ceiling.

**Consequences, from mild to serious**

1. Tone: shorter, more formal replies
2. Friction: the character asks what you meant, or corrects you in character
3. Branch: the scene takes a worse path (no favor, colder walk to the subway)
4. Repair required: the scene waits until you recover in the language, at the right level

**Register changes are offered, never taken.** In Korean this is the "말 편하게 해도 돼요" moment. Accepting unlocks the new level; using it early costs respect. Some relationships are **asymmetric**: the other person goes casual while you stay polite (Kenji). Some **cap out** and never go casual.

**Absence is noticed in the story, never punished.** Come back after a week and Seo-yeon says "오랜만이에요!" No streak shame, no guilt messages.

## Register rules

Korean gates register mostly on age and hierarchy; Japanese mostly on in-group vs. out-group (uchi/soto). These are v1 simplifications: hand-check them, and have a native speaker review them before the beta.

**Korean**

| Level | Example ending | Used when |
| --- | --- | --- |
| 하십시오체 (formal) | -습니다 / -십시오 | Team leads, formal meetings, presentations |
| 해요체 (polite) | -아요 / -어요 | Default with most adults, including Seo-yeon at first |
| 반말 (casual) | -아 / -어, -야 | Only after an offer; older people may use it with you first |

Also judged: -(으)시- and 께서 when talking about someone senior, honorific vocabulary (드시다, 계시다), and titles (선배, 팀장님; never a senior's bare name). Kinship terms (형, 누나, 오빠, 언니) depend on the player's gender too, so onboarding must ask, or let the player choose how to be addressed.

**Japanese**

| Level | Example | Used when |
| --- | --- | --- |
| Keigo (尊敬語 / 謙譲語) | 何になさいますか / 伺います | Service to new customers, superiors, out-group |
| です / ます | 行きます / そうです | Default with acquaintances; your target with Kenji |
| Plain form | 行く / そうだよ | In-group only; Kenji uses it with regulars, you don't use it with him |

LLM judges miss keigo direction errors (elevating yourself, humbling the other person). Log every keigo call for review.

**Validation layer.** Korean sentence endings are regular enough for a rule-based check that confirms or vetoes the judge's register label. Japanese uses fugashi (MeCab) to tell です/ます from plain form; keigo stays LLM-judged with manual review.

**Texting has its own register** (for the texting layer later): ㅋ vs. ㅋㅋㅋ, leaving someone on read (읽씹, 既読スルー), stickers and emoji with seniors.

## Characters

The shared premise in both languages: **you've just moved there for work.** One character is at work, the other is your regular spot after work. The two arcs teach opposite patterns: Seo-yeon's *equalizes* (you earn casual speech with each other), Kenji's stays *asymmetric* (he goes casual, you stay polite).

**Korean: 박서연 (Park Seo-yeon), your 선배 at a Seoul startup**

| | |
| --- | --- |
| Who | Marketing, two years older than you, assigned to show you the ropes. Sharp, a little overworked, quietly ambitious |
| Core lesson | Age decides register. Her first real question is "몇 년생이에요?" |
| Register arc | Both in 해요체 → she may slip into 반말 first (she's older) → "말 편하게 해도 돼요." You keep calling her 선배 |
| Offenses | 반말 before the offer, dropping 선배님 in front of the team lead, sloppy honorifics *about* the boss |
| Texting | KakaoTalk: ㅋㅋ, ㅠㅠ, late-night complaints about the team lead; leaving her on read costs you |
| Later cast | 오 팀장 (team lead, strictly formal), her job-hunting cousin, a rival coworker |

**Japanese: 中村健二 (Nakamura Kenji), the 大将 of a small izakaya near your apartment**

| | |
| --- | --- |
| Who | Mid-50s, runs an eight-seat izakaya alone. Gruff at first, proud of his food, worried about the neighborhood changing |
| Core lesson | Uchi/soto, experienced by crossing it: service keigo to new customers (いらっしゃいませ、何になさいますか), casual with regulars (おう、来たか。いつもの？) |
| Register arc | Asymmetric: he goes casual as you become a 常連; you aim for warm です/ます and never go plain |
| Offenses | Plain form with him, dining etiquette mistakes, careless about his food |
| Texting | LINE, once earned: he adds you mid-season (「今日、いいの入ったぞ」). Stickers matter |
| Later cast | His daughter (your age, a peer arc), a regular from your company, the landlord |

**Setting choice:** place the izakaya somewhere you know well, such as Nagoya, so you can judge whether it feels real. Hold off on regional dialect.

**The player:** a foreigner who just moved for work, the same in both languages so the stories can mirror each other later. Onboarding sets age, gender (or preferred address terms) and level.

**Character rules:** no romance, even if a user pushes. Characters have their own lives and other friends, and never guilt-trip. They're clearly fictional.

## Story system

The app runs in seasons, like a K-drama: weekly episodes with their own plot, so people return for the story, not a streak. **The LLM never invents the plot.** You write each episode as a short series of beats with conditions; the model improvises dialogue only inside the current beat.

```yaml
episode: seoyeon_s1e03_hoesik
characters: [seoyeon, team_lead_oh]
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

This keeps the story's shape in your hands, keeps branching to a few written variants, and makes each episode testable.

**Seo-yeon, Season 1**

1. First week: introductions, the age question, both in 해요체
2. Your first mistake at work; she covers for you
3. The team dinner (회식): pouring drinks, honorifics with the team lead
4. She's competing for a promotion
5. She asks you a favor
6. The register offer, if closeness and respect allow it
7. Finale: the promotion result

**Kenji, Season 1**

1. First visit: full service keigo; you order
2. He remembers your order
3. The regulars' gossip
4. His rent is going up and the shop is in trouble
5. You help with an English menu (roles reverse)
6. He adds you on LINE
7. Finale: your own bottle behind the bar (キープ), the sign you're a 常連

## Architecture and stack

Each turn splits after speech-to-text: one path produces the character's spoken reply, the other judges your turn and updates the relationship. The character reads state but never writes it.

```text
Push-to-talk ──> Speech-to-text ──> Character LLM ──> TTS voice
                 (raw, not             ^
                  normalized)          | state + memories
                      |                |
                      v                |
                  Judge LLM ──────> State store ──> Session summary
                  (JSON + register   (bounded
                   check)             deltas)
```

The judge can run in parallel with the reply to save time; its changes then apply from the next turn.

**Per turn**

1. Push-to-talk records audio
2. Speech-to-text returns a raw transcript, settings chosen so mistakes aren't "fixed"
3. The judge scores it against the character's social facts, state and current beat; returns JSON
4. The rule-based validator confirms or vetoes the register label; changes are written with reasons
5. The character replies, conditioned on persona, register, state, memories and the beat goal
6. Text-to-speech speaks it in the character's voice

**Stack on the M2 Pro (16 GB), all free and local**

| Layer | Choice | Memory |
| --- | --- | --- |
| Speech-to-text | Whisper large-v3-turbo via `mlx-whisper`; SenseVoice or Qwen3-ASR as backups | ~1.6 GB |
| Character + judge | Qwen3 8B via Ollama, one model with two prompts | ~5 GB |
| Text-to-speech | MeloTTS to start; CosyVoice 2 later (emotion control) | ~1–2 GB |
| Japanese parsing | fugashi (MeCab) | small |
| Storage | SQLite + YAML files in git | — |
| Interface | Python CLI, then FastAPI backend for the iPhone app | — |

About 8–9 GB in total, leaving room for macOS. Avoid Supertonic 3 (discontinued). Check commercial licenses before any public release: Whisper is MIT; several model licenses (SenseVoice, EXAONE) restrict commercial use.

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
offer_threshold: {closeness: 60, respect: 55}
address_terms: [선배, 선배님]
offenses:
  - banmal_before_offer
  - bare_name_or_no_title_in_front_of_boss
  - missing_honorifics_about_superiors
persona: >
  Marketing at a Seoul startup, two years ahead of you. Sharp, a
  little overworked, quietly ambitious. Covers for people she likes.
voice_id: <tts voice>
channel: kakaotalk            # for the texting layer later
```

**Tables**

| Table | Key columns | Purpose |
| --- | --- | --- |
| `player` | age, address_prefs, level_ko, level_ja | Onboarding facts the judge needs |
| `character_state` | character_id, closeness, respect, offense, register_to_player, register_expected, updated_at | One row per character |
| `memories` | character_id, fact, source_turn_id | What you've told them; retrieved into the reply prompt |
| `episode_progress` | episode_id, current_beat, variant, status | Where you are in each story |
| `sessions` | character_id, episode_id, started_at, summary | One conversation; summary shown at the end |
| `turns` | session_id, user_text_raw, user_register, reply_text, judge_json | Full log, judge output as JSON |
| `state_events` | turn_id, variable, delta, reason | Every change with its reason: your tuning trail and future training data |

`state_events` and `turns` matter twice: you'll use them to tune pacing now, and they're the labeled data behind the long-term moat.

## Judge

A separate, low-temperature LLM call that returns structured JSON only and never writes dialogue. Keeping it separate stops the character from grading itself generously. On an 8B local model the judge is the weakest link, so the rule-based validator matters most here.

**Inputs:** raw transcript, character file, current state, current beat and its `pass_if`, last 4 turns, the register the character expects.

**Output**

```json
{
  "register_used": "banmal",
  "register_expected": "haeyo",
  "register_match": false,
  "offense_ids": ["banmal_before_offer"],
  "honorific_errors": [],
  "grammar_errors": [
    {"span": "어제 갈 거예요", "fix": "어제 갔어요", "type": "tense", "severity": "minor"}
  ],
  "beat_passed": false,
  "new_memories": ["going hiking this weekend"],
  "state_deltas": {"closeness": 1, "respect": -4},
  "offense": "mild",
  "repair_required": false,
  "reason": "Used 반말 before Seo-yeon offered; content was friendly."
}
```

**Rules the prompt enforces**

- Per-turn bounds (e.g. closeness −3 to +3, respect −10 to +3), so one turn can't swing the relationship
- Grammar lowers respect only if it would cause misunderstanding; register errors always count
- `repair_required` only for serious offense; the next turn is judged on whether it repairs
- `reason` is mandatory; it goes into `state_events` and the session summary

**After the judge:** the rule-based validator runs on the raw transcript. If it disagrees with `register_used`, log both and trust the rule for Korean endings.

## Build plan

The first two milestones answer the two biggest unknowns: does speech-to-text keep your mistakes, and does the judge catch register errors well enough? The day-by-day plan is in the separate "Build Plan: Day by Day" doc.

1. **Milestone 1 — STT check:** at most 1 silently corrected sentence per language
2. **Milestone 2 — text loop with Seo-yeon:** 10 typed sessions where state changes feel right
3. **Milestone 3 — voice on the Mac:** reply starts within about 3 s
4. **Milestone 4 — stories and consequences:** episodes 1–3 playable, with branching, repair and the register offer
5. **Milestone 5 — Kenji:** fugashi checks, asymmetric register, episodes 1–3

**Then the iPhone path:** FastAPI backend on the Mac over Tailscale; SwiftUI app with WhisperKit; relationship screens and SwiftData state; 4–6 weeks of daily personal use; TestFlight beta with 30–50 learners on a hosted model; go / no-go in June 2027.

## Later features

**Texting layer: characters in your real phone.** Between sessions, characters message you in the language, tied to the story. Your replies go through the same judge. Channels: KakaoTalk (ko) / LINE (ja) official accounts for immersion; message-style notifications from the app as the easiest; a Telegram bot for personal testing. Guardrails: opt-in, quiet hours, user-set frequency, no guilt-tripping, no romance.

**Share-house storyline (Korean, second track).** 한지우 (Han Ji-woo), a same-age housemate trying to break into webtoons, plus an older house manager and a younger student. The lesson shifts from *earning* 반말 to *managing* register across a group, with the house KakaoTalk group chat as the centerpiece. Comes after Seo-yeon.

**Mirrored worlds.** The same scenario in both languages, then a comparison of where the right move differed.

## Go-to-market and retention (summary)

- Acquisition: blunder clips, relationship share cards, "tell us your worst register mistake" scenes, expat creators, build in public, launches timed to departures (Japan April, Korea March/September, JET summer)
- Retention: seasons with cliffhangers, characters texting about their own lives, absence noticed warmly, reputation spreading between characters
- Exchange-app users: position as rehearsal before real exchange; target people frustrated with flaky partners or dating behavior
- Measure: 30-day retention by user motivation, and shares per user

## Scaling path (summary)

0. Prove retention in a beta → 1. Own one group (people moving there) → 2. Institutions → 3. More languages (du/Sie, tu/vous, tú/usted, Hindi, Thai, Vietnamese) → 4. Platform (authoring tool, fine-tuned judge, licensing). Bottlenecks: native-speaker review per language, LLM cost per user, your time.

## Risks and open questions

| Risk | Mitigation |
| --- | --- |
| STT "fixes" your speech | Milestone 1 test; compare models and decoding settings |
| Weak judge on 8B | Rule-based validator, bounded deltas, logged keigo calls; hosted judge for the beta if needed |
| Pacing | Tune from `state_events` over weeks of your own use |
| Story sprawl | Beat-based episodes, a few written variants only |
| Latency | Stream audio, parallel judge, an in-character "thinking" cue |
| Flat voices | MeloTTS / CosyVoice 2 before the marketing push |
| Close competitors | Move fast; build content and data, not just the mechanic |
| Attachment design | No romance, no guilt, characters with their own lives |

**Open questions:** closeness decay with absence or story-only? Can a serious offense permanently cap a relationship? Judge before the reply or in parallel? State on the phone or the server once there are testers? Which native speakers will review the rules?
