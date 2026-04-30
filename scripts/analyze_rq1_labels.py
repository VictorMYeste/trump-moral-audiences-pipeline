#!/usr/bin/env python3
"""Build flat and summary RQ1 label tables from low-temperature JSON outputs."""

# Simple explanation of this script (step by step):
# 1) Find low-temperature RQ1 generation JSON files in the outputs folder.
# 2) Read each file and skip records that failed parsing (`parse_error` not empty).
# 3) Flatten tweet-level and bundle-level labels into reusable CSV tables.
# 4) Build summary CSVs for stance, agreement, legitimacy, offensiveness, and endorsement.
# 5) Write an ingest report and a small manifest with run counts for transparency.

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


DEFAULT_INPUT_ROOT = "docs/private/RQ1/RQ1_all_outputs"
DEFAULT_OUTPUT_DIR = "docs/private/RQ1/RQ1_all_label_analysis"
STANCE_TO_SCORE = {"reject": -1.0, "neutral": 0.0, "support": 1.0}
NUMERIC_LABELS = [
    "stance_score",
    "agreement",
    "legitimacy",
    "offensiveness",
    "endorsement",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze low-temperature RQ1 outputs and export flat/summary CSVs "
            "for stance + additional labels."
        )
    )
    parser.add_argument(
        "--input-root",
        default=DEFAULT_INPUT_ROOT,
        help="Root folder containing per-topic RQ1 output subfolders",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Folder where flat and summary CSVs will be written",
    )
    parser.add_argument(
        "--include-neigh",
        action="store_true",
        help="Include IW neighbor-variant low outputs (`_neigh_` files)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite output files if they already exist",
    )
    return parser.parse_args()


def to_float(value: object) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        if math.isnan(float(value)):
            return None
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        num = float(text)
    except ValueError:
        return None
    if math.isnan(num):
        return None
    return num


def normalize_stance(value: object) -> str:
    text = str(value or "").strip().lower()
    if text in {"support", "neutral", "reject"}:
        return text
    return ""


def parse_folder_name(folder_name: str) -> Tuple[str, str]:
    # Expected: "iw_topic_name" or "mft_topic_name"
    if "_" not in folder_name:
        return "", folder_name
    mode, topic = folder_name.split("_", 1)
    return mode, topic


def detect_variant(mode: str, filename: str) -> str:
    if mode == "iw" and "_neigh_" in filename:
        return "neigh"
    return "topk"


def is_low_generation_file(path: Path) -> bool:
    name = path.name
    return name.startswith("gpt-oss-20b_") and "_low_" in name and name.endswith(".json")


def discover_input_files(input_root: Path, include_neigh: bool) -> List[Path]:
    discovered: List[Path] = []
    for path in sorted(input_root.glob("*/*.json")):
        if not is_low_generation_file(path):
            continue
        mode, _topic = parse_folder_name(path.parent.name)
        if mode not in {"iw", "mft"}:
            continue
        if "_neigh_" in path.name and not include_neigh:
            continue
        discovered.append(path)
    return discovered


def ensure_writable(path: Path, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {path}")


def write_csv(path: Path, rows: Sequence[Dict[str, object]], fieldnames: Sequence[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def row_metric_summaries(
    rows: Sequence[Dict[str, object]], level: str
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    by_polarity: Dict[Tuple[str, str, str, str, str], List[float]] = defaultdict(list)
    overall: Dict[Tuple[str, str, str, str], List[float]] = defaultdict(list)
    for row in rows:
        mode = str(row["mode"])
        variant = str(row["variant"])
        topic = str(row["topic"])
        polarity = str(row["persona_polarity"])
        for metric in NUMERIC_LABELS:
            value = to_float(row.get(metric))
            if value is None:
                continue
            by_polarity[(mode, variant, topic, polarity, metric)].append(value)
            overall[(mode, variant, topic, metric)].append(value)

    def build_stats(values: List[float]) -> Dict[str, object]:
        values_sorted = sorted(values)
        n = len(values_sorted)
        std = statistics.stdev(values_sorted) if n > 1 else 0.0
        return {
            "n": n,
            "mean": round(statistics.mean(values_sorted), 6),
            "std": round(std, 6),
            "min": round(values_sorted[0], 6),
            "max": round(values_sorted[-1], 6),
        }

    by_polarity_rows: List[Dict[str, object]] = []
    for (mode, variant, topic, polarity, metric), values in sorted(by_polarity.items()):
        stats = build_stats(values)
        by_polarity_rows.append(
            {
                "mode": mode,
                "variant": variant,
                "topic": topic,
                "level": level,
                "persona_polarity": polarity,
                "metric": metric,
                **stats,
            }
        )

    overall_rows: List[Dict[str, object]] = []
    for (mode, variant, topic, metric), values in sorted(overall.items()):
        stats = build_stats(values)
        overall_rows.append(
            {
                "mode": mode,
                "variant": variant,
                "topic": topic,
                "level": level,
                "metric": metric,
                **stats,
            }
        )
    return by_polarity_rows, overall_rows


def stance_distributions(rows: Sequence[Dict[str, object]], level: str) -> List[Dict[str, object]]:
    counts: Counter[Tuple[str, str, str, str, str]] = Counter()
    totals: Counter[Tuple[str, str, str, str]] = Counter()
    for row in rows:
        stance = normalize_stance(row.get("stance"))
        if not stance:
            continue
        key_base = (
            str(row["mode"]),
            str(row["variant"]),
            str(row["topic"]),
            str(row["persona_polarity"]),
        )
        totals[key_base] += 1
        counts[key_base + (stance,)] += 1

    out: List[Dict[str, object]] = []
    for (mode, variant, topic, polarity, stance), count in sorted(counts.items()):
        total = totals[(mode, variant, topic, polarity)]
        pct = (count / total) if total else 0.0
        out.append(
            {
                "mode": mode,
                "variant": variant,
                "topic": topic,
                "level": level,
                "persona_polarity": polarity,
                "stance": stance,
                "n": count,
                "total": total,
                "pct": round(pct, 6),
            }
        )
    return out


def main() -> None:
    args = parse_args()
    input_root = Path(args.input_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_root.exists():
        raise FileNotFoundError(f"Input root not found: {input_root}")

    files = discover_input_files(input_root, args.include_neigh)
    if not files:
        raise RuntimeError(f"No low-temperature generation files found in: {input_root}")

    output_paths = {
        "tweet_flat": output_dir / "rq1_tweet_labels_flat.csv",
        "bundle_flat": output_dir / "rq1_bundle_labels_flat.csv",
        "summary_polarity": output_dir / "rq1_label_summary_by_polarity.csv",
        "summary_overall": output_dir / "rq1_label_summary_overall.csv",
        "stance_dist": output_dir / "rq1_stance_distribution.csv",
        "ingest_report": output_dir / "rq1_ingest_report.csv",
        "manifest": output_dir / "rq1_analysis_manifest.json",
    }
    for target in output_paths.values():
        ensure_writable(target, args.overwrite)

    tweet_rows: List[Dict[str, object]] = []
    bundle_rows: List[Dict[str, object]] = []
    ingest_rows: List[Dict[str, object]] = []

    total_records = 0
    parse_error_records = 0
    malformed_records = 0

    for path in files:
        mode, topic = parse_folder_name(path.parent.name)
        variant = detect_variant(mode, path.name)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"Expected list at {path}, got {type(payload).__name__}")

        file_records = len(payload)
        file_parse_errors = 0
        file_malformed = 0
        file_kept = 0
        file_tweet_rows = 0
        file_bundle_rows = 0

        for record in payload:
            total_records += 1
            parse_error = str(record.get("parse_error") or "").strip()
            if parse_error:
                parse_error_records += 1
                file_parse_errors += 1
                continue

            parsed = record.get("parsed_json") or {}
            if not isinstance(parsed, dict):
                malformed_records += 1
                file_malformed += 1
                continue

            persona_mode = str(record.get("persona_mode") or mode)
            persona_id = str(record.get("persona_id") or "")
            persona_topic = str(record.get("persona_topic") or topic)
            persona_polarity = str(record.get("persona_polarity") or "").strip().lower()
            selection_rank = record.get("selection_rank")
            bundle_id = str(record.get("bundle_id") or "")
            author_role = str(record.get("author_role") or "")
            assignment_key = str(record.get("persona_assignment_key") or "")
            attempt_count = record.get("attempt_count")

            bundle_stance = normalize_stance(parsed.get("bundle_overall_stance"))
            bundle_row = {
                "mode": persona_mode,
                "variant": variant,
                "topic": persona_topic,
                "persona_id": persona_id,
                "persona_polarity": persona_polarity,
                "selection_rank": selection_rank,
                "persona_assignment_key": assignment_key,
                "bundle_id": bundle_id,
                "author_role": author_role,
                "attempt_count": attempt_count,
                "stance": bundle_stance,
                "stance_score": STANCE_TO_SCORE.get(bundle_stance),
                "agreement": to_float(parsed.get("bundle_overall_agreement")),
                "legitimacy": to_float(parsed.get("bundle_overall_legitimacy")),
                "offensiveness": to_float(parsed.get("bundle_overall_offensiveness")),
                "endorsement": to_float(parsed.get("bundle_overall_endorsement")),
                "emotional_reaction": str(parsed.get("bundle_overall_emotional_reaction") or ""),
                "brief_reason": str(parsed.get("bundle_overall_reason") or ""),
            }
            bundle_rows.append(bundle_row)
            file_bundle_rows += 1

            responses = parsed.get("responses") or []
            if not isinstance(responses, list):
                malformed_records += 1
                file_malformed += 1
                continue

            for response in responses:
                if not isinstance(response, dict):
                    continue
                stance = normalize_stance(response.get("stance"))
                tweet_rows.append(
                    {
                        "mode": persona_mode,
                        "variant": variant,
                        "topic": persona_topic,
                        "persona_id": persona_id,
                        "persona_polarity": persona_polarity,
                        "selection_rank": selection_rank,
                        "persona_assignment_key": assignment_key,
                        "bundle_id": bundle_id,
                        "tweet_id": str(response.get("tweet_id") or ""),
                        "author_role": author_role,
                        "attempt_count": attempt_count,
                        "stance": stance,
                        "stance_score": STANCE_TO_SCORE.get(stance),
                        "agreement": to_float(response.get("agreement")),
                        "legitimacy": to_float(response.get("legitimacy")),
                        "offensiveness": to_float(response.get("offensiveness")),
                        "endorsement": to_float(response.get("endorsement")),
                        "emotional_reaction": str(response.get("emotional_reaction") or ""),
                        "brief_reason": str(response.get("brief_reason") or ""),
                    }
                )
                file_tweet_rows += 1

            file_kept += 1

        ingest_rows.append(
            {
                "file_path": str(path),
                "mode": mode,
                "variant": variant,
                "topic": topic,
                "records_total": file_records,
                "records_kept": file_kept,
                "records_parse_error_skipped": file_parse_errors,
                "records_malformed_skipped": file_malformed,
                "tweet_rows_written": file_tweet_rows,
                "bundle_rows_written": file_bundle_rows,
            }
        )

    tweet_summary_by_pol, tweet_summary_overall = row_metric_summaries(tweet_rows, "tweet")
    bundle_summary_by_pol, bundle_summary_overall = row_metric_summaries(bundle_rows, "bundle")
    summary_by_polarity = tweet_summary_by_pol + bundle_summary_by_pol
    summary_overall = tweet_summary_overall + bundle_summary_overall
    stance_dist = stance_distributions(tweet_rows, "tweet") + stance_distributions(bundle_rows, "bundle")

    write_csv(
        output_paths["tweet_flat"],
        tweet_rows,
        [
            "mode",
            "variant",
            "topic",
            "persona_id",
            "persona_polarity",
            "selection_rank",
            "persona_assignment_key",
            "bundle_id",
            "tweet_id",
            "author_role",
            "attempt_count",
            "stance",
            "stance_score",
            "agreement",
            "legitimacy",
            "offensiveness",
            "endorsement",
            "emotional_reaction",
            "brief_reason",
        ],
    )
    write_csv(
        output_paths["bundle_flat"],
        bundle_rows,
        [
            "mode",
            "variant",
            "topic",
            "persona_id",
            "persona_polarity",
            "selection_rank",
            "persona_assignment_key",
            "bundle_id",
            "author_role",
            "attempt_count",
            "stance",
            "stance_score",
            "agreement",
            "legitimacy",
            "offensiveness",
            "endorsement",
            "emotional_reaction",
            "brief_reason",
        ],
    )
    write_csv(
        output_paths["summary_polarity"],
        summary_by_polarity,
        ["mode", "variant", "topic", "level", "persona_polarity", "metric", "n", "mean", "std", "min", "max"],
    )
    write_csv(
        output_paths["summary_overall"],
        summary_overall,
        ["mode", "variant", "topic", "level", "metric", "n", "mean", "std", "min", "max"],
    )
    write_csv(
        output_paths["stance_dist"],
        stance_dist,
        ["mode", "variant", "topic", "level", "persona_polarity", "stance", "n", "total", "pct"],
    )
    write_csv(
        output_paths["ingest_report"],
        ingest_rows,
        [
            "file_path",
            "mode",
            "variant",
            "topic",
            "records_total",
            "records_kept",
            "records_parse_error_skipped",
            "records_malformed_skipped",
            "tweet_rows_written",
            "bundle_rows_written",
        ],
    )

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input_root": str(input_root),
        "output_dir": str(output_dir),
        "include_neigh": bool(args.include_neigh),
        "files_analyzed": len(files),
        "records_total": total_records,
        "records_parse_error_skipped": parse_error_records,
        "records_malformed_skipped": malformed_records,
        "tweet_rows_written": len(tweet_rows),
        "bundle_rows_written": len(bundle_rows),
        "summary_rows_by_polarity": len(summary_by_polarity),
        "summary_rows_overall": len(summary_overall),
        "stance_distribution_rows": len(stance_dist),
        "outputs": {k: str(v) for k, v in output_paths.items()},
    }
    output_paths["manifest"].write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Files analyzed: {len(files)}")
    print(f"Records total: {total_records}")
    print(f"Skipped parse_error records: {parse_error_records}")
    print(f"Skipped malformed records: {malformed_records}")
    print(f"Tweet rows: {len(tweet_rows)}")
    print(f"Bundle rows: {len(bundle_rows)}")
    print(f"Output dir: {output_dir}")


if __name__ == "__main__":
    main()
