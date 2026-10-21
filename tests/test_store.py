import json

import store


def setup_db(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "sanje.db")
    store.init_db()


def save(chat_id=123, plan_id="one", text="Plan one"):
    store.save_plan(
        chat_id=chat_id,
        plan_id=plan_id,
        day="2026-10-22",
        slot="evening",
        plan_json=json.dumps({"text": text}),
        location="Mangalore",
        rain_baseline=30,
    )


def test_approving_a_new_plan_replaces_the_old_one(monkeypatch, tmp_path):
    setup_db(monkeypatch, tmp_path)
    save()
    store.mark_reminder("one")
    store.mark_rain_check("one", "24h", alerted=True, current=90, baseline=30)

    save(plan_id="two", text="Plan two")

    plans = store.all_plans()
    assert len(plans) == 1
    assert plans[0]["plan_id"] == "two"
    assert plans[0]["reminder_sent"] == 0
    assert plans[0]["rain_24h_sent"] == 0
    assert plans[0]["rain_alerted"] == 0
    assert store.plan_text(plans[0]) == "Plan two"


def test_missing_plan_is_none(monkeypatch, tmp_path):
    setup_db(monkeypatch, tmp_path)
    assert store.get_plan(999) is None


def test_delete_saved_plan(monkeypatch, tmp_path):
    setup_db(monkeypatch, tmp_path)
    save()
    store.delete_plan(123)
    assert store.get_plan(123) is None
