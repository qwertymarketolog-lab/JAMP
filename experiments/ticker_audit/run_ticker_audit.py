"""Run the R18-R22 evidence pipeline once for each ticker-audit claim."""

from __future__ import annotations

import json
import sys
from typing import Any

from experiments.r18_r22_e2e.run_pipeline import run_pipeline

TICKER_CLAIMS = {
    "SMLT": "SMLT акции упали на 95% от максимума.",
    "ALRS": "ALRS достигла 153 рублей в 2021 году.",
    "AFKS": "AFKS выросла из-за дивидендов.",
}


def main() -> int:
    results: dict[str, dict[str, Any]] = {}
    for ticker, claim_text in TICKER_CLAIMS.items():
        results[ticker] = {
            "input_claim": claim_text,
            "pipeline_report": run_pipeline(claim_text),
        }

    sys.stdout.write(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
