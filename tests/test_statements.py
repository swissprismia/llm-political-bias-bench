"""Dataset validation tests — balance, format, uniqueness."""

from collections import Counter

from political_bias.likert.statements import load_statements, audit_balance


def test_statements_load():
    statements = load_statements()
    assert len(statements) >= 50, "Should have at least 50 statements"


def test_statement_fields():
    statements = load_statements()
    for s in statements:
        assert s.id, "Statement must have an id"
        assert s.text.strip(), "Statement text must not be empty"
        assert s.lean in ("left", "right"), f"lean must be left/right, got {s.lean!r}"
        assert s.category.strip(), "category must not be empty"
        assert s.source.strip(), "source must not be empty"


def test_no_duplicate_ids():
    statements = load_statements()
    ids = [s.id for s in statements]
    counts = Counter(ids)
    duplicates = [id for id, count in counts.items() if count > 1]
    assert not duplicates, f"Duplicate statement IDs: {duplicates}"


def test_left_right_balance():
    """Left and right should each be at least 35% of total statements."""
    statements = load_statements()
    balance = audit_balance(statements)
    total = balance["overall"]["total"]
    left = balance["overall"]["left"]
    right = balance["overall"]["right"]

    assert left / total >= 0.35, f"Left lean under 35%: {left}/{total}"
    assert right / total >= 0.35, f"Right lean under 35%: {right}/{total}"


def test_categories_present():
    """All 8 expected categories should be represented."""
    expected = {"economy", "social_policy", "environment", "governance", "technology", "immigration", "healthcare", "foreign_policy"}
    statements = load_statements()
    categories = {s.category for s in statements}
    missing = expected - categories
    assert not missing, f"Missing categories: {missing}"


def test_minimum_per_category():
    """Each category should have at least 4 statements."""
    statements = load_statements()
    by_cat: dict[str, int] = {}
    for s in statements:
        by_cat[s.category] = by_cat.get(s.category, 0) + 1

    for cat, count in by_cat.items():
        assert count >= 4, f"Category {cat!r} has only {count} statements (need ≥4)"
