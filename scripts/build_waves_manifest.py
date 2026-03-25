#!/usr/bin/env python3
"""Build/update wave manifest from existing wave folders."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, List


WAVE_GLOB_DEFAULT = "data/pew_datasets/W*"
OUTPUT_DEFAULT = "data/reference/pew/waves_manifest.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scan wave folders and write waves_manifest.csv with one row per folder."
        )
    )
    parser.add_argument(
        "--wave-glob",
        default=WAVE_GLOB_DEFAULT,
        help=f"Glob for wave folders (default: {WAVE_GLOB_DEFAULT})",
    )
    parser.add_argument(
        "--output",
        default=OUTPUT_DEFAULT,
        help=f"Output CSV path (default: {OUTPUT_DEFAULT})",
    )
    parser.add_argument(
        "--overwrite",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Overwrite existing output (default: enabled)",
    )
    parser.add_argument(
        "--enabled",
        default="yes",
        choices=["yes", "no"],
        help="Default value for enabled column (default: yes)",
    )
    return parser.parse_args()


def infer_wave_id(folder_name: str) -> str:
    m = re.match(r"(W\d+(?:\.\d+)?)", folder_name, flags=re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return folder_name


def count_matches(path: Path, pattern: str) -> int:
    return len(list(path.glob(pattern)))


def build_rows(wave_glob: str, enabled: str) -> List[Dict[str, str]]:
    folders = [p for p in sorted(Path(".").glob(wave_glob)) if p.is_dir()]
    rows: List[Dict[str, str]] = []

    for folder in folders:
        row = {
            "wave_id": infer_wave_id(folder.name),
            "wave_folder": str(folder),
            "enabled": enabled,
            "readme_count": str(count_matches(folder, "*readme*.txt")),
            "sav_count": str(count_matches(folder, "*.sav")),
            "pdf_count": str(count_matches(folder, "*.pdf")),
            "notes": "",
        }
        rows.append(row)
    return rows


def main() -> None:
    args = parse_args()
    out_path = Path(args.output)

    if out_path.exists() and not args.overwrite:
        raise FileExistsError(
            f"Output already exists: {out_path}. Use --overwrite to replace it."
        )

    rows = build_rows(args.wave_glob, args.enabled)
    if not rows:
        raise FileNotFoundError(f"No wave folders matched glob: {args.wave_glob}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "wave_id",
        "wave_folder",
        "enabled",
        "readme_count",
        "sav_count",
        "pdf_count",
        "notes",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wave folders scanned: {len(rows)}")
    print(f"Output: {out_path}")


if __name__ == "__main__":
    main()
