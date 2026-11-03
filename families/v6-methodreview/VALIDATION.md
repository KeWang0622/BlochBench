# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| reference_arm | reference | - | none (all pass) |
| reference | reference | - | none (all pass) |
| missed_two_planted_issues | negative | recall_planted_issues | recall_planted_issues |
| false_accusations_of_sound_decoys | negative | false_accusations_limited | false_accusations_limited |
| wrong_categories | negative | recall_planted_issues | recall_planted_issues |
| fabricated_quote | negative | quotes_verbatim | quotes_verbatim |
| nonexistent_paragraph_id | negative | schema_valid | schema_valid, quotes_verbatim |
| lenient_recommendation | negative | recommendation_consistent | recommendation_consistent |
| category_outside_list | negative | schema_valid | schema_valid |
| shotgun_review_every_paragraph | negative | false_accusations_limited | false_accusations_limited |
| issues_at_wrong_location | negative | recall_planted_issues | recall_planted_issues, false_accusations_limited |
