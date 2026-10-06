from __future__ import annotations

import argparse
import sys

from .adapter import JampClientAdapter


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="JAMP CLI Client Adapter v0.1")
    subparsers = parser.add_subparsers(dest="command", required=True)

    execute_parser = subparsers.add_parser("execute", help="Execute task request via Runtime API")
    execute_parser.add_argument("prompt", help="User prompt or payload")
    execute_parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000",
        help="Target Runtime API base URL",
    )

    parsed_args = parser.parse_args(args)
    if parsed_args.command == "execute":
        adapter = JampClientAdapter(parsed_args.api_url)
        try:
            result = adapter.execute_payload({"prompt": parsed_args.prompt})
        except RuntimeError as exc:
            print(f"CLIENT_ERROR: {exc}", file=sys.stderr)
            return 1

        print(f"status: {result.status}")
        print(f"trace_id: {result.trace_id}")
        if result.status == "EXECUTE":
            print(f"model: {result.selected_model}")
            print(f"output: {result.output}")
        else:
            print(f"reason: {result.reason}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
