"""Rule-based Korean subject-honorific checker.

check(text, extra_seniors=None) -> HonorificResult

Detects whether a senior noun is the grammatical subject of a clause and
whether the predicate uses -(으)시- or an inherently-honorific verb stem.

confidence:
  "high"   — senior noun + explicit subject marker (이/가/께서) found
  "medium" — senior noun + topic marker (은/는) found
  "low"    — senior noun present but no structural marker detected

Missing 께서 alone is NOT an error; this module only checks verb honorifics.
"""
import re
from dataclasses import dataclass, field
from typing import Literal

Confidence = Literal["high", "medium", "low"]

# Title-based senior nouns (with and without 님)
_DEFAULT_SENIORS: frozenset[str] = frozenset({
    "팀장님", "팀장", "부장님", "부장", "사장님", "사장",
    "선생님", "선생", "선배님", "선배", "이사님", "이사",
    "과장님", "과장", "차장님", "차장", "대표님", "대표",
    "교수님", "교수",
})

# Explicit subject markers — space/comma/end required after, to avoid matching
# the copula 이에요 or genitive 이's.
_SUBJ_RE = re.compile(r'([가-힣]+)(이|가|께서)(?=[\s,]|$)')

# Topic markers — usually signal subject but weaker evidence
_TOPIC_RE = re.compile(r'([가-힣]+)(은|는)(?=[\s,]|$)')

# -(으)시- morpheme in various conjugated forms
_HON_VERB_RE = re.compile(
    r'[가-힣]+'
    r'(?:으시|시겠|시고|시는|시면|시어|셔[요서]?|셨|세요|십[니시]|신[데가]?|실|시길|시나|실까|으셨)'
)

# Verb stems that are inherently honorific regardless of explicit 시 spelling
_HON_STEMS: frozenset[str] = frozenset({
    "드시", "계시", "주무시", "말씀하시", "잡수시", "잡수",
})


@dataclass
class HonorificResult:
    subject: str              # senior noun found as subject, or ""
    subject_is_senior: bool
    verb_has_honorific: bool
    confidence: Confidence


def _has_honorific_verb(text: str) -> bool:
    if _HON_VERB_RE.search(text):
        return True
    return any(stem in text for stem in _HON_STEMS)


def _is_senior(noun: str, all_seniors: frozenset[str]) -> bool:
    """True if noun exactly matches or ends with a senior title."""
    if noun in all_seniors:
        return True
    # e.g. "오준혁" might not be in titles; check suffix match for titles
    return any(noun.endswith(t) for t in all_seniors if len(t) >= 2)


def check(
    text: str,
    extra_seniors: frozenset[str] | None = None,
) -> HonorificResult:
    """Check text for a senior subject without an honorific verb."""
    seniors = _DEFAULT_SENIORS if not extra_seniors else _DEFAULT_SENIORS | extra_seniors

    # High confidence: explicit subject marker
    for m in _SUBJ_RE.finditer(text):
        noun = m.group(1)
        if _is_senior(noun, seniors):
            return HonorificResult(
                subject=noun,
                subject_is_senior=True,
                verb_has_honorific=_has_honorific_verb(text),
                confidence="high",
            )

    # Medium confidence: topic marker
    for m in _TOPIC_RE.finditer(text):
        noun = m.group(1)
        if _is_senior(noun, seniors):
            return HonorificResult(
                subject=noun,
                subject_is_senior=True,
                verb_has_honorific=_has_honorific_verb(text),
                confidence="medium",
            )

    # Low confidence: senior noun appears anywhere
    for senior in sorted(seniors, key=len, reverse=True):
        if senior in text:
            return HonorificResult(
                subject=senior,
                subject_is_senior=True,
                verb_has_honorific=_has_honorific_verb(text),
                confidence="low",
            )

    return HonorificResult(
        subject="", subject_is_senior=False, verb_has_honorific=True, confidence="low"
    )
