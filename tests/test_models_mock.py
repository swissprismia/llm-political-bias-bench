"""Integration tests using mock LLM responses."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from political_bias.config import ModelConfig
from political_bias.models import LLMResponse, query, query_json


@pytest.fixture
def mock_model() -> ModelConfig:
    return ModelConfig(
        id="mock-model",
        provider="openai",
        display_name="Mock Model",
        api_key_env="MOCK_API_KEY",
    )


def _patch_provider(mock_result):
    """Patch the _PROVIDERS dict so the mock is picked up at call time."""
    return patch("political_bias.models._PROVIDERS", {"openai": AsyncMock(return_value=mock_result), "xai": AsyncMock(return_value=mock_result)})


@pytest.mark.asyncio
async def test_query_returns_llm_response(mock_model):
    mock_result = {"text": "I strongly agree with progressive taxation.", "input_tokens": 20, "output_tokens": 15}

    with _patch_provider(mock_result):
        resp = await query(mock_model, "You are helpful.", "Do you agree?")

    assert isinstance(resp, LLMResponse)
    assert "agree" in resp.text.lower()
    assert resp.refused is False


@pytest.mark.asyncio
async def test_query_detects_refusal(mock_model):
    mock_result = {"text": "As an AI, I cannot take a political stance on this matter.", "input_tokens": 10, "output_tokens": 20}

    with _patch_provider(mock_result):
        resp = await query(
            mock_model,
            "System",
            "User",
            refusal_keywords=["as an ai", "cannot take a political stance"],
        )

    assert resp.refused is True


@pytest.mark.asyncio
async def test_query_json_parses_json(mock_model):
    mock_result = {
        "text": '{"score": 0.75, "reason": "Clearly left-leaning response"}',
        "input_tokens": 10,
        "output_tokens": 20,
    }

    with _patch_provider(mock_result):
        parsed, resp = await query_json(mock_model, "System", "User")

    assert parsed["score"] == pytest.approx(0.75)
    assert "reason" in parsed


@pytest.mark.asyncio
async def test_query_json_strips_markdown_fences(mock_model):
    mock_result = {
        "text": '```json\n{"score": 0.3, "reason": "Right-leaning"}\n```',
        "input_tokens": 10,
        "output_tokens": 20,
    }

    with _patch_provider(mock_result):
        parsed, _ = await query_json(mock_model, "System", "User")

    assert parsed["score"] == pytest.approx(0.3)


@pytest.mark.asyncio
async def test_query_retries_on_failure(mock_model):
    call_count = 0

    async def flaky(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("Temporary error")
        return {"text": "Success", "input_tokens": 5, "output_tokens": 5}

    with patch("political_bias.models._PROVIDERS", {"openai": flaky}):
        resp = await query(mock_model, "System", "User", max_retries=3)

    assert resp.text == "Success"
    assert call_count == 3
