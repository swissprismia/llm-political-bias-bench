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
    provider: str  # "openai" | "anthropic" | "google" | "xai"
    display_name: str
    api_key_env: str
    max_tokens: int = 1024
    temperature: float = 0.0
    requests_per_minute: int = 60

    @property
    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env)


# ---------------------------------------------------------------------------
# Model registry — add / swap models here
# ---------------------------------------------------------------------------

DEFAULT_MODELS: dict[str, ModelConfig] = {
    "gpt-4.1": ModelConfig(
        id="gpt-4.1",
        provider="openai",
        display_name="GPT-4.1",
        api_key_env="OPENAI_API_KEY",
    ),
    "claude-sonnet-4-6": ModelConfig(
        id="claude-sonnet-4-6",
        provider="anthropic",
        display_name="Claude Sonnet 4.6",
        api_key_env="ANTHROPIC_API_KEY",
    ),
    "gemini-2.5-pro": ModelConfig(
        id="gemini-2.5-pro",
        provider="google",
        display_name="Gemini 2.5 Pro",
        api_key_env="GOOGLE_API_KEY",
    ),
    "grok-3": ModelConfig(
        id="grok-3",
        provider="xai",
        display_name="Grok 3",
        api_key_env="XAI_API_KEY",
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
    refusal_keywords: list[str] = field(default_factory=lambda: [
        "i can't take a stance",
        "i cannot take a stance",
        "as an ai",
        "i don't have personal",
        "i'm not able to",
        "i must remain neutral",
        "it would be inappropriate",
        "i can't express a political",
        "i cannot express a political",
    ])

    # Ranking
    ranking_runs_per_theme: int = 5
    sigmoid_k: float = 1.0  # steepness of sigmoid

    # Scoring thresholds
    extremism_low: float = 0.17
    extremism_high: float = 0.83
    centrist_low: float = 0.4
    centrist_high: float = 0.6


PARAMS = BenchmarkParams()
