# Contributing to llm-political-bias-bench

Thank you for your interest in contributing! This document explains how to get involved.

## Code of Conduct

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before participating.

## How to Contribute

### Reporting Bugs

Open a [bug report](.github/ISSUE_TEMPLATE/bug_report.yml) and include:
- A clear description of the issue
- Steps to reproduce
- Expected vs. actual behavior
- Your environment details

### Suggesting Features

Open a [feature request](.github/ISSUE_TEMPLATE/feature_request.yml) describing the problem you want to solve and your proposed solution.

### Submitting Pull Requests

1. Fork the repository
2. Create a branch: `git checkout -b feat/your-feature` or `fix/your-bug`
3. Make your changes and add tests if applicable
4. Commit following [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` new feature
   - `fix:` bug fix
   - `docs:` documentation only
   - `chore:` maintenance/tooling
   - `refactor:` code restructuring without behavior change
5. Push and open a pull request against `main`
6. Fill in the pull request template

### Branch Naming

- Features: `feat/short-description`
- Bug fixes: `fix/short-description`
- Documentation: `docs/short-description`

## Development Setup

```bash
git clone https://github.com/swissprismia/llm-political-bias-bench.git
cd llm-political-bias-bench
pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and fill in your API keys before running tests.

Run the test suite:

```bash
pytest
```

## Versioning

This project follows [Semantic Versioning](https://semver.org/) (MAJOR.MINOR.PATCH).
