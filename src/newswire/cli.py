"""Command-line entry point: ``newswire`` or ``python -m newswire``."""

from __future__ import annotations

import argparse
import os
from typing import NoReturn, Sequence

from dotenv import load_dotenv

from newswire.config import ConfigError, load_config
from newswire.core import run
from newswire.state.base import StateError


def main(argv: Sequence[str] | None = None) -> NoReturn:
    load_dotenv()

    parser = argparse.ArgumentParser(
        prog="newswire",
        description="Config-driven source -> digest -> channel news notifier.",
    )
    parser.add_argument(
        "--config",
        default=os.getenv("NOTIFIER_CONFIG", "config.yml"),
        help="config file or directory (default: config.yml, or $NOTIFIER_CONFIG)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="fetch and render, but send nothing and write no state",
    )
    parser.add_argument(
        "--source",
        action="append",
        metavar="ID",
        help="check only this source id (repeatable); skips 'no news' messages",
    )
    parser.add_argument(
        "--no-state-write",
        action="store_true",
        help="send for real but leave state untouched (works for any backend, "
        "gist included) - the next run treats the same items as new again",
    )
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        code = run(
            config,
            dry_run=args.dry_run,
            only=args.source,
            write_state=not args.no_state_write,
        )
    except (ConfigError, StateError) as exc:
        raise SystemExit(f"Error: {exc}") from exc
    raise SystemExit(code)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
