import asyncio
from types import SimpleNamespace

import store
from bot.app import on_plan_button


class FakeQuery:
    def __init__(self, data):
        self.data = data
        self.edited = []
        self.message = SimpleNamespace(reply_text=self._reply)

    async def answer(self):
        return None

    async def edit_message_text(self, text):
        self.edited.append(text)

    async def edit_message_reply_markup(self, reply_markup=None):
        return None

    async def _reply(self, text):
        self.edited.append(text)


def pending(plan_id="new"):
    return {
        "id": plan_id,
        "text": "Beach plan",
        "created_at": "2026-10-21T12:00:00",
        "day": "2026-10-22",
        "slot": "evening",
        "location": "Mangalore",
        "people": 2,
        "budget": 1500,
        "rain_baseline": 30,
    }


def make_context(plan):
    return SimpleNamespace(user_data={"pending_plan": plan})


def make_update(data):
    return SimpleNamespace(
        callback_query=FakeQuery(data),
        effective_chat=SimpleNamespace(id=123),
    )


def test_current_approval_button_saves_one_plan(monkeypatch):
    saved = []
    monkeypatch.setattr(store, "get_plan", lambda chat_id: None)
    monkeypatch.setattr(
        store,
        "save_plan",
        lambda **kwargs: saved.append(kwargs),
    )
    context = make_context(pending("new"))
    update = make_update("plan:approve:new")

    asyncio.run(on_plan_button(update, context))

    assert saved[0]["chat_id"] == 123
    assert saved[0]["plan_id"] == "new"
    assert saved[0]["day"] == "2026-10-22"
    assert "pending_plan" not in context.user_data
    assert "Saved." in update.callback_query.edited[0]


def test_old_approval_button_cannot_save_newer_plan(monkeypatch):
    saved = []
    monkeypatch.setattr(store, "get_plan", lambda chat_id: None)
    monkeypatch.setattr(
        store,
        "save_plan",
        lambda **kwargs: saved.append(kwargs),
    )
    context = make_context(pending("new"))
    update = make_update("plan:approve:old")

    asyncio.run(on_plan_button(update, context))

    assert saved == []
    assert context.user_data["pending_plan"]["id"] == "new"
    assert "replaced by a newer one" in update.callback_query.edited[0]
