#!/usr/bin/env python3
"""Export method appendix artifacts (rules, regexes, and audit summaries)."""

# Simple explanation of this script (step by step):
# 1) Read the machine-readable rule spec from data/reference/methods/filter_spec.json.
# 2) Export rule tables and regex tables directly from code + spec.
# 3) Read current pipeline outputs and compute decision/audit counts.
# 4) Write appendix-ready files under reports/methods/.

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import preprocess_posts as pp
import select_pew_for_rq3 as sp
import topic_rules as tr

SPEC_DEFAULT = "data/reference/methods/filter_spec.json"
TOPIC_SPEC_DEFAULT = "data/reference/methods/topic_keywords.json"
OUTDIR_DEFAULT = "reports/methods"
RAW_DEFAULTS = [
    "data/raw/trump_archive_me2bert_filtered_2009_2021.csv",
    "data/raw/trump_manual_me2bert_filtered_2022_2024.csv",
]
POSTS_CLEAN_DEFAULT = "data/interim/preprocessing/posts_clean.csv"
POSTS_VALIDATED_DEFAULT = "data/interim/preprocessing/posts_topic_validated.csv"
POSTS_PROMPT_DEFAULT = "data/interim/preprocessing/posts_prompt_ready.csv"
PEW_RQ3_DEFAULT = "data/interim/pew/pew_rq3_inventory.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export appendix-ready method tables and decision audit files."
    )
    parser.add_argument("--spec", default=SPEC_DEFAULT)
    parser.add_argument("--topic-spec", default=TOPIC_SPEC_DEFAULT)
    parser.add_argument("--outdir", default=OUTDIR_DEFAULT)
    parser.add_argument(
        "--raw",
        action="append",
        default=[],
        help="Raw post CSV path. Repeat to combine multiple raw files.",
    )
    parser.add_argument("--posts-clean", default=POSTS_CLEAN_DEFAULT)
    parser.add_argument("--posts-validated", default=POSTS_VALIDATED_DEFAULT)
    parser.add_argument("--posts-prompt", default=POSTS_PROMPT_DEFAULT)
    parser.add_argument("--pew-rq3", default=PEW_RQ3_DEFAULT)
    return parser.parse_args()


def load_spec(path: Path) -> Dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"Rule spec not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".json":
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise SystemExit(
                "YAML spec requested but PyYAML is not installed. "
                "Install with: pip install pyyaml or use the default JSON spec."
            ) from exc
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    else:
        raise ValueError(f"Unsupported spec file extension: {path.suffix}")
    if not isinstance(data, dict):
        raise ValueError(f"Invalid spec format (expected object): {path}")
    return data


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return []
        return list(reader)


def read_many_csv_rows(paths: Sequence[str], default_paths: Sequence[str]) -> List[Dict[str, str]]:
    selected_paths = list(paths) if paths else list(default_paths)
    rows: List[Dict[str, str]] = []
    for path_str in selected_paths:
        rows.extend(read_csv_rows(Path(path_str)))
    return rows


def normalize_list_value(value: object) -> str:
    if isinstance(value, list):
        return "|".join(str(v) for v in value)
    if value is None:
        return ""
    return str(value)


def export_filter_table(spec: Dict[str, object], outdir: Path) -> Path:
    rows: List[Dict[str, str]] = []
    for rule_set_key in ["preprocess_rules", "pew_rules"]:
        rule_set = spec.get(rule_set_key, [])
        if not isinstance(rule_set, list):
            continue
        for item in rule_set:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "rule_set": "preprocess" if rule_set_key == "preprocess_rules" else "pew",
                    "rule_order": str(item.get("rule_order", "")),
                    "rule_id": str(item.get("rule_id", "")),
                    "stage": str(item.get("stage", "")),
                    "input_columns": normalize_list_value(item.get("input_columns", "")),
                    "condition": str(item.get("condition", "")),
                    "action": str(item.get("action", "")),
                    "output_code": str(item.get("output_code", "")),
                    "rationale": str(item.get("rationale", "")),
                }
            )

    rows.sort(key=lambda r: (r["rule_set"], int(r["rule_order"] or 0), r["rule_id"]))
    path = outdir / "filter_table.csv"
    write_csv(
        path,
        [
            "rule_set",
            "rule_order",
            "rule_id",
            "stage",
            "input_columns",
            "condition",
            "action",
            "output_code",
            "rationale",
        ],
        rows,
    )
    return path


def export_topic_patterns(outdir: Path, topic_spec_path: Path) -> Path:
    topic_spec = tr.load_topic_spec(topic_spec_path)
    metadata = topic_spec.get("metadata", {})
    spec_version = ""
    if isinstance(metadata, dict):
        spec_version = str(metadata.get("spec_version", "")).strip()

    posts_topics = {topic for topic, _ in pp.TOPIC_PATTERNS}
    pew_topics = {topic for topic, _ in sp.TOPIC_PATTERNS}

    rows: List[Dict[str, str]] = []
    topics = topic_spec.get("topics", [])
    if isinstance(topics, list):
        for item in topics:
            if not isinstance(item, dict):
                continue
            topic = str(item.get("topic", "")).strip()
            regex = str(item.get("regex", "")).strip()
            applies_to_raw = item.get("applies_to", [])
            applies_to = applies_to_raw if isinstance(applies_to_raw, list) else []
            applies_to_text = "|".join(str(v) for v in applies_to)
            rationale = str(item.get("selection_rationale", "")).strip()
            source_basis = str(item.get("source_basis", "")).strip()
            if not topic:
                continue
            rows.append(
                {
                    "topic": topic,
                    "regex": regex,
                    "applies_to": applies_to_text,
                    "selection_rationale": rationale,
                    "source_basis": source_basis,
                    "used_in_preprocess_posts": "yes" if topic in posts_topics else "no",
                    "used_in_select_pew_for_rq3": "yes" if topic in pew_topics else "no",
                    "topic_spec_version": spec_version,
                }
            )
    rows.sort(key=lambda r: r["topic"])

    path = outdir / "topic_patterns.csv"
    write_csv(
        path,
        [
            "topic",
            "regex",
            "applies_to",
            "selection_rationale",
            "source_basis",
            "used_in_preprocess_posts",
            "used_in_select_pew_for_rq3",
            "topic_spec_version",
        ],
        rows,
    )
    return path


def export_anonymization_rules(outdir: Path) -> Path:
    rows: List[Dict[str, str]] = []
    order = 1

    for pattern, replacement in pp.ROLE_REPLACEMENTS:
        rows.append(
            {
                "rule_order": str(order),
                "group": "role_replacements",
                "pattern": pattern.pattern,
                "replacement": replacement,
                "notes": "Role-sensitive normalization",
            }
        )
        order += 1

    for pattern, replacement in pp.IDENTITY_REPLACEMENTS:
        rows.append(
            {
                "rule_order": str(order),
                "group": "identity_replacements",
                "pattern": pattern.pattern,
                "replacement": replacement,
                "notes": "Direct identity masking",
            }
        )
        order += 1

    rows.append(
        {
            "rule_order": str(order),
            "group": "campaign_tag_replacement",
            "pattern": pp.CAMPAIGN_TAG_RE.pattern,
            "replacement": "[CAMPAIGN_TAG]",
            "notes": "Campaign-specific hashtag masking",
        }
    )
    order += 1

    for pattern, replacement in pp.ALLOWLIST_REPLACEMENTS:
        rows.append(
            {
                "rule_order": str(order),
                "group": "allowlist_replacements",
                "pattern": pattern.pattern,
                "replacement": replacement,
                "notes": "Institution handle normalization",
            }
        )
        order += 1

    rows.append(
        {
            "rule_order": str(order),
            "group": "generic_handle_replacement",
            "pattern": pp.HANDLE_RE.pattern,
            "replacement": "[USER]",
            "notes": "Fallback replacement for remaining handles",
        }
    )

    path = outdir / "anonymization_rules.csv"
    write_csv(path, ["rule_order", "group", "pattern", "replacement", "notes"], rows)
    return path


def export_pew_selection_rules(outdir: Path) -> Path:
    rows: List[Dict[str, str]] = []

    rows.extend(
        [
            {
                "rule_group": "trump_target",
                "rule_name": "TRUMP_DIRECT_RE",
                "output_code": "trump_direct (trace)",
                "pattern": sp.TRUMP_DIRECT_RE.pattern,
            },
            {
                "rule_group": "trump_target",
                "rule_name": "TRUMP_VARIABLE_RE",
                "output_code": "trump_direct (trace)",
                "pattern": sp.TRUMP_VARIABLE_RE.pattern,
            },
            {
                "rule_group": "trump_target",
                "rule_name": "PRESIDENT_REF_RE + TRUMP_CONTEXT_HINT_RE",
                "output_code": "president_context (trace)",
                "pattern": f"{sp.PRESIDENT_REF_RE.pattern} && {sp.TRUMP_CONTEXT_HINT_RE.pattern}",
            },
            {
                "rule_group": "excluded_form",
                "rule_name": "THERMOMETER_RE",
                "output_code": "exclude_thermometer",
                "pattern": sp.THERMOMETER_RE.pattern,
            },
            {
                "rule_group": "excluded_form",
                "rule_name": "TRAIT_RE",
                "output_code": "exclude_trait",
                "pattern": sp.TRAIT_RE.pattern,
            },
            {
                "rule_group": "excluded_form",
                "rule_name": "AFFECT_RE",
                "output_code": "exclude_affective_reaction",
                "pattern": sp.AFFECT_RE.pattern,
            },
            {
                "rule_group": "excluded_form",
                "rule_name": "KNOWLEDGE_RE",
                "output_code": "exclude_knowledge_or_awareness",
                "pattern": sp.KNOWLEDGE_RE.pattern,
            },
            {
                "rule_group": "excluded_form",
                "rule_name": "BROAD_FAVORABILITY_RE",
                "output_code": "exclude_broad_favorability",
                "pattern": sp.BROAD_FAVORABILITY_RE.pattern,
            },
            {
                "rule_group": "excluded_form",
                "rule_name": "BROAD_JOB_APPROVAL_RE",
                "output_code": "exclude_general_presidential_approval",
                "pattern": sp.BROAD_JOB_APPROVAL_RE.pattern,
            },
            {
                "rule_group": "excluded_form",
                "rule_name": "PRESIDENT_ELECT_PLANS_RE",
                "output_code": "exclude_general_presidential_approval",
                "pattern": sp.PRESIDENT_ELECT_PLANS_RE.pattern,
            },
            {
                "rule_group": "judgment_family",
                "rule_name": "APPROVAL_RE",
                "output_code": "approval",
                "pattern": sp.APPROVAL_RE.pattern,
            },
            {
                "rule_group": "judgment_family",
                "rule_name": "CONFIDENCE_RE",
                "output_code": "confidence",
                "pattern": sp.CONFIDENCE_RE.pattern,
            },
            {
                "rule_group": "judgment_family",
                "rule_name": "FAVOR_OPPOSE_RE",
                "output_code": "policy_support",
                "pattern": sp.FAVOR_OPPOSE_RE.pattern,
            },
            {
                "rule_group": "judgment_family",
                "rule_name": "SUPPORT_OPPOSE_RE",
                "output_code": "policy_support",
                "pattern": sp.SUPPORT_OPPOSE_RE.pattern,
            },
        ]
    )

    for topic, pattern in sp.TOPIC_PATTERNS:
        rows.append(
            {
                "rule_group": "issue_topic",
                "rule_name": f"TOPIC_PATTERNS::{topic}",
                "output_code": topic,
                "pattern": pattern.pattern,
            }
        )

    path = outdir / "pew_selection_rules.csv"
    write_csv(path, ["rule_group", "rule_name", "output_code", "pattern"], rows)
    return path


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def count_exclude_reasons(rows: Sequence[Dict[str, str]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        raw = (row.get("exclude_reason") or "").strip()
        if not raw:
            continue
        for part in raw.split(";"):
            key = part.strip()
            if key:
                counts[key] += 1
    return counts


def export_decision_audit(
    outdir: Path,
    spec: Dict[str, object],
    raw_rows: Sequence[Dict[str, str]],
    posts_clean_rows: Sequence[Dict[str, str]],
    posts_validated_rows: Sequence[Dict[str, str]],
    posts_prompt_rows: Sequence[Dict[str, str]],
    pew_rows: Sequence[Dict[str, str]],
) -> Path:
    now_utc = datetime.now(timezone.utc).isoformat()
    spec_meta = spec.get("metadata", {})
    spec_version = ""
    if isinstance(spec_meta, dict):
        spec_version = str(spec_meta.get("spec_version", ""))

    include_counts = Counter((r.get("include_for_rq3") or "").strip() for r in pew_rows)
    pew_exclude_counts = Counter((r.get("exclude_code") or "").strip() for r in pew_rows if (r.get("exclude_code") or "").strip())
    post_exclude_counts = count_exclude_reasons(posts_validated_rows)
    moderation_counts = Counter((r.get("moderation_status") or "").strip() for r in posts_validated_rows if (r.get("moderation_status") or "").strip())
    keep_counts = Counter((r.get("keep_for_prompt") or "").strip() for r in posts_validated_rows if (r.get("keep_for_prompt") or "").strip())

    pew_topic_counts = Counter(
        (r.get("issue_topic") or "").strip()
        for r in pew_rows
        if (r.get("include_for_rq3") or "").strip().lower() == "yes" and (r.get("issue_topic") or "").strip()
    )
    post_topic_counts = Counter((r.get("topic") or "").strip() for r in posts_prompt_rows if (r.get("topic") or "").strip())
    overlap_topics = sorted(set(pew_topic_counts) & set(post_topic_counts))

    lines: List[str] = []
    lines.append("# Decision Audit")
    lines.append("")
    lines.append(f"Generated (UTC): `{now_utc}`")
    if spec_version:
        lines.append(f"Rule spec version: `{spec_version}`")
    lines.append("")

    lines.append("## Stage Counts")
    lines.append("")
    stage_rows = [
        ["raw_input_rows", str(len(raw_rows))],
        ["posts_clean_rows", str(len(posts_clean_rows))],
        ["posts_topic_validated_rows", str(len(posts_validated_rows))],
        ["posts_prompt_ready_rows", str(len(posts_prompt_rows))],
        ["pew_rq3_rows", str(len(pew_rows))],
        ["pew_include_yes", str(include_counts.get("yes", 0))],
        ["pew_include_no", str(include_counts.get("no", 0))],
        ["hard_drop_inferred", str(max(0, len(raw_rows) - len(posts_clean_rows)))],
    ]
    lines.append(markdown_table(["metric", "value"], stage_rows))
    lines.append("")

    lines.append("## Post Exclusion Reasons")
    lines.append("")
    if post_exclude_counts:
        rows = [[k, str(v)] for k, v in post_exclude_counts.most_common()]
        lines.append(markdown_table(["exclude_reason", "count"], rows))
    else:
        lines.append("No post exclusion reasons found.")
    lines.append("")

    lines.append("## Post Keep and Moderation Counts")
    lines.append("")
    if keep_counts:
        rows = [[k, str(v)] for k, v in sorted(keep_counts.items())]
        lines.append(markdown_table(["keep_for_prompt", "count"], rows))
    else:
        lines.append("No keep_for_prompt values found.")
    lines.append("")

    if moderation_counts:
        rows = [[k, str(v)] for k, v in sorted(moderation_counts.items())]
        lines.append(markdown_table(["moderation_status", "count"], rows))
    else:
        lines.append("No moderation_status values found.")
    lines.append("")

    lines.append("## PEW Exclusion Codes")
    lines.append("")
    if pew_exclude_counts:
        rows = [[k, str(v)] for k, v in pew_exclude_counts.most_common()]
        lines.append(markdown_table(["exclude_code", "count"], rows))
    else:
        lines.append("No PEW exclude_code values found.")
    lines.append("")

    lines.append("## Topic Overlap")
    lines.append("")
    if overlap_topics:
        rows = [
            [topic, str(pew_topic_counts.get(topic, 0)), str(post_topic_counts.get(topic, 0))]
            for topic in overlap_topics
        ]
        lines.append(markdown_table(["topic", "pew_included_rows", "prompt_ready_rows"], rows))
    else:
        lines.append("No overlap topics.")
    lines.append("")

    path = outdir / "decision_audit.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return path


def main() -> None:
    args = parse_args()
    spec_path = Path(args.spec)
    topic_spec_path = Path(args.topic_spec)
    outdir = Path(args.outdir)

    spec = load_spec(spec_path)

    raw_rows = read_many_csv_rows(args.raw, RAW_DEFAULTS)
    posts_clean_rows = read_csv_rows(Path(args.posts_clean))
    posts_validated_rows = read_csv_rows(Path(args.posts_validated))
    posts_prompt_rows = read_csv_rows(Path(args.posts_prompt))
    pew_rows = read_csv_rows(Path(args.pew_rq3))

    out_filter = export_filter_table(spec, outdir)
    out_topics = export_topic_patterns(outdir, topic_spec_path)
    out_anon = export_anonymization_rules(outdir)
    out_pew = export_pew_selection_rules(outdir)
    out_audit = export_decision_audit(
        outdir,
        spec,
        raw_rows,
        posts_clean_rows,
        posts_validated_rows,
        posts_prompt_rows,
        pew_rows,
    )

    print(f"Spec: {spec_path}")
    print(f"Topic spec: {topic_spec_path}")
    print(f"Output directory: {outdir}")
    print(f"Wrote: {out_filter}")
    print(f"Wrote: {out_topics}")
    print(f"Wrote: {out_anon}")
    print(f"Wrote: {out_pew}")
    print(f"Wrote: {out_audit}")


if __name__ == "__main__":
    main()
