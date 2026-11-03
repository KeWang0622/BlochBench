# WRITE-03 · Methods and statistics review of an MRI manuscript

- Task ID: WRITE-03
- Legacy ID: v6-methodreview

- Domain: Writing and review
- Tier: Core (v1.0 candidate); review status: pending
- Time cap: 45 min
- Instances recorded: 4 (instances.json)
- Automated checks (8): deliverables_present, schema_valid, quotes_verbatim, recall_planted_issues, false_accusations_limited, recommendation_consistent, review_md_consistent, limitations_present

## Task (example instance)

~~~text
A neurology imaging journal has asked for a methods-and-statistics review of the attached manuscript on deep-learning reconstruction of undersampled FLAIR* for assessing the central vein sign in suspected multiple sclerosis (the manuscript is synthetic; see public/inputs and task.json). Please serve as the methodological referee.

Go through every paragraph and table and judge the study design, the analysis plan and handling of data, the statistics, the numbers and units, and whether the conclusions follow. For every problem you identify, give the paragraph or table in which it appears, a category from the list in task.json, a verbatim quote that demonstrates it, and a short explanation of why it matters and how the authors should fix it. Keep to substantive problems: stylistic remarks and generic limitations are not wanted, flagging sound paragraphs counts against the review, and the pass thresholds are stated in task.json.

Deliver review.json in the schema given in task.json and review.md, a readable referee report with an overall recommendation. Save both files in the workspace root and add a short note on the limitations of your review. If you write code, keep it with the deliverables and add a brief environment record (interpreter and package versions).
~~~

The full specification is in task.example.json. code/ holds the generator, grader, reference solution and control scripts of the example instance; VALIDATION.md lists how the reference and the controls scored.

