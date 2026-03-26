#!/usr/bin/env python3
"""Shared topic-keyword registry loader and validator."""

# Simple explanation of this script (step by step):
# 1) Load the canonical topic keyword registry JSON.
# 2) Validate the structure (required fields, topic uniqueness, regex validity).
# 3) Compile reusable regex patterns once.
# 4) Return the same topic set to any script that needs deterministic topic matching.

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


DEFAULT_TOPIC_SPEC = "data/reference/methods/topic_keywords.json"
VALID_APPLIES_TO = {"posts", "pew", "both"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_topic_spec_path() -> Path:
    return _repo_root() / DEFAULT_TOPIC_SPEC


def load_topic_spec(path: Path | None = None) -> Dict[str, object]:
    spec_path = path or default_topic_spec_path()
    if not spec_path.exists():
        raise FileNotFoundError(f"Topic spec not found: {spec_path}")
    with spec_path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid topic spec format (expected object): {spec_path}")
    validate_topic_spec(data, spec_path)
    return data


def validate_topic_spec(data: Dict[str, object], spec_path: Path | None = None) -> None:
    prefix = f"{spec_path}: " if spec_path else ""

    topics = data.get("topics")
    if not isinstance(topics, list) or not topics:
        raise ValueError(prefix + "topics must be a non-empty list")

    seen_topics = set()
    for idx, item in enumerate(topics):
        if not isinstance(item, dict):
            raise ValueError(prefix + f"topics[{idx}] must be an object")

        topic = str(item.get("topic", "")).strip()
        regex = str(item.get("regex", "")).strip()
        applies_to = item.get("applies_to")
        rationale = str(item.get("selection_rationale", "")).strip()
        source_basis = str(item.get("source_basis", "")).strip()

        if not topic:
            raise ValueError(prefix + f"topics[{idx}].topic is required")
        if topic in seen_topics:
            raise ValueError(prefix + f"duplicate topic id: {topic}")
        seen_topics.add(topic)

        if not regex:
            raise ValueError(prefix + f"topics[{idx}].regex is required ({topic})")
        try:
            re.compile(regex, re.IGNORECASE)
        except re.error as exc:
            raise ValueError(prefix + f"invalid regex for topic '{topic}': {exc}") from exc

        if not isinstance(applies_to, list) or not applies_to:
            raise ValueError(prefix + f"topics[{idx}].applies_to must be a non-empty list ({topic})")
        applies_to_clean = {str(v).strip().lower() for v in applies_to}
        invalid = sorted(applies_to_clean - VALID_APPLIES_TO)
        if invalid:
            raise ValueError(
                prefix + f"topics[{idx}].applies_to has invalid values for '{topic}': {', '.join(invalid)}"
            )

        if not rationale:
            raise ValueError(prefix + f"topics[{idx}].selection_rationale is required ({topic})")
        if not source_basis:
            raise ValueError(prefix + f"topics[{idx}].source_basis is required ({topic})")


def _scope_match(applies_to: Sequence[str], scope: str) -> bool:
    scope_norm = scope.strip().lower()
    targets = {str(v).strip().lower() for v in applies_to}
    if scope_norm == "both":
        return True
    return scope_norm in targets or "both" in targets


def compile_topic_patterns(
    scope: str = "both", spec_path: Path | None = None
) -> List[Tuple[str, re.Pattern[str]]]:
    if scope.strip().lower() not in {"posts", "pew", "both"}:
        raise ValueError("scope must be one of: posts, pew, both")

    spec = load_topic_spec(spec_path)
    topics = spec.get("topics", [])
    if not isinstance(topics, list):
        return []

    compiled: List[Tuple[str, re.Pattern[str]]] = []
    for item in topics:
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic", "")).strip()
        regex = str(item.get("regex", "")).strip()
        applies_to_raw = item.get("applies_to", [])
        applies_to = applies_to_raw if isinstance(applies_to_raw, list) else []
        if not topic or not regex:
            continue
        if not _scope_match([str(v) for v in applies_to], scope):
            continue
        compiled.append((topic, re.compile(regex, re.IGNORECASE)))
    return compiled
