#!/usr/bin/env python3
"""Merge wave-level PEW inventory partial CSVs into one master inventory CSV."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, List, Tuple


INPUT_GLOB_DEFAULT = "data/pew_datasets/W*/pew_question_inventory_partial.csv"
OUTPUT_DEFAULT = "data/interim/pew/pew_question_inventory.csv"
RQ4_MINIMAL_HEADER = [
    "inventory_id",
    "pew_wave",
    "field_dates",
    "dataset_file",
    "variable_name",
    "question_text_raw",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Merge all per-wave pew_question_inventory_partial.csv files into one "
            "master CSV."
        )
    )
    parser.add_argument(
        "--input-glob",
        default=INPUT_GLOB_DEFAULT,
        help=f"Glob for partial inventory files (default: {INPUT_GLOB_DEFAULT})",
    )
    parser.add_argument(
        "--output",
        default=OUTPUT_DEFAULT,
        help=f"Output CSV path (default: {OUTPUT_DEFAULT})",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting output file if it already exists",
    )
    return parser.parse_args()


def list_input_files(input_glob: str) -> List[Path]:
    files = [Path(p) for p in sorted(Path(".").glob(input_glob))]
    return [path for path in files if path.is_file()]


def normalize_row_to_header(row: Dict[str, str], header: List[str]) -> Dict[str, str]:
    return {col: row.get(col, "") for col in header}


def parse_wave_sort_key(pew_wave: str) -> Tuple[int, str]:
    m = re.search(r"ATP_(\d+(?:\.\d+)?)", (pew_wave or "").strip())
    if not m:
        return (10**9, pew_wave or "")
    wave_num = m.group(1)
    # Use scaled integer so decimal waves preserve ordering.
    if "." in wave_num:
        major, minor = wave_num.split(".", 1)
        return (int(major) * 1000 + int(minor), pew_wave)
    return (int(wave_num) * 1000, pew_wave)


def row_sort_key(row: Dict[str, str]) -> Tuple[int, str, str]:
    wave_key, wave_label = parse_wave_sort_key(row.get("pew_wave", ""))
    return (wave_key, wave_label, row.get("variable_name", ""))


def row_dedupe_key(row: Dict[str, str]) -> Tuple[str, str]:
    return (
        row.get("pew_wave", "").strip(),
        row.get("variable_name", "").strip(),
    )


def read_partial_rows(path: Path, header: List[str]) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return []
        rows = []
        for row in reader:
            if not any((value or "").strip() for value in row.values()):
                continue
            rows.append(normalize_row_to_header(row, header))
        return rows


def main() -> None:
    args = parse_args()
    output_path = Path(args.output)

    if output_path.exists() and not args.overwrite:
        raise FileExistsError(
            f"Output already exists: {output_path}. Use --overwrite to replace it."
        )

    input_files = list_input_files(args.input_glob)
    if not input_files:
        raise FileNotFoundError(f"No partial inventory files matched: {args.input_glob}")

    header = list(RQ4_MINIMAL_HEADER)
    all_rows: List[Dict[str, str]] = []
    rows_read_total = 0

    for file_path in input_files:
        rows = read_partial_rows(file_path, header)
        rows_read_total += len(rows)
        all_rows.extend(rows)

    deduped: List[Dict[str, str]] = []
    seen: set[Tuple[str, str]] = set()
    duplicate_count = 0

    for row in sorted(all_rows, key=row_sort_key):
        key = row_dedupe_key(row)
        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)
        deduped.append(row)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(deduped)

    print(f"Input files: {len(input_files)}")
    print("Schema: rq4_minimal")
    print(f"Rows read: {rows_read_total}")
    print(f"Duplicate rows dropped (pew_wave + variable_name): {duplicate_count}")
    print(f"Rows written: {len(deduped)}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
