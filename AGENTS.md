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
# Read the check list in a way that cannot be truncated into a false pass.
# `gh pr checks <n> | tail -3` HID a failure once already, and a PR went out with
# a red e2e job. Use the helper, which exits non-zero unless everything passed.
./scripts/ci-gate.py <n> && gh pr merge <n> --squash --delete-branch
```

**EVERY commit goes through a PR, without exception.** Merge it yourself once CI
is green; never push to `main` directly.

This is a rule, and a rule was not enough — it was already written here and did
not prevent it twice. Both times were a `git push` with no refspec, written into
a command chain, run while `HEAD` was already on `main`: commits `d26b589` and
`dc26c66` reached `main` with no PR and no CI. `ci-gate.py` protected every
merge and saw neither, because those were **pushes**, and a merge gate has
nothing to merge.

So the rule now has teeth in front of the push:

```
make install-git-hooks   # once per clone
```

`.git/hooks/pre-push` refuses to push a commit to `main` that carries no merged
PR reference, and `scripts/check_main_provenance.py` runs in CI on every push to
`main` so the commit is visible even if the hook was bypassed. The hook has a
deliberate escape hatch — `git push --no-verify` — because an override has to
exist, or the first real emergency produces a force-push, which is worse than
the thing it prevents.

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
  it. Put real credentials in `backend/.env` (gitignored, loaded by
  `core.config`); `VERITAS_NO_DOTENV=1` opts out, which is how the test suite
  keeps itself in fixture mode on a machine that has them.
- `scripts/validate_cloudinary_live.py` exercises the live paths. **It has been
  run** — 20 pass, 0 fail, 0 warnings, 1 skipped (`f_pdf`, paid-plan only) —
  and it found six real defects in the transformation grammar that the unit tests
  were green about. Re-run it after touching `core/cloudinary_client.py`; a URL
  that a test asserts the shape of is not a URL anyone has loaded.
- Develop on the local APFS repo at `~/veritas-dmrv`. **That tree and GitHub are
  the only things that matter.** `~/Desktop/cc` is a portable mirror;
  `/Volumes/VENTOY/cc` is a convenience mirror on removable FAT32 media, and it
  is frequently not connected.
- Neither mirror is part of any build. `make sync-usb` and `make sync-desktop`
  are optional and exit cleanly when their target is absent — a target that fails
  when a drive is unplugged is a target that trains you to ignore its failures.
  Anything that matters belongs in a commit, not on removable media.
- Frontend: `make fe-build` (npm ci + production build + typecheck) and
  `make e2e` (Playwright against a production build, backend not required).
  `frontend/package-lock.json` is committed, so `npm ci` is what runs.

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
