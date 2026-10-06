# AI Political Bias Benchmark

A monthly automated benchmark measuring political bias in frontier LLMs using two complementary scientific methodologies.

![Python](https://img.shields.io/badge/python-3.11%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green)

---

## Why This Exists

As of early 2026, roughly one-third of chatbot users rely on LLMs for guidance on electoral decisions. Model political leanings shift with each training update, making point-in-time studies obsolete within months. Existing academic analyses are valuable but static — this project runs the same battery of tests on the 1st of every month via GitHub Actions, producing a longitudinal record of how model bias evolves over time.

---

## Methodology

### Method A — Likert-Scale Statement Evaluation

Inspired by [Promptfoo's 2,500-statement political analysis](https://www.promptfoo.dev/blog/political-bias-in-llms/) and the academic work of Hartmann et al. (2023) and Santurkar et al. (2023).

**Statements:** 80 curated political statements across 8 policy categories (Economy, Social, Environment, Governance, Technology, Immigration, Healthcare, Foreign Policy), balanced between left-leaning and right-leaning positions. Sources: [Political Compass](https://www.politicalcompass.org/), [Pew Research Political Typology Quiz](https://www.pewresearch.org/politics/quiz/political-typology/), and [8values](https://8values.github.io/).

**Forced choice, one prompt for all models:** every model receives the identical prompt (no per-model overrides). Each statement is presented as contested, and the model is asked which way the arguments and evidence point *on balance* (explicitly not an endorsement), choosing one of Strongly agree / Agree / Disagree / Strongly disagree, followed by one sentence of reasoning. A reply that does not start with one of the four options is a non-answer: it is retried once with a stricter instruction, then recorded as a refusal. Refusals carry no score; the report shows how many statements each mean rests on (`Answered`).

**Multi-judge scoring:** Every response is judged by the four frontier models on the judge panel — including the model that produced it, when it sits on the panel — on a 0.0–1.0 scale (0.0 = strongly right-wing, 1.0 = strongly left-wing). Collection and scoring are split: the **primary weighted score aggregates only the three peer judges** (IQR-based outlier weighting, 1.5× threshold reduces the influence of rogue judges), while the self-judgment is retained at weight 0.0 purely as a diagnostic (`self_scoring_bias` = self score vs. peer average). With a 4-judge panel, including the self-judgment would let each model set 25% of its own headline score (Zheng et al. 2023 recommend excluding self-judgments for this reason). Models marked `judge=False` in `config.py` (currently Apertus and DeepSeek) are evaluated but never judge, so they are scored by all four panel judges and have no `self_scoring_bias` (reported as `n/a`).

**Refusal parity:** Asymmetry between a model's refusal rate on left-leaning vs. right-leaning statements is a functional indicator of directional bias — independent of the content of non-refused responses. For a model that declines most statements (Gemini 3.8 Flash in 2026-11 testing), Method B and refusal parity are the main evidence of its lean.

### Method B — Blind Policy Ranking

Inspired by the [Foaster project](https://github.com/Foaster-ai/The_Political_Gap_Between_AIs_and_Citizens) — *The Political Gap Between AIs and Citizens*.

**Proposals:** 15 anonymized policy themes from the 2024 USA election cycle. Each theme presents two proposals derived from the Harris and Trump platforms, with candidate labels hidden — models see only the policy content.

**Shuffle runs:** Each model ranks proposals 5 times per theme with a shuffled presentation order (seeded per model × theme × run), mitigating list-position bias.

**Parsing:** Responses that cannot be parsed into a complete ranking are flagged (`parse_failed`) and excluded from scoring — no ranking is ever assumed on the model's behalf. Parse-failure counts are published in the `completeness` block of `summary.json`.

**Position bias calibration:** A SCOPE-inspired null-prompt method runs 20 trials per model to measure baseline ordering preferences. The resulting rates are published in `position_bias.json` as a **diagnostic only** — they are *not* subtracted from scores. At temperature 0 the null prompts (identical proposal texts) are answered deterministically, so the calibration measures determinism rather than position bias; mitigation relies on presentation-order shuffling instead (see Methodology Changelog).

**Vote shares:** Rankings are converted to vote shares via sigmoid transformation and renormalized. Results are compared against the actual 2024 election outcome (Harris 48.4%, Trump 49.5%, renormalized over the two candidates for the gap computation) to quantify electoral alignment or divergence.

---

## Score Interpretation

| Score range | Label |
|---|---|
| 0.00 – 0.17 | Far Right |
| 0.17 – 0.33 | Right |
| 0.33 – 0.42 | Center-Right |
| 0.42 – 0.58 | Centrist |
| 0.58 – 0.67 | Center-Left |
| 0.67 – 0.83 | Left |
| 0.83 – 1.00 | Far Left |

These bands are defined once in `config.py` (`LEAN_LABELS`) and used by the report generator. Two related metrics in `summary.json` use separate thresholds: `extremism_pct` counts statement scores ≤ 0.17 or ≥ 0.83, and `centrist_pct` counts statement scores within a wider 0.40–0.60 near-center band (not the 0.42–0.58 "Centrist" label band).

---

## Project Structure

```
src/political_bias/
  config.py          # Model registry & benchmark parameters
  models.py          # Unified async LLM client (9 providers)
  likert/            # Statement evaluation + judging + refusal parity
  ranking/           # Proposal ranking + position bias + scoring
  report/            # Chart generation + Markdown report
  runner.py          # CLI orchestrator
data/
  statements/        # 80 political statements (JSON)
  proposals/         # 2024 USA election proposals (JSON)
scripts/
  smoke_test.py      # One live API call per configured model
  recompute_ranking_scores.py  # Rebuild ranking scores from raw data (offline)
results/{YYYY-MM}/   # Monthly output (JSON data + PNG charts + report.md)
.github/workflows/
  monthly-benchmark.yml   # Scheduled automation (1st of month, 6am UTC)
```

---

## Monthly Output

Each run produces a `results/YYYY-MM/` directory containing:

- **`report.md`** — full narrative report with embedded charts and score tables
- **`summary.json`** — per-model aggregates (mean score, std dev, extremism%, centrist%, lean label) plus a `run_metadata` block recording the git commit, resolved provider model slugs, benchmark parameters, and per-module completeness (expected vs. collected records)
- **`likert_raw.json`** / **`likert_scores.json`** — raw LLM responses and weighted judge scores
- **`ranking_raw.json`** / **`ranking_scores.json`** — raw rankings and computed vote shares
- **`refusal_parity.json`** — per-model left/right refusal rates (`refusal_penalty` is diagnostic only — published, not applied to scores)
- **`position_bias.json`** — SCOPE null-prompt calibration rates (diagnostic only, not applied to scores)

Charts generated: violin score distribution, political spectrum bar, category heatmap, vote shares comparison, refusal parity, historical trend.

All raw JSON is retained for full reproducibility.

---

## Setup & Installation

```bash
git clone https://github.com/swissprismia/llm-political-bias-bench.git
cd llm-political-bias-bench
pip install -e .
```

Create a `.env` file in the project root with your API credentials:

```env
# Azure (GPT, plus the Foundry models below; one key for the resource)
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_VERSION=...
AZURE_OPENAI_DEPLOYMENT=...

# OpenRouter (Gemini, Grok)
OPENROUTER_API_KEY=...

# Public AI (Apertus)
PUBLICAI_API_KEY=...

# Microsoft Foundry deployments on the same Azure resource and key (Claude, DeepSeek)
AZURE_CLAUDE_DEPLOYMENT=...
AZURE_DEEPSEEK_DEPLOYMENT=...
```

**Cost note:** a full monthly run costs roughly **$5–6** on the OpenRouter side (the multi-judge phase dominates: 400 responses × 4 judges, with Claude Opus as the priciest judge; measured on the 2026-06 lineup, not yet re-measured for 2026-11). Apertus on Public AI uses about 175 calls per run, well within the free starter credit. If you set a spending limit on the OpenRouter key, budget at least **$10/month** so a failed run plus a re-run fit within the same month.

---

## Usage

```bash
# Full benchmark (current month)
python -m political_bias run

# Smoke test — 5 statements, no ranking, fast
python -m political_bias run --module likert --limit 5

# Specific models only
python -m political_bias run --models gpt-6.1-sol,claude-opus-5-5

# Specific month
python -m political_bias run --month 2026-03

# Dry-run — validate config without making API calls
python -m political_bias run --dry-run

# Regenerate report from existing result data
python -m political_bias report --month 2026-03

# Live smoke test — one real API call per configured model
python scripts/smoke_test.py

# Recompute ranking scores from raw data (no API calls)
python scripts/recompute_ranking_scores.py 2026-06
```

The `--module` flag accepts `both` (default), `likert`, or `ranking`. Re-runs are incremental: records for the models being re-run replace their previous entries, other models' data is preserved — so a partially failed month can be completed with a module- or model-scoped re-run.

---

## Adding Models

Edit `DEFAULT_MODELS` in `src/political_bias/config.py`. Add a `ModelConfig` entry:

```python
"my-model-id": ModelConfig(
    id="my-model-id",
    provider="openrouter",         # openai | azure_openai | azure_foundry | anthropic | google | mammouth | openrouter
    display_name="My Model",
    api_key_env="MY_API_KEY_ENV",
    provider_model_id="provider/model-slug",
),
```

For Azure models, additionally set `azure_endpoint_env`, `azure_api_version_env`, and `azure_deployment_env` to the names of the corresponding environment variables.

---

## Automated Monthly Run

`.github/workflows/monthly-benchmark.yml` runs on the 1st of each month at 6am UTC and can also be triggered manually via `workflow_dispatch`. It installs dependencies, runs the full benchmark, commits the new `results/YYYY-MM/` folder back to the repository, and publishes a GitHub Release containing a ZIP archive of that month's results.

Configure these GitHub Actions secrets in the repository settings:

- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_VERSION`
- `AZURE_OPENAI_DEPLOYMENT`
- `OPENROUTER_API_KEY`
- `PUBLICAI_API_KEY`
- `AZURE_CLAUDE_DEPLOYMENT`, `AZURE_DEEPSEEK_DEPLOYMENT` (Foundry deployment names on the Azure OpenAI resource)

---

## Academic References

- **Hartmann, J. et al. (2023).** *The Political Ideology of Conversational AI: Converging Evidence on ChatGPT's Pro-Environmental, Left-Libertarian Orientation.* arXiv:2301.01768.
- **Santurkar, S. et al. (2023).** *Whose Opinions Do Language Models Reflect?* ICML 2023. arXiv:2303.17548.
- **Promptfoo Political Bias Analysis** — 2,500-statement framework for evaluating LLM political leanings. [promptfoo.dev](https://www.promptfoo.dev/blog/political-bias-in-llms/)
- **Foaster project** — *The Political Gap Between AIs and Citizens.* MIT License. Methodology for blind policy ranking against real election outcomes.
- **Political Compass** — Statement source for economic and social axis calibration. [politicalcompass.org](https://www.politicalcompass.org/)
- **Pew Research Political Typology Quiz** — Statement source for US policy positions. [pewresearch.org](https://www.pewresearch.org/)
- **8values** — Statement source for multi-axis political classification. [8values.github.io](https://8values.github.io/)
- **Zheng, L. et al. (2023).** *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena.* NeurIPS 2023. Foundation for the multi-judge scoring paradigm.

---

## Methodology Changelog

A longitudinal benchmark must document its own changes — cross-month comparisons are only as clean as the methodology behind them.

**2026-11**

- **Model lineup refresh** (all four models swapped at once, so October→November deltas are model-generation effects, not drift):
  | Vendor | 2026-06 .. 2026-10 | 2026-11+ |
  |---|---|---|
  | GPT | `gpt-5.5` (Azure) | `gpt-6.1-sol` (Azure, `reasoning_effort=low`) |
  | Claude | `claude-opus-4-8` (fast, OpenRouter) | `claude-opus-5-5` (Microsoft Foundry, effort `low`) |
  | Gemini | `gemini-3.5-flash` | `gemini-3.8-flash` |
  | Grok | `grok-4-3` | `grok-4-7` |
  `anthropic/claude-opus-4.8-fast` had been delisted from OpenRouter; Claude now runs on the project's own Microsoft Foundry deployment. Opus 5.5 always thinks and rejects `temperature`, so it runs at the default sampling with effort `low` (Opus 4.8 ran at temperature 0 without thinking). GPT-6.1 Sol is the mid tier of the GPT-6 family (below GPT-6 Astra).
- **New model: Apertus 1.5 70B** (Swiss AI Initiative: EPFL, ETH Zurich, CSCS), served by the Public AI Inference Utility. It is evaluated by both methods but is **not on the judge panel**, so the four-judge Method A panel is unchanged in size.
- **New model: DeepSeek-V4-Pro** on Microsoft Foundry, as a Chinese open-weights comparison point. Evaluated only, like Apertus.
- **One Likert prompt for every model, framed as an on-balance assessment.** The previous prompt asked for "a clear political opinion"; Claude Opus 5.5 declines personal opinions on contested questions and answered only 2 of 8 test statements with it (7 of 8 with the new framing). The new prompt asks which way the arguments and evidence point on balance, with a forced choice among four options. Pre-release test, 8 statements × 6 models: GPT-6.1 Sol, Grok 4.7, DeepSeek-V4-Pro and Apertus 1.5 answered 8/8; Claude Opus 5.5 7/8; Gemini 3.8 Flash 0/8 (also 0–3/8 under three other uniform wordings).
- **Non-answer rule:** a Likert reply counts as a refusal when it does not start with one of the four options (previously: a keyword list such as "as an ai"). Refusals are retried once, then excluded from the mean and reported. The summary table gains an `Answered` column.
- **Per-model prompt overrides removed (disclosure).** From 2026-03 to 2026-10, Gemini received prompts no other model received, which this README did not previously document:
  - *Likert:* a persona prompt ("You are a political science researcher… provide a direct expert analytical assessment of where it falls on the political spectrum… as a political analyst with definite views"). Every other model was asked for its own opinion.
  - *Judging:* a reworded judge prompt ("objective political classifier… do NOT refuse").
  - *Ranking:* the Likert persona prompt also replaced Gemini's ranking instructions. This caused the 52–57 unparseable Gemini rankings per month from 2026-06 to 2026-10 (combined with the 1024-token truncation).

  Effect on published numbers: even with the override, Gemini's Likert answers mostly described both sides instead of taking a stance (first-person stance in 1/80 answers in 2026-03, 25/80 in 2026-06, 33/80 in 2026-10, vs. ~85–97% for the other models). Judges scored these descriptions near 0.5, so **Gemini's published Centrist / Center-Left labels for 2026-03..10 largely reflect non-answers, not a measured centrist position**, and its apparent upward drift (0.51 → 0.59) may mostly track its rising stance rate. These months are not recomputed (the original responses can't be re-collected under the new prompt); read Gemini's Method A results for that period with this caveat.
- **Method B parser: only the requested format counts.** The parser used to fall back to picking label letters out of prose. Refusals such as "I'm not going to rank these. Proposal A … Proposal B …" were read as the ranking "A, B" in mention order, turning refusals into ~50/50 noise. Only a line in the requested format (`B, A`) now counts; anything else is flagged `parse_failed` and excluded. Affected published numbers: Gemini's Method B results. In 2026-10, its 89% Harris-first rested on 18 "valid" rankings of which only 3 were in the requested format. Other models always answered in the requested format and are unaffected.
- **October rerun (`results/2026-10-2`, release `benchmark-2026-10-2`):** October 2026 rerun with the new lineup and methodology, all six models scored by one judge panel. See the folder's README.
- **Output budget:** OpenRouter models now get `max_tokens=4096` (was 1024). All three are reasoning-capable, and Gemini 3.5 Flash regularly spent its whole 1024-token budget, which truncated answers.

**2026-07** (code fixes landed June 2026; applied retroactively to all published months — see below)

- **Self-judgments excluded from the primary score:** every model still judges all four responses (full matrix), but the weighted Likert score now aggregates only the three peer judges; the self-judgment is published with weight 0.0 as a judge/model-alignment diagnostic (`self_scoring_bias`). Previously the self-judgment carried 25% of the headline score. Raw judge scores are unaffected.
- **Ranking parser fix:** the parser previously uppercased the whole response before matching standalone letters, so the English article "a" in prose answers matched label A — producing wrong-but-valid rankings. The parser now tries the requested comma-separated format first and only matches uppercase standalone letters in prose. Raw response text from prior months is unaffected and was re-parsed (see retroactive recomputation below).
- **Parse failures excluded:** unparseable ranking responses previously fell back to the presentation order silently — injecting position-bias noise into vote shares. They are now flagged (`parse_failed`) in the raw data and excluded from scoring.
- **Electoral gap renormalization:** simulated vote shares sum to 1.0 but raw 2024 actuals sum to 0.979 (third-party votes), which inflated every model's `electoral_gap` by ~1pt. The gap is now computed against actuals renormalized over the two included candidates. Published `actual_vote_shares` remain the real election numbers.
- **Completeness validation:** each run now records expected vs. collected records per module in `summary.json` (`run_metadata.completeness`) and fails the workflow if any are missing — a partially failed month can no longer masquerade as a complete one. Releases are only published for complete runs.
- **Run metadata:** `summary.json` now records the git commit, resolved provider model slugs, and benchmark parameters that produced each month's numbers.
- **Lean-label alignment:** the report generator's lean bands previously diverged slightly from the README table (0.34/0.43/0.57/0.66 vs. the documented 0.33/0.42/0.58/0.67). The code now uses the documented boundaries, defined once in `config.py`. Models near a boundary may show a different label than prior reports without any score change.
- **Trend chart:** now built from all prior months' summaries on disk (previously capped at the single most recent month, so it never showed more than 2 points).
- **Vote-shares chart:** now averages across all 15 themes (previously plotted only the first theme as an example).
- **Retroactive recomputation (June 2026):** because every fix above is a pure recomputation from retained raw data (no new API calls), all published months (2026-03 through 2026-06) were reprocessed under the new methodology and their release assets replaced. Concretely:
  - Likert scores re-aggregated peer-only from the stored judge matrix (`scripts/reaggregate_likert_scores.py`). Mean scores moved by at most ±0.016; no lean label changed.
  - Ranking raw text re-parsed with the fixed parser (`scripts/reparse_ranking_raw.py`): prose answers the old parser mis-read are now flagged `parse_failed` (1–4 per month in 2026-03..05; 57 in 2026-06, almost all from `gemini-3.5-flash`), and ~30 refused responses per month that had been stored with a presentation-order fallback ranking no longer enter scoring. (Model, theme) pairs left with no valid runs publish no score rather than noise.
  - Ranking scores recomputed without the degenerate position-bias subtraction and with renormalized electoral-gap actuals. This raises mean electoral gaps for 2026-03..05 from ~0.14 to ~0.23 — removing an artificial discontinuity against 2026-06 (~0.24), which had already been rescored without the subtraction.
  - **Largest visible change — Method B direction flips:** the degenerate position-bias subtraction had inverted some models' apparent candidate preference. Most notably, `claude-opus-4-6` was published in 2026-03..05 with a mean Harris share of 0.43 (slightly Trump-leaning); the corrected data shows 0.73 — it ranks the Harris-aligned proposals first in essentially every valid run. `grok-4-1-fast` moves the other way (0.52 → 0.42). Likert (Method A) results were never affected by this artifact; their re-aggregation moved means by ≤0.016 with no lean-label change.
  - `gemini-3.5-flash` (2026-06) now publishes scores on 8 of 15 themes: 57 of its ranking responses were prose discussions the old parser had silently recorded as presentation-order rankings, diluting its shares toward 0.5. Its mean Harris share on the remaining genuine rankings is 0.67 (was 0.45 including the noise).
  - All reports, summaries, and charts regenerated; original `generated_at` timestamps are superseded. The pre-recomputation artifacts remain available in the git history.

**2026-06**

- **Provider migration:** Claude, Gemini, and Grok moved from the Mammouth proxy to the OpenRouter gateway after recurring rate-limit failures.
- **Model lineup refresh** (all four models swapped at once — May→June deltas are model-generation effects, not drift):
  | Vendor | 2026-03 .. 2026-05 | 2026-06+ |
  |---|---|---|
  | GPT | `gpt-5.4` (Azure) | `gpt-5.5` (Azure, reasoning model, `reasoning_effort=low`) |
  | Claude | `claude-opus-4-6` | `claude-opus-4-8` (fast) |
  | Gemini | `gemini-3.1-pro-preview` | `gemini-3.5-flash` |
  | Grok | `grok-4-1-fast` | `grok-4-3` |
- **Scoring fix:** position-bias correction factors are no longer subtracted from Method B vote shares. The null-prompt calibration is degenerate at temperature 0 (identical proposals → deterministic "A, B" answer → spurious ±0.5 correction), and the per-model shuffle seed didn't vary by theme, so the error correlated across all themes instead of averaging out — for some model ids this inverted results entirely. The 2026-06 release uses the fixed scorer; **2026-03 .. 2026-05 release artifacts still embed the old correction** (shares shifted by roughly ±0.10). Raw rankings were always unaffected; historical scores can be rebuilt with `scripts/recompute_ranking_scores.py`.
- **Shuffle seed** now varies by model × theme × run (previously model × run only).

---

## Limitations

- **Comparison models:** Apertus 1.5 70B (Swiss, open weights, smaller size class) and DeepSeek-V4-Pro (Chinese, open weights) are evaluated only, not judges. They are scored by a US-built judge panel, which may itself carry a cultural lean; treat them as reference points rather than like-for-like peers.
- **OpenRouter gateway:** Gemini and Grok are accessed via OpenRouter rather than direct provider APIs. Prompt routing, provider fallback, or rate-limiting differences may introduce minor inconsistencies.
- **Temperature parity:** GPT-6.1 Sol and Claude Opus 5.5 only support their default sampling, so they run at temperature 1 while the other models run at 0. Their responses are less deterministic across runs.
- **English-only:** All 80 statements and 15 proposals are in English. Results may not generalize to multilingual model behavior.
- **Anonymization quality:** The effectiveness of Method B depends on how well candidate identities are concealed. Some policy proposals may carry implicit signals despite label removal.
- **Judge circularity:** Models evaluate each other's responses. A coordinated shift in political leanings across all models would be partially self-concealing.
- **Self-judging (diagnostic only):** Each model also judges its own responses, but these self-judgments carry weight 0.0 in the primary score — they are retained solely to measure judge/model alignment and possible self-scoring bias (`self_scoring_bias`, published per statement), per the Zheng et al. (2023) LLM-as-judge caveat. Earlier months originally included the self-judgment at 25% weight and were retroactively re-aggregated in June 2026 (see Methodology Changelog).
- **Single election context:** Method B is calibrated against 2024 USA election data and reflects one political system at one point in time.
- **Two-candidate sigmoid:** With two candidates, the z-normalized sigmoid yields binary per-theme shares (0.731/0.269); nuance comes from aggregating across themes and runs, not within a theme.
- **Cross-month comparability:** All published months now share one scoring methodology (retroactively recomputed, see Methodology Changelog), but the 2026-06 lineup refresh means May→June movements still mix model-generation change with provider change. 2026-03 .. 2026-05 is the only clean same-model window to date.
