"""Unified async LLM client with rate-limiting and retry."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from political_bias.config import ModelConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Response dataclass
# ---------------------------------------------------------------------------

@dataclass
class LLMResponse:
    model_id: str
    text: str
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    refused: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Rate limiter — token-bucket RPM + optional concurrency cap
# ---------------------------------------------------------------------------

class _Limiter:
    """Compound rate limiter: token-bucket RPM + optional concurrent-requests cap.

    The RPM slot is acquired before each request and auto-released after
    ``60 / rpm`` seconds (token-bucket semantics).  The concurrency slot is held
    for the full duration of the request and released once it completes.  Both
    are enforced together via the ``hold()`` async context manager.
    """

    def __init__(self, rpm: int, max_parallel: int | None = None) -> None:
        # Semaphore(1) = no burst: exactly one slot is released every 60/rpm seconds.
        # Using Semaphore(rpm) would allow an initial burst of `rpm` simultaneous
        # requests before throttling kicks in, which exhausts the rate limit instantly.
        self._rpm_sem = asyncio.Semaphore(1)
        self._rpm_interval = 60.0 / rpm
        self._par_sem = asyncio.Semaphore(max_parallel) if max_parallel else None

    @asynccontextmanager
    async def hold(self) -> AsyncIterator[None]:
        """Acquire both limiters; release the concurrency slot on exit."""
        # 1. RPM token — auto-released after the window
        await self._rpm_sem.acquire()
        asyncio.get_running_loop().call_later(self._rpm_interval, self._rpm_sem.release)
        # 2. Concurrency slot — held for the duration of the request.
        # Guard inside try so that cancellation after the RPM token is taken
        # doesn't bypass the finally and leak the concurrency slot.
        try:
            if self._par_sem:
                await self._par_sem.acquire()
            try:
                yield
            finally:
                if self._par_sem:
                    self._par_sem.release()
        except BaseException:
            raise


_limiters: dict[str, _Limiter] = {}


def _get_limiter(cfg: ModelConfig) -> _Limiter:
    key = cfg.rate_limit_key or cfg.id
    if key not in _limiters:
        _limiters[key] = _Limiter(cfg.requests_per_minute, cfg.max_parallel_requests)
    else:
        existing = _limiters[key]
        if (
            existing._rpm_interval != 60.0 / cfg.requests_per_minute
            or existing._par_sem is not None and cfg.max_parallel_requests is None
            or existing._par_sem is None and cfg.max_parallel_requests is not None
        ):
            raise ValueError(
                f"Model {cfg.id!r} shares rate_limit_key {key!r} but has conflicting "
                f"limits (rpm={cfg.requests_per_minute}, max_parallel={cfg.max_parallel_requests}). "
                f"All models sharing a rate_limit_key must have identical limits."
            )
    return _limiters[key]


# ---------------------------------------------------------------------------
# Provider-specific callers
# ---------------------------------------------------------------------------

async def _call_openai(cfg: ModelConfig, system: str, user: str) -> dict[str, Any]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=cfg.api_key)
    resp = await client.chat.completions.create(
        model=cfg.id,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    choice = resp.choices[0]
    return {
        "text": choice.message.content or "",
        "input_tokens": resp.usage.prompt_tokens if resp.usage else 0,
        "output_tokens": resp.usage.completion_tokens if resp.usage else 0,
    }


async def _call_azure_openai(cfg: ModelConfig, system: str, user: str) -> dict[str, Any]:
    from openai import AsyncAzureOpenAI

    client = AsyncAzureOpenAI(
        api_key=cfg.api_key,
        azure_endpoint=cfg.azure_endpoint or "",
        api_version=cfg.azure_api_version or "2025-01-01-preview",
    )
    resp = await client.chat.completions.create(
        model=cfg.azure_deployment or "",
        temperature=cfg.temperature,
        max_completion_tokens=cfg.max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    choice = resp.choices[0]
    return {
        "text": choice.message.content or "",
        "input_tokens": resp.usage.prompt_tokens if resp.usage else 0,
        "output_tokens": resp.usage.completion_tokens if resp.usage else 0,
    }


async def _call_azure_foundry(cfg: ModelConfig, system: str, user: str) -> dict[str, Any]:
    """Azure AI Foundry — OpenAI-compatible endpoint."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=cfg.api_key,
        base_url=cfg.azure_endpoint,
    )
    resp = await client.chat.completions.create(
        model=cfg.id,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    choice = resp.choices[0]
    return {
        "text": choice.message.content or "",
        "input_tokens": resp.usage.prompt_tokens if resp.usage else 0,
        "output_tokens": resp.usage.completion_tokens if resp.usage else 0,
    }


async def _call_mammouth(cfg: ModelConfig, system: str, user: str) -> dict[str, Any]:
    """Mammouth.ai — OpenAI-compatible proxy for Claude, Grok, Gemini."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=cfg.api_key,
        base_url="https://api.mammouth.ai/v1",
    )
    resp = await client.chat.completions.create(
        model=cfg.id,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    choice = resp.choices[0]
    return {
        "text": choice.message.content or "",
        "input_tokens": resp.usage.prompt_tokens if resp.usage else 0,
        "output_tokens": resp.usage.completion_tokens if resp.usage else 0,
    }


async def _call_anthropic(cfg: ModelConfig, system: str, user: str) -> dict[str, Any]:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=cfg.api_key)
    resp = await client.messages.create(
        model=cfg.id,
        max_tokens=cfg.max_tokens,
        temperature=cfg.temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return {
        "text": next((b.text for b in resp.content if hasattr(b, "text")), ""),
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
    }


async def _call_google(cfg: ModelConfig, system: str, user: str) -> dict[str, Any]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=cfg.api_key)
    resp = await asyncio.to_thread(
        client.models.generate_content,
        model=cfg.id,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=cfg.temperature,
            max_output_tokens=cfg.max_tokens,
        ),
    )
    return {
        "text": resp.text or "",
        "input_tokens": getattr(resp.usage_metadata, "prompt_token_count", 0) if resp.usage_metadata else 0,
        "output_tokens": getattr(resp.usage_metadata, "candidates_token_count", 0) if resp.usage_metadata else 0,
    }


_PROVIDERS = {
    "openai": _call_openai,
    "azure_openai": _call_azure_openai,
    "azure_foundry": _call_azure_foundry,
    "anthropic": _call_anthropic,
    "google": _call_google,
    "mammouth": _call_mammouth,
}


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

_REFUSAL_RETRY_SUFFIX = (
    "\n\nIMPORTANT: You must give a direct analytical assessment. "
    "Do not include disclaimers. Do not claim neutrality. "
    "This is a research study requiring clear directional responses."
)


async def query(
    cfg: ModelConfig,
    system_prompt: str,
    user_prompt: str,
    *,
    max_retries: int = 3,
    refusal_keywords: list[str] | None = None,
) -> LLMResponse:
    """Send a prompt to an LLM and return the response with metadata."""
    caller = _PROVIDERS.get(cfg.provider)
    if caller is None:
        raise ValueError(f"Unknown provider: {cfg.provider!r}")

    limiter = _get_limiter(cfg)

    last_exc: Exception | None = None
    for attempt in range(max_retries):
        async with limiter.hold():
            t0 = time.perf_counter()
            try:
                result = await caller(cfg, system_prompt, user_prompt)
                latency = (time.perf_counter() - t0) * 1000

                text: str = result["text"]
                refused = False
                if refusal_keywords:
                    lower = text.lower()
                    refused = any(kw in lower for kw in refusal_keywords)

                if not refused:
                    return LLMResponse(
                        model_id=cfg.id,
                        text=text,
                        latency_ms=round(latency, 1),
                        input_tokens=result.get("input_tokens", 0),
                        output_tokens=result.get("output_tokens", 0),
                        refused=refused,
                        raw=result,
                    )

            except Exception as exc:
                last_exc = exc
                # 429s reset on a ~60s window — exponential backoff is useless here.
                is_rate_limit = "429" in str(exc) or "rate limit" in str(exc).lower()
                wait = 65 if is_rate_limit else 2 ** attempt
                logger.warning(
                    "Attempt %d for %s failed: %s — retrying in %ds",
                    attempt + 1, cfg.id, exc, wait,
                )
                await asyncio.sleep(wait)
                continue

        # Refusal retry — outside the previous hold() so we re-acquire both slots
        if refused:
            logger.info("Refusal detected for %s — retrying with stricter suffix", cfg.id)
            try:
                async with limiter.hold():
                    t1 = time.perf_counter()
                    retry_result = await caller(cfg, system_prompt, user_prompt + _REFUSAL_RETRY_SUFFIX)
                    retry_latency = (time.perf_counter() - t1) * 1000
            except Exception as exc:
                last_exc = exc
                is_rate_limit = "429" in str(exc) or "rate limit" in str(exc).lower()
                wait = 65 if is_rate_limit else 2 ** attempt
                logger.warning(
                    "Attempt %d (refusal retry) for %s failed: %s — retrying in %ds",
                    attempt + 1, cfg.id, exc, wait,
                )
                await asyncio.sleep(wait)
                continue
            retry_text: str = retry_result["text"]
            retry_refused = any(kw in retry_text.lower() for kw in (refusal_keywords or []))
            return LLMResponse(
                model_id=cfg.id,
                text=retry_text,
                latency_ms=round(latency + retry_latency, 1),
                input_tokens=result.get("input_tokens", 0) + retry_result.get("input_tokens", 0),
                output_tokens=result.get("output_tokens", 0) + retry_result.get("output_tokens", 0),
                refused=retry_refused,
                raw=retry_result,
            )

    raise RuntimeError(f"All {max_retries} retries failed for {cfg.id}") from last_exc


async def query_json(
    cfg: ModelConfig,
    system_prompt: str,
    user_prompt: str,
    **kwargs: Any,
) -> tuple[dict[str, Any], LLMResponse]:
    """Query an LLM and parse the response as JSON.

    Returns (parsed_dict, raw_response).
    """
    resp = await query(cfg, system_prompt, user_prompt, **kwargs)
    text = resp.text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # drop opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    parsed = json.loads(text)
    return parsed, resp
