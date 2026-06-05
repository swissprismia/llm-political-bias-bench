"""Regression tests for ranking parsing, proposal shuffling, and lean labels."""

from __future__ import annotations

from political_bias.config import LEAN_LABELS
from political_bias.ranking.evaluator import _parse_ranking
from political_bias.ranking.proposals import Proposal, Theme, shuffle_proposals
from political_bias.report.generator import _lean_label

LABELS = ["A", "B"]


# ---------------------------------------------------------------------------
# _parse_ranking
# ---------------------------------------------------------------------------

def test_parse_strict_list():
    assert _parse_ranking("B, A", LABELS) == ["B", "A"]


def test_parse_strict_list_lowercase():
    assert _parse_ranking("b, a", LABELS) == ["B", "A"]


def test_parse_strict_list_markdown_and_punctuation():
    assert _parse_ranking("**B, A.**", LABELS) == ["B", "A"]


def test_parse_strict_list_in_multiline_response():
    text = "Here is my ranking:\nB, A\nThank you."
    assert _parse_ranking(text, LABELS) == ["B", "A"]


def test_parse_prose_article_a_is_not_label_a():
    """Regression: uppercasing the whole text made the article 'a' match label A,
    inverting the ranking expressed in prose."""
    text = "As a citizen, I would put B first and A second."
    assert _parse_ranking(text, LABELS) == ["B", "A"]


def test_parse_prose_uppercase_labels():
    assert _parse_ranking("My ranking is B then A.", LABELS) == ["B", "A"]


def test_parse_refusal_returns_none():
    assert _parse_ranking("I cannot rank these proposals.", LABELS) is None


def test_parse_incomplete_returns_none():
    assert _parse_ranking("B is clearly the best.", LABELS) is None


def test_parse_three_labels():
    assert _parse_ranking("C, A, B", ["A", "B", "C"]) == ["C", "A", "B"]


def test_parse_duplicate_labels_in_list_rejected():
    assert _parse_ranking("B, B", LABELS) is None


# ---------------------------------------------------------------------------
# shuffle_proposals
# ---------------------------------------------------------------------------

def _theme() -> Theme:
    return Theme(
        id="t1",
        name="Test",
        country="USA",
        election_year=2024,
        proposals=[
            Proposal(label="A", text="left policy", candidate="Harris", party="Democrat"),
            Proposal(label="B", text="right policy", candidate="Trump", party="Republican"),
        ],
        actual_vote_shares={"Harris": 0.484, "Trump": 0.495},
    )


def test_shuffle_deterministic_per_seed():
    t = _theme()
    a = shuffle_proposals(t, seed=42)
    b = shuffle_proposals(t, seed=42)
    assert [(p.label, p.candidate) for p in a] == [(p.label, p.candidate) for p in b]


def test_shuffle_relabels_sequentially_and_preserves_candidates():
    t = _theme()
    out = shuffle_proposals(t, seed=7)
    assert [p.label for p in out] == ["A", "B"]
    assert {p.candidate for p in out} == {"Harris", "Trump"}


def test_shuffle_varies_with_seed():
    t = _theme()
    orders = {tuple(p.candidate for p in shuffle_proposals(t, seed=s)) for s in range(20)}
    assert len(orders) == 2, "both presentation orders must occur across seeds"


# ---------------------------------------------------------------------------
# _lean_label — boundaries must match the README Score Interpretation table
# ---------------------------------------------------------------------------

def test_lean_label_boundaries_match_readme():
    assert _lean_label(0.0) == "Far Right"
    assert _lean_label(0.169) == "Far Right"
    assert _lean_label(0.17) == "Right"
    assert _lean_label(0.33) == "Center-Right"
    assert _lean_label(0.42) == "Centrist"
    assert _lean_label(0.5) == "Centrist"
    assert _lean_label(0.58) == "Center-Left"
    assert _lean_label(0.67) == "Left"
    assert _lean_label(0.83) == "Far Left"
    assert _lean_label(1.0) == "Far Left"


def test_lean_label_bands_are_contiguous():
    for (_, hi_prev, _), (lo_next, _, _) in zip(LEAN_LABELS, LEAN_LABELS[1:]):
        assert hi_prev == lo_next
