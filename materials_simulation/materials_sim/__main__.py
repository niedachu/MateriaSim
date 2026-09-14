"""Expose the package command-line interface without import-time execution."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
