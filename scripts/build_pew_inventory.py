#!/usr/bin/env python3
"""Build a partial PEW question inventory CSV for one ATP wave folder."""

# Simple explanation of this script (step by step):
# 1) Read one PEW wave folder (readme + .sav and, optionally, the codebook PDF).
# 2) Extract variable names and question text automatically.
# 3) Clean noisy text and apply filters (for example: Trump-only, no weights, no cross-wave).
# 4) Build rows using a single minimal schema.
# 5) Write `pew_question_inventory_partial.csv` for that wave.

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple
from xml.etree import ElementTree as ET


CODEBOOK_DEFAULT = "data/pew_datasets/Codebook-and-instructions-for-working-with-ATP-data.pdf"
INVENTORY_HEADER = [
    "inventory_id",
    "pew_wave",
    "field_dates",
    "dataset_file",
    "variable_name",
    "question_text_raw",
]

WAVE_FROM_FOLDER_RE = re.compile(r"^W(?P<wave>\d+(?:\.\d+)?)", re.IGNORECASE)

WAVE_LINE_RE = re.compile(
    r"Wave\s+(?P<wave>\d+(?:\.\d+)?)\s+American Trends Panel", re.IGNORECASE
)
DATE_LINE_RE = re.compile(r"^\s*Dates:\s*(?P<dates>.+?)\s*$", re.IGNORECASE)
RELEASE_TITLE_RE = re.compile(
    r'^\s*[A-Za-z]+\s+\d{1,2},\s+\d{4}\s+"(?P<title>[^"]+)"\s*$'
)
URL_RE = re.compile(r"^\s*https?://\S+\s*$", re.IGNORECASE)

VAR_SUFFIX_RE = re.compile(
    r"\b(?P<var>[A-Za-z][A-Za-z0-9_]*_W\d+(?:_[A-Za-z0-9_]*W?\d+)*)\b"
)
VAR_LABEL_ANY_RE = re.compile(
    r"^\W*(?P<var>[A-Za-z][A-Za-z0-9_]{1,63})\.\s*(?P<label>.*)$"
)
VAR_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{1,63}$")
CODE_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,}(?:_[A-Za-z0-9]{1,})+\S*")
GENERIC_VAR_TOKEN_RE = re.compile(r"\b(?:F_[A-Za-z0-9_]+|[A-Z][A-Z0-9]{1,}_[A-Za-z0-9_]+)\b")
TRAILING_VAR_FRAGMENT_RE = re.compile(r"\s+[A-Z][A-Z0-9_]{2,}[}\]>.,:;]*\s*$")
TRAILING_TOKEN_RE = re.compile(
    r"\b(?P<tok>[A-Za-z][A-Za-z0-9_]{3,})(?:\s+\d+)?(?:\s*[^\w\s]+)?\s*$"
)
PAREN_VAR_LABEL_RE = re.compile(r"\s+\([A-Z][A-Z0-9]{4,}\.\s*")
SAFE_TRAILING_UPPER_TOKENS = {
    "TRUMP",
    "BIDEN",
    "HARRIS",
    "CLINTON",
    "PRESIDENT",
    "AMERICA",
    "AMERICAN",
    "REPUBLICAN",
    "DEMOCRAT",
    "CONGRESS",
    "SUPREME",
    "COURT",
    "GOP",
}

PROFILE_GLOSSARY_MARKERS = [
    "Metropolitan area indicator",
    "Census region",
    "Census division",
    "Age category",
    "Education level category",
    "Includes RACE backcodes",
    "Combining race",
    "Race-Ethnicity",
    "NATIVITY.",
]
PROFILE_VAR_RE = re.compile(r"\bF_[A-Z0-9_]+\b")
PROFILE_HEADING_RE = re.compile(r"^F_[A-Z0-9_]+$")
DOCX_MAIN_XML = "word/document.xml"
MONTH_NAME_RE = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"
)
DATE_TOKEN_RE = rf"{MONTH_NAME_RE}\s+\d{{1,2}},\s+\d{{4}}"
DATE_BETWEEN_RE = re.compile(
    rf"\bbetween\s+(?P<start>{DATE_TOKEN_RE})\s*,?\s+and\s+(?P<end>{DATE_TOKEN_RE})\b",
    re.IGNORECASE,
)
DATE_FROM_TO_RE = re.compile(
    rf"\bfrom\s+(?P<start>{DATE_TOKEN_RE})\s*,?\s+to\s+(?P<end>{DATE_TOKEN_RE})\b",
    re.IGNORECASE,
)
TRUMP_RELATED_PATTERNS = [
    re.compile(r"\btrump\b", re.IGNORECASE),
    re.compile(r"\bpresident[- ]elect\b", re.IGNORECASE),
    re.compile(r"\bwhite\s+house\b", re.IGNORECASE),
    re.compile(r"\bimpeach(?:ment|ed|ing)?\b", re.IGNORECASE),
    re.compile(r"\bbiden\b", re.IGNORECASE),
    re.compile(r"\bkamala\b", re.IGNORECASE),
    re.compile(r"\bkamala\s+harris\b", re.IGNORECASE),
    re.compile(r"\bbiden[- ]harris\b", re.IGNORECASE),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a partially filled PEW question inventory CSV from one wave folder."
        )
    )
    parser.add_argument(
        "--wave-folder",
        required=True,
        help="Path to one wave folder (e.g., data/pew_datasets/W55_Oct19)",
    )
    parser.add_argument(
        "--codebook-pdf",
        default=CODEBOOK_DEFAULT,
        help=(
            "Path to ATP codebook PDF for extracting F_ profile variables and "
            "glossary markers"
        ),
    )
    parser.add_argument(
        "--output",
        default="",
        help=(
            "Output CSV path. Default: <wave-folder>/pew_question_inventory_partial.csv"
        ),
    )
    parser.add_argument(
        "--trump-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Keep only rows where variable/question text includes Trump-related "
            "keywords (default: enabled; use --no-trump-only to disable)"
        ),
    )
    parser.add_argument(
        "--include-weights",
        action="store_true",
        help="Include WEIGHT_* variables (excluded by default)",
    )
    parser.add_argument(
        "--include-cross-wave",
        action="store_true",
        help=(
            "Include variables that only reference non-current wave suffixes "
            "(excluded by default)"
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting output file if it already exists",
    )
    return parser.parse_args()


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def is_plausible_variable_name(token: str) -> bool:
    value = token.strip()
    if not VAR_NAME_RE.fullmatch(value):
        return False
    upper = value.upper()
    if upper in {"HTTP", "HTTPS", "WWW", "COM", "ORG", "NET"}:
        return False
    has_digit = any(ch.isdigit() for ch in value)
    has_underscore = "_" in value
    # Accept classic ATP variable IDs (uppercase), plus mixed-case IDs with
    # underscores/digits (e.g., EN6F1count_W55).
    if value.isupper() or has_digit or has_underscore:
        return True
    return False


def is_likely_question_text_noise(text: str) -> bool:
    low = text.lower()
    tokens = re.findall(r"[A-Za-z]+", text)
    if len(tokens) < 4:
        return False
    long_tokens = [t for t in tokens if len(t) >= 5]
    if len(long_tokens) < 3:
        return False

    no_vowel = sum(1 for t in long_tokens if not re.search(r"[aeiou]", t, re.IGNORECASE))
    repeated = sum(1 for t in long_tokens if re.search(r"(.)\1\1", t, re.IGNORECASE))

    no_vowel_ratio = no_vowel / len(long_tokens)
    repeated_ratio = repeated / len(long_tokens)

    if no_vowel_ratio >= 0.65:
        return True
    if repeated_ratio >= 0.45:
        return True
    if no_vowel_ratio >= 0.45 and repeated_ratio >= 0.20:
        return True
    # Value-label dumps occasionally leak from SPSS binary strings.
    if "don't know/refused/web blank" in low:
        return True
    if (
        "lean more toward" in low
        and "none/other candidate" in low
        and "don't know/refused" in low
    ):
        return True
    return False


def is_probable_leaked_variable_token(token: str, current_var: str) -> bool:
    tok = token.strip()
    if not tok:
        return False
    if tok.upper() == (current_var or "").upper():
        return False
    if "_" in tok or any(ch.isdigit() for ch in tok):
        return True
    if tok.isupper() and len(tok) >= 5 and tok not in SAFE_TRAILING_UPPER_TOKENS:
        return True

    upper = sum(1 for ch in tok if ch.isupper())
    lower = sum(1 for ch in tok if ch.islower())
    if len(tok) >= 6 and upper >= 4 and lower >= 1:
        return True

    # All-uppercase leaked tokens without separators are rare but possible.
    if len(tok) >= 10 and upper == len(tok) and re.search(r"[bcdfghjklmnpqrstvwxyz]{6,}", tok, re.I):
        return True
    return False


def is_temporary_office_file(path: Path) -> bool:
    return path.name.startswith("~$")


def find_readme_txt_case_insensitive(root: Path) -> Path | None:
    matches = sorted(
        (
            p
            for p in root.iterdir()
            if p.is_file() and p.suffix.lower() == ".txt" and "readme" in p.name.lower()
        ),
        key=lambda p: p.name.lower(),
    )
    if not matches:
        return None
    return matches[0]


def extract_text_from_docx(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            if DOCX_MAIN_XML not in zf.namelist():
                return ""
            xml_bytes = zf.read(DOCX_MAIN_XML)
    except Exception:
        return ""

    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return ""

    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    chunks = [node.text for node in root.findall(".//w:t", ns) if node.text]
    return normalize_whitespace(" ".join(chunks))


def infer_field_dates_from_wave_docs(wave_folder: Path) -> str:
    docx_files = sorted(
        [
            p
            for p in wave_folder.iterdir()
            if p.is_file()
            and p.suffix.lower() == ".docx"
            and not is_temporary_office_file(p)
        ],
        key=lambda p: p.name.lower(),
    )
    if not docx_files:
        return ""

    for docx_path in docx_files:
        text = extract_text_from_docx(docx_path)
        if not text:
            continue

        # Prefer the "most respondents completed ... between ..." range when present.
        idx = text.lower().find("most respondents completed")
        if idx != -1:
            focused = text[idx : idx + 500]
            m_between = DATE_BETWEEN_RE.search(focused)
            if m_between:
                start = normalize_whitespace(m_between.group("start"))
                end = normalize_whitespace(m_between.group("end"))
                return f"{start} - {end}"

        m_between = DATE_BETWEEN_RE.search(text)
        if m_between:
            start = normalize_whitespace(m_between.group("start"))
            end = normalize_whitespace(m_between.group("end"))
            return f"{start} - {end}"

        m_from_to = DATE_FROM_TO_RE.search(text)
        if m_from_to:
            start = normalize_whitespace(m_from_to.group("start"))
            end = normalize_whitespace(m_from_to.group("end"))
            return f"{start} - {end}"

    return ""


def find_sav_case_insensitive(root: Path) -> Path | None:
    matches = sorted(
        (p for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".sav"),
        key=lambda p: p.name.lower(),
    )
    if not matches:
        return None
    return matches[0]


def infer_wave_from_folder_name(folder_name: str) -> str:
    m = WAVE_FROM_FOLDER_RE.match(folder_name.strip())
    if not m:
        return ""
    return m.group("wave")


def parse_readme(readme_path: Path) -> Dict[str, object]:
    text = readme_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    wave = ""
    field_dates = ""
    report_titles: List[str] = []
    report_urls: List[str] = []
    vars_from_readme: set[str] = set()

    for line in lines:
        if not wave:
            m_wave = WAVE_LINE_RE.search(line)
            if m_wave:
                wave = m_wave.group("wave")
        if not field_dates:
            m_date = DATE_LINE_RE.search(line)
            if m_date:
                field_dates = normalize_whitespace(m_date.group("dates"))

        m_release = RELEASE_TITLE_RE.search(line)
        if m_release:
            report_titles.append(normalize_whitespace(m_release.group("title")))

        if URL_RE.search(line):
            report_urls.append(normalize_whitespace(line))

        for var_match in VAR_SUFFIX_RE.finditer(line):
            vars_from_readme.add(var_match.group("var"))

    return {
        "wave": wave,
        "field_dates": field_dates,
        "report_titles": report_titles,
        "report_urls": report_urls,
        "vars_from_readme": sorted(vars_from_readme),
    }


def compile_glossary_regex(markers: List[str]) -> re.Pattern[str]:
    if not markers:
        return re.compile(r"$^")
    return re.compile("|".join(re.escape(marker) for marker in markers), re.IGNORECASE)


def compile_profile_var_regex(profile_vars: set[str]) -> re.Pattern[str]:
    if not profile_vars:
        return PROFILE_VAR_RE
    tokens = sorted(profile_vars, key=len, reverse=True)
    return re.compile(r"\b(?:%s)\b" % "|".join(re.escape(token) for token in tokens))


def extract_profile_metadata_from_codebook(
    codebook_path: Path,
) -> Tuple[set[str], List[str], str]:
    if not codebook_path.exists():
        return set(), [], "missing"

    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return set(), [], "pypdf_unavailable"

    try:
        reader = PdfReader(str(codebook_path))
    except Exception:
        return set(), [], "read_error"

    full_text_parts: List[str] = []
    for page in reader.pages:
        full_text_parts.append(page.extract_text() or "")
    full_text = "\n".join(full_text_parts)

    profile_vars = set(PROFILE_VAR_RE.findall(full_text))
    markers = set(PROFILE_GLOSSARY_MARKERS)
    lines = [normalize_whitespace(line) for line in full_text.splitlines()]

    for idx, line in enumerate(lines):
        if not PROFILE_HEADING_RE.fullmatch(line):
            continue
        for next_line in lines[idx + 1 : idx + 7]:
            if not next_line:
                continue
            if PROFILE_HEADING_RE.fullmatch(next_line):
                break
            if re.fullmatch(r"\d+.*", next_line):
                continue
            if next_line.startswith("ASK IF") or next_line.startswith("What is your"):
                continue
            if next_line.isupper():
                continue
            if len(next_line) < 8:
                continue
            markers.add(next_line.rstrip("."))
            break

    return profile_vars, sorted(markers), "loaded"


def run_strings(path: Path, min_len: int = 8) -> List[str]:
    # `strings` is available in this environment and gives us labels from .sav binaries.
    result = subprocess.run(
        ["strings", "-n", str(min_len), str(path)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.splitlines()


def is_wave_variable(var_name: str, wave_number: str) -> bool:
    if not var_name:
        return False
    if var_name.startswith("WEIGHT_"):
        return True
    suffixes = set(re.findall(r"_W(\d+(?:\.\d+)?)", var_name))
    if not suffixes:
        # Older ATP waves often use unsuffixed variable names.
        return True
    if not wave_number:
        return True
    return wave_number in suffixes


def clean_question_text(
    text: str,
    current_var: str,
    profile_glossary_re: re.Pattern[str],
    profile_var_token_re: re.Pattern[str],
) -> str:
    output = normalize_whitespace(text)
    if not output:
        return ""

    marker_match = profile_glossary_re.search(output)
    if marker_match and marker_match.start() > 0:
        output = output[: marker_match.start()].strip()

    # Cut at the first occurrence of another variable token that leaked in.
    for match in VAR_SUFFIX_RE.finditer(output):
        other_var = match.group("var")
        if other_var != current_var and match.start() > 0:
            output = output[: match.start()].strip()
            break

    # Cut when demographic profile variable-like tokens leak into question text.
    for match in profile_var_token_re.finditer(output):
        token = match.group(0)
        if token == current_var:
            continue
        if match.start() >= 20:
            output = output[: match.start()].strip()
            break

    # Cut when generic variable-like tokens leak into question text.
    for match in GENERIC_VAR_TOKEN_RE.finditer(output):
        token = match.group(0)
        if token == current_var:
            continue
        if match.start() >= 20:
            output = output[: match.start()].strip()
            break

    # Cut trailing code-like fragments such as EMTDEM_B>, V42_A v, CLIM6_W5e.
    for match in CODE_TOKEN_RE.finditer(output):
        if match.start() >= 20 or (match.start() == 0 and len(output) <= 30):
            output = output[: match.start()].strip()
            break
    # Cut parenthetical variable-code headers like "(CANDCNTCT. ...)" that leak in.
    paren_var_match = PAREN_VAR_LABEL_RE.search(output)
    if paren_var_match and paren_var_match.start() >= 20:
        output = output[: paren_var_match.start()].strip()

    # Remove common binary value-label prefixes leaking from SPSS strings output.
    output = re.sub(r"\s+@[\w-]+.*$", "", output).strip()
    output = re.sub(r"\s+@[^ \t\n\r\f\v].*$", "", output).strip()
    # Remove survey-template artifacts that are not part of the substantive prompt.
    output = re.sub(r"\bInsert\s+text(?:\s+for)?\b.*$", "", output, flags=re.IGNORECASE).strip()
    # Normalize a common truncated phrase from binary extraction artifacts.
    output = re.sub(r"\bif anyt(?:hing)?\s*$", "if anything", output, flags=re.IGNORECASE).strip()
    # Remove trailing fragments like "CLIM9F1 s" when they appear at the end.
    output = re.sub(r"\s+[A-Z][A-Z0-9]{2,}\s+[A-Za-z]\s*$", "", output).strip()
    output = TRAILING_VAR_FRAGMENT_RE.sub("", output).strip()
    trail = TRAILING_TOKEN_RE.search(output)
    if trail:
        tok = trail.group("tok")
        if is_probable_leaked_variable_token(tok, current_var):
            output = output[: trail.start()].rstrip()

    # Keep question text concise for manual review.
    output = output[:600].strip()
    return output


def extract_sav_question_labels(
    sav_path: Path,
    wave_number: str,
    profile_glossary_re: re.Pattern[str],
    profile_var_token_re: re.Pattern[str],
) -> Tuple[Dict[str, str], set[str]]:
    lines = run_strings(sav_path)
    labels: Dict[str, str] = {}
    variables_seen: set[str] = set()
    current_var = ""

    for raw in lines:
        line = normalize_whitespace(raw)
        if not line:
            continue

        label_match = VAR_LABEL_ANY_RE.match(line)
        if label_match:
            var = label_match.group("var")
            if not is_plausible_variable_name(var):
                current_var = ""
                continue
            if not is_wave_variable(var, wave_number):
                current_var = ""
                continue
            label_text = clean_question_text(
                label_match.group("label"),
                var,
                profile_glossary_re=profile_glossary_re,
                profile_var_token_re=profile_var_token_re,
            )
            if label_text and is_likely_question_text_noise(label_text):
                current_var = ""
                continue
            variables_seen.add(var)
            labels[var] = label_text
            current_var = var
            continue

        # Append wrapped label fragments for the current variable.
        if current_var:
            # Skip obvious non-label fragments.
            if re.fullmatch(r"[A-Z0-9_]{4,}", line):
                continue
            if line.startswith("$FL2@(#)") or "IBM SPSS" in line:
                continue
            if VAR_SUFFIX_RE.search(line):
                current_var = ""
                continue
            if profile_var_token_re.search(line):
                current_var = ""
                continue
            if GENERIC_VAR_TOKEN_RE.search(line):
                current_var = ""
                continue
            line_clean = clean_question_text(
                line,
                current_var,
                profile_glossary_re=profile_glossary_re,
                profile_var_token_re=profile_var_token_re,
            )
            if not line_clean:
                current_var = ""
                continue
            if is_likely_question_text_noise(line_clean):
                current_var = ""
                continue
            existing = labels.get(current_var, "")
            combined = clean_question_text(
                (existing + " " + line_clean).strip(),
                current_var,
                profile_glossary_re=profile_glossary_re,
                profile_var_token_re=profile_var_token_re,
            )
            if combined and is_likely_question_text_noise(combined):
                current_var = ""
                continue
            labels[current_var] = combined
            if line.endswith(("?", ".", ";")):
                current_var = ""

    # Trim noisy over-continued labels.
    for var, text in list(labels.items()):
        labels[var] = normalize_whitespace(text[:1200])

    return labels, variables_seen


def sanitize_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")

def is_trump_related(variable_name: str, question_text: str) -> bool:
    hay = f"{variable_name} {question_text}"
    return any(pattern.search(hay) for pattern in TRUMP_RELATED_PATTERNS)


def extract_wave_suffixes(variable_name: str) -> set[str]:
    return set(re.findall(r"_W(\d+(?:\.\d+)?)", variable_name))


def is_cross_wave_only(variable_name: str, wave_number: str) -> bool:
    if not wave_number:
        return False
    suffixes = extract_wave_suffixes(variable_name)
    if not suffixes:
        return False
    return wave_number not in suffixes


def should_keep_variable(
    variable_name: str,
    wave_number: str,
    include_weights: bool,
    include_cross_wave: bool,
) -> bool:
    if variable_name.startswith("WEIGHT_") and not include_weights:
        return False
    if is_cross_wave_only(variable_name, wave_number) and not include_cross_wave:
        return False
    return True


def make_inventory_row(
    wave_tag: str,
    field_dates: str,
    dataset_file: str,
    variable_name: str,
    question_text_raw: str,
) -> Dict[str, str]:
    row: Dict[str, str] = {key: "" for key in INVENTORY_HEADER}
    row["inventory_id"] = f"{sanitize_slug(wave_tag)}_{sanitize_slug(variable_name)}"
    row["pew_wave"] = wave_tag
    row["field_dates"] = field_dates
    row["dataset_file"] = dataset_file
    row["variable_name"] = variable_name
    row["question_text_raw"] = question_text_raw
    return row


def main() -> None:
    args = parse_args()
    wave_folder = Path(args.wave_folder)
    codebook_path = Path(args.codebook_pdf)
    if not wave_folder.exists():
        raise FileNotFoundError(f"Wave folder not found: {wave_folder}")

    output_path = (
        Path(args.output)
        if args.output
        else wave_folder / "pew_question_inventory_partial.csv"
    )
    if output_path.exists() and not args.overwrite:
        raise FileExistsError(
            f"Output already exists: {output_path}. Use --overwrite to replace it."
        )

    header = list(INVENTORY_HEADER)
    readme_path = find_readme_txt_case_insensitive(wave_folder)
    sav_path = find_sav_case_insensitive(wave_folder)
    profile_vars, profile_markers, codebook_status = extract_profile_metadata_from_codebook(
        codebook_path
    )
    profile_glossary_re = compile_glossary_regex(profile_markers)
    profile_var_token_re = compile_profile_var_regex(profile_vars)

    readme_meta: Dict[str, object] = {
        "wave": "",
        "field_dates": "",
        "report_titles": [],
        "report_urls": [],
        "vars_from_readme": [],
    }
    if readme_path:
        readme_meta = parse_readme(readme_path)

    wave_number = str(readme_meta.get("wave", "")).strip()
    if not wave_number:
        wave_number = infer_wave_from_folder_name(wave_folder.name)
    wave_tag = f"ATP_{wave_number}" if wave_number else "ATP_UNKNOWN"
    field_dates = str(readme_meta.get("field_dates", "")).strip()
    field_dates_source = "readme"
    if not field_dates:
        field_dates = infer_field_dates_from_wave_docs(wave_folder)
        if field_dates:
            field_dates_source = "docx_fallback"
        else:
            field_dates_source = "unknown"
    dataset_file = sav_path.name if sav_path else ""

    labels_from_sav: Dict[str, str] = {}
    vars_from_sav: set[str] = set()
    if sav_path:
        labels_from_sav, vars_from_sav = extract_sav_question_labels(
            sav_path,
            wave_number,
            profile_glossary_re=profile_glossary_re,
            profile_var_token_re=profile_var_token_re,
        )

    vars_from_readme = set(readme_meta.get("vars_from_readme", []))
    all_variables = sorted(vars_from_sav | vars_from_readme)

    rows: List[Dict[str, str]] = []
    skipped_weight = 0
    skipped_cross_wave = 0
    for var in all_variables:
        if not should_keep_variable(
            variable_name=var,
            wave_number=wave_number,
            include_weights=args.include_weights,
            include_cross_wave=args.include_cross_wave,
        ):
            if var.startswith("WEIGHT_"):
                skipped_weight += 1
            elif is_cross_wave_only(var, wave_number):
                skipped_cross_wave += 1
            continue

        q_text = labels_from_sav.get(var, "")
        row = make_inventory_row(
            wave_tag=wave_tag,
            field_dates=field_dates,
            dataset_file=dataset_file,
            variable_name=var,
            question_text_raw=q_text,
        )

        if args.trump_only and not is_trump_related(var, q_text):
            continue
        rows.append(row)

    # If no variables are discoverable, still write one wave-level placeholder row.
    if not rows:
        row = make_inventory_row(
            wave_tag=wave_tag,
            field_dates=field_dates,
            dataset_file=dataset_file,
            variable_name="",
            question_text_raw="",
        )
        row["inventory_id"] = f"{sanitize_slug(wave_tag)}_wave_metadata"
        rows.append(row)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wave folder: {wave_folder}")
    print(f"Readme found: {'yes' if readme_path else 'no'}")
    print(f"SAV found: {'yes' if sav_path else 'no'}")
    print("Schema: minimal")
    print(
        f"Codebook loaded: {'yes' if codebook_status == 'loaded' else f'no ({codebook_status})'}"
    )
    if profile_vars:
        print(f"Profile vars from codebook: {len(profile_vars)}")
    if profile_markers:
        print(f"Profile markers in cleanup regex: {len(profile_markers)}")
    print(f"Wave tag: {wave_tag}")
    print(f"Field dates: {field_dates or 'unknown'}")
    print(f"Field dates source: {field_dates_source}")
    if skipped_weight:
        print(f"Skipped WEIGHT_* variables: {skipped_weight}")
    if skipped_cross_wave:
        print(f"Skipped cross-wave-only variables: {skipped_cross_wave}")
    print(f"Rows written: {len(rows)}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
