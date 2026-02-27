"""SQLite database setup for pipeline persistence."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "studio.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pipelines (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT    NOT NULL,
                description     TEXT    DEFAULT '',
                nodes_json      TEXT    NOT NULL DEFAULT '[]',
                edges_json      TEXT    NOT NULL DEFAULT '[]',
                node_configs_json TEXT  NOT NULL DEFAULT '{}',
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
