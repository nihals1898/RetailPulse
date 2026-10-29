"""Minimal CLI entry point for startup verification."""

import argparse

from retailpulse import __version__


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="retailpulse",
        description="RetailPulse data platform project.",
    )
    parser.add_argument("--version", action="version", version=f"RetailPulse {__version__}")
    parser.parse_args()


if __name__ == "__main__":
    main()
