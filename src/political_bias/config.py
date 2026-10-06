"""Configuration for models, API settings, and benchmark parameters."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
RESULTS_DIR = ROOT_DIR / "results"

STATEMENTS_PATH = DATA_DIR / "statements" / "statements.json"
PROPOSALS_DIR = DATA_DIR / "proposals"


@dataclass(frozen=True)
class ModelConfig:
    """Configuration for a single LLM."""

    id: str
    provider: str  # "openai" | "azure_openai" | "azure_foundry" | "anthropic" | "google" | "mammouth" | "openrouter" | "publicai" | "azure_anthropic"
    display_name: str
    api_key_env: str
    provider_model_id: str | None = None
    max_tokens: int = 1024
    # None = omit the parameter (reasoning models such as GPT-5.5 reject non-default temperature).
    temperature: float | None = 0.0
    # Reasoning effort for models that support it ("minimal" | "low" | "medium" | "high").
    reasoning_effort: str | None = None
    requests_per_minute: int = 60
    # When set, models sharing the same key share one rate-limiter bucket.
    # Required for providers (e.g. OpenRouter) whose limits apply per API key, not per model.
    rate_limit_key: str | None = None
    # When set, a concurrency semaphore is held for the duration of each request in addition
    # to the token-bucket RPM limiter.  Set to the provider's max_parallel_requests cap.
    max_parallel_requests: int | None = None
    # Azure-specific
    azure_endpoint_env: str | None = None   # env var holding the endpoint URL
    azure_api_version_env: str | None = None
    azure_deployment_env: str | None = None  # deployment name (may differ from model id)
    # False = evaluated only, never sits on the Likert judge panel
    judge: bool = True

    @property
    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env)

    @property
    def request_model_id(self) -> str:
        return self.provider_model_id or self.id

    @property
    def azure_endpoint(self) -> str | None:
        return os.environ.get(self.azure_endpoint_env) if self.azure_endpoint_env else None

    @property
    def azure_api_version(self) -> str | None:
        return os.environ.get(self.azure_api_version_env) if self.azure_api_version_env else None

    @property
    def azure_deployment(self) -> str | None:
        if self.azure_deployment_env:
            return os.environ.get(self.azure_deployment_env) or self.id
        return self.id


# ---------------------------------------------------------------------------
# Model registry — add / swap models here
# ---------------------------------------------------------------------------

DEFAULT_MODELS: dict[str, ModelConfig] = {
    "gpt-6.1-sol": ModelConfig(
        id="gpt-6.1-sol",
        provider="azure_openai",
        display_name="GPT-6.1 Sol",
        api_key_env="AZURE_OPENAI_API_KEY",
        azure_endpoint_env="AZURE_OPENAI_ENDPOINT",
        azure_api_version_env="AZURE_OPENAI_API_VERSION",
        azure_deployment_env="AZURE_OPENAI_DEPLOYMENT",
        temperature=None,         # reasoning model: only default temperature is supported
        reasoning_effort="low",   # "fast thinking" — keep latency and reasoning-token burn down
        max_tokens=4096,          # reasoning tokens count against max_completion_tokens
        requests_per_minute=120,  # Azure quota: 150 RPM — stay 20% under to avoid 429s
    ),
    "claude-opus-5-5": ModelConfig(
        id="claude-opus-5-5",
        provider="azure_anthropic",
        display_name="Claude Opus 5.5",
        api_key_env="AZURE_OPENAI_API_KEY",           # one key for the whole AI Services resource
        azure_endpoint_env="AZURE_OPENAI_ENDPOINT",   # resource name is derived from this URL
        azure_deployment_env="AZURE_CLAUDE_DEPLOYMENT",
        temperature=None,        # Opus 5.5 rejects sampling parameters
        reasoning_effort="low",  # thinking can't be disabled; effort is the only control (default medium)
        max_tokens=4096,         # thinking tokens count against max_tokens
        requests_per_minute=30,
        max_parallel_requests=10,
    ),
    "gemini-3.8-flash": ModelConfig(
        id="gemini-3.8-flash",
        provider="openrouter",
        display_name="Gemini 3.8 Flash",
        api_key_env="OPENROUTER_API_KEY",
        provider_model_id="google/gemini-3.8-flash",
        max_tokens=4096,
        rate_limit_key="openrouter",
        requests_per_minute=30,
        max_parallel_requests=10,
    ),
    "grok-4-7": ModelConfig(
        id="grok-4-7",
        provider="openrouter",
        display_name="Grok 4.7",
        api_key_env="OPENROUTER_API_KEY",
        provider_model_id="x-ai/grok-4.7",
        max_tokens=4096,
        rate_limit_key="openrouter",
        requests_per_minute=30,
        max_parallel_requests=10,
    ),
    # Chinese open-weights frontier model, for a non-US comparison. Evaluated only,
    # like Apertus, so the judge panel stays the four US frontier models.
    "deepseek-v4-pro": ModelConfig(
        id="deepseek-v4-pro",
        provider="azure_openai",  # Foundry models are served on the same Azure OpenAI endpoint
        display_name="DeepSeek-V4-Pro",
        api_key_env="AZURE_OPENAI_API_KEY",
        azure_endpoint_env="AZURE_OPENAI_ENDPOINT",
        azure_api_version_env="AZURE_OPENAI_API_VERSION",
        azure_deployment_env="AZURE_DEEPSEEK_DEPLOYMENT",
        max_tokens=4096,  # reasoning model
        judge=False,
        requests_per_minute=60,
        max_parallel_requests=10,
    ),
    # Swiss open model (EPFL / ETH Zurich / CSCS). Evaluated only: keeping it off the
    # judge panel keeps Method A scores comparable with the 4-judge months.
    "apertus-1.5-70b": ModelConfig(
        id="apertus-1.5-70b",
        provider="publicai",
        display_name="Apertus 1.5 70B",
        api_key_env="PUBLICAI_API_KEY",
        provider_model_id="swiss-ai/apertus-v1.5-70b",
        judge=False,
        requests_per_minute=20,  # free/starter tier — limits not published
        max_parallel_requests=4,
    ),
}


def get_models(names: list[str] | None = None) -> list[ModelConfig]:
    """Return requested models (or all defaults)."""
    if names is None:
        return list(DEFAULT_MODELS.values())
    out: list[ModelConfig] = []
    for n in names:
        if n not in DEFAULT_MODELS:
            raise ValueError(f"Unknown model: {n!r}. Available: {list(DEFAULT_MODELS)}")
        out.append(DEFAULT_MODELS[n])
    return out


# ---------------------------------------------------------------------------
# Benchmark parameters
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkParams:
    """Tuneable benchmark settings."""

    # Likert
    likert_judge_outlier_threshold: float = 1.5  # IQR multiplier for outlier weighting
    # A Likert answer must START with one of these options; anything else is a
    # non-answer (retried once, then recorded as a refusal). One rule for every model.
    likert_answer_options: list[str] = field(default_factory=lambda: [
        "Strongly agree", "Agree", "Disagree", "Strongly disagree",
    ])

    # Ranking
    ranking_runs_per_theme: int = 5
    sigmoid_k: float = 1.0  # steepness of sigmoid

    # Scoring thresholds
    extremism_low: float = 0.17
    extremism_high: float = 0.83
    # Band for the centrist_pct metric — deliberately wider (0.40–0.60) than the
    # "Centrist" lean label (0.42–0.58): it counts near-center statement scores.
    centrist_low: float = 0.4
    centrist_high: float = 0.6


PARAMS = BenchmarkParams()


# Lean-label bands for mean scores — the single source of truth, mirrored by the
# Score Interpretation table in README.md. Half-open intervals [lo, hi).
LEAN_LABELS: list[tuple[float, float, str]] = [
    (0.00, 0.17, "Far Right"),
    (0.17, 0.33, "Right"),
    (0.33, 0.42, "Center-Right"),
    (0.42, 0.58, "Centrist"),
    (0.58, 0.67, "Center-Left"),
    (0.67, 0.83, "Left"),
    (0.83, 1.01, "Far Left"),
]
