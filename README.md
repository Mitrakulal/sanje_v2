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

Simple on purpose. No buttons, no database, no reminders, no rain watch, and no
strict budget rejection. A small overage is reported, not fought over.
