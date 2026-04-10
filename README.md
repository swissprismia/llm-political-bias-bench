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

**Forced stance:** Models are required to take a position. A refusal-detection mechanism identifies non-committal responses and triggers a retry with clarifying instructions.

**Multi-judge scoring:** Every model scores every other model's responses on a 0.0–1.0 scale (0.0 = strongly right-wing, 1.0 = strongly left-wing). Self-scoring bias is tracked separately. IQR-based outlier weighting (1.5× threshold) reduces the influence of rogue judges.

**Refusal parity:** Asymmetry between a model's refusal rate on left-leaning vs. right-leaning statements is a functional indicator of directional bias — independent of the content of non-refused responses.

### Method B — Blind Policy Ranking

Inspired by the [Foaster project](https://github.com/Foaster-ai/The_Political_Gap_Between_AIs_and_Citizens) — *The Political Gap Between AIs and Citizens*.

**Proposals:** 15 anonymized policy themes from the 2024 USA election cycle. Each theme presents two proposals derived from the Harris and Trump platforms, with candidate labels hidden — models see only the policy content.

**Shuffle runs:** Each model ranks proposals 5 times per theme with a randomly shuffled presentation order, mitigating list-position bias.

**Position bias calibration:** A SCOPE-inspired null-prompt method runs 20 trials per model to measure baseline ordering preferences, producing per-position correction factors applied during scoring.

**Vote shares:** Rankings are converted to vote shares via sigmoid transformation and renormalized. Results are compared against the actual 2024 election outcome (Harris 48.4%, Trump 49.5%) to quantify electoral alignment or divergence.

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

---

## Project Structure

```
src/political_bias/
  config.py          # Model registry & benchmark parameters
  models.py          # Unified async LLM client (6 providers)
  likert/            # Statement evaluation + judging + refusal parity
  ranking/           # Proposal ranking + position bias + scoring
  report/            # Chart generation + Markdown report
  runner.py          # CLI orchestrator
data/
  statements/        # 80 political statements (JSON)
  proposals/         # 2024 USA election proposals (JSON)
results/{YYYY-MM}/   # Monthly output (JSON data + PNG charts + report.md)
.github/workflows/
  monthly-benchmark.yml   # Scheduled automation (1st of month, 6am UTC)
```

---

## Monthly Output

Each run produces a `results/YYYY-MM/` directory containing:

- **`report.md`** — full narrative report with embedded charts and score tables
- **`summary.json`** — per-model aggregates: mean score, std dev, extremism%, centrist%, lean label
- **`likert_raw.json`** / **`likert_scores.json`** — raw LLM responses and weighted judge scores
- **`ranking_raw.json`** / **`ranking_scores.json`** — raw rankings and computed vote shares
- **`refusal_parity.json`** — per-model left/right refusal rates
- **`position_bias.json`** — SCOPE calibration correction factors

Charts generated: violin score distribution, political spectrum bar, category heatmap, vote shares comparison, refusal parity, historical trend.

All raw JSON is retained for full reproducibility.

---

## Setup & Installation

```bash
git clone <repo-url>
cd app-political-bias
pip install -e .
```

Create a `.env` file in the project root with your API credentials:

```env
# Azure OpenAI (GPT models)
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_VERSION=...
AZURE_OPENAI_DEPLOYMENT=...

# Mammouth (proxy for Claude, Gemini, Grok)
MAMMOUTH_API_KEY=...
```

---

## Usage

```bash
# Full benchmark (current month)
python -m political_bias run

# Smoke test — 5 statements, no ranking, fast
python -m political_bias run --module likert --limit 5

# Specific models only
python -m political_bias run --models gpt-5.4,claude-opus-4-6

# Specific month
python -m political_bias run --month 2026-03

# Dry-run — validate config without making API calls
python -m political_bias run --dry-run

# Regenerate report from existing result data
python -m political_bias report --month 2026-03
```

The `--module` flag accepts `both` (default), `likert`, or `ranking`.

---

## Adding Models

Edit `DEFAULT_MODELS` in `src/political_bias/config.py`. Add a `ModelConfig` entry:

```python
"my-model-id": ModelConfig(
    id="my-model-id",
    provider="anthropic",          # openai | azure_openai | azure_foundry | anthropic | google | mammouth
    display_name="My Model",
    api_key_env="MY_API_KEY_ENV",
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
- `MAMMOUTH_API_KEY`

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

## Limitations

- **Mammouth proxy:** Claude, Gemini, and Grok are accessed via the Mammouth API rather than direct provider APIs. Prompt routing or rate-limiting differences may introduce minor inconsistencies.
- **English-only:** All 80 statements and 15 proposals are in English. Results may not generalize to multilingual model behavior.
- **Anonymization quality:** The effectiveness of Method B depends on how well candidate identities are concealed. Some policy proposals may carry implicit signals despite label removal.
- **Judge circularity:** Models evaluate each other's responses. A coordinated shift in political leanings across all models would be partially self-concealing.
- **Single election context:** Method B is calibrated against 2024 USA election data and reflects one political system at one point in time.
