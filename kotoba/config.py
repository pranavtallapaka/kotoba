import os

OLLAMA_URL = "http://localhost:11434"

CHARACTER_MODEL = os.environ.get("KOTOBA_CHAR_MODEL", "qwen3:8b")
JUDGE_MODEL = os.environ.get("KOTOBA_JUDGE_MODEL", "qwen3:8b")

# Used as default in llm.py function signatures (matches character model).
MODEL = CHARACTER_MODEL
