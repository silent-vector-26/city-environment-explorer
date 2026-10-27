"""Run the groundedness evaluation against the configured Azure OpenAI deployment.

Usage (from the repository root, with AZURE_OPENAI_* set in .env or the shell):

    python -m evals.run_eval [--repeats 2] [--output evals/results.json]

Exits with status 1 if any run fails a check.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from cee.ai import generate_grounded_summary
from cee.evaluation import check_groundedness
from evals.cases import CASES


def run(repeats: int) -> list[dict]:
    results: list[dict] = []
    for case in CASES:
        for attempt in range(1, repeats + 1):
            try:
                summary = generate_grounded_summary(case["evidence"])
                failures = check_groundedness(
                    summary,
                    case["evidence"],
                    required_phrases=case["required"],
                    forbidden_phrases=case["forbidden"],
                )
            except Exception as error:  # a rejected citation is an eval failure
                summary = ""
                failures = [f"generation error: {error}"]
            results.append(
                {
                    "case": case["name"],
                    "attempt": attempt,
                    "passed": not failures,
                    "failures": failures,
                    "summary": summary,
                }
            )
            status = "PASS" if not failures else "FAIL"
            print(f"{status} {case['name']} #{attempt}")
            for failure in failures:
                print(f"     - {failure}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path("evals/results.json"))
    args = parser.parse_args()

    load_dotenv()
    results = run(args.repeats)
    args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")

    passed = sum(1 for r in results if r["passed"])
    print(f"\n{passed}/{len(results)} runs passed. Details: {args.output}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
