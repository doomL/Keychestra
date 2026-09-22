"""CLI entry point: python -m organ_bg"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from organ_bg import __version__
from organ_bg.daemon import OrganDaemon, configure_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="organ-bg",
        description="Background organ: keyboard keeps typing, keys also sound.",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=None,
        help="Path to config.yaml",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Debug logging",
    )
    parser.add_argument(
        "--daemonize",
        action="store_true",
        help="Fork to background (simple double-fork)",
    )
    parser.add_argument(
        "--pidfile",
        type=Path,
        default=Path.home() / ".cache" / "organ-bg" / "organ-bg.pid",
        help="PID file when --daemonize",
    )
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    if args.daemonize:
        _daemonize(args.pidfile)

    configure_logging(args.verbose)
    return OrganDaemon(args.config).run()


def _daemonize(pidfile: Path) -> None:
    """Minimal double-fork daemonize for Linux."""
    if os.fork() > 0:
        raise SystemExit(0)
    os.setsid()
    if os.fork() > 0:
        raise SystemExit(0)

    sys.stdout.flush()
    sys.stderr.flush()
    with open("/dev/null", "rb", 0) as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())
    # Keep stderr for journald / nohup redirection; reopen stdout to null
    with open("/dev/null", "ab", 0) as devnull:
        os.dup2(devnull.fileno(), sys.stdout.fileno())

    pidfile.parent.mkdir(parents=True, exist_ok=True)
    pidfile.write_text(str(os.getpid()), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
