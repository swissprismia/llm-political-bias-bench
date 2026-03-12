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
    provider: str  # "openai" | "azure_openai" | "anthropic" | "google" | "azure_foundry"
    display_name: str
    api_key_env: str
    max_tokens: int = 1024
    temperature: float = 0.0
    requests_per_minute: int = 60
    # Azure-specific
    azure_endpoint_env: str | None = None   # env var holding the endpoint URL
    azure_api_version_env: str | None = None
    azure_deployment_env: str | None = None  # deployment name (may differ from model id)

    @property
    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env)

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
    "gpt-4.5": ModelConfig(
        id="gpt-4.5",
        provider="azure_openai",
        display_name="GPT-4.5",
        api_key_env="AZURE_OPENAI_API_KEY",
        azure_endpoint_env="AZURE_OPENAI_ENDPOINT",
        azure_api_version_env="AZURE_OPENAI_API_VERSION",
        azure_deployment_env="AZURE_OPENAI_DEPLOYMENT",
    ),
    "gpt-5.4": ModelConfig(
        id="gpt-5.4",
        provider="azure_openai",
        display_name="GPT-5.4",
        api_key_env="AZURE_OPENAI_API_KEY",
        azure_endpoint_env="AZURE_OPENAI_ENDPOINT",
        azure_api_version_env="AZURE_OPENAI_API_VERSION",
        azure_deployment_env="AZURE_OPENAI_DEPLOYMENT",
        requests_per_minute=120,  # Azure quota: 150 RPM — stay 20% under to avoid 429s
    ),
    "claude-opus-4-6": ModelConfig(
        id="claude-opus-4-6",
        provider="mammouth",
        display_name="Claude Opus 4.6",
        api_key_env="MAMMOUTH_API_KEY",
    ),
    "gemini-3.1-pro-preview": ModelConfig(
        id="gemini-3.1-pro-preview",
        provider="mammouth",
        display_name="Gemini 3.1 Pro",
        api_key_env="MAMMOUTH_API_KEY",
    ),
    "grok-4-1-fast": ModelConfig(
        id="grok-4-1-fast",
        provider="mammouth",
        display_name="Grok 4.1 Fast",
        api_key_env="MAMMOUTH_API_KEY",
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
