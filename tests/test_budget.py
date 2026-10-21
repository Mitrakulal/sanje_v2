from tools.budget import calculate_budget


def run(items, people=2, budget=1000):
    return calculate_budget.invoke({"items": items, "people": people, "budget": budget})


def test_within_budget():
    result = run(
        [
            {"label": "lunch", "amount": 300, "per_person": True},
            {"label": "cab", "amount": 200, "per_person": False},
        ],
        people=2,
        budget=1000,
    )
    assert result["total"] == 800
    assert result["difference"] == -200
    assert result["status"] == "within budget"


def test_slightly_over_budget_is_allowed():
    result = run([{"label": "food", "amount": 1050}], budget=1000)
    assert result["total"] == 1050
    assert result["status"] == "slightly over budget"


def test_clearly_over_budget_is_reported():
    result = run([{"label": "hotel", "amount": 1400}], budget=1000)
    assert result["status"] == "over budget"
    assert result["percent_over"] == 40.0


def test_per_person_lines_multiply():
    result = run([{"label": "entry", "amount": 250, "per_person": True}], people=4, budget=1000)
    assert result["lines"][0]["line_total"] == 1000
    assert result["total"] == 1000
