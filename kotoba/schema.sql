PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS player (
    id                INTEGER PRIMARY KEY DEFAULT 1,
    name              TEXT    NOT NULL,
    age               INTEGER,
    gender            TEXT,
    address_prefs     TEXT    DEFAULT '{}',   -- JSON {ko, ja}
    level_ko          TEXT    DEFAULT 'beginner',
    level_ja          TEXT    DEFAULT 'beginner',
    support_level_ko  INTEGER DEFAULT 2,
    support_level_ja  INTEGER DEFAULT 2,
    created_at        TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS character_state (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id        TEXT    NOT NULL UNIQUE,
    closeness           INTEGER DEFAULT 20,
    respect             INTEGER DEFAULT 50,
    offense             TEXT    DEFAULT 'none',   -- none | mild | serious
    register_to_player  TEXT    NOT NULL,          -- what they use with you
    register_expected   TEXT    NOT NULL,          -- what they expect from you
    updated_at          TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS memories (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id   TEXT    NOT NULL,
    fact           TEXT    NOT NULL,
    source_turn_id INTEGER,
    created_at     TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (source_turn_id) REFERENCES turns(id)
);

CREATE TABLE IF NOT EXISTS episode_progress (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id   TEXT    NOT NULL UNIQUE,
    current_beat TEXT,
    variant      TEXT,
    status       TEXT    DEFAULT 'active',   -- active | complete | abandoned
    updated_at   TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id TEXT    NOT NULL,
    episode_id   TEXT,
    started_at   TEXT    DEFAULT (datetime('now')),
    ended_at     TEXT,
    summary      TEXT
);

CREATE TABLE IF NOT EXISTS turns (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    INTEGER NOT NULL,
    user_text_raw TEXT,
    user_register TEXT,
    reply_text    TEXT,
    judge_json    TEXT,   -- raw JSON blob from judge
    created_at    TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS state_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id    INTEGER,
    variable   TEXT    NOT NULL,   -- closeness | respect | offense | register_*
    delta      REAL    NOT NULL,   -- numeric change; 0 for string-field transitions
    reason     TEXT    NOT NULL,
    created_at TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (turn_id) REFERENCES turns(id)
);
