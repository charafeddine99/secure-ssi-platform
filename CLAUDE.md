# Working rules for Claude in this repository

These rules apply to every task in this project, not only the current one.

## Git workflow

1. Before starting any task, run `git status` and check the active branch. Identify the owner's working
   branch and make every change on it. If it is not clear which branch is the owner's, ask; never guess.
   The owner's working branch is currently `besna-dev`.
2. Never commit or push to `main`, and never merge into `main`.
3. Finish work in small, independent steps. After each step, run the tests that cover it. When they pass,
   stage only the files of that step, review them with `git diff --cached`, create a separate,
   descriptive commit and push it directly to the owner's branch.
4. Do not hold commits back until a large task is finished: move in small, safe, meaningful steps.
5. Review changes that were already in the working tree before the task. Never delete or overwrite the
   owner's changes or changes left by earlier work, and never put them into your own commits without
   the owner's permission.
6. Never commit or push `.env` files, API keys, passwords, private keys, user data, database backups or
   any other sensitive file.
7. If tests fail, do not create a normal commit: fix the failures first. Never force-push, rewrite
   history, reset, or overwrite existing commits.
8. After each commit and push, report the commit hash, what changed, the test results, and whether the
   push succeeded.

## Repository notes

- The repository is public: scan the staged changes for secrets and personal data before every push.
- `research/` is kept local on purpose. Never stage, commit or push it.
- Commit messages are written in English with a conventional prefix (`feat(identity): …`,
  `docs: …`, `test(audit): …`).
- The checkout lives under OneDrive; run commits as `git -c maintenance.auto=false commit …`.
