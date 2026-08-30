"""SQLite access shared by the migrated service."""

import os
import sqlite3


_PACKAGE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get(
    "NAV_API_DB_PATH",
    os.path.join(_PACKAGE_ROOT, "db", "nav_api.db"),
)
SCHEMA_PATH = os.path.join(_PACKAGE_ROOT, "db", "schema.sql")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
        schema_sql = schema_file.read()
    with get_conn() as conn:
        conn.executescript(schema_sql)
