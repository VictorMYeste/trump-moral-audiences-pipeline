#!/usr/bin/env python3
"""Preprocess Trump archive rows following preprocessing_protocol.md."""

# Simple explanation of this script (step by step):
# 1) Load the posts CSV and apply hard filters (retweets, minimum length, etc.).
# 2) Clean text (HTML, URLs, spaces) and derive metadata (role, moderation status).
# 3) Assign topics with rules, allow manual overrides, and mark ambiguous rows.
# 4) Anonymize text and drop rows not suitable for prompting.
# 5) Export multiple output layers (clean, labeled, validated, prompt_ready, moderation_analysis).

from __future__ import annotations

import argparse
import csv
import html
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Dict, List, Tuple


REQUIRED_SOURCE_COLUMNS = [
    "id",
    "text",
    "isRetweet",
    "isDeleted",
    "date",
    "isFlagged",
    "dominant_moral_dimension",
    "is_morally_relevant",
]

URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
WHITESPACE_RE = re.compile(r"\s+")
ALPHA_TOKEN_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
HANDLE_RE = re.compile(r"@[A-Za-z0-9_]{1,15}")
PUNCT_SPACE_RE = re.compile(r"\s+([,.;:!?])")
PLACEHOLDER_RE = re.compile(r"\[[^\]]+\]")

LOW_INFO_PATTERNS = [
    re.compile(r"^thank you[.! ]*$", re.IGNORECASE),
    re.compile(r"^true[.! ]*$", re.IGNORECASE),
    re.compile(r"^so true[.! ]*$", re.IGNORECASE),
    re.compile(r"^rigged[.! ]*$", re.IGNORECASE),
    re.compile(r"^vote[.! ]*$", re.IGNORECASE),
    re.compile(r"^great[.! ]*$", re.IGNORECASE),
]

TOPIC_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    (
        "immigration_border",
        re.compile(
            r"\b(border|immigration|immigrant|immigrants|migrant|migrants|asylum|"
            r"refugee|refugees|wall|dreamer|dreamers|ice)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "economy_jobs_trade",
        re.compile(
            r"\b(economy|economic|job|jobs|employment|unemployment|trade|tariff|tariffs|"
            r"tax|taxes|market|markets|manufacturing|manufacturer|manufacturers|"
            r"small business|small businesses|wage|wages|inflation)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "election_integrity_democracy",
        re.compile(
            r"\b(election|elections|vote|votes|voting|voter|voters|ballot|ballots|"
            r"mail[ -]?in|absentee|fraud|democracy|electoral|poll watcher|poll watchers)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "foreign_policy_national_security",
        re.compile(
            r"\b(china|iran|russia|north korea|nato|isis|afghanistan|iraq|syria|israel|"
            r"middle east|terror|terrorism|terrorist|terrorists|peace deal|foreign policy)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "crime_policing_criminal_justice",
        re.compile(
            r"\b(crime|police|law enforcement|criminal justice|justice|violent crime|"
            r"violent|murder|murders|homicide|riots|riot|looting|prison|jail|antifa)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "covid_public_health",
        re.compile(
            r"\b(covid|covid19|covid-19|coronavirus|virus|pandemic|vaccine|vaccines|"
            r"vaccination|cdc|fda|mask|masks|lockdown|lockdowns|ventilator|ventilators|"
            r"hospital|hospitals|health care|healthcare)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "judiciary_courts",
        re.compile(
            r"\b(court|courts|judge|judges|justice|justices|supreme court|scotus|"
            r"ruling|injunction|constitutional)\b",
            re.IGNORECASE,
        ),
    ),
]

ROLE_REPLACEMENTS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\bpresident[- ]elect trump\b"), "the president-elect"),
    (re.compile(r"(?i)\bpresident donald j\.? trump\b"), "the president"),
    (re.compile(r"(?i)\bpresident donald trump\b"), "the president"),
    (re.compile(r"(?i)\bpresident trump\b"), "the president"),
    (re.compile(r"(?i)\bcandidate donald j\.? trump\b"), "the candidate"),
    (re.compile(r"(?i)\bcandidate donald trump\b"), "the candidate"),
    (re.compile(r"(?i)\bcandidate trump\b"), "the candidate"),
]

IDENTITY_REPLACEMENTS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)@realdonaldtrump\b"), "[POLITICAL_ACTOR]"),
    (re.compile(r"(?i)\bdonald j\.? trump\b"), "[POLITICAL_ACTOR]"),
    (re.compile(r"(?i)\bdonald trump\b"), "[POLITICAL_ACTOR]"),
    (re.compile(r"(?i)\btrump\b"), "[POLITICAL_ACTOR]"),
]

CAMPAIGN_TAG_RE = re.compile(
    r"(?i)#?(maga|kag2020|marchfortrump|trump2020|trumppence|votetrump|americafirst)\b"
)

ALLOWLIST_REPLACEMENTS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)@WhiteHouse\b"), "the White House"),
    (re.compile(r"(?i)@CDCgov\b"), "CDC"),
    (re.compile(r"(?i)@CDC\b"), "CDC"),
    (re.compile(r"(?i)@US_FDA\b"), "FDA"),
    (re.compile(r"(?i)@FDA\b"), "FDA"),
    (re.compile(r"(?i)@DHSgov\b"), "DHS"),
    (re.compile(r"(?i)@ICEgov\b"), "ICE"),
]

IDENTITY_LEAK_PATTERNS = [
    re.compile(r"(?i)\btrump\b"),
    re.compile(r"(?i)\bdonald\b"),
    re.compile(r"(?i)@realdonaldtrump"),
    re.compile(r"(?i)#maga"),
    re.compile(r"(?i)#kag2020"),
    re.compile(r"(?i)#marchfortrump"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preprocess posts according to preprocessing_protocol.md"
    )
    parser.add_argument(
        "--input",
        default="data/raw/trump_archive_me2bert_filtered_2021.csv",
        help="Input CSV path",
    )
    parser.add_argument(
        "--outdir",
        default="data/interim/preprocessing",
        help="Output directory for staged CSV files",
    )
    parser.add_argument(
        "--manual-review-csv",
        default="",
        help=(
            "Optional CSV for manual topic-review overrides keyed by id. "
            "Supported columns: id,topic,topic_confidence,review_flag,exclude_reason_add"
        ),
    )
    return parser.parse_args()


def csv_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "t", "1", "yes"}


def parse_yyyy_mm_dd(date_value: str) -> date:
    return date.fromisoformat(date_value[:10])


def derive_role(row_date: date) -> str:
    if date(2009, 5, 12) <= row_date <= date(2015, 6, 15):
        return "public_figure"
    if date(2015, 6, 16) <= row_date <= date(2016, 11, 8):
        return "candidate"
    if date(2016, 11, 9) <= row_date <= date(2017, 1, 19):
        return "president_elect"
    if date(2017, 1, 20) <= row_date <= date(2021, 1, 8):
        return "sitting_president"
    return "out_of_range"


def derive_moderation_status(is_deleted: bool, is_flagged: bool) -> str:
    if is_deleted and is_flagged:
        return "deleted_and_flagged"
    if is_deleted:
        return "deleted"
    if is_flagged:
        return "flagged"
    return "not_deleted_not_flagged"


def clean_text(raw_text: str) -> Tuple[str, str, str]:
    text_html_decoded = html.unescape(raw_text or "")
    text_no_url = URL_RE.sub("", text_html_decoded)
    text_clean = WHITESPACE_RE.sub(" ", text_no_url).strip()
    return text_html_decoded, text_no_url, text_clean


def alpha_token_count(text_value: str) -> int:
    return len(ALPHA_TOKEN_RE.findall(text_value))


def is_low_information(text_value: str) -> bool:
    return any(pattern.match(text_value) for pattern in LOW_INFO_PATTERNS)


def detect_topics(text_value: str) -> List[str]:
    matched = []
    for topic_name, pattern in TOPIC_PATTERNS:
        if pattern.search(text_value):
            matched.append(topic_name)
    return matched


def anonymize_text(text_value: str) -> str:
    output = text_value
    for pattern, replacement in ROLE_REPLACEMENTS:
        output = pattern.sub(replacement, output)
    for pattern, replacement in IDENTITY_REPLACEMENTS:
        output = pattern.sub(replacement, output)
    output = CAMPAIGN_TAG_RE.sub("[CAMPAIGN_TAG]", output)
    for pattern, replacement in ALLOWLIST_REPLACEMENTS:
        output = pattern.sub(replacement, output)
    output = HANDLE_RE.sub("[USER]", output)
    output = WHITESPACE_RE.sub(" ", output)
    output = PUNCT_SPACE_RE.sub(r"\1", output)
    output = output.strip()
    return output


def has_identity_leak(text_value: str) -> bool:
    return any(pattern.search(text_value) for pattern in IDENTITY_LEAK_PATTERNS)


def add_exclude_reason(row: Dict[str, str], reason: str) -> None:
    existing = row.get("exclude_reason", "").strip()
    if not existing:
        row["exclude_reason"] = reason
        return
    parts = existing.split(";")
    if reason not in parts:
        row["exclude_reason"] = existing + ";" + reason


def row_fieldnames(base_fields: List[str]) -> List[str]:
    derived = [
        "year",
        "month",
        "role",
        "moderation_status",
        "text_html_decoded",
        "text_no_url",
        "text_clean",
        "review_flag",
        "topic_candidates",
        "topic",
        "topic_confidence",
        "keep_for_prompt",
        "exclude_reason",
        "text_anon",
    ]
    return base_fields + [field for field in derived if field not in base_fields]


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_manual_overrides(path_value: str) -> Dict[str, Dict[str, str]]:
    if not path_value:
        return {}
    path = Path(path_value)
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "id" not in reader.fieldnames:
            raise ValueError("manual-review CSV must include an 'id' column")
        overrides: Dict[str, Dict[str, str]] = {}
        for row in reader:
            row_id = (row.get("id") or "").strip()
            if not row_id:
                continue
            overrides[row_id] = row
    return overrides


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    with input_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("Input CSV has no header")
        missing = [col for col in REQUIRED_SOURCE_COLUMNS if col not in reader.fieldnames]
        if missing:
            raise ValueError(f"Input CSV missing required columns: {', '.join(missing)}")
        base_fields = list(reader.fieldnames)
        out_fields = row_fieldnames(base_fields)
        source_rows = list(reader)
    manual_overrides = load_manual_overrides(args.manual_review_csv)

    hard_drop_counts: Counter[str] = Counter()
    clean_rows: List[Dict[str, str]] = []

    for raw in source_rows:
        row = dict(raw)
        row_date = parse_yyyy_mm_dd(row["date"])
        is_morally_relevant = csv_bool(row["is_morally_relevant"])
        is_retweet = csv_bool(row["isRetweet"])
        is_deleted = csv_bool(row["isDeleted"])
        is_flagged = csv_bool(row["isFlagged"])
        raw_text = row.get("text", "")

        row["year"] = str(row_date.year)
        row["month"] = f"{row_date.month:02d}"
        row["role"] = derive_role(row_date)
        row["moderation_status"] = derive_moderation_status(is_deleted, is_flagged)
        row["review_flag"] = ""
        row["topic_candidates"] = ""
        row["topic"] = ""
        row["topic_confidence"] = ""
        row["keep_for_prompt"] = "no"
        row["exclude_reason"] = ""
        row["text_anon"] = ""

        if not is_morally_relevant:
            hard_drop_counts["not_morally_relevant"] += 1
            continue

        if is_retweet or raw_text.startswith("RT @"):
            hard_drop_counts["retweet"] += 1
            continue

        text_html_decoded, text_no_url, text_clean = clean_text(raw_text)
        row["text_html_decoded"] = text_html_decoded
        row["text_no_url"] = text_no_url
        row["text_clean"] = text_clean

        if len(text_clean) < 40:
            hard_drop_counts["too_short_after_url_strip"] += 1
            continue

        if alpha_token_count(text_clean) < 7:
            hard_drop_counts["too_few_tokens"] += 1
            continue

        if is_low_information(text_clean):
            hard_drop_counts["low_information_text"] += 1
            continue

        if "..." in text_clean or "\u2026" in text_clean:
            row["review_flag"] = "truncated_text"

        if row["role"] == "out_of_range":
            add_exclude_reason(row, "role_out_of_range")

        clean_rows.append(row)

    # Step 4 output snapshot (pre-topic labeling).
    posts_clean = [dict(row) for row in clean_rows]

    # Step 5: auto-label topics.
    for row in clean_rows:
        topic_hits = detect_topics(row["text_clean"])
        row["topic_candidates"] = "|".join(topic_hits)
        if len(topic_hits) == 1:
            row["topic"] = topic_hits[0]
            row["topic_confidence"] = "high"
        elif len(topic_hits) > 1:
            row["topic"] = "review_needed"
            row["topic_confidence"] = "medium"
        else:
            row["topic"] = "other_campaign_generic"
            row["topic_confidence"] = "low"

    posts_topic_labeled = [dict(row) for row in clean_rows]

    # Manual review overrides between labeled and validated stages.
    for row in clean_rows:
        override = manual_overrides.get(row["id"])
        if not override:
            continue

        new_topic = (override.get("topic") or "").strip()
        if new_topic:
            row["topic"] = new_topic

        new_topic_conf = (override.get("topic_confidence") or "").strip()
        if new_topic_conf:
            row["topic_confidence"] = new_topic_conf

        # Empty string explicitly clears review_flag.
        if "review_flag" in override:
            row["review_flag"] = (override.get("review_flag") or "").strip()

        exclude_reason_add = (override.get("exclude_reason_add") or "").strip()
        if exclude_reason_add:
            add_exclude_reason(row, exclude_reason_add)

    # Step 6 + Step 7 + Step 8 + Step 9.
    for row in clean_rows:
        row["text_anon"] = anonymize_text(row["text_clean"])

        if has_identity_leak(row["text_anon"]):
            add_exclude_reason(row, "identity_leak_after_anonymization")

        anon_token_count = alpha_token_count(row["text_anon"])
        placeholder_count = len(PLACEHOLDER_RE.findall(row["text_anon"]))
        if (
            len(row["text_anon"]) < 40
            or anon_token_count < 7
            or (len(row["text_anon"]) <= 80 and placeholder_count > 3)
        ):
            add_exclude_reason(row, "anonymization_degraded_text")

        if row["topic"] == "other_campaign_generic":
            add_exclude_reason(row, "other_campaign_generic")

        if row["topic"] == "review_needed":
            add_exclude_reason(row, "multi_topic_ambiguous")

        if row["review_flag"]:
            add_exclude_reason(row, "truncated_or_context_dependent")

        if row["moderation_status"] != "not_deleted_not_flagged":
            add_exclude_reason(row, "excluded_from_prompt_due_to_moderation_status")

        if row["exclude_reason"] == "":
            row["keep_for_prompt"] = "yes"
        else:
            row["keep_for_prompt"] = "no"

    posts_topic_validated = [dict(row) for row in clean_rows]
    validated_by_id = {row["id"]: row for row in posts_topic_validated}

    # QC 11.5: de-duplicate final prompt-ready by normalized anonymized text.
    prompt_candidates = [row for row in clean_rows if row["keep_for_prompt"] == "yes"]
    prompt_candidates.sort(key=lambda r: (r["text_anon"].lower().strip(), r["date"], r["id"]))

    seen_normalized: Dict[str, str] = {}
    for row in prompt_candidates:
        normalized = row["text_anon"].lower().strip()
        row_id = row["id"]
        if normalized not in seen_normalized:
            seen_normalized[normalized] = row_id
            continue
        row["keep_for_prompt"] = "no"
        add_exclude_reason(row, "duplicate_after_cleaning")
        validated_row = validated_by_id.get(row_id)
        if validated_row is not None:
            validated_row["keep_for_prompt"] = "no"
            add_exclude_reason(validated_row, "duplicate_after_cleaning")

    posts_prompt_ready = [row for row in clean_rows if row["keep_for_prompt"] == "yes"]
    posts_moderation_analysis = [dict(row) for row in posts_topic_validated]

    write_csv(outdir / "posts_clean.csv", posts_clean, out_fields)
    write_csv(outdir / "posts_topic_labeled.csv", posts_topic_labeled, out_fields)
    write_csv(outdir / "posts_topic_validated.csv", posts_topic_validated, out_fields)
    write_csv(outdir / "posts_prompt_ready.csv", posts_prompt_ready, out_fields)
    write_csv(
        outdir / "posts_moderation_analysis.csv",
        posts_moderation_analysis,
        out_fields,
    )

    print(f"Input rows: {len(source_rows)}")
    print(f"Rows after hard filters (posts_clean): {len(posts_clean)}")
    print(f"Rows in posts_topic_labeled: {len(posts_topic_labeled)}")
    print(f"Rows in posts_topic_validated: {len(posts_topic_validated)}")
    print(f"Rows in posts_prompt_ready: {len(posts_prompt_ready)}")
    print(f"Rows in posts_moderation_analysis: {len(posts_moderation_analysis)}")
    if manual_overrides:
        print(f"Manual overrides applied: {len(manual_overrides)}")
    print("Hard-filter drops:")
    for reason, count in sorted(hard_drop_counts.items()):
        print(f"  {reason}: {count}")

    topic_counts = Counter(row["topic"] for row in posts_topic_validated)
    moderation_counts = Counter(row["moderation_status"] for row in posts_topic_validated)
    keep_counts = Counter(row["keep_for_prompt"] for row in posts_topic_validated)
    print("Validated topic counts:")
    for topic, count in sorted(topic_counts.items()):
        print(f"  {topic}: {count}")
    print("Moderation status counts:")
    for status, count in sorted(moderation_counts.items()):
        print(f"  {status}: {count}")
    print("keep_for_prompt counts:")
    for status, count in sorted(keep_counts.items()):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
