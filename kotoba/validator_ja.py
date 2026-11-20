"""Rule-based Japanese register classifier using fugashi (MeCab + unidic_lite).

classify(text) -> (register, confidence, evidence)

register:   "desu_masu" | "plain" | "unknown"
confidence: "high" | "medium" | "low"
evidence:   the surface form that determined the classification

Multi-sentence text: returns the most casual register found (plain > desu_masu > unknown).
Noise stripped before classification: emoji, supplementary-plane characters, punctuation.
"""
import re
from typing import Literal

import fugashi

Register = Literal["desu_masu", "plain", "unknown"]
Confidence = Literal["high", "medium", "low"]

_tagger: fugashi.Tagger | None = None


def _get_tagger() -> fugashi.Tagger:
    global _tagger
    if _tagger is None:
        _tagger = fugashi.Tagger()
    return _tagger


# 助動詞 cType values that signal desu/masu register.
_DESU_MASU_CTYPES = frozenset({"助動詞-マス", "助動詞-デス"})

# 助動詞 cType values that signal plain-form speech (excluding た — see below).
# 助動詞-ヌ is excluded: its surface ん always appears inside ません (skipped below).
_PLAIN_CTYPES = frozenset({"助動詞-ダ", "助動詞-ナイ"})

# Verb/adjective cForm values that mark a plain sentence-final form.
_PLAIN_CFORMS = frozenset({"終止形-一般", "終止形-促音便"})

# POS categories that follow the predicate without carrying register information.
_SKIP_POS = frozenset({"補助記号", "空白", "助詞"})


def _strip_noise(text: str) -> str:
    """Remove supplementary-plane characters (emoji) and normalize whitespace."""
    text = re.sub(r"[\U00010000-\U0010FFFF]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"[。！？!?]", text)
    return [p.strip() for p in parts if p.strip()]


def _ctype(token) -> str:
    return getattr(token.feature, "cType", None) or ""


def _classify_tokens(tokens: list) -> tuple[Register, Confidence, str]:
    """Scan tokens right-to-left for the first register-indicating form."""
    for i in range(len(tokens) - 1, -1, -1):
        token = tokens[i]
        pos = token.feature.pos1
        ct = _ctype(token)
        cform = getattr(token.feature, "cForm", None) or ""
        surface = token.surface

        if pos in _SKIP_POS:
            continue

        if pos == "助動詞":
            # ん in ません/ございません is a contracted negative inside a polite form.
            # unidic tags it 助動詞-ヌ (classical ぬ) or 助動詞-ナイ depending on context.
            # Skip it so the scan continues left to find ませ (助動詞-マス).
            if surface == "ん" and ct in ("助動詞-ナイ", "助動詞-ヌ"):
                continue

            # た is ambiguous: plain past (食べた) vs. polite past (ました/でした).
            # Peek at the token immediately to the left to decide.
            if ct == "助動詞-タ":
                left = tokens[i - 1] if i > 0 else None
                left_ct = _ctype(left) if left else ""
                if left_ct in _DESU_MASU_CTYPES:
                    return "desu_masu", "high", surface
                return "plain", "high", surface

            if ct in _DESU_MASU_CTYPES:
                return "desu_masu", "high", surface
            if ct in _PLAIN_CTYPES:
                return "plain", "high", surface
            break  # unrecognized auxiliary — stop

        if pos == "動詞":
            if cform in _PLAIN_CFORMS:
                return "plain", "medium", surface
            break  # non-terminal verb form (連用形 etc.) — stop

        if pos == "形容詞":
            if cform in _PLAIN_CFORMS:
                return "plain", "medium", surface
            break

        # Content word with no following predicate marker — stop.
        if pos not in ("感動詞", "フィラー"):
            break

    return "unknown", "low", ""


def _classify_sentence(sentence: str) -> tuple[Register, Confidence, str]:
    tagger = _get_tagger()
    tokens = list(tagger(sentence))
    return _classify_tokens(tokens)


def classify(text: str) -> tuple[Register, Confidence, str]:
    """Classify the register of Japanese text.

    Splits on sentence-final punctuation and returns the most casual register
    found across all sentences (plain > desu_masu > unknown).
    """
    cleaned = _strip_noise(text)
    sentences = _split_sentences(cleaned)
    if not sentences:
        sentences = [cleaned]

    results = [_classify_sentence(s) for s in sentences if s]

    for target in ("plain", "desu_masu"):
        for reg, conf, evidence in results:
            if reg == target:
                return reg, conf, evidence
    return "unknown", "low", ""
