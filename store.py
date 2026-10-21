"""SQLite storage for the one approved plan per chat.

Only the bot writes here, only after the user taps Approve. The table uses
`chat_id` as the primary key, so approving a new plan replaces the old one.
"""

from __future__ import annotations

import json
import sqlite3

from config import ROOT, now

DB_PATH = ROOT / "data" / "sanje.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS plans (
    chat_id INTEGER PRIMARY KEY,
    plan_id TEXT NOT NULL,
    day TEXT NOT NULL DEFAULT '',
    slot TEXT NOT NULL DEFAULT '',
    plan_json TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '',
    reminder_sent INTEGER NOT NULL DEFAULT 0,
    rain_24h_sent INTEGER NOT NULL DEFAULT 0,
    rain_3h_sent INTEGER NOT NULL DEFAULT 0,
    rain_alerted INTEGER NOT NULL DEFAULT 0,
    rain_baseline INTEGER,
    last_rain INTEGER,
    created_at TEXT NOT NULL
)
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with _connect() as connection:
        connection.execute(SCHEMA)


def save_plan(
    *,
    chat_id: int,
    plan_id: str,
    day: str,
    slot: str,
    plan_json: str,
    location: str,
    rain_baseline: int | None,
) -> None:
    """Insert or replace the chat's only saved plan."""
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO plans (
                chat_id, plan_id, day, slot, plan_json, location,
                rain_baseline, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                plan_id = excluded.plan_id,
                day = excluded.day,
                slot = excluded.slot,
                plan_json = excluded.plan_json,
                location = excluded.location,
                reminder_sent = 0,
                rain_24h_sent = 0,
                rain_3h_sent = 0,
                rain_alerted = 0,
                rain_baseline = excluded.rain_baseline,
                last_rain = NULL,
                created_at = excluded.created_at
            """,
            (
                int(chat_id),
                plan_id,
                day,
                slot,
                plan_json,
                location,
                int(rain_baseline) if rain_baseline is not None else None,
                now().isoformat(),
            ),
        )


def get_plan(chat_id: int) -> dict | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM plans WHERE chat_id = ?", (int(chat_id),)
        ).fetchone()
    return dict(row) if row else None


def all_plans() -> list[dict]:
    with _connect() as connection:
        rows = connection.execute("SELECT * FROM plans").fetchall()
    return [dict(row) for row in rows]


def delete_plan(chat_id: int) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM plans WHERE chat_id = ?", (int(chat_id),))


def mark_reminder(plan_id: str) -> None:
    with _connect() as connection:
        connection.execute(
            "UPDATE plans SET reminder_sent = 1 WHERE plan_id = ?", (plan_id,)
        )


def mark_rain_check(
    plan_id: str,
    window: str,
    *,
    alerted: bool = False,
    current: int | None = None,
    baseline: int | None = None,
) -> None:
    column = "rain_24h_sent" if window == "24h" else "rain_3h_sent"
    with _connect() as connection:
        connection.execute(
            f"""
            UPDATE plans SET
                {column} = 1,
                rain_alerted = CASE WHEN ? THEN 1 ELSE rain_alerted END,
                last_rain = ?,
                rain_baseline = COALESCE(rain_baseline, ?)
            WHERE plan_id = ?
            """,
            (1 if alerted else 0, current, baseline, plan_id),
        )


def plan_text(plan: dict) -> str:
    """Return the human-readable plan from the stored JSON."""
    raw = plan.get("plan_json") or ""
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return raw
    if isinstance(payload, dict):
        return str(payload.get("text") or "")
    return raw
