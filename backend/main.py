"""RelationInsight API — T-001 skeleton (sync FastAPI)."""

from __future__ import annotations

import sys

from fastapi import FastAPI

from db import DB_PATH, REQUIRED_TABLES, init_db, list_user_tables

app = FastAPI(title="RelationInsight", version="0.1.0")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    tables = list_user_tables()
    missing = [name for name in REQUIRED_TABLES if name not in tables]
    db_ok = DB_PATH.exists() and not missing
    return {
        "status": "ok" if db_ok else "degraded",
        "python": sys.version.split()[0],
        "database_path": str(DB_PATH),
        "database_exists": DB_PATH.exists(),
        "tables": tables,
        "missing_tables": missing,
    }
