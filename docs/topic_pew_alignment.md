# Topic-PEW Alignment Specification

This document defines the public alignment rules between PEW survey items and tweet-topic subsets.

Implementation source of truth:
- `scripts/select_pew_for_rq4.py`
- `scripts/report_topic_overlap.py`
- `scripts/build_rq4_final_subsets.py`

## 1. Alignment Objective

A PEW item is alignment-ready only when it can be compared to anonymized, topic-constrained message bundles using the same judgment construct.

Alignment requires both:
1. Issue alignment: same policy/issue domain.
2. Measurement alignment: same response construct (for example, confidence vs approval).

## 2. Deterministic Inclusion Rules

Each PEW row is evaluated automatically.

Required conditions for `include_for_rq4 = yes`:
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
- Exact patterns are defined in code and should be changed only via versioned edits.

## 4. Alignment Outputs

`data/interim/pew/pew_rq4_inventory.csv` includes:
- `response_scale_raw`
- `judgment_family`
- `issue_topic`
- `include_for_rq4`
- `exclude_code`
- `rule_trace`

`rule_trace` records how each decision was reached.

## 5. Overlap and Final Subsetting

Topic overlap is computed between:
- included PEW topics (`include_for_rq4=yes`), and
- prompt-ready post topics from `posts_prompt_ready.csv`.

Scripts:
1. `scripts/report_topic_overlap.py` for diagnostics.
2. `scripts/build_rq4_final_subsets.py` for final constrained outputs.

Final outputs:
- `data/interim/rq4/rq4_topics_final.csv`
- `data/interim/rq4/rq4_pew_subset.csv`
- `data/interim/rq4/rq4_posts_subset.csv`

These files ensure both PEW and post subsets share the same final topic list.

## 6. Scientific Rationale for Excluded Item Families

Excluded families are removed because they are weakly identifiable from anonymized message content alone and are therefore not comparable under controlled prompting.

Examples:
- trait/personality batteries rely on person-level priors
- broad favorability captures global attitude, not issue-specific judgment
- affective reaction items measure emotional state rather than policy judgment

## 7. Versioning Rule

If topic regexes or inclusion logic are changed:
1. rerun the full pipeline,
2. regenerate all PEW and RQ4 outputs,
3. document the change in commit history and release notes.
