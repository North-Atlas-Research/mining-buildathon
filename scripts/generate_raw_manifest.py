"""Generate the immutable Raw data file manifest."""
from __future__ import annotations

import argparse
from pathlib import Path

from mining_sprint.paths import raw_dir
from mining_sprint.raw_manifest import RawManifestError, generate_manifest

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "metadata" / "raw_manifest.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=raw_dir(), help="Raw data directory")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output CSV path")
    args = parser.parse_args()
    try:
        output = generate_manifest(args.raw_dir, args.output)
    except RawManifestError as error:
        raise SystemExit(f"Raw manifest generation failed: {error}") from error
    print(f"Wrote raw manifest: {output}")


if __name__ == "__main__":
    main()
