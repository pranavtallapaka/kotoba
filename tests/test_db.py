import pytest
from kotoba.db import (
    init_db, load_player, get_state, update_state,
    log_turn, log_event, add_memory, get_memories, _connect,
)


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("KOTOBA_DB", str(tmp_path / "test.db"))


def test_init_creates_player():
    init_db()
    p = load_player()
    assert p["name"] == "한"
    assert p["age"] == 21
    assert p["level_ko"] == "beginner"
    assert p["support_level_ko"] == 2
    assert p["support_level_ja"] == 2


def test_default_state_on_first_get():
    init_db()
    s = get_state("seoyeon")
    assert s["closeness"] == 20
    assert s["respect"] == 50
    assert s["offense"] == "none"
    assert s["register_to_player"] == "haeyo"
    assert s["register_expected"] == "haeyo"


def test_get_state_is_idempotent():
    init_db()
    s1 = get_state("seoyeon")
    s2 = get_state("seoyeon")
    assert s1["id"] == s2["id"]


def test_update_state():
    init_db()
    get_state("seoyeon")
    update_state("seoyeon", closeness=30, respect=45)
    s = get_state("seoyeon")
    assert s["closeness"] == 30
    assert s["respect"] == 45


def test_log_turn_and_event():
    init_db()
    conn = _connect()
    conn.execute("INSERT INTO sessions (character_id) VALUES ('seoyeon')")
    conn.commit()
    conn.close()

    turn_id = log_turn(1, "안녕하세요", "haeyo", "안녕하세요!", {"beat_passed": True})
    log_event(turn_id, "respect", -2, "used 반말 before offer")

    conn = _connect()
    events = conn.execute(
        "SELECT * FROM state_events WHERE turn_id = ?", (turn_id,)
    ).fetchall()
    conn.close()

    assert len(events) == 1
    assert events[0]["variable"] == "respect"
    assert events[0]["delta"] == pytest.approx(-2.0)
    assert "반말" in events[0]["reason"]
