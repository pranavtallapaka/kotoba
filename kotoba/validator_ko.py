"""Rule-based Korean register classifier based on sentence-final endings.

classify(text) -> (register, confidence, matched_ending)

register:   "hapsyo" | "haeyo" | "banmal" | "unknown"
confidence: "high" | "medium" | "low"
matched_ending: the matched suffix string, or "" when unknown

Multi-sentence text: returns the most casual register found.
Noise stripped before classification: trailing punctuation, ㅋ+, ㅠ+, emoji.
"""
import re
from typing import Literal

Register = Literal["hapsyo", "haeyo", "banmal", "unknown"]
Confidence = Literal["high", "medium", "low"]

_HAPSYO_SUFFIXES = ("니다", "니까", "십시오")
_HAEYO_CHAR = "요"
_HAEYO_SECONDARY = ("죠",)  # -지요 contracted

# Open-syllable endings that are unambiguously banmal when sentence-final.
# Hapsyo and haeyo are checked first so 다 / 요 never reach this set.
_BANMAL_ENDINGS: frozenset[str] = frozenset({
    "어", "아", "워", "봐", "줘", "져", "려",
    "야", "자", "지", "니", "냐",
    "해", "가", "나", "래", "파", "다", "게", "거",
})


def _strip_noise(text: str) -> str:
    """Remove emoji, standalone jamo noise (ㅋ, ㅠ, ㅎ), and trailing punctuation."""
    text = re.sub(r"[\U00010000-\U0010FFFF]", "", text)
    text = re.sub(r"[ㅋㅠㅎ]+", "", text)
    return text.strip().rstrip("!?.,~…·。！？").strip()


def _check_word(word: str) -> tuple[Register, Confidence, str]:
    """Check a single Korean word for a register-indicating ending."""
    if not word:
        return "unknown", "low", ""
    for suffix in _HAPSYO_SUFFIXES:
        if word.endswith(suffix):
            return "hapsyo", "high", suffix
    if word.endswith(_HAEYO_CHAR):
        return "haeyo", "high", _HAEYO_CHAR
    for s in _HAEYO_SECONDARY:
        if word.endswith(s):
            return "haeyo", "medium", s
    last = word[-1]
    if "가" <= last <= "힣" and last in _BANMAL_ENDINGS:
        return "banmal", "medium", last
    return "unknown", "low", ""


def _classify_sentence(sentence: str) -> tuple[Register, Confidence, str]:
    """Classify one sentence by scanning words right-to-left.

    Scanning right-to-left lets us skip trailing address terms like 선배님
    that follow the actual sentence-final verb.
    """
    cleaned = _strip_noise(sentence)
    if not cleaned:
        return "unknown", "low", ""
    for word in reversed(cleaned.split()):
        reg, conf, ending = _check_word(word)
        if reg != "unknown":
            return reg, conf, ending
    return "unknown", "low", ""


def find_register_word(text: str, register: Register) -> str:
    """Return the first word (scanning right-to-left per sentence) whose endings
    match the given register, or "" if none found."""
    for sentence in re.split(r"[.?!]", text):
        for word in reversed(sentence.split()):
            w = _strip_noise(word)
            if not w:
                continue
            reg, _, _ = _check_word(w)
            if reg == register:
                return w
    return ""


def classify(text: str) -> tuple[Register, Confidence, str]:
    """Classify the register of Korean text.

    Splits on sentence-final punctuation and returns the most casual register
    found across all sentences (banmal > haeyo > hapsyo > unknown).
    """
    parts = re.split(r"[.?!]", text)
    sentences = [p.strip() for p in parts if p.strip()]
    if not sentences:
        sentences = [text]

    results = [_classify_sentence(s) for s in sentences]

    for target in ("banmal", "haeyo", "hapsyo"):
        for reg, conf, ending in results:
            if reg == target:
                return reg, conf, ending
    return "unknown", "low", ""
