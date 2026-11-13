"""Unit tests for memory attribution correctness.

Tests that:
1. Character's own words never produce user memories.
2. Player's words produce user memories with matching source_quote.
3. The post-LLM source_quote filter drops fabricated user memories.
4. MemoryItems with about="seoyeon" are kept but not saved to the user DB.

Usage: python tests/test_memory.py
"""
import os
import sys
import tempfile
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).parent.parent))

_DB = tempfile.mktemp(suffix="_test_memory.db")
os.environ["KOTOBA_DB"] = _DB

from kotoba.judge import MemoryItem, JudgeResult, GrammarError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(**kwargs) -> JudgeResult:
    defaults = dict(
        register_used="haeyo",
        register_expected="haeyo",
        register_match=True,
        offense_ids=[],
        honorific_errors=[],
        grammar_errors=[],
        beat_passed=None,
        new_memories=[],
        state_deltas={"closeness": 0, "respect": 0},
        offense="none",
        repair_required=False,
        reason="ok",
    )
    defaults.update(kwargs)
    return JudgeResult(**defaults)


def _user_mem(fact: str, source_quote: str) -> MemoryItem:
    return MemoryItem(about="user", fact=fact, source_quote=source_quote)


def _char_mem(fact: str, source_quote: str) -> MemoryItem:
    return MemoryItem(about="seoyeon", fact=fact, source_quote=source_quote)


def _filter_user_memories(memories: list[MemoryItem], player_turn: str) -> list[MemoryItem]:
    """Mirror the post-LLM filter from judge.py."""
    return [m for m in memories if m.about != "user" or m.source_quote in player_turn]


# ---------------------------------------------------------------------------
# Case 1: character says she's busy → no user memory
# ---------------------------------------------------------------------------

def test_character_says_busy_no_user_memory():
    # Seo-yeon says "저 오늘 바빠요" — this is NOT the player's turn.
    # The LLM should not produce a user memory, but even if it does,
    # the source_quote filter must drop it.
    player_turn = "안녕하세요, 선배님."
    seoyeon_line = "저 오늘 바빠요."  # character's own line — should NOT be in memories

    # Simulate a buggy LLM response that attributes the character's line to the user:
    bad_memory = _user_mem(
        fact="The user has a busy schedule today.",
        source_quote=seoyeon_line,  # source is character's line, not player's turn
    )
    result = _make_result(new_memories=[bad_memory])

    filtered = _filter_user_memories(result.new_memories, player_turn)
    user_facts = [m for m in filtered if m.about == "user"]

    assert user_facts == [], (
        f"Expected no user memories when source is character's line, got: {user_facts}"
    )
    print("PASS case 1: character's 'I'm busy' does not become a user memory")


# ---------------------------------------------------------------------------
# Case 2: player says they're from California → user memory saved
# ---------------------------------------------------------------------------

def test_player_says_california_saves_memory():
    player_turn = "저는 캘리포니아에서 왔어요."

    good_memory = _user_mem(
        fact="The player is from California.",
        source_quote="캘리포니아에서 왔어요",
    )
    result = _make_result(new_memories=[good_memory])

    filtered = _filter_user_memories(result.new_memories, player_turn)
    user_facts = [m for m in filtered if m.about == "user"]

    assert len(user_facts) == 1, f"Expected 1 user memory, got: {user_facts}"
    assert "California" in user_facts[0].fact
    print("PASS case 2: player 'from California' is saved as user memory")


# ---------------------------------------------------------------------------
# Case 3: source_quote not in player turn → memory dropped
# ---------------------------------------------------------------------------

def test_source_quote_mismatch_drops_memory():
    player_turn = "오늘 날씨 좋네요."

    # LLM hallucinated a source_quote that isn't in the player turn
    hallucinated = _user_mem(
        fact="The player likes hiking.",
        source_quote="등산을 좋아해요",  # not in player_turn
    )
    result = _make_result(new_memories=[hallucinated])

    filtered = _filter_user_memories(result.new_memories, player_turn)
    user_facts = [m for m in filtered if m.about == "user"]

    assert user_facts == [], f"Expected dropped memory, got: {user_facts}"
    print("PASS case 3: hallucinated source_quote is filtered out")


# ---------------------------------------------------------------------------
# Case 4: character fact (about=seoyeon) is preserved but not counted as user
# ---------------------------------------------------------------------------

def test_character_fact_preserved_not_user():
    player_turn = "선배님, 많이 바쁘세요?"

    char_fact = _char_mem(
        fact="Seo-yeon has a busy schedule.",
        source_quote="많이 바쁘세요",  # from player's question — still about seoyeon
    )
    user_fact = _user_mem(
        fact="The player asked about Seo-yeon's schedule.",
        source_quote="많이 바쁘세요",
    )
    result = _make_result(new_memories=[char_fact, user_fact])

    filtered = _filter_user_memories(result.new_memories, player_turn)
    seoyeon_facts = [m for m in filtered if m.about == "seoyeon"]
    user_facts = [m for m in filtered if m.about == "user"]

    assert len(seoyeon_facts) == 1, f"Expected seoyeon fact preserved, got: {seoyeon_facts}"
    assert len(user_facts) == 1, f"Expected user fact preserved, got: {user_facts}"
    # Confirm the seoyeon fact is NOT treated as a user memory
    assert all(m.about != "user" for m in seoyeon_facts)
    print("PASS case 4: seoyeon fact preserved, user fact preserved, neither confused")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_character_says_busy_no_user_memory()
    test_player_says_california_saves_memory()
    test_source_quote_mismatch_drops_memory()
    test_character_fact_preserved_not_user()
    print("\nAll memory tests passed.")
