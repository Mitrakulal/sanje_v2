from datetime import date

from langchain_core.messages import HumanMessage

from bot.plan_meta import extract_day, extract_slot, plan_meta, pretty_when

BASE = date(2026, 10, 21)


def test_relative_and_explicit_days():
    assert extract_day("Tomorrow, 4 of us", BASE) == date(2026, 10, 22)
    assert extract_day("day after tomorrow", BASE) == date(2026, 10, 23)
    assert extract_day("today evening", BASE) == date(2026, 10, 21)
    assert extract_day("22 October", BASE) == date(2026, 10, 22)
    assert extract_day("Oct 22", BASE) == date(2026, 10, 22)
    assert extract_day("2026-11-05", BASE) == date(2026, 11, 5)
    assert extract_day("Thursday", BASE) == date(2026, 10, 22)


def test_slot_variants():
    assert extract_slot("full-day trip") == "full day"
    assert extract_slot("Tomorrow evening") == "evening"
    assert extract_slot("morning or afternoon") == "morning"
    assert extract_slot("no fixed time") == ""


def test_plan_meta_uses_weather_and_budget_facts():
    history = [
        HumanMessage(content="Tomorrow evening, 4 of us, Rs 2000, from Mangalore")
    ]
    meta = plan_meta(
        history,
        "Plan text",
        {"day": "2026-10-22", "location": "Mangalore", "rain_probability_max": 30},
        {"people": 4, "budget": 2000},
    )

    assert meta == {
        "day": "2026-10-22",
        "slot": "evening",
        "location": "Mangalore",
        "people": 4,
        "budget": 2000,
        "rain_baseline": 30,
    }
    assert pretty_when(meta["day"], meta["slot"]) == "Thu 22 Oct (evening)"
