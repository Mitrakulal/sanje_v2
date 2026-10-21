"""One place for sending model markdown to Telegram."""

from __future__ import annotations

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import BadRequest

from bot.formatting import html_to_plain, split_html, to_telegram_html


async def send_text(
    bot: Bot,
    chat_id: int,
    text: str,
    *,
    reply_to: int | None = None,
) -> None:
    """Send rendered HTML, with a plain-text fallback for Telegram errors."""
    rendered = to_telegram_html(text)
    for part in split_html(rendered):
        kwargs = {
            "chat_id": chat_id,
            "parse_mode": ParseMode.HTML,
            "disable_web_page_preview": True,
        }
        if reply_to is not None:
            kwargs["reply_to_message_id"] = reply_to

        try:
            await bot.send_message(text=part, **kwargs)
        except BadRequest as exc:
            print(f"[delivery] html rejected: {exc}", flush=True)
            fallback = {
                "chat_id": chat_id,
                "text": html_to_plain(part),
                "disable_web_page_preview": True,
            }
            if reply_to is not None:
                fallback["reply_to_message_id"] = reply_to
            await bot.send_message(**fallback)
