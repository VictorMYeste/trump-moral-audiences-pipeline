# Preprocessing Protocol

This document defines the reproducible preprocessing pipeline for Trump archive posts.

The implementation source of truth is:
- `scripts/preprocess_posts.py`
- `data/reference/methods/filter_spec.json` (machine-readable rule list used for appendix export)
- `data/reference/methods/topic_keywords.json` (canonical topic keyword registry)

## 1. Objective

Produce a prompt-ready, anonymized, issue-topic subset for synthetic audience prompting, while preserving a broader analytical archive for moderation-status analysis.

## 2. Input Dataset

Default raw input files:
- `data/raw/trump_archive_me2bert_filtered_2009_2021.csv`
- `data/raw/trump_manual_me2bert_filtered_2022_2024.csv`

Source provenance:
- Current window source (up to 2021): Kaggle archive
  - <https://www.kaggle.com/datasets/headsortails/trump-twitter-archive>
  - https://www.kaggle.com/datasets/headsortails/trump-twitter-archive
- Planned extension source (2021-2024): The Trump Archive
  - <https://www.thetrumparchive.com/>
  - https://www.thetrumparchive.com/
- Current protocol windows:
- `2009-05-12` to `2021-01-08` from the Kaggle archive file
- `2022-04-29` to `2024-11-04` from the manually prepared Trump Archive file
- Multiple raw inputs can be combined in one preprocessing run.

Required source columns:
- `id`
- `text`
- `isRetweet`
- `date`
- `dominant_moral_dimension`
- `is_morally_relevant`

Optional-but-supported source columns:
- `isDeleted`
- `isFlagged`
- `device`

### 2.1 Expected Raw CSV Schema

Expected header (17 columns):

1. `id`
2. `text`
3. `isRetweet`
4. `isDeleted`
5. `device`
6. `favorites`
7. `retweets`
8. `date`
9. `isFlagged`
10. `CH`
11. `FC`
12. `LB`
13. `AS`
14. `PD`
15. `moral_max`
16. `dominant_moral_dimension`
17. `is_morally_relevant`

Field format contract:

| Field | Type | Expected format / values | Used by pipeline |
| --- | --- | --- | --- |
| `id` | string/integer | unique tweet id (digits recommended) | yes |
| `text` | string | UTF-8 text content | yes |
| `isRetweet` | string bool | `t`/`f` (parser also accepts common boolean variants) | yes |
| `isDeleted` | string bool | `t`/`f` | optional |
| `device` | string | free text source label | optional pass-through |
| `favorites` | integer | non-negative integer | no (pass-through) |
| `retweets` | integer | non-negative integer | no (pass-through) |
| `date` | datetime string | `YYYY-MM-DD HH:MM:SS` | yes |
| `isFlagged` | string bool | `t`/`f` | optional |
| `CH` | float | moral score in `[0, 1]` | no (pass-through) |
| `FC` | float | moral score in `[0, 1]` | no (pass-through) |
| `LB` | float | moral score in `[0, 1]` | no (pass-through) |
| `AS` | float | moral score in `[0, 1]` | no (pass-through) |
| `PD` | float | moral score in `[0, 1]` | no (pass-through) |
| `moral_max` | float | max moral score in `[0, 1]` | no (pass-through) |
| `dominant_moral_dimension` | enum string | one of `CH`, `FC`, `LB`, `AS`, `PD` | yes |
| `is_morally_relevant` | string bool | `True`/`False` (or parser-compatible boolean values) | yes |

Reference synthetic sample:
- `data/reference/examples/raw_input_sample.csv`

The sample is illustrative only and contains no original raw post content.

Example (synthetic):

```csv
id,text,isRetweet,isDeleted,device,favorites,retweets,date,isFlagged,CH,FC,LB,AS,PD,moral_max,dominant_moral_dimension,is_morally_relevant
111111111111111111,"Our border policies must be lawful and secure for everyone.",f,f,Twitter for iPhone,10234,2456,2020-02-01 12:34:56,f,0.12345,0.23456,0.34567,0.45678,0.56789,0.56789,PD,True
```

## 3. Output Files

Default output directory:
- `data/interim/preprocessing/`

Generated files:
1. `posts_clean.csv`
2. `posts_topic_labeled.csv`
3. `posts_topic_validated.csv`
4. `posts_prompt_ready.csv`
5. `posts_moderation_analysis.csv`

## 4. Derived Columns

The pipeline appends these columns:
- `source_file`
- `year`
- `month`
- `role`
- `moderation_status`
- `text_html_decoded`
- `text_no_url`
- `text_clean`
- `review_flag`
- `topic_candidates`
- `topic`
- `topic_confidence`
- `keep_for_prompt`
- `exclude_reason`
- `text_anon`

## 5. Deterministic Processing Rules

Rules are applied in fixed order.
Canonical rule IDs and rationales are versioned in:
- `data/reference/methods/filter_spec.json`

### 5.1 Hard filters before topic labeling

1. Keep only rows with `is_morally_relevant = true`.
2. Drop retweets (`isRetweet = true` or text starts with `RT @`).
3. Decode HTML entities in `text` into `text_html_decoded`.
4. Remove URLs (`https?://\S+`) into `text_no_url`.
5. Normalize whitespace into `text_clean`.
6. Drop if `len(text_clean) < 40`.
7. Drop if alphabetic token count (`[A-Za-z]+(?:'[A-Za-z]+)?`) is less than 7.
8. Drop if cleaned text matches low-information patterns exactly:
   - `thank you`
   - `true`
   - `so true`
   - `rigged`
   - `vote`
   - `great`
9. Set `review_flag = truncated_text` if text contains `...` or `...`.

### 5.2 Role and moderation metadata

`role` from `date`:
- `public_figure`: 2009-05-12 to 2015-06-15
- `candidate`: 2015-06-16 to 2016-11-08
- `president_elect`: 2016-11-09 to 2017-01-19
- `sitting_president`: 2017-01-20 to 2021-01-20
- `former_president`: 2021-01-21 to 2022-11-14
- `candidate_2024`: 2022-11-15 to 2024-11-05
- `out_of_range`: all others

`moderation_status` from `isDeleted`, `isFlagged`:
- `deleted_and_flagged`
- `deleted`
- `flagged`
- `not_deleted_not_flagged`
- `unknown_missing_source_metadata` when one or both moderation columns are absent/blank in the source file

### 5.3 Topic labeling

Each row is matched against fixed issue-topic regex patterns. Current labels:
- `immigration_border`
- `economy_jobs_trade`
- `election_integrity_democracy`
- `foreign_policy_national_security`
- `crime_policing_criminal_justice`
- `covid_public_health`
- `judiciary_courts`

Assignment rules:
- 1 topic hit -> `topic=<label>`, `topic_confidence=high`
- >1 topic hit -> `topic=review_needed`, `topic_confidence=medium`
- 0 topic hits -> `topic=other_campaign_generic`, `topic_confidence=low`

Exact regex patterns are documented in code:
- `data/reference/methods/topic_keywords.json` (canonical reusable registry)
- `scripts/topic_rules.py` (shared loader used by post and PEW scripts)
- `reports/methods/topic_patterns.csv` (generated table for appendix use)

### 5.4 Optional manual override layer

If provided, `--manual-review-csv` can override row-level values by `id`.
Supported override columns:
- `id`
- `topic`
- `topic_confidence`
- `review_flag`
- `exclude_reason_add`

### 5.5 Anonymization

`text_anon` is produced from `text_clean` using ordered replacements:
1. Role-sensitive replacements (for example, `President Trump` -> `the president`).
2. Identity replacement (`Trump`, `Donald Trump`, `@realDonaldTrump` -> `[POLITICAL_ACTOR]`).
3. Campaign tag replacement (`MAGA`, `KAG2020`, etc. -> `[CAMPAIGN_TAG]`).
4. Institution allowlist normalization (for example, `@CDCgov` -> `CDC`).
5. Remaining handles -> `[USER]`.

Anonymization quality checks:
- detect identity leaks (`trump`, `donald`, specific campaign tags)
- flag degradation if text becomes too short/sparse after anonymization

### 5.6 Prompt-readiness exclusions

Rows are excluded from `posts_prompt_ready.csv` if any apply:
- `role_out_of_range`
- `identity_leak_after_anonymization`
- `anonymization_degraded_text`
- `other_campaign_generic`
- `multi_topic_ambiguous`
- `truncated_or_context_dependent`
- `excluded_from_prompt_due_to_moderation_status`
- `duplicate_after_cleaning`

Moderation note:
- rows are excluded for moderation only when the source explicitly marks them as `deleted`, `flagged`, or `deleted_and_flagged`
- rows with `moderation_status=unknown_missing_source_metadata` remain eligible for prompting

`keep_for_prompt=yes` is assigned only when `exclude_reason` is empty.

### 5.7 Final deduplication

Prompt candidates are deduplicated by normalized lowercase `text_anon`.
First occurrence is kept; subsequent duplicates are excluded with `duplicate_after_cleaning`.

## 6. Interpretation of Output Files

- `posts_prompt_ready.csv`: strict prompting pool.
- `posts_moderation_analysis.csv`: full post-filter pool including deleted/flagged statuses for comparative analysis.

PEW alignment note:
- Broad Trump job-approval items are not used for topic-specific public-opinion comparison.
- These rows remain in `pew_rq3_inventory.csv` with `exclude_code=exclude_general_presidential_approval`.
- `rule_trace` keeps diagnostic topic hits, but `issue_topic` remains empty for these excluded rows.

## 7. Reproducible Execution

Run:

```bash
python3 scripts/preprocess_posts.py
```

Equivalent explicit multi-input run:

```bash
python3 scripts/preprocess_posts.py \
  --input data/raw/trump_archive_me2bert_filtered_2009_2021.csv \
  --input data/raw/trump_manual_me2bert_filtered_2022_2024.csv
```

Optional overrides:

```bash
python3 scripts/preprocess_posts.py --manual-review-csv path/to/manual_review_overrides.csv
```

The script prints row counts, drop counts, topic counts, moderation counts, and prompt-keep counts for auditability.

## 8. Methods Appendix Artifacts

After running the full pipeline (or `scripts/export_methods_appendix.py`), the following appendix-ready files are generated:
- `reports/methods/filter_table.csv`: ordered preprocessing and PEW selection rules with rule IDs.
- `reports/methods/topic_patterns.csv`: full topic regex inventory used by both post and PEW selectors.
- `reports/methods/anonymization_rules.csv`: ordered anonymization replacements and fallback patterns.
- `reports/methods/pew_selection_rules.csv`: deterministic PEW inclusion/exclusion regexes.
- `reports/methods/decision_audit.md`: stage counts and exclusion-count diagnostics.
