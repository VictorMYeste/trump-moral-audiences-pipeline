# Decision Audit

Generated (UTC): `2026-03-26T08:52:07.818579+00:00`
Rule spec version: `1.0.0`

## Stage Counts

| metric | value |
| --- | --- |
| raw_input_rows | 22822 |
| posts_clean_rows | 17497 |
| posts_topic_validated_rows | 17497 |
| posts_prompt_ready_rows | 3718 |
| pew_rq4_rows | 6 |
| pew_include_yes | 0 |
| pew_include_no | 6 |
| hard_drop_inferred | 5325 |

## Post Exclusion Reasons

| exclude_reason | count |
| --- | --- |
| other_campaign_generic | 11371 |
| truncated_or_context_dependent | 2395 |
| multi_topic_ambiguous | 1494 |
| excluded_from_prompt_due_to_moderation_status | 374 |
| identity_leak_after_anonymization | 156 |
| anonymization_degraded_text | 52 |
| duplicate_after_cleaning | 20 |

## Post Keep and Moderation Counts

| keep_for_prompt | count |
| --- | --- |
| no | 13779 |
| yes | 3718 |

| moderation_status | count |
| --- | --- |
| deleted | 267 |
| flagged | 107 |
| not_deleted_not_flagged | 17123 |

## PEW Exclusion Codes

| exclude_code | count |
| --- | --- |
| exclude_not_trump_target | 3 |
| exclude_no_topic_match | 1 |
| exclude_judgment_not_supported | 1 |
| exclude_knowledge_or_awareness | 1 |

## Topic Overlap

No overlap topics.
