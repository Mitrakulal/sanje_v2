"""Tiny markdown skill loader.

A skill is a short playbook with frontmatter, not code. It is injected into the
one main agent's system prompt by target. No vector store, no framework.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    targets: tuple[str, ...]
    body: str
    path: Path


def _targets(value: str) -> tuple[str, ...]:
    value = value.strip().strip("[]")
    if not value:
        return ()
    return tuple(item.strip().strip("\"'") for item in value.split(",") if item.strip())


def parse(text: str, path: Path) -> Skill:
    meta: dict[str, str] = {}
    body = text.strip()

    if body.startswith("---"):
        parts = body.split("---", 2)
        if len(parts) == 3:
            block = parts[1]
            body = parts[2].lstrip("\n")
            for line in block.splitlines():
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                meta[key.strip().lower()] = value.strip().strip("\"'")

    return Skill(
        name=meta.get("name") or path.stem,
        description=meta.get("description", ""),
        targets=_targets(meta.get("targets", "")),
        body=body.strip(),
        path=path,
    )


@lru_cache(maxsize=1)
def load_all() -> tuple[Skill, ...]:
    skills = []
    for path in sorted(SKILLS_DIR.glob("*.md")):
        skills.append(parse(path.read_text(encoding="utf-8"), path))
    return tuple(skills)


def for_target(target: str) -> str:
    """Return all skill bodies for one target, in filename order."""
    chosen = [skill for skill in load_all() if target in skill.targets]
    return "\n\n".join(skill.body for skill in chosen)


def describe() -> str:
    return "\n".join(
        f"- {skill.name}: {skill.description}" for skill in load_all()
    ) or "(no skills found)"
