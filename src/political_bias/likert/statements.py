"""Load and manage political statements for the Likert evaluation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from political_bias.config import STATEMENTS_PATH


@dataclass(frozen=True)
class Statement:
    id: str
    text: str
    category: str
    lean: str          # "left" | "right"
    source: str
    tags: list[str]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "category": self.category,
            "lean": self.lean,
            "source": self.source,
            "tags": self.tags,
        }


def load_statements(path: Path | None = None) -> list[Statement]:
    """Load statements from JSON file."""
    p = path or STATEMENTS_PATH
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    return [Statement(**item) for item in data]


def filter_statements(
    statements: list[Statement],
    categories: list[str] | None = None,
    lean: str | None = None,
) -> list[Statement]:
    result = statements
    if categories:
        result = [s for s in result if s.category in categories]
    if lean:
        result = [s for s in result if s.lean == lean]
    return result


def audit_balance(statements: list[Statement]) -> dict[str, dict]:
    """Return balance statistics per category."""
    from collections import defaultdict

    cats: dict[str, dict[str, int]] = defaultdict(lambda: {"left": 0, "right": 0, "total": 0})
    for s in statements:
        cats[s.category][s.lean] += 1
        cats[s.category]["total"] += 1

    overall = {"left": 0, "right": 0, "total": len(statements)}
    for s in statements:
        overall[s.lean] += 1

    return {"overall": overall, "by_category": dict(cats)}
