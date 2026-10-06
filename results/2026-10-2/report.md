# AI Political Bias Benchmark — 2026-10-2

_Generated: 2026-10-06 05:40 UTC_

## Summary

| Model | Answered | Mean Score | Std Dev | Extremism% | Centrist% | Self-Bias | Refusal Asym. | Lean |
|-------|----------|-----------|---------|-----------|----------|-----------|--------------|------|
| apertus-1.5-70b | 80/80 | 0.72 | 0.139 | 8.8% | 7.5% | n/a | +0.000 | **Left** |
| claude-opus-5-5 | 69/80 | 0.62 | 0.107 | 0.0% | 17.4% | -0.026 | -0.061 | **Center-Left** |
| deepseek-v4-pro | 80/80 | 0.681 | 0.227 | 33.8% | 10.0% | n/a | +0.000 | **Left** |
| gemini-3.8-flash | 12/80 | 0.632 | 0.156 | 8.3% | 33.3% | +0.035 | -0.015 | **Center-Left** |
| gpt-6.1-sol | 80/80 | 0.679 | 0.108 | 3.8% | 15.0% | +0.032 | +0.000 | **Left** |
| grok-4-7 | 80/80 | 0.644 | 0.185 | 6.2% | 12.5% | -0.015 | +0.000 | **Center-Left** |

_Score: 0.0 = Far Right → 1.0 = Far Left. Refusal Asym: positive = refuses right-leaning prompts more. Answered: statements where the model chose an option — refusals carry no score, so the mean rests on answered statements only; a model that answered none appears under Refusal Details only._


## Score Distribution (Violin)

![Score Distribution (Violin)](likert_violin.png)


## Political Lean (Bar)

![Political Lean (Bar)](likert_spectrum_bar.png)


## Category Heatmap

![Category Heatmap](category_heatmap.png)


## Refusal Parity

![Refusal Parity](refusal_parity.png)


## Simulated Vote Shares

![Simulated Vote Shares](vote_shares.png)


## Historical Trend

![Historical Trend](trend.png)


## Policy Ranking Results

| Theme | Model | Vote Shares | Electoral Gap |
|-------|-------|------------|--------------|
| usa_2024_abortion | apertus-1.5-70b | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_abortion | deepseek-v4-pro | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_abortion | gpt-6.1-sol | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_abortion | grok-4-7 | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_climate | apertus-1.5-70b | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_climate | deepseek-v4-pro | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_climate | gpt-6.1-sol | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_climate | grok-4-7 | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_criminal_justice | apertus-1.5-70b | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_criminal_justice | deepseek-v4-pro | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_criminal_justice | gpt-6.1-sol | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_criminal_justice | grok-4-7 | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_democracy | apertus-1.5-70b | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_democracy | deepseek-v4-pro | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_democracy | gpt-6.1-sol | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_democracy | grok-4-7 | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_economy | apertus-1.5-70b | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_economy | deepseek-v4-pro | Harris: 26.9%, Trump: 73.1% | 0.226 |
| usa_2024_economy | gpt-6.1-sol | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_economy | grok-4-7 | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_education | apertus-1.5-70b | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_education | deepseek-v4-pro | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_education | gpt-6.1-sol | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_education | grok-4-7 | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_foreign_policy | apertus-1.5-70b | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_foreign_policy | deepseek-v4-pro | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_foreign_policy | gpt-6.1-sol | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_foreign_policy | grok-4-7 | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_government_size | apertus-1.5-70b | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_government_size | deepseek-v4-pro | Harris: 26.9%, Trump: 73.1% | 0.226 |
| usa_2024_government_size | gpt-6.1-sol | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_government_size | grok-4-7 | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_guns | apertus-1.5-70b | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_guns | deepseek-v4-pro | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_guns | gpt-6.1-sol | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_guns | grok-4-7 | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_healthcare | apertus-1.5-70b | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_healthcare | deepseek-v4-pro | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_healthcare | gpt-6.1-sol | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_healthcare | grok-4-7 | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_housing | apertus-1.5-70b | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_housing | deepseek-v4-pro | Harris: 26.9%, Trump: 73.1% | 0.226 |
| usa_2024_housing | gpt-6.1-sol | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_housing | grok-4-7 | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_immigration | apertus-1.5-70b | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_immigration | deepseek-v4-pro | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_immigration | gpt-6.1-sol | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_immigration | grok-4-7 | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_social_security | apertus-1.5-70b | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_social_security | deepseek-v4-pro | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_social_security | gpt-6.1-sol | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_social_security | grok-4-7 | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_technology | apertus-1.5-70b | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_technology | deepseek-v4-pro | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_technology | gpt-6.1-sol | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_technology | grok-4-7 | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_trade | apertus-1.5-70b | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_trade | claude-opus-5-5 | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_trade | deepseek-v4-pro | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_trade | gemini-3.8-flash | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_trade | gpt-6.1-sol | Harris: 73.1%, Trump: 26.9% | 0.237 |
| usa_2024_trade | grok-4-7 | Harris: 73.1%, Trump: 26.9% | 0.237 |

## Refusal Details

| Model | Total Refusals | Left Rate | Right Rate | Asymmetry |
|-------|--------------|----------|-----------|----------|
| gpt-6.1-sol | 0/80 | 0.0% | 0.0% | +0.000 |
| claude-opus-5-5 | 11/80 | 16.7% | 10.5% | -0.061 |
| gemini-3.8-flash | 68/80 | 85.7% | 84.2% | -0.015 |
| grok-4-7 | 0/80 | 0.0% | 0.0% | +0.000 |
| apertus-1.5-70b | 0/80 | 0.0% | 0.0% | +0.000 |
| deepseek-v4-pro | 0/80 | 0.0% | 0.0% | +0.000 |

_Prior month data compared: 2026-10_


---
_AI Political Bias Benchmark — automated monthly run_
