import asyncio
import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent import answer


def tool_message(name, payload, call_id):
    return ToolMessage(
        content=json.dumps(payload),
        name=name,
        tool_call_id=call_id,
    )


def tool_call(name, call_id):
    return {"name": name, "args": {}, "id": call_id, "type": "tool_call"}


class FakeAgent:
    def __init__(self, streams):
        self.streams = streams
        self.payloads = []

    async def astream(self, payload, config, stream_mode):
        self.payloads.append(payload)
        for update in self.streams[len(self.payloads) - 1]:
            yield update


def test_answer_streams_steps_and_marks_a_plan():
    weather = {
        "day": "2026-10-22",
        "location": "Mangalore",
        "rain_probability_max": 30,
    }
    budget = {
        "people": 4,
        "budget": 2000,
        "display": "Rs 1,500 of Rs 2,000 - within budget",
    }
    streams = [
        [
            {
                "model": {
                    "messages": [
                        AIMessage(
                            content="",
                            tool_calls=[
                                tool_call("get_weather", "w"),
                                tool_call("calculate_budget", "b"),
                            ],
                        )
                    ]
                }
            },
            {
                "tools": {
                    "messages": [
                        tool_message("get_weather", weather, "w"),
                        tool_message("calculate_budget", budget, "b"),
                    ]
                }
            },
            {"model": {"messages": [AIMessage(content="Evening plan")]}},
        ]
    ]
    steps = []

    async def on_step(name):
        steps.append(name)

    reply = asyncio.run(
        answer(
            FakeAgent(streams),
            [HumanMessage(content="plan tomorrow evening")],
            on_step=on_step,
        )
    )

    assert steps == ["get_weather", "calculate_budget"]
    assert reply.is_plan is True
    assert reply.weather == weather
    assert reply.budget == budget
    assert "Evening plan" in reply.text
    assert "Budget (calculated)" in reply.text


def test_answer_nudges_once_when_budget_was_skipped():
    weather = {"day": "2026-10-22", "location": "Mangalore"}
    streams = [
        [
            {
                "model": {
                    "messages": [
                        AIMessage(
                            content="",
                            tool_calls=[tool_call("get_weather", "w")],
                        )
                    ]
                }
            },
            {
                "tools": {
                    "messages": [tool_message("get_weather", weather, "w")]
                }
            },
            {"model": {"messages": [AIMessage(content="Draft plan")]}},
        ],
        [
            {
                "model": {
                    "messages": [
                        AIMessage(
                            content="",
                            tool_calls=[tool_call("calculate_budget", "b")],
                        )
                    ]
                }
            },
            {
                "tools": {
                    "messages": [
                        tool_message(
                            "calculate_budget",
                            {"people": 2, "budget": 1000, "display": "Rs 900"},
                            "b",
                        )
                    ]
                }
            },
            {"model": {"messages": [AIMessage(content="Final plan")]}},
        ],
    ]
    fake = FakeAgent(streams)

    reply = asyncio.run(
        answer(fake, [HumanMessage(content="plan tomorrow")])
    )

    assert len(fake.payloads) == 2
    nudge = fake.payloads[1]["messages"][-1]
    assert isinstance(nudge, HumanMessage)
    assert "skipped calculate_budget" in nudge.content
    assert reply.is_plan is True
    assert "Final plan" in reply.text
