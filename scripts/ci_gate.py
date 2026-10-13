"""Fail closed for failed, cancelled, skipped, absent or malformed required job results."""

import json
import os
import sys


def passes(results: object, required: list[str]) -> bool:
    return (
        bool(required)
        and isinstance(results, dict)
        and set(results) == set(required)
        and all(
            isinstance(results[job], dict) and results[job].get("result") == "success"
            for job in required
        )
    )


def main() -> int:
    try:
        results = json.loads(os.environ.get("CI_NEEDS", ""))
    except (TypeError, ValueError):
        results = None
    accepted = passes(results, sys.argv[1:])
    print("All required jobs passed." if accepted else "Required CI jobs did not all succeed.")
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
