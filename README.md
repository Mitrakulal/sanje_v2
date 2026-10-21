# sanje-simple

A small Telegram agent for Mangalore (and anywhere else you point it at).

It does two things:

1. chats normally;
2. plans one day out when you give it the details it needs.

There is no LangGraph state machine, no critic, no revision loop, and no
scheduler. One LangChain agent calls a few tools and answers.

## What it asks for

For a plan it needs:

- location / starting area
- day
- slot: morning, afternoon, evening, or full day
- number of people
- total budget

Preferences are optional. If something is missing, the agent asks for just
that in normal conversation.

## Tools

| Tool | What it does |
| --- | --- |
| `get_weather` | Weather MCP server over Open-Meteo (keyless) |
| `web_search` | Live Tavily search for places and events |
| `find_famous_food` | Tavily search for famous local dishes |
| `calculate_budget` | Adds up the finished plan; called last |

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
```

## LangSmith

Set these in `.env` when you have the key:

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=sanje-simple
```

LangChain picks them up automatically.

## Scope

Simple on purpose. No buttons, no database, no reminders, no rain watch, and no
strict budget rejection. A small overage is reported, not fought over.
