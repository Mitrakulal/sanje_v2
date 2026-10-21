"""Telegram entry point.

The bot is intentionally thin: one message in, one agent run, one reply.
Conversation history is kept in memory per user. A restart clears it.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from agent import answer, build_agent
from config import SETTINGS

WELCOME = (
    "Sanje here. I can chat, or plan one day out.\n\n"
    "For a plan, tell me: where you are starting, the day, morning/afternoon/"
    "evening/full day, how many people, and your total budget.\n\n"
    "Example: Tomorrow, 4 of us, Rs 2000, evening, from Mangalore."
)

FAILED = "Something went wrong on my side. Try that once more in a moment."
MAX_HISTORY = 12


async def _post_init(application: Application) -> None:
    application.bot_data["agent"] = await build_agent()
    print("[bot] agent ready")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    await update.effective_message.reply_text(WELCOME)


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    await update.effective_message.reply_text("Fresh start. What are we doing?")


def _chunks(text: str, size: int = 4000) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)] or [""]


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

    try:
        await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
        reply = await answer(agent, history[-MAX_HISTORY:])
    except Exception as exc:  # noqa: BLE001
        print(f"[bot] agent failed: {type(exc).__name__}: {exc}")
        await message.reply_text(FAILED)
        return

    history.append(AIMessage(content=reply))
    context.user_data["history"] = history[-MAX_HISTORY:]

    for part in _chunks(reply):
        await message.reply_text(part)


def build_application() -> Application:
    if not SETTINGS.bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is missing in .env")

    application = (
        Application.builder()
        .token(SETTINGS.bot_token)
        .post_init(_post_init)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("new", reset))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return application


def run() -> None:
    application = build_application()
    print("[bot] polling Telegram - Ctrl+C to stop")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )
