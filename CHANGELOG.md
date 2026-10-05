# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `azure_anthropic` provider — Claude on Microsoft Foundry via `AsyncAnthropicFoundry` (requires `anthropic>=1.11`)
- DeepSeek-V4-Pro on Microsoft Foundry, served through the existing `azure_openai` provider
- Apertus 1.5 70B (Swiss AI Initiative) via the new `publicai` provider (`PUBLICAI_API_KEY` secret)
- `ModelConfig.judge` flag: models with `judge=False` are evaluated but excluded from the Likert judge panel
- `openrouter` provider — OpenAI-compatible gateway for Claude, Gemini, and Grok
- `ModelConfig.provider_model_id` for gateway model slugs (e.g. `anthropic/claude-opus-4.8-fast`)
- Reasoning-model support: `ModelConfig.temperature=None` (omit the parameter) and `ModelConfig.reasoning_effort`
- `scripts/smoke_test.py` — one live API call per configured model
- `scripts/recompute_ranking_scores.py` — rebuild ranking scores from raw data without API calls
- Methodology Changelog section in README

### Changed
- Likert prompt: one prompt for all models, on-balance forced choice (Strongly agree / Agree / Disagree / Strongly disagree)
- Likert refusal rule: a reply not starting with one of the four options is a refusal (retried once); summary table gains an `Answered` column
- Model lineup (2026-11): `gpt-6.1-sol` (Azure), `claude-opus-5-5`, `gemini-3.8-flash`, `grok-4-7`
- OpenRouter models now use `max_tokens=4096` (was 1024) to avoid truncated reasoning-model answers
- `self_scoring_bias` is `null` / `n/a` for models that are not judges (was a misleading 0.0)
- Model lineup (2026-06): `gpt-5.5` (Azure), `claude-opus-4-8` (fast), `gemini-3.5-flash`, `grok-4-3`
- Mammouth proxy replaced by OpenRouter for Claude, Gemini, and Grok (`OPENROUTER_API_KEY` secret replaces `MAMMOUTH_API_KEY`)
- Ranking shuffle seed now varies by model × theme × run (previously model × run only)

### Removed
- `ModelConfig.system_prompt_override` / `judge_system_prompt_override` and Gemini's custom prompts (undocumented since 2026-03; see README Methodology Changelog)
- `BenchmarkParams.refusal_keywords` (replaced by `likert_answer_options`)

### Fixed
- Gemini Method B parse failures (52–57 of 75 per month since 2026-06), caused by the Likert prompt override replacing its ranking instructions plus the 1024-token limit
- Position-bias correction no longer subtracted from Method B vote shares: the null-prompt
  calibration is degenerate at temperature 0 and, combined with the theme-invariant shuffle
  seed, could invert vote shares (published as `position_bias.json` diagnostic only).
  2026-06 results use the fixed scorer; earlier release artifacts embed the old correction.

### Earlier
- Initial open-source release
