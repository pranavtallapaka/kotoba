"""Persistence layer: SQLite state + YAML character/player files.

Only the judge writes relationship state (closeness, respect, offense,
register). The character model calls get_state() and get_memories() only.
"""
import json
import os
import sqlite3
from pathlib import Path

import yaml

HERE = Path(__file__).parent
ROOT = HERE.parent
SCHEMA = HERE / "schema.sql"
CHARS_DIR = ROOT / "characters"
PLAYER_YAML = ROOT / "player.yaml"


def _db_path() -> Path:
    return Path(os.environ.get("KOTOBA_DB", str(ROOT / "kotoba.db")))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

def init_db() -> None:
    conn = _connect()
    conn.executescript(SCHEMA.read_text())
    if conn.execute("SELECT COUNT(*) FROM player").fetchone()[0] == 0:
        p = yaml.safe_load(PLAYER_YAML.read_text())
        conn.execute(
            "INSERT INTO player "
            "(id, name, age, gender, address_prefs, "
            "level_ko, level_ja, support_level_ko, support_level_ja) "
            "VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                p["name"],
                p.get("age"),
                p.get("gender"),
                json.dumps(p.get("address_prefs", {})),
                p.get("level_ko", "beginner"),
                p.get("level_ja", "beginner"),
                p.get("support_level_ko", 2),
                p.get("support_level_ja", 2),
            ),
        )
        conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------

def load_player() -> dict:
    conn = _connect()
    row = conn.execute("SELECT * FROM player WHERE id = 1").fetchone()
    conn.close()
    if row is None:
        raise RuntimeError("DB not initialised — run: python -m kotoba.db init")
    d = dict(row)
    d["address_prefs"] = json.loads(d["address_prefs"] or "{}")
    return d


# ---------------------------------------------------------------------------
# Character state
# ---------------------------------------------------------------------------

def _load_char_yaml(char_id: str) -> dict:
    path = CHARS_DIR / f"{char_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Character file not found: {path}")
    return yaml.safe_load(path.read_text())


def get_state(char_id: str) -> dict:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM character_state WHERE character_id = ?", (char_id,)
    ).fetchone()
    if row is not None:
        conn.close()
        return dict(row)
    char = _load_char_yaml(char_id)
    conn.execute(
        "INSERT INTO character_state "
        "(character_id, closeness, respect, offense, "
        "register_to_player, register_expected) "
        "VALUES (?, 20, 50, 'none', ?, ?)",
        (
            char_id,
            char.get("register_to_player_default", "haeyo"),
            char.get("register_expected_default", "haeyo"),
        ),
    )
    conn.commit()
    state = dict(conn.execute(
        "SELECT * FROM character_state WHERE character_id = ?", (char_id,)
    ).fetchone())
    conn.close()
    return state


def update_state(char_id: str, **kwargs) -> None:
    allowed = {
        "closeness", "respect", "offense",
        "register_to_player", "register_expected",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    cols = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [char_id]
    conn = _connect()
    conn.execute(
        f"UPDATE character_state "
        f"SET {cols}, updated_at = datetime('now') "
        f"WHERE character_id = ?",
        vals,
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Sessions and turns
# ---------------------------------------------------------------------------

def start_session(char_id: str, episode_id: str | None = None) -> int:
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO sessions (character_id, episode_id) VALUES (?, ?)",
        (char_id, episode_id),
    )
    conn.commit()
    session_id = cur.lastrowid
    conn.close()
    return session_id


def end_session(session_id: int, summary: str | None = None) -> None:
    conn = _connect()
    conn.execute(
        "UPDATE sessions SET ended_at = datetime('now'), summary = ? WHERE id = ?",
        (summary, session_id),
    )
    conn.commit()
    conn.close()


def log_turn(
    session_id: int,
    user_text_raw: str,
    user_register: str,
    reply_text: str,
    judge_json: dict,
) -> int:
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO turns "
        "(session_id, user_text_raw, user_register, reply_text, judge_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (session_id, user_text_raw, user_register, reply_text,
         json.dumps(judge_json)),
    )
    conn.commit()
    turn_id = cur.lastrowid
    conn.close()
    return turn_id


def log_event(
    turn_id: int | None,
    variable: str,
    delta: float,
    reason: str,
) -> None:
    conn = _connect()
    conn.execute(
        "INSERT INTO state_events (turn_id, variable, delta, reason) "
        "VALUES (?, ?, ?, ?)",
        (turn_id, variable, delta, reason),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Memories
# ---------------------------------------------------------------------------

def add_memory(
    char_id: str,
    fact: str,
    source_turn_id: int | None = None,
) -> None:
    conn = _connect()
    conn.execute(
        "INSERT INTO memories (character_id, fact, source_turn_id) "
        "VALUES (?, ?, ?)",
        (char_id, fact, source_turn_id),
    )
    conn.commit()
    conn.close()


def get_memories(char_id: str) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM memories WHERE character_id = ? ORDER BY created_at",
        (char_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# CLI: python -m kotoba.db init | show <char_id>
# ---------------------------------------------------------------------------

def _cmd_init() -> None:
    init_db()
    p = load_player()
    print("Database initialised.")
    print(f"  player : {p['name']}, age {p['age']}, {p['gender']}")
    print(f"  Korean : {p['level_ko']}  (support {p['support_level_ko']})")
    print(f"  Japanese: {p['level_ja']}  (support {p['support_level_ja']})")


def _cmd_show(char_id: str) -> None:
    s = get_state(char_id)
    char = _load_char_yaml(char_id)
    print(f"Character : {char['name']} ({char_id})")
    print(f"  closeness        : {s['closeness']}")
    print(f"  respect          : {s['respect']}")
    print(f"  offense          : {s['offense']}")
    print(f"  register → you   : {s['register_to_player']}")
    print(f"  register expects : {s['register_expected']}")
    print(f"  updated_at       : {s['updated_at']}")
    mems = get_memories(char_id)
    if mems:
        print(f"  memories ({len(mems)}):")
        for m in mems:
            print(f"    • {m['fact']}")
    else:
        print("  memories         : none")


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    if not args:
        print("Usage: python -m kotoba.db init | show <char_id>")
        sys.exit(1)
    if args[0] == "init":
        _cmd_init()
    elif args[0] == "show" and len(args) == 2:
        _cmd_show(args[1])
    else:
        print("Usage: python -m kotoba.db init | show <char_id>")
        sys.exit(1)
