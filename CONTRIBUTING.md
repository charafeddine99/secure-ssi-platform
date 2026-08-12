# Contribution workflow

## Completed change publication rule

Every completed sprint, prompt, or user request that changes this repository
must follow this sequence before it is considered delivered. Read-only requests
and requests that produce no repository changes do not create empty commits.

1. Run the complete sprint-specific test suite and all applicable regression,
   lint, type-check, build, dependency, and formatting checks.
2. Review `git status`, the complete diff, and `git diff --check`. Confirm that
   the change set contains only sprint-related source, test, configuration, and
   request-related source, test, configuration, and documentation files. Never
   commit secrets, `.env` files, private keys,
   caches, dependency directories, build output, or other generated artifacts.
3. Stage only the reviewed files and create a descriptive commit on the sprint
   branch. One completed logical change should have one clear commit whenever
   practical.
4. Immediately push the tested commit and its sprint branch to the configured
   GitHub remote with a normal, non-force push.
5. Keep `main` stable. Advance it only through a reviewed fast-forward or merge
   of completed and tested sprint history, and push it immediately afterward.
6. Verify the remote branch and commit, then confirm that the local working tree
   is clean.

Do not rewrite shared history or use a force push for the normal sprint
workflow. If the remote history conflicts with the local tested history, stop
and resolve the discrepancy explicitly before publishing.
