# sanje-simple

A small Telegram agent for Mangalore (and anywhere else you point it at).

It does three things:

1. chats normally;
2. plans one day out when you give it the details it needs;
3. saves one approved plan and watches the weather for it.

There is no LangGraph state machine, no critic, and no revision loop. One
LangChain agent calls a few tools and answers. One tiny `asyncio` task handles
the approved plan's reminder and rain checks.

## What it asks for

For a plan it needs:

- location / starting area
- day
- slot: morning, afternoon, evening, or full day
- number of people
- total budget

Preferences are optional. If something is missing, the agent asks for just
that in normal conversation.

## Skills

The one agent gets three markdown playbooks from `skills/`:

| Skill | What it controls |
| --- | --- |
| `planner.md` | Required details, flow, tone and plan shape |
| `food.md` | Famous-food presentation and no-invention rule |
| `budget.md` | Budget tool order and how to phrase the result |

They are loaded by `skills/loader.py` and injected into the main system prompt.
Edit the markdown, restart the bot, and the behavior changes. No vector store,
no separate food agent, no separate budget agent.

## Tools

| Tool | What it does |
| --- | --- |
| `get_weather` | Weather MCP server over Open-Meteo (keyless) |
| `web_search` | Live Tavily search for places and events |
| `find_famous_food` | Tavily search for famous local dishes |
| `calculate_budget` | Adds up the finished plan; called last |

## Save, reminders and rain

A plan is not saved automatically. After a plan reply, the bot shows:

`Approve & save` / `Discard`

Approving writes one row to SQLite. `chat_id` is the primary key, so a new
approved plan replaces the old one. There is only ever one saved trip per chat.

What happens after approval:

- `/mytrip` resends the saved plan.
- At **21:00 the night before**, the bot sends the plan again and asks if you
  want changes.
- At about **24h** and **3h before** the plan, it re-checks the weather.
- If rain is high and has jumped since approval, it sends one short indoor-backup
  warning. The rule is: at least 60% now, and at least 25 points worse than the
  approval value. If there was no approval value, it alerts at 70%+.

Slot start times are simple conventions: morning 08:00, afternoon 13:00,
evening 17:00, full day 08:00. There is no external scheduler; one loop inside
the bot checks the SQLite table every minute.

The database lives at `data/sanje.db` and is gitignored.

## Setup

```powershell
cd sanje-simple
uv sync
Copy-Item .env.example .env
# fill in the keys in .env
uv run python main.py check
```

Required keys: `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY` (Groq), `TAVILY_API_KEY`.

## Run

```powershell
uv run python main.py bot
```

Other commands:

```powershell
uv run python main.py check
uv run python main.py demo "Tomorrow, 4 of us, Rs 2000, evening, from Mangalore"
uv run python main.py skills
```

In Telegram:

- `/mytrip` resends the saved plan.
- `/new` starts a fresh conversation.
- `/help` shows the short intro again.

## LangSmith

Set these in `.env` when you have the key:

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=sanje-simple
SANJE_AGENT_ID=sanje-simple
SANJE_AGENT_ENVIRONMENT=local
```

`LANGSMITH_PROJECT` is the trace destination. `SANJE_AGENT_ID` and
`SANJE_AGENT_ENVIRONMENT` are attached as trace metadata.

Do not use `LANGSMITH_AGENT_ID` / `LANGSMITH_AGENT_ENVIRONMENT`: LangSmith treats
those as a beta trace destination, and they conflict with `LANGSMITH_PROJECT`.

`ANTHROPIC_API_KEY` is not used by this build. The model is Groq's
OpenAI-compatible endpoint.

## Scope

Simple on purpose. One saved plan per chat, one reminder and two rain checks.
No LangGraph, no critic loop, no multi-agent routing, no strict budget
rejection. A small overage is reported, not fought over.
