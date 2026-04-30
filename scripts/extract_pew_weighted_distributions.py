#!/usr/bin/env python3
"""Extract weighted PEW response distributions for included RQ3 rows."""

# Simple explanation of this script (step by step):
# 1) Read `rq3_pew_subset.csv` (included PEW rows only).
# 2) Resolve each row to its source `.sav` file and choose a wave-appropriate weight variable.
# 3) Extract the selected PEW variable from respondent-level `.sav` data.
# 4) Convert response options into comparable buckets (positive/negative/neutral/missing).
# 5) Write weighted distributions and diagnostics for RQ3 alignment analysis.

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import DefaultDict, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import pyreadstat  # type: ignore
except Exception:  # pragma: no cover
    pyreadstat = None


PEW_SUBSET_DEFAULT = "data/interim/rq3/rq3_pew_subset.csv"
WAVES_ROOT_DEFAULT = "data/pew_datasets"
OUTPUT_DIR_DEFAULT = "data/interim/rq3"

MISSING_LABEL_RE = re.compile(
    r"\b(refused|don.?t know|don't know|web blank|not sure|no answer|missing|inapp)\b",
    re.IGNORECASE,
)
POSITIVE_LABEL_RE = re.compile(
    r"\b(approve|favor|support|very confident|somewhat confident)\b",
    re.IGNORECASE,
)
NEGATIVE_LABEL_RE = re.compile(
    r"\b(disapprove|oppose|not too confident|not at all confident)\b",
    re.IGNORECASE,
)
NEUTRAL_LABEL_RE = re.compile(
    r"\b(neither|about the same|equally|neutral)\b",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract weighted PEW response distributions from .sav files for "
            "rows included in rq3_pew_subset.csv."
        )
    )
    parser.add_argument(
        "--pew-subset",
        default=PEW_SUBSET_DEFAULT,
        help=f"Included PEW subset CSV (default: {PEW_SUBSET_DEFAULT})",
    )
    parser.add_argument(
        "--waves-root",
        default=WAVES_ROOT_DEFAULT,
        help=f"Root folder with PEW wave folders (default: {WAVES_ROOT_DEFAULT})",
    )
    parser.add_argument(
        "--output-dir",
        default=OUTPUT_DIR_DEFAULT,
        help=f"Output folder for weighted distributions (default: {OUTPUT_DIR_DEFAULT})",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting output files",
    )
    return parser.parse_args()


def read_csv_rows(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        return list(reader.fieldnames), list(reader)


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def normalize(text: object) -> str:
    return str(text or "").strip()


def to_float(value: object) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        num = float(value)
        if math.isnan(num):
            return None
        return num
    text = normalize(value)
    if not text:
        return None
    try:
        num = float(text)
    except ValueError:
        return None
    if math.isnan(num):
        return None
    return num


def wave_number_from_tag(pew_wave: str) -> str:
    m = re.search(r"ATP_(\d+)", pew_wave)
    return m.group(1) if m else ""


def find_sav_path(row: Dict[str, str], waves_root: Path) -> Optional[Path]:
    dataset_file = normalize(row.get("dataset_file"))
    pew_wave = normalize(row.get("pew_wave"))
    wave_num = wave_number_from_tag(pew_wave)
    if not wave_num:
        return None

    candidate_dirs = sorted(p for p in waves_root.glob(f"W{wave_num}*") if p.is_dir())
    for folder in candidate_dirs:
        sav_files = sorted([p for p in folder.glob("*.sav")] + [p for p in folder.glob("*.SAV")])
        if not sav_files:
            continue
        if dataset_file:
            for sav in sav_files:
                if sav.name.lower() == dataset_file.lower():
                    return sav
        if len(sav_files) == 1:
            return sav_files[0]

    if dataset_file:
        matches = list(waves_root.rglob(dataset_file))
        if matches:
            return matches[0]
    return None


def choose_weight_var(columns: Sequence[str], wave_num: str) -> Optional[str]:
    upper_map = {c.upper(): c for c in columns}
    exact_candidates = [
        f"WEIGHT_W{wave_num}",
        f"WEIGHT_{wave_num}",
        "WEIGHT",
    ]
    for cand in exact_candidates:
        if cand in upper_map:
            return upper_map[cand]

    wave_prefix = f"WEIGHT_W{wave_num}"
    pref = [c for c in columns if c.upper().startswith(wave_prefix)]
    preferred = [c for c in pref if "VALIDATEDVOTE" not in c.upper() and "_VOTE" not in c.upper()]
    if preferred:
        return sorted(preferred, key=len)[0]
    if pref:
        return sorted(pref, key=len)[0]

    generic = [c for c in columns if c.upper().startswith("WEIGHT")]
    if generic:
        return sorted(generic, key=len)[0]
    return None


def lookup_label(value: object, value_labels: Dict[object, object]) -> str:
    if value is None:
        return ""
    if value in value_labels:
        return normalize(value_labels[value])

    num = to_float(value)
    if num is not None:
        for key, label in value_labels.items():
            key_num = to_float(key)
            if key_num is None:
                continue
            if abs(key_num - num) < 1e-9:
                return normalize(label)
    return ""


def classify_response(value: object, label_text: str, response_scale_raw: str) -> str:
    num = to_float(value)
    if num is None:
        return "missing"

    label = normalize(label_text).lower()
    scale = normalize(response_scale_raw)
    if MISSING_LABEL_RE.search(label):
        return "missing"

    if scale == "very_somewhat_not_too_not_at_all_confident":
        if num in {1.0, 2.0}:
            return "positive"
        if num in {3.0, 4.0}:
            return "negative"

    if scale == "approve_disapprove":
        if "disapprove" in label:
            return "negative"
        if "approve" in label:
            return "positive"

    if scale in {"favor_oppose", "support_oppose"}:
        if "oppose" in label:
            return "negative"
        if "favor" in label or "support" in label:
            return "positive"

    if NEGATIVE_LABEL_RE.search(label):
        return "negative"
    if POSITIVE_LABEL_RE.search(label):
        return "positive"
    if NEUTRAL_LABEL_RE.search(label):
        return "neutral"

    return "unclassified"


def main() -> None:
    args = parse_args()
    if pyreadstat is None:
        raise RuntimeError(
            "pyreadstat is required for .sav extraction. Install with: python3 -m pip install pyreadstat"
        )

    subset_path = Path(args.pew_subset)
    waves_root = Path(args.waves_root)
    output_dir = Path(args.output_dir)

    if not subset_path.exists():
        raise FileNotFoundError(f"PEW subset file not found: {subset_path}")
    if not waves_root.exists():
        raise FileNotFoundError(f"Waves root not found: {waves_root}")

    outputs = {
        "question_summary": output_dir / "pew_weighted_question_summary.csv",
        "question_distribution": output_dir / "pew_weighted_question_distribution.csv",
        "raw_value_distribution": output_dir / "pew_weighted_raw_value_distribution.csv",
        "topic_summary": output_dir / "pew_weighted_topic_summary.csv",
        "issues": output_dir / "pew_weighted_extraction_issues.csv",
        "manifest": output_dir / "pew_weighted_manifest.json",
    }
    if not args.overwrite:
        for path in outputs.values():
            if path.exists():
                raise FileExistsError(f"Output already exists: {path}. Use --overwrite.")

    _fields, input_rows = read_csv_rows(subset_path)
    if not input_rows:
        raise RuntimeError(f"No rows found in {subset_path}")

    rows: List[Dict[str, str]] = []
    for row in input_rows:
        if normalize(row.get("include_for_rq3", "yes")).lower() != "yes":
            continue
        rows.append(row)
    if not rows:
        raise RuntimeError("No include_for_rq3=yes rows found in PEW subset.")

    issues: List[Dict[str, object]] = []

    requests_by_sav: DefaultDict[Path, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        sav_path = find_sav_path(row, waves_root)
        if sav_path is None:
            issues.append(
                {
                    "inventory_id": row.get("inventory_id", ""),
                    "pew_wave": row.get("pew_wave", ""),
                    "dataset_file": row.get("dataset_file", ""),
                    "variable_name": row.get("variable_name", ""),
                    "issue_type": "missing_sav",
                    "detail": "Could not resolve .sav path from wave + dataset_file",
                }
            )
            continue
        row_copy = dict(row)
        row_copy["_sav_path"] = str(sav_path)
        requests_by_sav[sav_path].append(row_copy)

    question_summary_rows: List[Dict[str, object]] = []
    question_dist_rows: List[Dict[str, object]] = []
    raw_dist_rows: List[Dict[str, object]] = []

    processed_questions = 0
    unresolved_questions = 0

    for sav_path, sav_rows in sorted(requests_by_sav.items(), key=lambda x: str(x[0])):
        wave_num = wave_number_from_tag(normalize(sav_rows[0].get("pew_wave", "")))
        try:
            _meta_df, meta = pyreadstat.read_sav(str(sav_path), metadataonly=True)
        except Exception as exc:
            for row in sav_rows:
                issues.append(
                    {
                        "inventory_id": row.get("inventory_id", ""),
                        "pew_wave": row.get("pew_wave", ""),
                        "dataset_file": row.get("dataset_file", ""),
                        "variable_name": row.get("variable_name", ""),
                        "issue_type": "read_error_metadata",
                        "detail": str(exc),
                    }
                )
                unresolved_questions += 1
            continue

        columns = list(meta.column_names)
        weight_var = choose_weight_var(columns, wave_num)
        if not weight_var:
            for row in sav_rows:
                issues.append(
                    {
                        "inventory_id": row.get("inventory_id", ""),
                        "pew_wave": row.get("pew_wave", ""),
                        "dataset_file": row.get("dataset_file", ""),
                        "variable_name": row.get("variable_name", ""),
                        "issue_type": "missing_weight_var",
                        "detail": "No WEIGHT* column found in .sav",
                    }
                )
                unresolved_questions += 1
            continue

        requested_vars = sorted({normalize(r.get("variable_name", "")) for r in sav_rows if normalize(r.get("variable_name", ""))})
        present_vars = [v for v in requested_vars if v in columns]
        missing_vars = sorted(set(requested_vars) - set(present_vars))
        for missing_var in missing_vars:
            matched_row = next((r for r in sav_rows if normalize(r.get("variable_name", "")) == missing_var), None)
            issues.append(
                {
                    "inventory_id": matched_row.get("inventory_id", "") if matched_row else "",
                    "pew_wave": matched_row.get("pew_wave", "") if matched_row else "",
                    "dataset_file": matched_row.get("dataset_file", "") if matched_row else sav_path.name,
                    "variable_name": missing_var,
                    "issue_type": "missing_variable_in_sav",
                    "detail": f"Variable not found in {sav_path.name}",
                }
            )
            unresolved_questions += 1

        if not present_vars:
            continue

        usecols = present_vars + [weight_var]
        try:
            df, meta_with_values = pyreadstat.read_sav(str(sav_path), usecols=usecols)
        except Exception as exc:
            for row in sav_rows:
                issues.append(
                    {
                        "inventory_id": row.get("inventory_id", ""),
                        "pew_wave": row.get("pew_wave", ""),
                        "dataset_file": row.get("dataset_file", ""),
                        "variable_name": row.get("variable_name", ""),
                        "issue_type": "read_error_data",
                        "detail": str(exc),
                    }
                )
                unresolved_questions += 1
            continue

        for row in sav_rows:
            variable_name = normalize(row.get("variable_name", ""))
            if not variable_name or variable_name not in present_vars:
                continue
            processed_questions += 1

            values = df[variable_name].tolist()
            weights = df[weight_var].tolist()
            value_labels = meta_with_values.variable_value_labels.get(variable_name, {})

            bucket_unw: Counter[str] = Counter()
            bucket_w: DefaultDict[str, float] = defaultdict(float)

            raw_unw: Counter[Tuple[str, str, str]] = Counter()
            raw_w: DefaultDict[Tuple[str, str, str], float] = defaultdict(float)

            for value, weight in zip(values, weights):
                label = lookup_label(value, value_labels)
                bucket = classify_response(value, label, normalize(row.get("response_scale_raw", "")))
                bucket_unw[bucket] += 1

                value_text = "" if to_float(value) is None else str(to_float(value))
                key = (value_text, label, bucket)
                raw_unw[key] += 1

                w = to_float(weight)
                if w is not None and w > 0:
                    bucket_w[bucket] += w
                    raw_w[key] += w

            unweighted_total = float(sum(bucket_unw.values()))
            weighted_total = float(sum(bucket_w.values()))
            unweighted_valid = float(bucket_unw.get("positive", 0) + bucket_unw.get("negative", 0) + bucket_unw.get("neutral", 0))
            weighted_valid = float(bucket_w.get("positive", 0.0) + bucket_w.get("negative", 0.0) + bucket_w.get("neutral", 0.0))

            def pct(num: float, den: float) -> Optional[float]:
                if den <= 0:
                    return None
                return round((num / den) * 100.0, 6)

            base = {
                "inventory_id": row.get("inventory_id", ""),
                "pew_wave": row.get("pew_wave", ""),
                "field_dates": row.get("field_dates", ""),
                "dataset_file": row.get("dataset_file", ""),
                "sav_path": str(sav_path),
                "variable_name": variable_name,
                "issue_topic": row.get("issue_topic", ""),
                "judgment_family": row.get("judgment_family", ""),
                "response_scale_raw": row.get("response_scale_raw", ""),
                "weight_var": weight_var,
            }

            for bucket in ["positive", "negative", "neutral", "missing", "unclassified"]:
                w_n = float(bucket_w.get(bucket, 0.0))
                uw_n = float(bucket_unw.get(bucket, 0))
                is_valid_bucket = bucket in {"positive", "negative", "neutral"}
                question_dist_rows.append(
                    {
                        **base,
                        "response_bucket": bucket,
                        "weighted_n": round(w_n, 6),
                        "weighted_pct_all": pct(w_n, weighted_total),
                        "weighted_pct_valid": pct(w_n, weighted_valid) if is_valid_bucket else None,
                        "unweighted_n": int(uw_n),
                        "unweighted_pct_all": pct(uw_n, unweighted_total),
                        "unweighted_pct_valid": pct(uw_n, unweighted_valid) if is_valid_bucket else None,
                    }
                )

            for (value_text, label_text, bucket), uw_n in sorted(raw_unw.items()):
                raw_dist_rows.append(
                    {
                        **base,
                        "response_value": value_text,
                        "response_label": label_text,
                        "response_bucket": bucket,
                        "weighted_n": round(float(raw_w.get((value_text, label_text, bucket), 0.0)), 6),
                        "unweighted_n": int(uw_n),
                    }
                )

            positive_w = float(bucket_w.get("positive", 0.0))
            negative_w = float(bucket_w.get("negative", 0.0))
            neutral_w = float(bucket_w.get("neutral", 0.0))
            positive_uw = float(bucket_unw.get("positive", 0))
            negative_uw = float(bucket_unw.get("negative", 0))
            neutral_uw = float(bucket_unw.get("neutral", 0))

            pos_pct_w = pct(positive_w, weighted_valid)
            neg_pct_w = pct(negative_w, weighted_valid)
            neu_pct_w = pct(neutral_w, weighted_valid)
            pos_pct_uw = pct(positive_uw, unweighted_valid)
            neg_pct_uw = pct(negative_uw, unweighted_valid)
            neu_pct_uw = pct(neutral_uw, unweighted_valid)

            question_summary_rows.append(
                {
                    **base,
                    "n_respondents_unweighted": int(unweighted_total),
                    "n_valid_unweighted": int(unweighted_valid),
                    "weighted_total": round(weighted_total, 6),
                    "weighted_valid_total": round(weighted_valid, 6),
                    "positive_unweighted_n": int(positive_uw),
                    "negative_unweighted_n": int(negative_uw),
                    "neutral_unweighted_n": int(neutral_uw),
                    "missing_unweighted_n": int(bucket_unw.get("missing", 0)),
                    "unclassified_unweighted_n": int(bucket_unw.get("unclassified", 0)),
                    "positive_weighted_n": round(positive_w, 6),
                    "negative_weighted_n": round(negative_w, 6),
                    "neutral_weighted_n": round(neutral_w, 6),
                    "missing_weighted_n": round(float(bucket_w.get("missing", 0.0)), 6),
                    "unclassified_weighted_n": round(float(bucket_w.get("unclassified", 0.0)), 6),
                    "positive_weighted_pct_valid": pos_pct_w,
                    "negative_weighted_pct_valid": neg_pct_w,
                    "neutral_weighted_pct_valid": neu_pct_w,
                    "positive_unweighted_pct_valid": pos_pct_uw,
                    "negative_unweighted_pct_valid": neg_pct_uw,
                    "neutral_unweighted_pct_valid": neu_pct_uw,
                    "weighted_net_positive_minus_negative": None
                    if pos_pct_w is None or neg_pct_w is None
                    else round(pos_pct_w - neg_pct_w, 6),
                }
            )

    topic_acc: DefaultDict[str, Dict[str, object]] = defaultdict(
        lambda: {
            "issue_topic": "",
            "questions_count": 0,
            "waves": set(),
            "weighted_valid_sum": 0.0,
            "weighted_positive_sum": 0.0,
            "weighted_negative_sum": 0.0,
            "weighted_neutral_sum": 0.0,
            "mean_net_components": [],
        }
    )

    for row in question_summary_rows:
        topic = normalize(row.get("issue_topic", ""))
        if not topic:
            continue
        slot = topic_acc[topic]
        slot["issue_topic"] = topic
        slot["questions_count"] = int(slot["questions_count"]) + 1
        slot["waves"].add(normalize(row.get("pew_wave", "")))
        slot["weighted_valid_sum"] = float(slot["weighted_valid_sum"]) + float(row.get("weighted_valid_total", 0.0) or 0.0)
        slot["weighted_positive_sum"] = float(slot["weighted_positive_sum"]) + float(row.get("positive_weighted_n", 0.0) or 0.0)
        slot["weighted_negative_sum"] = float(slot["weighted_negative_sum"]) + float(row.get("negative_weighted_n", 0.0) or 0.0)
        slot["weighted_neutral_sum"] = float(slot["weighted_neutral_sum"]) + float(row.get("neutral_weighted_n", 0.0) or 0.0)
        net = row.get("weighted_net_positive_minus_negative")
        if net is not None and net != "":
            slot["mean_net_components"].append(float(net))

    topic_summary_rows: List[Dict[str, object]] = []
    for topic in sorted(topic_acc):
        slot = topic_acc[topic]
        valid_sum = float(slot["weighted_valid_sum"])
        positive_sum = float(slot["weighted_positive_sum"])
        negative_sum = float(slot["weighted_negative_sum"])
        neutral_sum = float(slot["weighted_neutral_sum"])

        def pct_local(num: float, den: float) -> Optional[float]:
            if den <= 0:
                return None
            return round((num / den) * 100.0, 6)

        comps = slot["mean_net_components"]
        topic_summary_rows.append(
            {
                "issue_topic": topic,
                "questions_count": int(slot["questions_count"]),
                "waves_count": len(slot["waves"]),
                "weighted_valid_sum": round(valid_sum, 6),
                "weighted_positive_sum": round(positive_sum, 6),
                "weighted_negative_sum": round(negative_sum, 6),
                "weighted_neutral_sum": round(neutral_sum, 6),
                "weighted_positive_pct_valid": pct_local(positive_sum, valid_sum),
                "weighted_negative_pct_valid": pct_local(negative_sum, valid_sum),
                "weighted_neutral_pct_valid": pct_local(neutral_sum, valid_sum),
                "weighted_net_positive_minus_negative": None
                if valid_sum <= 0
                else round((positive_sum / valid_sum - negative_sum / valid_sum) * 100.0, 6),
                "mean_question_net_positive_minus_negative": None
                if not comps
                else round(sum(comps) / len(comps), 6),
            }
        )

    write_csv(
        outputs["question_summary"],
        [
            "inventory_id",
            "pew_wave",
            "field_dates",
            "dataset_file",
            "sav_path",
            "variable_name",
            "issue_topic",
            "judgment_family",
            "response_scale_raw",
            "weight_var",
            "n_respondents_unweighted",
            "n_valid_unweighted",
            "weighted_total",
            "weighted_valid_total",
            "positive_unweighted_n",
            "negative_unweighted_n",
            "neutral_unweighted_n",
            "missing_unweighted_n",
            "unclassified_unweighted_n",
            "positive_weighted_n",
            "negative_weighted_n",
            "neutral_weighted_n",
            "missing_weighted_n",
            "unclassified_weighted_n",
            "positive_weighted_pct_valid",
            "negative_weighted_pct_valid",
            "neutral_weighted_pct_valid",
            "positive_unweighted_pct_valid",
            "negative_unweighted_pct_valid",
            "neutral_unweighted_pct_valid",
            "weighted_net_positive_minus_negative",
        ],
        question_summary_rows,
    )

    write_csv(
        outputs["question_distribution"],
        [
            "inventory_id",
            "pew_wave",
            "field_dates",
            "dataset_file",
            "sav_path",
            "variable_name",
            "issue_topic",
            "judgment_family",
            "response_scale_raw",
            "weight_var",
            "response_bucket",
            "weighted_n",
            "weighted_pct_all",
            "weighted_pct_valid",
            "unweighted_n",
            "unweighted_pct_all",
            "unweighted_pct_valid",
        ],
        question_dist_rows,
    )

    write_csv(
        outputs["raw_value_distribution"],
        [
            "inventory_id",
            "pew_wave",
            "field_dates",
            "dataset_file",
            "sav_path",
            "variable_name",
            "issue_topic",
            "judgment_family",
            "response_scale_raw",
            "weight_var",
            "response_value",
            "response_label",
            "response_bucket",
            "weighted_n",
            "unweighted_n",
        ],
        raw_dist_rows,
    )

    write_csv(
        outputs["topic_summary"],
        [
            "issue_topic",
            "questions_count",
            "waves_count",
            "weighted_valid_sum",
            "weighted_positive_sum",
            "weighted_negative_sum",
            "weighted_neutral_sum",
            "weighted_positive_pct_valid",
            "weighted_negative_pct_valid",
            "weighted_neutral_pct_valid",
            "weighted_net_positive_minus_negative",
            "mean_question_net_positive_minus_negative",
        ],
        topic_summary_rows,
    )

    write_csv(
        outputs["issues"],
        ["inventory_id", "pew_wave", "dataset_file", "variable_name", "issue_type", "detail"],
        issues,
    )

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input_subset_csv": str(subset_path),
        "waves_root": str(waves_root),
        "rows_requested": len(rows),
        "rows_resolved_to_sav": sum(len(v) for v in requests_by_sav.values()),
        "questions_processed": processed_questions,
        "questions_unresolved": unresolved_questions,
        "issues_count": len(issues),
        "topic_count": len(topic_summary_rows),
        "outputs": {k: str(v) for k, v in outputs.items()},
    }
    outputs["manifest"].write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    issue_counter = Counter(str(i.get("issue_type", "")) for i in issues)

    print(f"Requested included PEW rows: {len(rows)}")
    print(f"Resolved rows with .sav path: {sum(len(v) for v in requests_by_sav.values())}")
    print(f"Questions processed: {processed_questions}")
    print(f"Questions unresolved: {unresolved_questions}")
    print(f"Issue rows: {len(issues)}")
    if issue_counter:
        print("Issue type counts:")
        for key, count in sorted(issue_counter.items()):
            print(f"  {key}: {count}")
    print(f"Topic summary rows: {len(topic_summary_rows)}")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
