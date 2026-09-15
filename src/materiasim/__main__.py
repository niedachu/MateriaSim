"""Expose the package command-line interface without import-time execution."""

from materiasim.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
