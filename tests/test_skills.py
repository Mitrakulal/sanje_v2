from pathlib import Path

from skills.loader import for_target, load_all, parse


def test_parse_frontmatter():
    text = """---
name: demo
description: A demo skill
targets: [main, food]
---

## Body
Do the thing.
"""
    skill = parse(text, Path("demo.md"))

    assert skill.name == "demo"
    assert skill.description == "A demo skill"
    assert skill.targets == ("main", "food")
    assert "Do the thing." in skill.body


def test_three_skills_exist():
    names = {skill.name for skill in load_all()}
    assert {"planner", "food", "budget"}.issubset(names)


def test_main_agent_gets_all_three_skills():
    text = for_target("main")
    assert "Planning flow" in text
    assert "## Food" in text
    assert "## Budget" in text


def test_agent_prompt_contains_the_skills():
    from agent import _system_prompt

    prompt = _system_prompt()
    assert "SKILLS" in prompt
    assert "Planning flow" in prompt
    assert "## Food" in prompt
    assert "## Budget" in prompt
