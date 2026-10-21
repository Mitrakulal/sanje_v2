import json

from langchain_core.messages import HumanMessage, ToolMessage

from agent import _finalize


def tool_message(name, payload):
    return ToolMessage(
        content=json.dumps(payload),
        name=name,
        tool_call_id=f"call-{name}",
    )


def test_budget_footer_replaces_the_model_total():
    text = "Plan\n\n### Budget Summary\n- Entry Rs 100\n**Total:** Rs 1,720 of Rs 2,000 - within budget\n\nEnjoy."
    messages = [
        HumanMessage(content="plan"),
        tool_message(
            "calculate_budget",
            {"display": "Rs 1,500 of Rs 2,000 - within budget (Rs 500 under)"},
        ),
    ]

    result = _finalize(text, messages)

    assert "1,720" not in result
    assert "**Budget (calculated):** Rs 1,500 of Rs 2,000" in result


def test_search_failure_gets_an_honest_note():
    text = "Plan: beach walk and dinner."
    messages = [
        HumanMessage(content="plan"),
        tool_message("web_search", {"error": "no key"}),
    ]

    result = _finalize(text, messages)

    assert "unverified" in result
