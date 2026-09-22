"""Synchronous SQLite helpers for RelationInsight."""

from __future__ import annotations

import sqlite3
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = BACKEND_DIR / "data"
DB_PATH = DATA_DIR / "relationinsight.db"
SCHEMA_PATH = BACKEND_DIR / "schema.sql"

REQUIRED_TABLES = (
    "persons",
    "messages",
    "analyses",
    "evidence",
    "profile_versions",
    "consents",
)


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | None = None) -> Path:
    path = db_path or DB_PATH
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_connection(path)
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()
    return path


def list_user_tables(db_path: Path | None = None) -> list[str]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return [row["name"] for row in rows]
    finally:
        conn.close()
