# Working Agreement — VERITAS dMRV

## 1. Never push directly to `main`

All work lands on a feature branch, is pushed, and goes through a pull request.
The branch exists so the change is **reviewable and revertible as a unit** — not
as a gate someone has to wait at.

```
git switch -c <type>/<short-description>   # e.g. fix/solar-fixture-margin
# ... work, commit on the branch ...
git push -u origin <branch>
gh pr create --base main --title "..." --body "..."
# wait for CI, then merge the PR yourself (section 2)
gh pr merge <n> --squash --delete-branch
```

`main` is expected to stay green at all times, so a PR should be reviewable on
its own. If a change needs two unrelated things, that is two PRs.

## 2. Raise the PR, then merge it

**The agent opens the PR and merges it once CI is green.** The repository owner
is not required to review first; review remains available and encouraged, but
blocking on it costs more than it protects. The owner may also ask for a walk
through of the diff before merging, and that request is always honoured.

After merging, report to the owner:

- the PR URL and the merge commit,
- what the change does,
- what was **verified** versus merely asserted,
- anything the owner must decide or supply.

Then start the next unit of work from the updated `main`.

Never push follow-up commits to `main` to "fix CI after the fact". If a merged
change turns out to be wrong, that is a new branch and a new PR, so the
correction is itself auditable.

## 3. Branch naming

| Prefix | Use |
| :--- | :--- |
| `feat/` | new capability |
| `fix/` | defect or wrong behaviour |
| `refactor/` | no behaviour change |
| `test/` | tests only |
| `docs/` | documentation only |
| `chore/` | tooling, deps, CI |

## 4. What every PR must state

1. **The problem**, in one paragraph.
2. **What changed**, and what deliberately did not.
3. **Verification** — the exact commands run and their results. A claim with no
   command behind it is a guess.
4. **Defects found while building it**, including ones in the author's own
   earlier work. These are recorded rather than quietly fixed, because a
   codebase that hides its corrections cannot be trusted about the rest.
5. **What is not done**, and why.

## 5. Merge preconditions

Merging is the agent's call, so the bar has to be written down. Merge only when
all of these hold:

- [ ] Every required check on the PR is green — read the actual check list, do
      not assume
- [ ] `make verify`, `make lint` and `scripts/verify_docs.py` pass locally
- [ ] The PR body states verified vs. asserted, and lists what is **not** done
- [ ] `git diff main...HEAD --stat` contains nothing unintended: no secrets, no
      large binaries, no unrelated edits
- [ ] Fixture-mode degradation still works with Cloudinary credentials unset

If a check is red, fix it on the branch and re-run CI. If a check cannot be made
green without credentials or a decision from the owner, leave the PR open and
ask — do not merge a red or knowingly-incomplete change to keep moving.

## 6. Definition of done for a PR

- [ ] `make verify` passes locally (fixture freshness + full suite)
- [ ] `make lint` passes
- [ ] Coverage gate 85% still met
- [ ] `scripts/verify_docs.py` reports 0 errors
- [ ] No new ungrounded claim in `docs/`
- [ ] Fixture-mode degradation still works with Cloudinary credentials unset
- [ ] Any new threshold or constant is justified by a measurement, in a comment
      or a test, not asserted
- [ ] PR merged, and `main` green

## 7. Evidence standard

The single rule this project exists to enforce, applied to ourselves first:

> A number, threshold or capability in this codebase must be traceable to a
> reference implementation, a physical argument, or a measurement taken by this
> team. Anything else is a defect.

This is why there is a doc linter, a fixture generator that refuses to emit
unreliable cases, a grounding check on generated prose, and a benchmark that
publishes a machine profile. Adding a constant is a design decision and needs
the same scrutiny as adding code.

Known cases where this standard caught us:

| Claim | Outcome |
| :--- | :--- |
| Chave allometric prefactor `0.0673` | "Corrected" to `exp(-0.533)` — **withdrawn**, the original was right |
| Moiré threshold `> 4.2` | unachievable by the phenomenon; demoted to advisory |
| `< 800 ms` homography | unbaselined; measured 1217 ms at 4K and **failed** until optimised |
| Solar test vectors | all four outside their own tolerance; one physically impossible |
| `createThinPlateSplineShapeTransformer` | does not exist in OpenCV 4.10 |
| `react@19.0.0-rc-66855b96-20241015` | HTTP 404, never published |
| `react@19.0.0-rc-65a56d0e-20241020` | resolved, but pinned as an **exact** version by `next@15.0.0` — a framework pinning one dated RC is a maintenance trap |
