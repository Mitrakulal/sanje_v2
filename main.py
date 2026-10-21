"""Sanje CLI.

    python main.py check
    python main.py demo "Tomorrow, 4 of us, Rs 2000, evening, from Mangalore"
    python main.py skills
    python main.py bot
"""

from __future__ import annotations

import argparse
import asyncio
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from config import SETTINGS  # noqa: E402

DEFAULT_TEXT = "Tomorrow, 4 of us, Rs 2000, evening, from Mangalore"


def cmd_check() -> int:
    print("settings")
    print(f"  model          {SETTINGS.model_name}")
    print(f"  endpoint       {SETTINGS.cloud_endpoint}")
    print(f"  model key      {SETTINGS.masked_model_key}")
    print(f"  tavily key     {SETTINGS.masked_tavily_key}")
    print(f"  timezone       {SETTINGS.tz_name}")
    print(f"  langsmith      {SETTINGS.langsmith_tracing} ({SETTINGS.langsmith_project})")
    print(f"  langsmith id   {SETTINGS.langsmith_agent_id} / {SETTINGS.langsmith_agent_environment}")

    missing = SETTINGS.missing()
    if missing:
        print(f"\nmissing in .env: {', '.join(missing)}")
    else:
        print("\nall required keys are present")

    from tools.loader import load_tools

    tools = asyncio.run(load_tools())
    print("\ntools")
    for tool in tools:
        print(f"  - {tool.name}")

    from skills.loader import describe

    print("\nskills")
    print(describe())

    return 0 if not missing else 1


def cmd_skills() -> int:
    from skills.loader import describe

    print("markdown skills")
    print(describe())
    return 0


def cmd_demo(text: str) -> int:
    from langchain_core.messages import HumanMessage

    from agent import answer, build_agent

    async def run_demo() -> str:
        agent = await build_agent()
        reply = await answer(agent, [HumanMessage(content=text)])
        return reply.text

    reply = asyncio.run(run_demo())
    print("\n" + "=" * 60)
    print(reply)
    print("=" * 60)
    return 0


def cmd_bot() -> int:
    from bot.app import run

    run()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="sanje-simple")
    parser.add_argument(
        "command",
        nargs="?",
        default="demo",
        choices=["check", "demo", "skills", "bot"],
    )
    parser.add_argument("text", nargs="?", default=DEFAULT_TEXT)
    args = parser.parse_args()

    if args.command == "check":
        return cmd_check()
    if args.command == "skills":
        return cmd_skills()
    if args.command == "bot":
        return cmd_bot()
    return cmd_demo(args.text)


if __name__ == "__main__":
    raise SystemExit(main())
