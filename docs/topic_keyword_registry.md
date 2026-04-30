# Topic Keyword Registry

This document defines how topic keywords are selected, versioned, reused, and audited.

Canonical registry:
- `data/reference/methods/topic_keywords.json`

Shared loader:
- `scripts/topic_rules.py`

Validator:
- `scripts/validate_topic_rules.py`

## 1. Why a Shared Registry

The project uses one topic system for:
1. Post preprocessing (`scripts/preprocess_posts.py`)
2. PEW alignment (`scripts/select_pew_for_rq3.py`)

Using a shared registry prevents silent drift between topic filters in different scripts.

## 2. Registry Schema

Top-level fields:
1. `metadata`
2. `topics`

Each topic row includes:
1. `topic`: stable topic ID used in outputs
2. `regex`: deterministic matching expression
3. `applies_to`: one or more of `posts`, `pew`, `both`
4. `selection_rationale`: plain-language reason for inclusion
5. `source_basis`: provenance basis (PEW wording, corpus vocabulary, policy lexicon)

## 3. Selection Policy

Keywords are selected with a conservative, high-precision policy:
1. Start from PEW issue-domain wording that is comparable to topic-constrained prompts.
2. Add policy-domain terms that are frequent and semantically stable in the post corpus.
3. Prefer terms with clear issue anchoring.
4. Avoid trait/affective/global-favorability terms that are not issue domains.

## 4. Reuse Contract

1. Topic matching logic must be loaded from `topic_keywords.json` via `scripts/topic_rules.py`.
2. `scripts/preprocess_posts.py` and `scripts/select_pew_for_rq3.py` should not hardcode topic regexes.
3. `scripts/validate_topic_rules.py` must pass before pipeline execution.

## 5. Audit and Appendix Outputs

`scripts/export_methods_appendix.py` exports:
- `reports/methods/topic_patterns.csv`

This table includes:
1. topic ID
2. regex
3. `applies_to`
4. `selection_rationale`
5. `source_basis`
6. script-usage flags (`used_in_preprocess_posts`, `used_in_select_pew_for_rq3`)
7. topic spec version

## 6. Change-Control Checklist

When topic keywords change:
1. edit `data/reference/methods/topic_keywords.json`
2. run `python3 scripts/validate_topic_rules.py`
3. rerun `scripts/run_full_pipeline.sh`
4. regenerate methods artifacts with `python3 scripts/export_methods_appendix.py`
5. report spec version/date and affected outputs in commit/release notes
