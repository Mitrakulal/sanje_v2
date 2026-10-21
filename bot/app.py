"""Telegram entry point.

The bot is intentionally thin: one message in, one agent run, one reply, plus
one approval button and a tiny proactive watcher.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import store
from agent import answer, build_agent
from bot.delivery import send_text
from bot.jobs import plan_watch
from bot.plan_meta import plan_meta, pretty_when
from config import SETTINGS, now

WELCOME = (
    "Sanje here. I can chat, or plan one day out.\n\n"
    "For a plan, tell me: where you are starting, the day, morning/afternoon/"
    "evening/full day, how many people, and your total budget.\n\n"
    "Example: Tomorrow, 4 of us, Rs 2000, evening, from Mangalore.\n\n"
    "/mytrip resends your saved plan. /new starts a fresh chat."
)

FAILED = "Something went wrong on my side. Try that once more in a moment."
TIMEOUT = "This is taking too long. Please try that once more."
MAX_HISTORY = 12
AGENT_TIMEOUT = 150

STEP_TEXT = {
    "get_weather": "Checking weather…",
    "web_search": "Searching places…",
    "find_famous_food": "Finding local food…",
    "calculate_budget": "Adding up the budget…",
}


async def _post_init(application: Application) -> None:
    store.init_db()
    application.bot_data["agent"] = await build_agent()
    application.bot_data["scheduler"] = asyncio.create_task(
        plan_watch(application), name="plan-watch"
    )
    print("[bot] agent ready; plan watch running", flush=True)


async def _post_shutdown(application: Application) -> None:
    task = application.bot_data.get("scheduler")
    if task is None:
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def _typing_loop(bot, chat_id: int) -> None:
    while True:
        try:
            await bot.send_chat_action(chat_id, ChatAction.TYPING)
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(4)


async def _clear_status(status_message) -> None:
    try:
        await status_message.delete()
    except Exception:  # noqa: BLE001
        with contextlib.suppress(Exception):
            await status_message.edit_text("Done")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("history", None)
    context.user_data.pop("pending_plan", None)
    await update.effective_message.reply_text(WELCOME)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(WELCOME)


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    await update.effective_message.reply_text("Fresh start. What are we doing?")


async def mytrip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    plan = store.get_plan(update.effective_chat.id)
    if plan is None:
        await message.reply_text(
            "No saved plan yet. Plan something, then tap Approve & save."
        )
        return

    when = pretty_when(plan.get("day") or "", plan.get("slot") or "")
    header = f"Your saved plan for {when}:" if when else "Your saved plan:"
    await send_text(
        context.bot,
        update.effective_chat.id,
        f"{header}\n\n{store.plan_text(plan)}",
        reply_to=message.message_id,
    )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    text = (message.text or "").strip()
    if not text:
        return

    agent = context.bot_data.get("agent")
    if agent is None:
        await message.reply_text(FAILED)
        return

    history = list(context.user_data.get("history") or [])
    history.append(HumanMessage(content=text))

    status = await message.reply_text("Thinking…")
    current = {"text": "Thinking…"}

    async def set_status(value: str) -> None:
        if value == current["text"]:
            return
        current["text"] = value
        try:
            await status.edit_text(value)
        except BadRequest:
            pass
        except Exception as exc:  # noqa: BLE001
            print(f"[bot] status edit failed: {type(exc).__name__}: {exc}")

    async def on_step(name: str) -> None:
        await set_status(STEP_TEXT.get(name, "Working on it…"))

    typing = asyncio.create_task(
        _typing_loop(context.bot, update.effective_chat.id),
        name="typing",
    )
    try:
        reply = await asyncio.wait_for(
            answer(agent, history[-MAX_HISTORY:], on_step=on_step),
            timeout=AGENT_TIMEOUT,
        )
    except asyncio.TimeoutError:
        await set_status(TIMEOUT)
        return
    except Exception as exc:  # noqa: BLE001
        print(f"[bot] agent failed: {type(exc).__name__}: {exc}", flush=True)
        await set_status(FAILED)
        return
    finally:
        typing.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await typing

    history.append(AIMessage(content=reply.text))
    context.user_data["history"] = history[-MAX_HISTORY:]

    try:
        await send_text(
            context.bot,
            update.effective_chat.id,
            reply.text,
            reply_to=message.message_id,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[bot] delivery failed: {type(exc).__name__}: {exc}", flush=True)
        await set_status(FAILED)
        return

    await _clear_status(status)

    if not reply.is_plan:
        return

    pending = {
        "id": uuid4().hex,
        "text": reply.text,
        "created_at": now().isoformat(),
        **plan_meta(history, reply.text, reply.weather, reply.budget),
    }
    context.user_data["pending_plan"] = pending

    saved = store.get_plan(update.effective_chat.id)
    prompt = "Save this plan? I keep only one saved trip per chat."
    if saved is not None:
        prompt = "Save this plan? It will replace your current saved trip."
    if not pending["day"]:
        prompt += "\n\nI couldn't read the date, so reminders will be off."
    elif not pending["location"]:
        prompt += "\n\nI couldn't read the location, so rain checks will be off."

    await message.reply_text(
        prompt,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Approve & save",
                        callback_data=f"plan:approve:{pending['id']}",
                    ),
                    InlineKeyboardButton(
                        "Discard",
                        callback_data=f"plan:discard:{pending['id']}",
                    ),
                ]
            ]
        ),
    )


async def on_plan_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    with contextlib.suppress(Exception):
        await query.answer()

    chat_id = update.effective_chat.id
    pending = context.user_data.get("pending_plan")

    parts = (query.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""
    token = parts[2] if len(parts) > 2 else ""

    if pending is not None and token != pending["id"]:
        await _edit_callback(
            query,
            "That plan was replaced by a newer one. Use the newest buttons.",
        )
        return

    if action == "discard":
        context.user_data.pop("pending_plan", None)
        await _edit_callback(query, "Okay, not saved.")
        return

    if action != "approve":
        await _edit_callback(query, "That button is not valid any more.")
        return

    if pending is None:
        await _edit_callback(query, "That plan expired. Ask me to plan it again.")
        return

    context.user_data.pop("pending_plan", None)

    existing = store.get_plan(chat_id)
    plan_json = json.dumps(
        {
            "text": pending["text"],
            "location": pending["location"],
            "people": pending["people"],
            "budget": pending["budget"],
        },
        ensure_ascii=False,
    )

    try:
        store.save_plan(
            chat_id=chat_id,
            plan_id=pending["id"],
            day=pending["day"],
            slot=pending["slot"],
            plan_json=plan_json,
            location=pending["location"],
            rain_baseline=pending["rain_baseline"],
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[bot] save failed: {type(exc).__name__}: {exc}", flush=True)
        await _edit_callback(query, "I couldn't save that plan. Please try again.")
        return

    parts = ["Replaced your previous saved plan." if existing else "Saved."]
    if pending["day"]:
        when = pretty_when(pending["day"], pending["slot"])
        parts.append(
            "I'll remind you at 21:00 the night before and check rain 24h and "
            f"3h before for {when}."
        )
        if not pending["location"]:
            parts.append("Rain checks are off because I couldn't read the location.")
    else:
        parts.append(
            "I couldn't read the date, so automatic reminders are off. "
            "/mytrip will still resend it."
        )
    parts.append("/mytrip resends it any time.")

    await _edit_callback(query, "\n\n".join(parts))


async def _edit_callback(query, text: str) -> None:
    try:
        await query.edit_message_text(text)
    except BadRequest:
        with contextlib.suppress(Exception):
            await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(text)


def build_application() -> Application:
    if not SETTINGS.bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is missing in .env")

    application = (
        Application.builder()
        .token(SETTINGS.bot_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("new", reset))
    application.add_handler(CommandHandler("mytrip", mytrip))
    application.add_handler(
        CallbackQueryHandler(on_plan_button, pattern=r"^plan:")
    )
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return application


def run() -> None:
    # httpx logs the full Telegram URL, including the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    application = build_application()
    print("[bot] polling Telegram - Ctrl+C to stop", flush=True)
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )
