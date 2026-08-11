"""
SQLite persistence layer for Ideation Bot (@ideated_bot).

Caches LLM-generated app ideas per Straits Times article URL so that:
1. The same article is never re-billed against the free Claude quota twice.
2. If a live Gemini call fails for an article that was already generated
   before, the bot can still serve the previously LLM-generated idea
   instead of fabricating templated text.

There is deliberately no "synthetic" row type here -- every row in this
table was produced by Gemini at some point.
"""

import os
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ideas.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ideas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    article_url     TEXT NOT NULL UNIQUE,
    theme_key       TEXT NOT NULL,
    headline        TEXT NOT NULL,
    app_name        TEXT NOT NULL,
    overview        TEXT NOT NULL,
    smooth_path     TEXT NOT NULL,
    hard_path       TEXT NOT NULL,
    potential_users TEXT NOT NULL,
    model_used      TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ideas_theme_key ON ideas(theme_key);
"""


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Creates the ideas table if it doesn't already exist. Safe to call on every startup."""
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def get_cached_idea(article_url: str) -> dict | None:
    """Returns a previously Gemini-generated idea for this exact article URL, or None."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT app_name, overview, smooth_path, hard_path, potential_users, model_used "
            "FROM ideas WHERE article_url = ?",
            (article_url,),
        ).fetchone()

    if not row:
        return None

    app_name, overview, smooth_path, hard_path, potential_users_json, model_used = row
    return {
        "app_name": app_name,
        "overview": overview,
        "smooth_path": smooth_path,
        "hard_path": hard_path,
        "potential_users": json.loads(potential_users_json),
        "model_used": model_used,
    }


def save_idea(article_url: str, theme_key: str, headline: str, idea: dict, model_used: str) -> None:
    """Upserts a Claude-generated idea, keyed by article URL."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO ideas (article_url, theme_key, headline, app_name, overview,
                                smooth_path, hard_path, potential_users, model_used, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(article_url) DO UPDATE SET
                theme_key       = excluded.theme_key,
                headline        = excluded.headline,
                app_name        = excluded.app_name,
                overview        = excluded.overview,
                smooth_path     = excluded.smooth_path,
                hard_path       = excluded.hard_path,
                potential_users = excluded.potential_users,
                model_used      = excluded.model_used,
                created_at      = excluded.created_at
            """,
            (
                article_url,
                theme_key,
                headline,
                idea["app_name"],
                idea["overview"],
                idea["smooth_path"],
                idea["hard_path"],
                json.dumps(idea["potential_users"]),
                model_used,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
