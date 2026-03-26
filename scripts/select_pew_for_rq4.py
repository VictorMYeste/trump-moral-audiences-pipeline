#!/usr/bin/env python3
"""Build a minimal, deterministic PEW inventory for RQ4 without manual columns."""

# Simple explanation of this script (step by step):
# 1) Read the master PEW inventory.
# 2) Detect whether each question targets Trump and what judgment type it uses.
# 3) Exclude formats that are not comparable (thermometer, traits, affective reactions, etc.).
# 4) Assign an issue topic when there is a single clear match.
# 5) Set `include_for_rq4` with deterministic rules and keep decision traces.

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple


INPUT_DEFAULT = "data/interim/pew/pew_question_inventory.csv"
OUTPUT_DEFAULT = "data/interim/pew/pew_rq4_inventory.csv"

ALLOWED_JUDGMENTS = {"approval", "confidence", "policy_support"}

TRUMP_DIRECT_RE = re.compile(r"\b(trump|donald|president[- ]elect)\b", re.IGNORECASE)
PRESIDENT_REF_RE = re.compile(r"\b(the )?president\b", re.IGNORECASE)
TRUMP_CONTEXT_HINT_RE = re.compile(
    r"\b(impeach|impeachment|white house|administration|inquiry|job approval|job as president)\b",
    re.IGNORECASE,
)

THERMOMETER_RE = re.compile(r"\bthermometer\b|\b0\s*(to|-)\s*100\b", re.IGNORECASE)
TRAIT_RE = re.compile(
    r"\b(honest|keeps? promises?|mentally sharp|even[- ]tempered|describe\s+donald trump)\b",
    re.IGNORECASE,
)
AFFECT_RE = re.compile(
    r"\b(feel|frustrated|angry|hopeful|proud|surprised|excited|upset)\b", re.IGNORECASE
)
KNOWLEDGE_RE = re.compile(
    r"\b(how much have you heard|as far as you know|know enough)\b", re.IGNORECASE
)
BROAD_FAVORABILITY_RE = re.compile(r"\b(favorable|unfavorable|favorability)\b", re.IGNORECASE)

APPROVAL_RE = re.compile(r"\bapprove or disapprove\b|\bapprove\b.*\bdisapprove\b", re.IGNORECASE)
CONFIDENCE_RE = re.compile(r"\bhow confident are you\b|\bconfidence\b", re.IGNORECASE)
FAVOR_OPPOSE_RE = re.compile(r"\bfavor or oppose\b|\bfavor\b.*\boppose\b", re.IGNORECASE)
SUPPORT_OPPOSE_RE = re.compile(
    r"\bsupport or oppose\b|\bsupport\b.*\boppose\b", re.IGNORECASE
)

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Select a minimal, deterministic PEW inventory for RQ4 from merged "
            "pew_question_inventory.csv."
        )
    )
    parser.add_argument("--input", default=INPUT_DEFAULT, help="Merged inventory CSV input")
    parser.add_argument("--output", default=OUTPUT_DEFAULT, help="Output CSV path")
    parser.add_argument(
        "--only-included",
        action="store_true",
        help="Write only rows with include_for_rq4=yes",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting output if it exists",
    )
    return parser.parse_args()


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def is_trump_target(text: str, variable_name: str) -> Tuple[bool, str]:
    hay = f"{variable_name} {text}"
    if TRUMP_DIRECT_RE.search(hay):
        return True, "trump_direct"
    if PRESIDENT_REF_RE.search(hay) and TRUMP_CONTEXT_HINT_RE.search(hay):
        return True, "president_context"
    return False, "not_trump_target"


def excluded_form_code(text: str) -> str:
    if THERMOMETER_RE.search(text):
        return "exclude_thermometer"
    if TRAIT_RE.search(text):
        return "exclude_trait"
    if AFFECT_RE.search(text):
        return "exclude_affective_reaction"
    if KNOWLEDGE_RE.search(text):
        return "exclude_knowledge_or_awareness"
    if BROAD_FAVORABILITY_RE.search(text):
        return "exclude_broad_favorability"
    return ""


def infer_judgment_family(text: str) -> Tuple[str, str]:
    if APPROVAL_RE.search(text):
        return "approval", "approve_disapprove"
    if CONFIDENCE_RE.search(text):
        return "confidence", "very_somewhat_not_too_not_at_all_confident"
    if FAVOR_OPPOSE_RE.search(text):
        return "policy_support", "favor_oppose"
    if SUPPORT_OPPOSE_RE.search(text):
        return "policy_support", "support_oppose"
    return "other", "unknown"


def infer_issue_topic(text: str, variable_name: str) -> Tuple[str, List[str]]:
    hay = f"{variable_name} {text}"
    hits: List[str] = []
    for topic, pattern in TOPIC_PATTERNS:
        if pattern.search(hay):
            hits.append(topic)
    return ("", hits) if len(hits) != 1 else (hits[0], hits)


def select_row(row: Dict[str, str]) -> Dict[str, str]:
    text = normalize_whitespace(row.get("question_text_raw", ""))
    variable_name = row.get("variable_name", "")

    output = dict(row)
    output["question_text_raw"] = text
    output["response_scale_raw"] = ""
    output["judgment_family"] = ""
    output["issue_topic"] = ""
    output["include_for_rq4"] = "no"
    output["exclude_code"] = ""
    output["rule_trace"] = ""

    trace: List[str] = []
    judgment_family, response_scale = infer_judgment_family(text)
    output["judgment_family"] = judgment_family
    output["response_scale_raw"] = response_scale
    trace.append(f"judgment:{judgment_family}")
    issue_topic, topic_hits = infer_issue_topic(text, variable_name)
    output["issue_topic"] = issue_topic
    trace.append(f"topic_hits:{'|'.join(topic_hits) if topic_hits else 'none'}")

    trump_ok, trump_trace = is_trump_target(text, variable_name)
    trace.append(trump_trace)
    if not trump_ok:
        output["exclude_code"] = "exclude_not_trump_target"
        output["rule_trace"] = ";".join(trace)
        return output

    excluded_code = excluded_form_code(text)
    if excluded_code:
        trace.append(excluded_code)
        output["exclude_code"] = excluded_code
        output["rule_trace"] = ";".join(trace)
        return output

    if judgment_family not in ALLOWED_JUDGMENTS:
        output["exclude_code"] = "exclude_judgment_not_supported"
        output["rule_trace"] = ";".join(trace)
        return output
    if response_scale == "unknown":
        output["exclude_code"] = "exclude_unknown_response_scale"
        output["rule_trace"] = ";".join(trace)
        return output

    if not issue_topic:
        if len(topic_hits) == 0:
            output["exclude_code"] = "exclude_no_topic_match"
        else:
            output["exclude_code"] = "exclude_multi_topic_ambiguous"
        output["rule_trace"] = ";".join(trace)
        return output

    output["issue_topic"] = issue_topic
    trace.append(f"topic:{issue_topic}")

    output["include_for_rq4"] = "yes"
    output["exclude_code"] = ""
    output["rule_trace"] = ";".join(trace)
    return output


def read_rows(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Input CSV has no header: {path}")
        return list(reader.fieldnames), list(reader)


def write_rows(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if output_path.exists() and not args.overwrite:
        raise FileExistsError(
            f"Output already exists: {output_path}. Use --overwrite to replace it."
        )

    input_fieldnames, rows = read_rows(input_path)
    selected = [select_row(row) for row in rows]
    if args.only_included:
        selected = [row for row in selected if row["include_for_rq4"] == "yes"]

    fieldnames = list(input_fieldnames)
    for col in [
        "response_scale_raw",
        "judgment_family",
        "issue_topic",
        "include_for_rq4",
        "exclude_code",
        "rule_trace",
    ]:
        if col not in fieldnames:
            fieldnames.append(col)
    write_rows(output_path, selected, fieldnames)

    include_counts = Counter(row["include_for_rq4"] for row in selected)
    exclude_counts = Counter(row["exclude_code"] for row in selected if row["exclude_code"])
    judgment_counts = Counter(row["judgment_family"] for row in selected)
    topic_counts = Counter(
        row["issue_topic"]
        for row in selected
        if row["include_for_rq4"] == "yes" and row["issue_topic"]
    )

    print(f"Input rows: {len(rows)}")
    print(f"Output rows: {len(selected)}")
    print("include_for_rq4 counts:")
    for key, val in sorted(include_counts.items()):
        print(f"  {key}: {val}")
    print("Top exclude_code counts:")
    for key, val in exclude_counts.most_common(15):
        print(f"  {key}: {val}")
    print("Judgment family counts:")
    for key, val in sorted(judgment_counts.items()):
        print(f"  {key}: {val}")
    print("Included topic counts:")
    for key, val in sorted(topic_counts.items()):
        print(f"  {key}: {val}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
