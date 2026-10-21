"""Turn model markdown into readable Telegram HTML.

Telegram does not render markdown tables or `###` headings, so raw model output
looks broken. This module keeps the useful structure (headings, bold, bullets)
and turns tables into short labelled blocks.
"""

from __future__ import annotations

import html
import re

_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_BULLET = re.compile(r"^\s*[-*•]\s+(.*)$")
_NUMBERED = re.compile(r"^\s*\d+[.)]\s+")
_RULE = re.compile(r"^\s*([-*_])\1{2,}\s*$")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_INLINE_CODE = re.compile(r"`([^`]+)`")


def _inline(text: str) -> str:
    text = _BR.sub("\n", text)
    text = html.escape(text, quote=False)
    text = _LINK.sub(r'<a href="\2">\1</a>', text)
    text = _BOLD.sub(r"<b>\1</b>", text)
    text = _ITALIC.sub(r"<i>\1</i>", text)
    text = _INLINE_CODE.sub(r"<code>\1</code>", text)
    text = text.replace("**", "")
    return text.strip()


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.count("|") >= 2


def _is_separator(row: list[str]) -> bool:
    cells = [cell for cell in row if cell]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _table(rows: list[list[str]]) -> str:
    headers = rows[0]
    out: list[str] = []

    for row in rows[2:]:
        cells = row + [""] * max(0, len(headers) - len(row))
        title = _inline(cells[0]) if cells else ""
        if title:
            if title.startswith("<b>") and title.endswith("</b>"):
                out.append(title)
            else:
                out.append(f"<b>{title}</b>")

        for index in range(1, len(cells)):
            cell = cells[index].strip()
            if not cell:
                continue
            header = headers[index].strip() if index < len(headers) else ""
            first = True

            for fragment in re.split(r"<br\s*/?>|\n", cell, flags=re.IGNORECASE):
                for piece in re.split(r"\s*•\s*", fragment):
                    piece = re.sub(r"^[-*]\s+", "", piece.strip())
                    if not piece:
                        continue
                    label = f"<b>{_inline(header)}:</b> " if first and header else ""
                    out.append(f"• {label}{_inline(piece)}")
                    first = False

        out.append("")

    return "\n".join(out).strip()


def to_telegram_html(text: str) -> str:
    """Convert model markdown into a Telegram-safe HTML fragment."""
    lines = text.splitlines()
    out: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]

        if _is_table_line(line):
            rows: list[list[str]] = []
            end = index
            while end < len(lines) and _is_table_line(lines[end]):
                rows.append(_cells(lines[end]))
                end += 1
            if len(rows) >= 3 and _is_separator(rows[1]):
                out.append("")
                out.append(_table(rows))
                out.append("")
                index = end
                continue

        heading = _HEADING.match(line)
        if heading:
            out.extend(["", f"<b>{_inline(heading.group(1))}</b>", ""])
        elif _BULLET.match(line):
            out.append(f"• {_inline(_BULLET.match(line).group(1))}")
        elif _NUMBERED.match(line):
            out.append(_inline(line))
        elif _RULE.match(line):
            out.append("────────")
        elif not line.strip():
            out.append("")
        else:
            out.append(_inline(line))

        index += 1

    result = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", result).strip()


def split_html(text: str, limit: int = 3900) -> list[str]:
    """Split at line boundaries so an HTML tag is never cut in half."""
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    size = 0

    for line in text.splitlines(keepends=True):
        if size + len(line) > limit and current:
            chunks.append("".join(current).strip())
            current = []
            size = 0
        if len(line) > limit:
            # Rare, but do not send an over-limit message.
            chunks.extend(line[pos : pos + limit] for pos in range(0, len(line), limit))
            continue
        current.append(line)
        size += len(line)

    if current:
        chunks.append("".join(current).strip())

    return [chunk for chunk in chunks if chunk]


def html_to_plain(text: str) -> str:
    """Fallback if Telegram rejects the HTML entities."""
    return html.unescape(re.sub(r"<[^>]+>", "", text))
