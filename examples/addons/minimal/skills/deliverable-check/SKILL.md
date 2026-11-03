---
name: deliverable-check
description: >-
  Checks that every deliverable a task asks for exists, has the requested name and format, and matches what the
  final report claims. Use before finishing any task that names output files.
license: Apache-2.0
metadata:
  author: BlochBench maintainers
  version: "1.0.0"
---

# Deliverable check

Before you finish:

1. Re-read the task statement (TASK.txt) and list every requested deliverable with its exact file name, format and
   location.
2. Confirm that each file exists, is not empty and opens with the tool the task expects (for example, load JSON with a
   JSON parser instead of reading it by eye).
3. If the task asks for code that must run again, run it once from a clean shell in the workspace and check that it
   reproduces the files you deliver.
4. Compare every number in your written summary with the delivered files; fix whichever is wrong.
