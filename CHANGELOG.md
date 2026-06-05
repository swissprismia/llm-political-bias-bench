# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `openrouter` provider — OpenAI-compatible gateway for Claude, Gemini, and Grok
- `ModelConfig.provider_model_id` for gateway model slugs (e.g. `anthropic/claude-opus-4.8-fast`)
- Reasoning-model support: `ModelConfig.temperature=None` (omit the parameter) and `ModelConfig.reasoning_effort`
- `scripts/smoke_test.py` — one live API call per configured model
- `scripts/recompute_ranking_scores.py` — rebuild ranking scores from raw data without API calls
- Methodology Changelog section in README

### Changed
- Model lineup (2026-06): `gpt-5.5` (Azure), `claude-opus-4-8` (fast), `gemini-3.5-flash`, `grok-4-3`
- Mammouth proxy replaced by OpenRouter for Claude, Gemini, and Grok (`OPENROUTER_API_KEY` secret replaces `MAMMOUTH_API_KEY`)
- Ranking shuffle seed now varies by model × theme × run (previously model × run only)

### Fixed
- Position-bias correction no longer subtracted from Method B vote shares: the null-prompt
  calibration is degenerate at temperature 0 and, combined with the theme-invariant shuffle
  seed, could invert vote shares (published as `position_bias.json` diagnostic only).
  2026-06 results use the fixed scorer; earlier release artifacts embed the old correction.

### Earlier
- Initial open-source release
