# 2026-10-2: October rerun with the 2026-11 setup

This is **not** a regular monthly run. It reruns October 2026 with the new lineup and methodology, so the change can be read before the scheduled 2026-11 run. The published `2026-10` release is unchanged.

- **Models (6):** gpt-6.1-sol (Azure), claude-opus-5-5 (Microsoft Foundry), gemini-3.8-flash, grok-4-7 (OpenRouter), deepseek-v4-pro (Microsoft Foundry, evaluated only), apertus-1.5-70b (Public AI, evaluated only).
- **Judges:** gpt-6.1-sol, claude-opus-5-5, gemini-3.8-flash, grok-4-7 — one panel for all six models.
- **Method:** one Likert prompt for every model (on-balance forced choice); a reply that doesn't start with one of the four options is a refusal; rankings count only in the requested `B, A` format. See the README Methodology Changelog (2026-11).
- **Collection:** 2026-10-05, two runs from the same commit (`181aea4`) with the same judge panel: (1) the four frontier models, (2) DeepSeek and Apertus. Rankings were re-parsed offline with the strict parser (`scripts/reparse_ranking_raw.py`).

| Model | Method A mean | Answered | Method B: Harris first (valid rankings) |
|---|---|---|---|
| gpt-6.1-sol | 0.68 Left | 80/80 | 100% (75/75) |
| apertus-1.5-70b | 0.72 Left | 80/80 | 100% (75/75) |
| deepseek-v4-pro | 0.68 Left | 80/80 | 83% (75/75) |
| grok-4-7 | 0.64 Center-Left | 80/80 | 96% (75/75) |
| claude-opus-5-5 | 0.62 Center-Left | 69/80 | declined 74/75 |
| gemini-3.8-flash | 0.63 (12 answers only) | 12/80 | declined 74/75 |

`overview.png` summarises both methods.
