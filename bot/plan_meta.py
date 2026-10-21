"""Small deterministic helpers for plan approval and reminders.

The agent owns the planning. This module only reads a few facts the bot needs
after the reply exists: day, slot, location, people and budget.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from config import now

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

_WEEKDAYS = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "tues": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}

_MONTH_PATTERN = "|".join(sorted(_MONTHS, key=len, reverse=True))
_WEEKDAY_PATTERN = "|".join(sorted(_WEEKDAYS, key=len, reverse=True))


def extract_slot(text: str) -> str:
    """Return one of the four slots, or an empty string."""
    lower = text.lower()
    if re.search(r"\bfull[\s-]?day\b", lower):
        return "full day"
    for slot in ("morning", "afternoon", "evening"):
        if re.search(rf"\b{slot}\b", lower):
            return slot
    return ""


def _month_date(day: int, month_name: str, base: date, year: int | None) -> date | None:
    month = _MONTHS.get(month_name)
    if month is None:
        return None

    try:
        candidate = date(year or base.year, month, day)
    except ValueError:
        return None

    if year is None and candidate < base - timedelta(days=1):
        try:
            candidate = date(base.year + 1, month, day)
        except ValueError:
            return None
    return candidate


def extract_day(text: str, base: date | None = None) -> date | None:
    """Read a day from natural text. Returns None when it is not clear."""
    base = base or now().date()
    lower = text.lower()

    if re.search(r"\bday after tomorrow\b", lower):
        return base + timedelta(days=2)
    if re.search(r"\btomorrow\b", lower):
        return base + timedelta(days=1)
    if re.search(r"\btoday\b|\btonight\b", lower):
        return base

    match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass

    match = re.search(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_PATTERN})"
        rf"(?:\s+(\d{{4}}))?\b",
        lower,
    )
    if match:
        result = _month_date(
            int(match.group(1)),
            match.group(2),
            base,
            int(match.group(3)) if match.group(3) else None,
        )
        if result:
            return result

    match = re.search(
        rf"\b({_MONTH_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?"
        rf"(?:\s+(\d{{4}}))?\b",
        lower,
    )
    if match:
        result = _month_date(
            int(match.group(2)),
            match.group(1),
            base,
            int(match.group(3)) if match.group(3) else None,
        )
        if result:
            return result

    match = re.search(rf"\b({_WEEKDAY_PATTERN})\b", lower)
    if match:
        target = _WEEKDAYS[match.group(1)]
        return base + timedelta(days=(target - base.weekday()) % 7)

    return None


def _human_texts(history) -> list[str]:
    texts: list[str] = []
    for message in reversed(history):
        if getattr(message, "type", "") != "human":
            continue
        text = str(message.content or "").strip()
        if text:
            texts.append(text)
    return texts


def plan_day(history, plan_text: str, weather: dict | None = None) -> date | None:
    weather_day = (weather or {}).get("day")
    if weather_day:
        try:
            return date.fromisoformat(str(weather_day))
        except ValueError:
            pass

    for text in [*_human_texts(history), plan_text]:
        day = extract_day(text)
        if day:
            return day
    return None


def plan_slot(history, plan_text: str) -> str:
    for text in [*_human_texts(history), plan_text]:
        slot = extract_slot(text)
        if slot:
            return slot
    return ""


def plan_meta(
    history,
    plan_text: str,
    weather: dict | None = None,
    budget: dict | None = None,
) -> dict:
    """A small, JSON-safe bundle attached to an approved plan."""
    day = plan_day(history, plan_text, weather)
    weather = weather or {}
    budget = budget or {}
    return {
        "day": day.isoformat() if day else "",
        "slot": plan_slot(history, plan_text),
        "location": str(weather.get("location") or ""),
        "people": budget.get("people"),
        "budget": budget.get("budget"),
        "rain_baseline": weather.get("rain_probability_max"),
    }


def pretty_day(day: str) -> str:
    try:
        return date.fromisoformat(day).strftime("%a %d %b")
    except (TypeError, ValueError):
        return day


def pretty_when(day: str, slot: str) -> str:
    when = pretty_day(day) if day else ""
    if slot:
        when = f"{when} ({slot})".strip()
    return when
