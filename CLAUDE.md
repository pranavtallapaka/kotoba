# kotoba

Voice app for practicing Korean and Japanese. Characters keep a relationship
state (closeness, respect, offense, register) that changes based on how the
user speaks to them. Mistakes have social consequences inside the scene.

## Key rules
- A separate "judge" LLM call scores each user turn and returns JSON; only the
  judge writes relationship state. The character model reads state, never writes it.
- Speech-to-text must NOT correct the user's mistakes. Never add text cleanup
  or normalization that could hide errors.
- Story plots are authored as episode YAML with beats; the LLM only improvises
  dialogue inside the current beat.
- Characters are never romantic and never guilt-trip the user.

## Stack (all local)
- Python 3.12, venv at .venv
- STT: mlx-whisper (whisper-large-v3-turbo); choice recorded in notes/decisions.md
- LLM: Qwen3 8B via Ollama (http://localhost:11434), used for both character and judge
- TTS: MeloTTS (added later)
- Storage: SQLite + YAML files in git

## Layout
characters/, episodes/, prompts/, kotoba/ (package), tests/, tools/, notes/

## Conventions
- Keep modules small and plain; no frameworks beyond what's listed.
- Record decisions with a reason in notes/decisions.md.
- End each session by adding one line to notes/tuning.md: what was done, what's next.
