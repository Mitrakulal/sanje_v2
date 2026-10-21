import asyncio
import json
from datetime import datetime

import store
from bot import jobs
from config import SETTINGS


def plan(**overrides):
    base = {
        "chat_id": 7,
        "plan_id": "p1",
        "day": "2026-10-22",
        "slot": "evening",
        "plan_json": json.dumps({"text": "Beach walk and dinner"}),
        "location": "Mangalore",
        "rain_baseline": 30,
        "rain_alerted": 0,
        "rain_24h_sent": 0,
        "rain_3h_sent": 0,
        "reminder_sent": 0,
    }
    base.update(overrides)
    return base


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, **kwargs):
        self.sent.append(kwargs)


def test_plan_start_uses_slot_convention():
    assert jobs.plan_start("2026-10-22", "evening").hour == 17
    assert jobs.plan_start("2026-10-22", "morning").hour == 8
    assert jobs.plan_start("not-a-day", "evening") is None


def test_reminder_is_due_at_nine_the_night_before():
    at = datetime(2026, 10, 21, 21, 0, tzinfo=SETTINGS.tz)
    assert jobs.reminder_due(plan(), at) is True
    assert jobs.reminder_due(plan(), at.replace(hour=20)) is False
    assert jobs.reminder_due(plan(reminder_sent=1), at) is False


def test_rain_windows_open_at_24h_and_3h():
    start = datetime(2026, 10, 22, 17, 0, tzinfo=SETTINGS.tz)
    assert jobs.rain_checks_due(plan(), start.replace(day=21)) == ["24h"]
    assert jobs.rain_checks_due(
        plan(rain_24h_sent=1), start.replace(hour=15)
    ) == ["3h"]
    assert jobs.rain_checks_due(plan(), start.replace(hour=18)) == []


def test_rain_alert_thresholds():
    assert jobs.rain_should_alert(90, 30) is True
    assert jobs.rain_should_alert(60, 40) is False
    assert jobs.rain_should_alert(70, None) is True
    assert jobs.rain_should_alert(65, None) is False
    assert jobs.rain_should_alert(None, 10) is False


def test_due_jobs_send_reminder(monkeypatch):
    bot = FakeBot()
    reminders = []
    monkeypatch.setattr(store, "all_plans", lambda: [plan(rain_alerted=1)])
    monkeypatch.setattr(
        store,
        "mark_reminder",
        lambda plan_id: reminders.append(plan_id),
    )
    monkeypatch.setattr(store, "mark_rain_check", lambda *args, **kwargs: None)

    at = datetime(2026, 10, 21, 21, 0, tzinfo=SETTINGS.tz)
    asyncio.run(jobs.run_due_jobs(bot, at=at))

    assert reminders == ["p1"]
    assert len(bot.sent) == 1
    assert "Tomorrow's plan" in bot.sent[0]["text"]
    assert "Beach walk and dinner" in bot.sent[0]["text"]


def test_due_jobs_send_one_rain_alert(monkeypatch):
    bot = FakeBot()
    checks = []
    monkeypatch.setattr(
        store,
        "all_plans",
        lambda: [plan(rain_24h_sent=0, rain_3h_sent=0)],
    )
    monkeypatch.setattr(
        store,
        "mark_rain_check",
        lambda plan_id, window, **kwargs: checks.append((window, kwargs)),
    )
    monkeypatch.setattr(
        jobs,
        "get_weather",
        lambda location, day: {"rain_probability_max": 90},
    )

    at = datetime(2026, 10, 22, 15, 0, tzinfo=SETTINGS.tz)
    asyncio.run(jobs.run_due_jobs(bot, at=at))

    assert len(bot.sent) == 1
    assert "Rain chance is now 90%" in bot.sent[0]["text"]
    assert [window for window, _ in checks] == ["24h", "3h"]
    assert checks[0][1]["alerted"] is True
    assert checks[1][1]["alerted"] is False
