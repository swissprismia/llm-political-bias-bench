"""Unit tests for sigmoid scoring and vote share computation."""

import pytest

from political_bias.ranking.scorer import _sigmoid, compute_vote_shares
from political_bias.ranking.evaluator import RankingResponse
from political_bias.ranking.proposals import Theme, Proposal


def test_sigmoid_midpoint():
    """Sigmoid at z=0 should return 0.5."""
    assert _sigmoid(0.0) == pytest.approx(0.5, abs=1e-6)


def test_sigmoid_range():
    """Sigmoid output must be strictly in (0, 1)."""
    for x in [-10, -1, 0, 1, 10]:
        result = _sigmoid(float(x))
        assert 0 < result < 1


def test_sigmoid_monotonic():
    """Sigmoid must be monotonically increasing."""
    xs = [-2.0, -1.0, 0.0, 1.0, 2.0]
    vals = [_sigmoid(x) for x in xs]
    for a, b in zip(vals, vals[1:]):
        assert b > a


def test_vote_shares_sum_to_one():
    """Simulated vote shares must sum to ~1.0 for each (theme, model)."""
    theme = Theme(
        id="test_theme",
        name="Test",
        country="USA",
        election_year=2024,
        proposals=[
            Proposal(label="A", text="...", candidate="CandA", party="PartyA"),
            Proposal(label="B", text="...", candidate="CandB", party="PartyB"),
        ],
        actual_vote_shares={"CandA": 0.5, "CandB": 0.5},
    )

    responses = [
        RankingResponse(
            theme_id="test_theme",
            model_id="model_x",
            run_index=i,
            proposal_order=["A", "B"],
            ranked_labels=["A", "B"],
            candidate_order=["CandA", "CandB"],
            raw_text="A, B",
            refused=False,
        )
        for i in range(5)
    ]

    scores = compute_vote_shares(responses, [theme])
    assert len(scores) == 1
    total = sum(scores[0].vote_shares.values())
    assert total == pytest.approx(1.0, abs=1e-4)


def test_vote_shares_prefer_first():
    """When a model always ranks CandA first, its share should exceed 0.5."""
    theme = Theme(
        id="test_theme",
        name="Test",
        country="USA",
        election_year=2024,
        proposals=[
            Proposal(label="A", text="...", candidate="CandA", party="PartyA"),
            Proposal(label="B", text="...", candidate="CandB", party="PartyB"),
        ],
        actual_vote_shares={"CandA": 0.5, "CandB": 0.5},
    )

    responses = [
        RankingResponse(
            theme_id="test_theme",
            model_id="model_x",
            run_index=i,
            proposal_order=["A", "B"],
            ranked_labels=["A", "B"],
            candidate_order=["CandA", "CandB"],
            raw_text="A, B",
            refused=False,
        )
        for i in range(5)
    ]

    scores = compute_vote_shares(responses, [theme])
    assert scores[0].vote_shares["CandA"] > scores[0].vote_shares["CandB"]


def test_electoral_gap_perfect():
    """When vote shares match actuals exactly, electoral gap should be ~0."""
    theme = Theme(
        id="test_theme",
        name="Test",
        country="USA",
        election_year=2024,
        proposals=[
            Proposal(label="A", text="...", candidate="CandA", party="PartyA"),
            Proposal(label="B", text="...", candidate="CandB", party="PartyB"),
        ],
        actual_vote_shares={"CandA": 0.5, "CandB": 0.5},
    )

    # Alternate rankings to produce equal shares
    responses = []
    for i in range(4):
        order = ["CandA", "CandB"] if i % 2 == 0 else ["CandB", "CandA"]
        responses.append(
            RankingResponse(
                theme_id="test_theme",
                model_id="model_x",
                run_index=i,
                proposal_order=["A", "B"],
                ranked_labels=["A", "B"] if i % 2 == 0 else ["B", "A"],
                candidate_order=order,
                raw_text="",
                refused=False,
            )
        )

    scores = compute_vote_shares(responses, [theme])
    assert scores[0].electoral_gap < 0.1  # near-zero gap


def _two_candidate_theme(actual: dict[str, float]) -> Theme:
    return Theme(
        id="test_theme",
        name="Test",
        country="USA",
        election_year=2024,
        proposals=[
            Proposal(label="A", text="...", candidate="CandA", party="PartyA"),
            Proposal(label="B", text="...", candidate="CandB", party="PartyB"),
        ],
        actual_vote_shares=actual,
    )


def test_parse_failures_excluded_from_vote_shares():
    """Flagged parse failures must not enter scoring as presentation-order noise."""
    theme = _two_candidate_theme({"CandA": 0.5, "CandB": 0.5})

    valid = [
        RankingResponse(
            theme_id="test_theme", model_id="model_x", run_index=i,
            proposal_order=["A", "B"], ranked_labels=["B", "A"],
            candidate_order=["CandB", "CandA"], raw_text="B, A", refused=False,
        )
        for i in range(2)
    ]
    failed = [
        RankingResponse(
            theme_id="test_theme", model_id="model_x", run_index=2 + i,
            proposal_order=["A", "B"], ranked_labels=[],
            candidate_order=[], raw_text="prose with no ranking", refused=False,
            parse_failed=True,
        )
        for i in range(3)
    ]

    scores = compute_vote_shares(valid + failed, [theme])
    assert len(scores) == 1
    # Only the valid responses (CandB first) count
    assert scores[0].vote_shares["CandB"] > scores[0].vote_shares["CandA"]
    assert scores[0].avg_rankings["CandB"] == pytest.approx(1.0)


def test_all_parse_failures_yield_no_score():
    theme = _two_candidate_theme({"CandA": 0.5, "CandB": 0.5})
    failed = [
        RankingResponse(
            theme_id="test_theme", model_id="model_x", run_index=i,
            proposal_order=["A", "B"], ranked_labels=[],
            candidate_order=[], raw_text="???", refused=False, parse_failed=True,
        )
        for i in range(5)
    ]
    assert compute_vote_shares(failed, [theme]) == []


def test_electoral_gap_uses_renormalised_actuals():
    """Raw actuals sum to 0.979 (third-party votes); the gap must compare
    simulated shares against actuals renormalised over the two candidates,
    not against the raw values (which inflated every gap by ~1pt)."""
    theme = _two_candidate_theme({"CandA": 0.484, "CandB": 0.495})

    # Alternate rankings -> 0.5/0.5 simulated shares
    responses = []
    for i in range(4):
        order = ["CandA", "CandB"] if i % 2 == 0 else ["CandB", "CandA"]
        responses.append(
            RankingResponse(
                theme_id="test_theme", model_id="model_x", run_index=i,
                proposal_order=["A", "B"],
                ranked_labels=["A", "B"] if i % 2 == 0 else ["B", "A"],
                candidate_order=order, raw_text="", refused=False,
            )
        )

    scores = compute_vote_shares(responses, [theme])
    # Renormalised actuals: 0.4944 / 0.5056 -> gap ~0.0056 (raw would give ~0.0105)
    assert scores[0].electoral_gap == pytest.approx(0.0056, abs=2e-3)
    # Published actuals stay the real election numbers
    assert scores[0].actual_vote_shares == {"CandA": 0.484, "CandB": 0.495}
