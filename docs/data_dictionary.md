# Data Dictionary

This document defines the main generated datasets used in the RQ4 pipeline.

## Scope

Covered files:
- `data/interim/preprocessing/posts_topic_validated.csv`
- `data/interim/preprocessing/posts_prompt_ready.csv`
- `data/interim/pew/pew_question_inventory.csv`
- `data/interim/pew/pew_rq4_inventory.csv`
- `data/interim/rq4/rq4_topics_final.csv`
- `data/interim/rq4/rq4_pew_subset.csv`
- `data/interim/rq4/rq4_posts_subset.csv`

Not covered:
- raw source data in `data/raw/`
- wave-level partial files in `data/pew_datasets/W*/pew_question_inventory_partial.csv`

## Lineage Summary

| Output file | Producer script | Primary input(s) | Row unit |
|---|---|---|---|
| `posts_topic_validated.csv` | `scripts/preprocess_posts.py` | raw post CSV | one post |
| `posts_prompt_ready.csv` | `scripts/preprocess_posts.py` | `posts_topic_validated` in-memory state | one post kept for prompting |
| `pew_question_inventory.csv` | `scripts/merge_pew_inventories.py` | per-wave PEW partial inventories | one PEW variable/question row |
| `pew_rq4_inventory.csv` | `scripts/select_pew_for_rq4.py` | `pew_question_inventory.csv` | one PEW variable/question row with RQ4 decision fields |
| `rq4_topics_final.csv` | `scripts/build_rq4_final_subsets.py` | `pew_rq4_inventory.csv` + `posts_prompt_ready.csv` | one overlap topic |
| `rq4_pew_subset.csv` | `scripts/build_rq4_final_subsets.py` | `pew_rq4_inventory.csv` | one PEW row in final overlap topics (`include_for_rq4=yes`) |
| `rq4_posts_subset.csv` | `scripts/build_rq4_final_subsets.py` | `posts_prompt_ready.csv` | one prompt-ready post in final overlap topics |

## Shared Topic Labels

Topic labels used in posts/PEW matching come from:
- `data/reference/methods/topic_keywords.json`

Current canonical topics:
- `immigration_border`
- `economy_jobs_trade`
- `election_integrity_democracy`
- `foreign_policy_national_security`
- `crime_policing_criminal_justice`
- `covid_public_health`
- `judiciary_courts`

## Shared Schema: Post-Level Outputs

The following columns are shared by:
- `posts_topic_validated.csv`
- `posts_prompt_ready.csv`
- `rq4_posts_subset.csv`

| Column | Type | Meaning | Typical values |
|---|---|---|---|
| `id` | string | Post ID. | numeric-like string |
| `text` | string | Raw post text from source CSV. | free text |
| `isRetweet` | bool-like string | Source retweet flag. | `t/f`, `true/false`, `1/0`, `yes/no` |
| `isDeleted` | bool-like string | Source deleted flag. | `t/f`, `true/false`, `1/0`, `yes/no` |
| `device` | string | Source client/device metadata. | e.g., `Twitter for iPhone` |
| `favorites` | integer-like string | Source favorite count. | numeric-like |
| `retweets` | integer-like string | Source retweet count. | numeric-like |
| `date` | datetime string | Source timestamp. | `YYYY-MM-DD HH:MM:SS` |
| `isFlagged` | bool-like string | Source flagged/moderation flag. | `t/f`, `true/false`, `1/0`, `yes/no` |
| `CH` | float-like string | Upstream moral score dimension. | `0..1` style numeric string |
| `FC` | float-like string | Upstream moral score dimension. | `0..1` style numeric string |
| `LB` | float-like string | Upstream moral score dimension. | `0..1` style numeric string |
| `AS` | float-like string | Upstream moral score dimension. | `0..1` style numeric string |
| `PD` | float-like string | Upstream moral score dimension. | `0..1` style numeric string |
| `moral_max` | float-like string | Max of moral dimensions (upstream field). | numeric-like |
| `dominant_moral_dimension` | string | Dominant moral dimension (upstream field). | e.g., `CH`, `FC`, `LB`, `AS`, `PD` |
| `is_morally_relevant` | bool-like string | Upstream moral relevance flag. | bool-like string |
| `source_file` | string | Raw input file name used for this row. | e.g., `trump_archive_me2bert_filtered_2009_2021.csv` |
| `year` | string | Year extracted from `date`. | 4-digit year |
| `month` | string | Month extracted from `date`. | `01`-`12` |
| `role` | enum string | Date-window role. | `public_figure`, `candidate`, `president_elect`, `sitting_president`, `former_president`, `candidate_2024`, `out_of_range` |
| `moderation_status` | enum string | Combined moderation state from `isDeleted` + `isFlagged`, with an explicit unknown state when source metadata is missing. | `not_deleted_not_flagged`, `deleted`, `flagged`, `deleted_and_flagged`, `unknown_missing_source_metadata` |
| `text_html_decoded` | string | `text` with HTML entities decoded. | free text |
| `text_no_url` | string | URL-stripped decoded text. | free text |
| `text_clean` | string | Whitespace-normalized version of `text_no_url`. | free text |
| `review_flag` | string | Optional quality/review marker. | empty or `truncated_text` |
| `topic_candidates` | string | Pipe-separated topic hits before final assignment. | e.g., `economy_jobs_trade|foreign_policy_national_security` |
| `topic` | enum string | Final topic assignment. | one canonical topic, `review_needed`, `other_campaign_generic` |
| `topic_confidence` | enum string | Confidence from topic-hit logic. | `high`, `medium`, `low` |
| `keep_for_prompt` | enum string | Final inclusion flag for prompt-ready pool. | `yes`, `no` |
| `exclude_reason` | string | Semicolon-separated exclusion rules that fired. | free text codes |
| `text_anon` | string | Anonymized text used for prompting. | free text |

Notes:
- `rq4_posts_subset.csv` is a filtered subset of `posts_prompt_ready.csv`, so `keep_for_prompt` is expected to be `yes`.
- In current runs, `rq4_posts_subset.csv` typically has `topic_confidence=high` and empty `review_flag`.

## Shared Schema: PEW Inventory Base

The base PEW inventory columns are:
- `inventory_id`
- `pew_wave`
- `field_dates`
- `dataset_file`
- `variable_name`
- `question_text_raw`

Used in:
- `pew_question_inventory.csv`
- `pew_rq4_inventory.csv` (plus RQ4 decision columns)
- `rq4_pew_subset.csv` (same columns as `pew_rq4_inventory.csv`)

| Column | Type | Meaning |
|---|---|---|
| `inventory_id` | string | Stable row ID (`{wave}_{variable}` style; placeholder rows can end with `_wave_metadata`). |
| `pew_wave` | string | Wave tag, e.g., `ATP_55`. |
| `field_dates` | string | Survey field date range extracted from wave metadata. |
| `dataset_file` | string | Source `.sav` file name used for extraction. |
| `variable_name` | string | PEW variable ID. Can be empty for placeholder metadata rows. |
| `question_text_raw` | string | Extracted/cleaned question label text from `.sav` strings. |

## Additional Schema: PEW RQ4 Decision Fields

Columns appended by `scripts/select_pew_for_rq4.py`:
- `response_scale_raw`
- `judgment_family`
- `issue_topic`
- `include_for_rq4`
- `exclude_code`
- `rule_trace`

| Column | Type | Meaning | Typical values |
|---|---|---|---|
| `response_scale_raw` | enum string | Deterministic inferred response-format family. | `approve_disapprove`, `very_somewhat_not_too_not_at_all_confident`, `favor_oppose`, `support_oppose`, `unknown` |
| `judgment_family` | enum string | High-level judgment type used for inclusion logic. | `approval`, `confidence`, `policy_support`, `other` |
| `issue_topic` | string | Deterministic single-topic match from shared topic registry. Empty when no unique match. | canonical topic or empty |
| `include_for_rq4` | enum string | Final deterministic inclusion decision. | `yes`, `no` |
| `exclude_code` | string | First exclusion rule that fired. Empty when included. | e.g., `exclude_not_trump_target`, `exclude_judgment_not_supported` |
| `rule_trace` | string | Semicolon-delimited diagnostics trace of decision path and topic hits. | free trace string |

## File-Specific Notes

### `data/interim/preprocessing/posts_topic_validated.csv`

Purpose:
- Full post-level output after topic assignment, anonymization, and exclusion-rule application.

Current observed properties:
- Contains both included and excluded rows (`keep_for_prompt` is mixed `yes/no`).
- Includes moderation statuses for analysis (`not_deleted_not_flagged`, `deleted`, `flagged`, possibly `deleted_and_flagged` if present in source).

### `data/interim/preprocessing/posts_prompt_ready.csv`

Purpose:
- Subset of `posts_topic_validated.csv` where `keep_for_prompt=yes` after all rules and deduplication.

Current observed properties:
- `keep_for_prompt=yes` for all rows by construction.
- `moderation_status` is expected to be either `not_deleted_not_flagged` or `unknown_missing_source_metadata`.

### `data/interim/pew/pew_question_inventory.csv`

Purpose:
- Merged minimal PEW inventory across all waves.

Current observed properties:
- May include placeholder wave rows (`variable_name` empty) when no kept variable is available for that wave under current extraction/filter settings.

### `data/interim/pew/pew_rq4_inventory.csv`

Purpose:
- Full PEW inventory with deterministic RQ4 selection diagnostics.

Current observed properties:
- Contains both `include_for_rq4=yes` and `no`.
- Included rows should have empty `exclude_code`.

### `data/interim/rq4/rq4_topics_final.csv`

Columns:
- `topic`: canonical overlap topic.
- `pew_rows`: number of included PEW rows for that topic.
- `post_rows`: number of prompt-ready post rows for that topic.

Purpose:
- Final topic list used to align both PEW and post subsets.

### `data/interim/rq4/rq4_pew_subset.csv`

Purpose:
- Final PEW rows restricted to:
  - `include_for_rq4=yes`
  - topics present in final overlap list

Schema:
- Same 12 columns as `pew_rq4_inventory.csv`.

### `data/interim/rq4/rq4_posts_subset.csv`

Purpose:
- Final prompt-ready post rows restricted to final overlap topics.

Schema:
- Same post-level shared schema.

Current observed properties:
- `keep_for_prompt=yes` for all rows.
- Rows are topic-aligned with `rq4_pew_subset.csv` via `rq4_topics_final.csv`.
