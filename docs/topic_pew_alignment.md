# Topic-PEW Alignment Specification

This document defines the public alignment rules between PEW survey items and tweet-topic subsets.

Detailed topic-keyword governance is documented in:
- `docs/topic_keyword_registry.md`

Implementation source of truth:
- `scripts/select_pew_for_rq3.py`
- `scripts/report_topic_overlap.py`
- `scripts/build_rq3_final_subsets.py`
- `data/reference/methods/filter_spec.json`
- `data/reference/methods/topic_keywords.json`

## 1. Alignment Objective

A PEW item is alignment-ready only when it can be compared to anonymized, topic-constrained message bundles using the same judgment construct.

Alignment requires both:
1. Issue alignment: same policy/issue domain.
2. Measurement alignment: same response construct (for example, confidence vs approval).

## 2. Deterministic Inclusion Rules

Each PEW row is evaluated automatically.

Required conditions for `include_for_rq3 = yes`:
1. The item targets Trump directly or via constrained presidential context.
2. `judgment_family` is one of:
   - `approval`
   - `confidence`
   - `policy_support`
3. Item form is not excluded:
   - thermometer scales
   - trait batteries (for example, honest, keeps promises, mentally sharp)
   - affective reaction items (for example, excited/upset/surprised)
   - knowledge-awareness items
   - broad favorability without issue anchor
   - broad presidential job approval without an issue-specific policy anchor
4. Exactly one issue-topic hit is detected.

If any condition fails, the row is excluded with a machine-readable `exclude_code`.

## 3. Issue Topics Used in Alignment

Current deterministic topic set:
- `immigration_border`
- `economy_jobs_trade`
- `election_integrity_democracy`
- `foreign_policy_national_security`
- `crime_policing_criminal_justice`
- `covid_public_health`
- `judiciary_courts`

Important:
- Topic regexes are intentionally conservative and auditable.
- Exact patterns are defined in `data/reference/methods/topic_keywords.json` and loaded by both selectors.
- Generated appendix table:
  - `reports/methods/topic_patterns.csv`

## 3.1 Keyword Selection and Reuse Policy

Topic keywords are selected with a deterministic, high-precision policy:
1. Start from PEW issue-domain wording relevant to Trump-targeted item families.
2. Add policy-domain terms observed in the post corpus.
3. Keep terms specific enough to reduce cross-topic leakage.
4. Avoid trait/emotion terms that are not issue-domain anchors.

Reuse rule:
1. `scripts/preprocess_posts.py` and `scripts/select_pew_for_rq3.py` must load topics from the same canonical registry (`topic_keywords.json`).
2. Registry validity is checked via `scripts/validate_topic_rules.py`.
3. Any registry update requires pipeline rerun and regenerated methods appendix artifacts.

## 4. Alignment Outputs

`data/interim/pew/pew_rq3_inventory.csv` includes:
- `response_scale_raw`
- `judgment_family`
- `issue_topic`
- `include_for_rq3`
- `exclude_code`
- `rule_trace`

`rule_trace` records how each decision was reached.

## 5. Overlap and Final Subsetting

Topic overlap is computed between:
- included PEW topics (`include_for_rq3=yes`), and
- prompt-ready post topics from `posts_prompt_ready.csv`.

Scripts:
1. `scripts/report_topic_overlap.py` for diagnostics.
2. `scripts/build_rq3_final_subsets.py` for final constrained outputs.

Final outputs:
- `data/interim/rq3/rq3_topics_final.csv`
- `data/interim/rq3/rq3_pew_subset.csv`
- `data/interim/rq3/rq3_posts_subset.csv`

These files ensure both PEW and post subsets share the same final topic list.

## 6. Scientific Rationale for Excluded Item Families

Excluded families are removed because they are weakly identifiable from anonymized message content alone and are therefore not comparable under controlled prompting.

Examples:
- trait/personality batteries rely on person-level priors
- broad favorability captures global attitude, not issue-specific judgment
- broad presidential job approval captures overall evaluation of Trump rather than the policy topic of a message bundle
- affective reaction items measure emotional state rather than policy judgment

## 7. Versioning Rule

If topic regexes or inclusion logic are changed:
1. rerun the full pipeline,
2. regenerate all PEW and RQ3 outputs,
3. regenerate `reports/methods/*.csv` and `reports/methods/decision_audit.md`,
4. document the change in commit history and release notes.
