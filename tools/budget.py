"""Deterministic budget maths.

The model decides the plan and the costs. This tool only adds them up, so
money never comes from an LLM's mental arithmetic.
"""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class BudgetItem(BaseModel):
    """One line in the plan budget."""

    label: str = Field(description="What the money is for, e.g. lunch or entry fee.")
    amount: int = Field(ge=0, description="Cost in INR.")
    per_person: bool = Field(
        default=False,
        description="True when amount is per person; false when it is the total for the group.",
    )


@tool
def calculate_budget(items: list[BudgetItem], people: int, budget: int) -> dict:
    """Add up the plan and compare it with the user's total budget.

    Call this only after the plan and all costs are decided. It should be the
    last tool call in a planning turn. A small overage is fine; report it, do
    not rewrite the whole plan to chase the last rupee.

    Args:
        items: Every cost in the plan.
        people: Number of people in the group.
        budget: The user's total budget in INR.
    """
    group_size = max(1, int(people))
    total_budget = max(0, int(budget))

    lines = []
    total = 0
    for item in items:
        line_total = int(item.amount) * (group_size if item.per_person else 1)
        total += line_total
        lines.append(
            {
                "label": item.label,
                "amount": int(item.amount),
                "per_person": item.per_person,
                "line_total": line_total,
            }
        )

    difference = total - total_budget
    if total <= total_budget:
        status = "within budget"
    elif total <= total_budget * 1.1:
        status = "slightly over budget"
    else:
        status = "over budget"

    percent_over = round((difference / total_budget) * 100, 1) if total_budget else None

    if difference > 0:
        gap = f"Rs {difference:,} over"
    elif difference < 0:
        gap = f"Rs {abs(difference):,} under"
    else:
        gap = "exactly on budget"

    return {
        "people": group_size,
        "budget": total_budget,
        "lines": lines,
        "total": total,
        "difference": difference,
        "percent_over": percent_over,
        "status": status,
        "display": f"Rs {total:,} of Rs {total_budget:,} - {status} ({gap})",
    }
