# Decision Audit

Generated (UTC): `2026-04-30T15:52:18.126477+00:00`
Rule spec version: `1.2.0`

## Stage Counts

| metric | value |
| --- | --- |
| raw_input_rows | 31366 |
| posts_clean_rows | 23230 |
| posts_topic_validated_rows | 23230 |
| posts_prompt_ready_rows | 5270 |
| pew_rq3_rows | 981 |
| pew_include_yes | 25 |
| pew_include_no | 956 |
| hard_drop_inferred | 8136 |

## Post Exclusion Reasons

| exclude_reason | count |
| --- | --- |
| other_campaign_generic | 13621 |
| truncated_or_context_dependent | 3225 |
| multi_topic_ambiguous | 3043 |
| excluded_from_prompt_due_to_moderation_status | 374 |
| identity_leak_after_anonymization | 162 |
| duplicate_after_cleaning | 88 |
| anonymization_degraded_text | 52 |

## Post Keep and Moderation Counts

| keep_for_prompt | count |
| --- | --- |
| no | 17960 |
| yes | 5270 |

| moderation_status | count |
| --- | --- |
| deleted | 267 |
| flagged | 107 |
| not_deleted_not_flagged | 17123 |
| unknown_missing_source_metadata | 5733 |

## PEW Exclusion Codes

| exclude_code | count |
| --- | --- |
| exclude_not_trump_target | 502 |
| exclude_judgment_not_supported | 303 |
| exclude_affective_reaction | 47 |
| exclude_trait | 44 |
| exclude_general_presidential_approval | 31 |
| exclude_no_topic_match | 16 |
| exclude_multi_topic_ambiguous | 5 |
| exclude_knowledge_or_awareness | 5 |
| exclude_thermometer | 2 |
| exclude_broad_favorability | 1 |

## Topic Overlap

| topic | pew_included_rows | prompt_ready_rows |
| --- | --- | --- |
| covid_public_health | 5 | 251 |
| economy_jobs_trade | 7 | 1116 |
| foreign_policy_national_security | 5 | 1112 |
| immigration_border | 4 | 539 |
| judiciary_courts | 4 | 300 |
