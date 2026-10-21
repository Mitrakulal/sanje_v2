"""The single LangChain agent.

No graph, no router, no critic. One model, four tools, one system prompt.
"""

from __future__ import annotations

import json
import re

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import BaseMessage, HumanMessage

from config import SETTINGS, now
from skills.loader import for_target
from tools.loader import load_tools


def _system_prompt() -> str:
    stamp = now()
    skills = for_target("main")
    return f"""You are Sanje, a friendly day-out planner and general chat assistant.
Today is {stamp:%A}, {stamp:%d %B %Y}, {stamp:%H:%M} in {SETTINGS.tz_name}.

You can chat normally about almost anything, or plan one day out.

PLANNING
A plan request needs exactly these details:
1. location (a city or starting area)
2. day (today, tomorrow, or a date)
3. slot: morning, afternoon, evening, or full day
4. people (how many)
5. budget (total INR for the group)

Food, vibe and transport preferences are optional.

If a required detail is missing, ask for only the missing details in one short,
natural question. Do not ask again for details the user already gave. Do not
start planning until all five are present. Resolve relative dates against today.

When all five are present, follow the planner, food and budget skills below.
Hard tool order: get_weather, then web_search, then find_famous_food, then
calculate_budget last. If the budget tool was skipped, the turn is incomplete.

RULES
- Never invent a place, price, opening time or event. If web search fails, say
  live place search is unavailable and keep the plan generic; do not name
  specific businesses from memory.
- If a tool fails, say what you could not check and continue with what you have.
- Keep the final plan under about 250 words. Use short bold headings and bullets.
- Format for Telegram: no markdown tables, no `###` headings, no `<br>` tags.
  A crisp bullet list reads better on a phone.
- When you recommend a place, mention the source name or link from web search.
- Do not claim to book, reserve, order or pay for anything.
- If the user just wants to chat, chat. Do not force a plan.
- Reply in the user's language. If they write in Tulu or Kannada, use the same
  language where you can.

SKILLS
{skills}
"""


def _model():
    if not SETTINGS.api_key:
        raise RuntimeError("OPENAI_API_KEY is missing in .env")
    return init_chat_model(
        model=SETTINGS.model_name,
        model_provider="openai",
        base_url=SETTINGS.cloud_endpoint,
        api_key=SETTINGS.api_key,
        temperature=0,
        max_tokens=max(600, SETTINGS.max_tokens),
        max_retries=5,
    )


def _trace_config() -> dict:
    """Attach the extra LangSmith identity fields to every agent run."""
    return {
        "run_name": SETTINGS.langsmith_agent_id,
        "metadata": {
            "agent_id": SETTINGS.langsmith_agent_id,
            "environment": SETTINGS.langsmith_agent_environment,
            "project": SETTINGS.langsmith_project,
        },
    }


async def build_agent():
    """Build the agent once at bot startup."""
    return create_agent(
        model=_model(),
        tools=await load_tools(),
        system_prompt=_system_prompt(),
    )


async def answer(agent, messages: list[BaseMessage]) -> str:
    """Run one turn and return the final text.

    One small guard: if the agent used planning tools but skipped the budget
    tool, nudge it once. This is not a revision loop.
    """
    result = await agent.ainvoke({"messages": messages}, config=_trace_config())
    used = _tool_names(result.get("messages") or [])

    planning_tools = {"get_weather", "web_search", "find_famous_food"}
    if used & planning_tools and "calculate_budget" not in used:
        nudge = HumanMessage(
            content=(
                "You skipped calculate_budget. Call it now with the costs from "
                "your plan, then give the final answer with its total and status."
            )
        )
        result = await agent.ainvoke(
            {"messages": [*(result.get("messages") or []), nudge]},
            config=_trace_config(),
        )

    for message in reversed(result.get("messages") or []):
        if getattr(message, "type", "") == "ai":
            text = str(message.content or "").strip()
            if text:
                return _finalize(text, result.get("messages") or [])
    return "I could not put an answer together. Try that once more."


def _tool_names(messages: list[BaseMessage]) -> set[str]:
    names: set[str] = set()
    for message in messages:
        for call in getattr(message, "tool_calls", None) or []:
            name = call.get("name") if isinstance(call, dict) else None
            if name:
                names.add(name)
    return names


def _tool_payload(messages: list[BaseMessage], name: str) -> dict | None:
    """Return the last JSON payload from a named tool, if it has one."""
    for message in reversed(messages):
        if getattr(message, "name", "") != name:
            continue

        content = message.content
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
        try:
            payload = json.loads(content)
        except (TypeError, ValueError):
            return None
        return payload if isinstance(payload, dict) else None
    return None


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("–", "-").replace("—", "-")).strip().lower()


def _finalize(text: str, messages: list[BaseMessage]) -> str:
    """Keep the model's wording, but make the budget and tool gaps trustworthy."""
    budget = _tool_payload(messages, "calculate_budget")
    if budget and budget.get("display"):
        display = budget["display"]
        if _normalize(display) not in _normalize(text):
            lines = [
                line
                for line in text.splitlines()
                if not re.match(
                    r"^\s*(?:#+\s*)?(?:\*\*)?(?:budget(?:\s+(?:summary|check|result))?|total)"
                    r"(?:\*\*)?\s*(?:[:\-–—].*)?$",
                    line,
                    re.IGNORECASE,
                )
            ]
            text = "\n".join(lines).strip()
            text += f"\n\n**Budget (calculated):** {display}"

    search_failed = any(
        (_tool_payload(messages, name) or {}).get("error")
        for name in ("web_search", "find_famous_food")
    )
    if search_failed and not re.search(
        r"unavailable|could not check|couldn't check|unverified", text, re.IGNORECASE
    ):
        text += (
            "\n\n_Live place search was unavailable, so venue details are "
            "unverified._"
        )

    return text
