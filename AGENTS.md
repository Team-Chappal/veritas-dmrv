# AGENTS.md — working notes for this repository

Read this before your first change. It carries only what you cannot get by
looking at the tree. The full agreement is in `CONTRIBUTING.md`.

## 1. You merge your own PRs

Work lands on a branch, goes through a PR, and **you merge it once CI is
green**. The owner reviews when he chooses; he is not a gate, so do not stop and
wait for him to click merge.

```
git switch -c <type>/<short-description>
# ... work ...
git push -u origin <branch>
gh pr create --base main --title "..." --body "..."
gh pr checks <n>                       # read the real list; assume nothing
gh pr merge <n> --squash --delete-branch
```

Merge only when the checks in `CONTRIBUTING.md` §5 hold. If a check cannot go
green without credentials or a decision from the owner, leave the PR open and
ask. A correction to merged work is a new branch and a new PR, so every
correction stays auditable.

## 2. Evidence standard

A number, threshold or constant must trace to a reference implementation, a
physical argument, or a measurement taken here. Anything else is a defect — the
doc linter, the fixture generator and the grounding check all exist to enforce
this, and they have already caught six bad constants, including a confident
"correction" to the Chave prefactor that had to be withdrawn. Look the value up
or measure it; do not recall it.

When you find one of these in your own earlier work, record it in the PR body
rather than quietly fixing it.

## 3. Environment

- Python lives in `backend/.venv`. Run tests as
  `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q`.
- `make verify` = fixture freshness + full suite. `make lint` import-checks every
  module and catches bad imports early.
- **Cloudinary credentials are absent by default.** Credentialed paths run in
  fixture mode and the app must stay usable that way — CI has a job that asserts
  it. `scripts/validate_cloudinary_live.py` is the one command that exercises the
  live paths; it has never been run, so treat those paths as unproven until it
  exits clean.
- Develop on the local APFS repo, not the USB volume at `/Volumes/VENTOY` — it
  is FAT32, case-insensitive and slow, and tests crawl there. `make sync-usb`
  mirrors when the volume is mounted.

## 4. Known open item

The Cloudinary webhook signature **scheme** is deliberately a parameter, not an
assertion. Getting it wrong lets an unauthenticated POST mark a fraudulent asset
as verified, so it gets settled by observing a real notification
(`validate_cloudinary_live.py` step 9) rather than by trusting documentation or
memory. Once the scheme is confirmed, pin it and record the evidence.

## 5. Where things stand

`EXECUTION-PLAN.md` holds the S0–S7 stage definitions. `docs/RUBRIC-TRACEABILITY.md`
maps the grading brief to implemented behaviour and lists the remaining gaps —
read its gaps section before planning a stage, so you are not rebuilding
something that already shipped.
