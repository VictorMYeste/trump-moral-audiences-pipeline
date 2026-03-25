#!/usr/bin/env python3
"""Validate PEW wave folder readiness before bulk extraction."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List, Tuple


WAVE_GLOB_DEFAULT = "data/pew_datasets/W*"
MANIFEST_DEFAULT = "data/reference/pew/waves_manifest.csv"
OUTPUT_DEFAULT = "reports/wave_preflight_report.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate wave folder inputs (readme/sav presence) and optionally check "
            "against a manifest."
        )
    )
    parser.add_argument(
        "--wave-glob",
        default=WAVE_GLOB_DEFAULT,
        help=f"Glob for wave folders (default: {WAVE_GLOB_DEFAULT})",
    )
    parser.add_argument(
        "--manifest",
        default=MANIFEST_DEFAULT,
        help=(
            "Optional manifest CSV with columns wave_id,wave_folder,enabled,notes "
            f"(default: {MANIFEST_DEFAULT})"
        ),
    )
    parser.add_argument(
        "--output",
        default=OUTPUT_DEFAULT,
        help=f"Output CSV report path (default: {OUTPUT_DEFAULT})",
    )
    parser.add_argument(
        "--strict",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Exit non-zero if any required checks fail (default: enabled)",
    )
    return parser.parse_args()


def normalize_bool(value: str, default: bool = True) -> bool:
    text = (value or "").strip().lower()
    if not text:
        return default
    return text in {"1", "true", "t", "yes", "y"}


def load_manifest(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Manifest has no header: {path}")
        required = {"wave_folder"}
        missing = [c for c in required if c not in set(reader.fieldnames)]
        if missing:
            raise ValueError(f"Manifest missing required columns: {', '.join(missing)}")
        rows = []
        for row in reader:
            if not normalize_bool(row.get("enabled", "yes"), default=True):
                continue
            rows.append(row)
        return rows


def list_wave_dirs_from_glob(pattern: str) -> List[Path]:
    return [p for p in sorted(Path(".").glob(pattern)) if p.is_dir()]


def wave_checks(wave_id: str, wave_folder: Path, notes: str, source: str) -> Dict[str, str]:
    exists = wave_folder.exists() and wave_folder.is_dir()
    readmes = sorted(wave_folder.glob("*readme*.txt")) if exists else []
    savs = sorted(wave_folder.glob("*.sav")) if exists else []
    pdfs = sorted(wave_folder.glob("*.pdf")) if exists else []

    has_questionnaire = any("questionnaire" in p.name.lower() for p in pdfs)
    has_topline = any("topline" in p.name.lower() for p in pdfs)
    has_methodology = any("methodology" in p.name.lower() for p in pdfs)
    has_partial = (wave_folder / "pew_question_inventory_partial.csv").exists() if exists else False

    required_ok = exists and len(readmes) >= 1 and len(savs) >= 1
    status = "pass" if required_ok else "fail"

    return {
        "wave_id": wave_id,
        "wave_folder": str(wave_folder),
        "source": source,
        "notes": notes,
        "exists": "yes" if exists else "no",
        "readme_count": str(len(readmes)),
        "sav_count": str(len(savs)),
        "pdf_count": str(len(pdfs)),
        "has_questionnaire_pdf": "yes" if has_questionnaire else "no",
        "has_topline_pdf": "yes" if has_topline else "no",
        "has_methodology_pdf": "yes" if has_methodology else "no",
        "has_partial_inventory": "yes" if has_partial else "no",
        "status": status,
    }


def build_report_rows(args: argparse.Namespace) -> Tuple[List[Dict[str, str]], bool, bool]:
    manifest_rows = load_manifest(Path(args.manifest))
    manifest_used = len(manifest_rows) > 0
    glob_dirs = list_wave_dirs_from_glob(args.wave_glob)

    report_rows: List[Dict[str, str]] = []

    if manifest_used:
        for row in manifest_rows:
            wave_folder = Path((row.get("wave_folder") or "").strip())
            wave_id = (row.get("wave_id") or wave_folder.name).strip() or wave_folder.name
            notes = (row.get("notes") or "").strip()
            report_rows.append(
                wave_checks(
                    wave_id=wave_id,
                    wave_folder=wave_folder,
                    notes=notes,
                    source="manifest",
                )
            )

        manifest_folders = {Path((r.get("wave_folder") or "").strip()) for r in manifest_rows}
        for folder in glob_dirs:
            if folder in manifest_folders:
                continue
            row = wave_checks(
                wave_id=folder.name,
                wave_folder=folder,
                notes="Found by wave-glob but not listed in enabled manifest rows",
                source="glob_unlisted",
            )
            if row["status"] == "pass":
                row["status"] = "warn"
            report_rows.append(row)
    else:
        for folder in glob_dirs:
            report_rows.append(
                wave_checks(
                    wave_id=folder.name,
                    wave_folder=folder,
                    notes="",
                    source="glob",
                )
            )

    report_rows.sort(key=lambda r: (r.get("wave_folder", ""), r.get("source", "")))
    return report_rows, manifest_used, bool(glob_dirs)


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    fieldnames = [
        "wave_id",
        "wave_folder",
        "source",
        "notes",
        "exists",
        "readme_count",
        "sav_count",
        "pdf_count",
        "has_questionnaire_pdf",
        "has_topline_pdf",
        "has_methodology_pdf",
        "has_partial_inventory",
        "status",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    rows, manifest_used, _ = build_report_rows(args)

    if not rows:
        raise FileNotFoundError(
            "No wave folders found. Check --wave-glob and/or manifest path."
        )

    output_path = Path(args.output)
    write_csv(output_path, rows)

    status_counts: Dict[str, int] = {}
    for row in rows:
        status = row.get("status", "")
        status_counts[status] = status_counts.get(status, 0) + 1

    print(f"Manifest used: {'yes' if manifest_used else 'no'}")
    print(f"Wave rows checked: {len(rows)}")
    print("Status counts:")
    for status in sorted(status_counts):
        print(f"  {status}: {status_counts[status]}")
    print(f"Report: {output_path}")

    has_fail = any(row.get("status") == "fail" for row in rows)
    if args.strict and has_fail:
        raise SystemExit("Preflight failed: at least one wave row is missing required files")


if __name__ == "__main__":
    main()
