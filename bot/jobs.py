"""The tiny proactive loop: one reminder and two rain checks per saved plan.

No scheduler library. This runs as one asyncio task inside the bot process and
checks the SQLite table every minute. If the bot was offline, the next loop
still picks up a check that is due.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta

import store
from bot.delivery import send_text
from bot.plan_meta import pretty_when
from config import SETTINGS, now
from weather_mcp.server import get_weather

SLOT_HOURS = {
    "morning": 8,
    "afternoon": 13,
    "evening": 17,
    "full day": 8,
    "full-day": 8,
}
RAIN_ALERT_AT = 60
RAIN_JUMP = 25
RAIN_HIGH = 70
CHECK_EVERY_SECONDS = 60


def plan_start(day: str, slot: str) -> datetime | None:
    """Use a simple convention: morning 08:00, afternoon 13:00, evening 17:00."""
    try:
        target = date.fromisoformat(day)
    except (TypeError, ValueError):
        return None

    hour = SLOT_HOURS.get((slot or "").strip().lower(), 8)
    return datetime.combine(target, time(hour)).replace(tzinfo=SETTINGS.tz)


def reminder_due(plan: dict, at: datetime | None = None) -> bool:
    at = at or now()
    if plan.get("reminder_sent"):
        return False

    start = plan_start(plan.get("day") or "", plan.get("slot") or "")
    if start is None:
        return False

    night_before = start.date() - timedelta(days=1)
    return at.date() == night_before and at.hour >= 21


def rain_checks_due(plan: dict, at: datetime | None = None) -> list[str]:
    at = at or now()
    start = plan_start(plan.get("day") or "", plan.get("slot") or "")
    if start is None or at >= start:
        return []

    windows: list[str] = []
    if not plan.get("rain_24h_sent") and at >= start - timedelta(hours=24):
        windows.append("24h")
    if not plan.get("rain_3h_sent") and at >= start - timedelta(hours=3):
        windows.append("3h")
    return windows


def rain_should_alert(current: int | None, baseline: int | None) -> bool:
    if current is None:
        return False
    if baseline is None:
        return current >= RAIN_HIGH
    return current >= RAIN_ALERT_AT and current - baseline >= RAIN_JUMP


def rain_message(plan: dict, current: int, baseline: int | None) -> str:
    when = pretty_when(plan.get("day") or "", plan.get("slot") or "")
    earlier = f" (earlier {baseline}%)" if baseline is not None else ""
    return (
        f"Rain update for your saved plan on {when}.\n"
        f"Rain chance is now {current}%{earlier}.\n"
        "Keep an indoor backup - a mall, cafe or movie - instead of the "
        "outdoor stops."
    )


async def run_due_jobs(bot, at: datetime | None = None) -> None:
    """Send anything that is due. Safe to call repeatedly."""
    at = at or now()

    for plan in store.all_plans():
        try:
            if reminder_due(plan, at):
                when = pretty_when(plan.get("day") or "", plan.get("slot") or "")
                text = store.plan_text(plan)
                await send_text(
                    bot,
                    int(plan["chat_id"]),
                    f"Tomorrow's plan ({when}):\n\n{text}\n\n"
                    "Want me to change anything? Just reply here.",
                )
                store.mark_reminder(plan["plan_id"])

            for window in rain_checks_due(plan, at):
                if plan.get("rain_alerted"):
                    store.mark_rain_check(plan["plan_id"], window, alerted=False)
                    continue

                location = plan.get("location") or ""
                day = plan.get("day") or ""
                if not location or not day:
                    store.mark_rain_check(plan["plan_id"], window)
                    continue

                weather = await asyncio.to_thread(get_weather, location, day)
                current = (
                    weather.get("rain_probability_max")
                    if isinstance(weather, dict)
                    else None
                )
                if current is None:
                    store.mark_rain_check(plan["plan_id"], window)
                    continue

                current = int(current)
                baseline = plan.get("rain_baseline")
                alerted = rain_should_alert(current, baseline)
                if alerted:
                    await send_text(
                        bot,
                        int(plan["chat_id"]),
                        rain_message(plan, current, baseline),
                    )
                    plan["rain_alerted"] = 1

                store.mark_rain_check(
                    plan["plan_id"],
                    window,
                    alerted=alerted,
                    current=current,
                    baseline=current,
                )
        except Exception as exc:  # noqa: BLE001
            print(
                f"[jobs] plan {plan.get('plan_id')} failed: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )


async def plan_watch(application) -> None:
    """Run one loop for the life of the bot."""
    while True:
        try:
            await run_due_jobs(application.bot)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            print(f"[jobs] loop failed: {type(exc).__name__}: {exc}", flush=True)
        await asyncio.sleep(CHECK_EVERY_SECONDS)
