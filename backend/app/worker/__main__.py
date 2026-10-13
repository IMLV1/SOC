import argparse
import json


def main() -> int:
    parser = argparse.ArgumentParser(description="SOC worker scaffold (no job handlers yet)")
    parser.add_argument(
        "--check", action="store_true", help="Check entrypoint without claiming jobs"
    )
    args = parser.parse_args()
    print(json.dumps({"component": "worker", "status": "scaffold", "queue_ready": False}))
    # Do not masquerade as a healthy queue worker or run a busy idle loop.
    return 0 if args.check else 2


if __name__ == "__main__":
    raise SystemExit(main())
