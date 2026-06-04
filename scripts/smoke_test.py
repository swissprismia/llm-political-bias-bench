"""Smoke test: one real API call per configured model.

Usage:
    python scripts/smoke_test.py            # all DEFAULT_MODELS
    python scripts/smoke_test.py grok-4-3   # only the listed model ids
"""

from __future__ import annotations

import asyncio
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from political_bias.config import DEFAULT_MODELS  # noqa: E402
from political_bias.models import query  # noqa: E402

SYSTEM = "You are a helpful assistant."
USER = "Reply with the single word: pong"


async def smoke(model_ids: list[str]) -> bool:
    ok = True
    for model_id in model_ids:
        cfg = DEFAULT_MODELS[model_id]
        if not cfg.api_key:
            print(f"  SKIP {model_id:<28} ({cfg.api_key_env} not set)")
            ok = False
            continue
        start = time.perf_counter()
        try:
            resp = await query(cfg, SYSTEM, USER, max_retries=1)
            elapsed = time.perf_counter() - start
            text = resp.text.strip().replace("\n", " ")[:60]
            print(f"  OK   {model_id:<28} {elapsed:5.1f}s  {text!r}")
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - start
            print(f"  FAIL {model_id:<28} {elapsed:5.1f}s  {type(exc).__name__}: {exc}")
            ok = False
    return ok


def main() -> None:
    requested = sys.argv[1:] or list(DEFAULT_MODELS)
    unknown = [m for m in requested if m not in DEFAULT_MODELS]
    if unknown:
        sys.exit(f"Unknown model id(s): {', '.join(unknown)} — choose from {', '.join(DEFAULT_MODELS)}")
    print(f"Smoke testing {len(requested)} model(s): one call each\n")
    ok = asyncio.run(smoke(requested))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
