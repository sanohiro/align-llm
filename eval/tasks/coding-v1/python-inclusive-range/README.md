# Inclusive range repair

The target repository contains an off-by-one defect in `inclusive_total`. Repair the implementation
so it includes both interval endpoints.

Constraints:

- Start from the exact Git revision in `task.json`.
- Edit only `src/inclusive_range.py`.
- Do not change or skip the tests.
- The validation command in `task.json` must pass.

The runner first proves the pinned checkout fails validation, applies the candidate patch, rejects
edits outside the allowlist, and then runs validation again. It creates the target repository in a
temporary directory and removes it after every run.
