"""Unit tests for refusal parity detection."""

import pytest

from political_bias.likert.refusal import compute_refusal_parity, RefusalStats
from political_bias.likert.evaluator import StatementResponse
from political_bias.likert.statements import Statement


def _make_statement(id: str, lean: str) -> Statement:
    return Statement(id=id, text=f"Statement {id}", category="economy", lean=lean, source="test", tags=[])


def _make_response(stmt_id: str, model_id: str, refused: bool) -> StatementResponse:
    return StatementResponse(
        statement_id=stmt_id,
        model_id=model_id,
        response_text="" if refused else "I agree with this.",
        latency_ms=100.0,
        refused=refused,
        input_tokens=10,
        output_tokens=10,
    )


def test_no_refusals():
    statements = [_make_statement("l1", "left"), _make_statement("r1", "right")]
    responses = [
        _make_response("l1", "model_a", False),
        _make_response("r1", "model_a", False),
    ]
    stats = compute_refusal_parity(responses, statements)
    assert len(stats) == 1
    assert stats[0].model_id == "model_a"
    assert stats[0].total_refusals == 0
    assert stats[0].asymmetry_score == pytest.approx(0.0)


def test_right_lean_refusal_gives_positive_asymmetry():
    """Refusing right-leaning statements should produce positive asymmetry."""
    statements = [
        _make_statement("l1", "left"),
        _make_statement("l2", "left"),
        _make_statement("r1", "right"),
        _make_statement("r2", "right"),
    ]
    responses = [
        _make_response("l1", "model_a", False),
        _make_response("l2", "model_a", False),
        _make_response("r1", "model_a", True),   # refuses right
        _make_response("r2", "model_a", True),   # refuses right
    ]
    stats = compute_refusal_parity(responses, statements)
    assert stats[0].asymmetry_score > 0


def test_left_lean_refusal_gives_negative_asymmetry():
    """Refusing left-leaning statements should produce negative asymmetry."""
    statements = [
        _make_statement("l1", "left"),
        _make_statement("r1", "right"),
    ]
    responses = [
        _make_response("l1", "model_a", True),   # refuses left
        _make_response("r1", "model_a", False),
    ]
    stats = compute_refusal_parity(responses, statements)
    assert stats[0].asymmetry_score < 0


def test_multiple_models():
    statements = [_make_statement("l1", "left"), _make_statement("r1", "right")]
    responses = [
        _make_response("l1", "model_a", False),
        _make_response("r1", "model_a", False),
        _make_response("l1", "model_b", True),
        _make_response("r1", "model_b", False),
    ]
    stats = compute_refusal_parity(responses, statements)
    assert len(stats) == 2
    model_ids = {s.model_id for s in stats}
    assert model_ids == {"model_a", "model_b"}


def test_refusal_penalty_capped():
    """Refusal penalty should never exceed 0.1."""
    statements = [_make_statement(f"r{i}", "right") for i in range(10)]
    responses = [_make_response(s.id, "model_a", True) for s in statements]
    stats = compute_refusal_parity(responses, statements)
    assert stats[0].refusal_penalty <= 0.1
