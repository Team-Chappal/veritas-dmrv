# Working Agreement — VERITAS dMRV

## 1. Never push directly to `main`

All work lands on a feature branch, is pushed, and is proposed as a pull
request. **The repository owner reviews and merges.** An agent opening a PR is
not the same thing as that change being accepted.

```
git switch -c <type>/<short-description>   # e.g. fix/solar-fixture-margin
# ... work, commit on the branch ...
git push -u origin <branch>
gh pr create --base main --title "..." --body "..."
# then STOP and report the PR URL for review
```

`main` is expected to stay green at all times, so a PR should be reviewable on
its own. If a change needs two unrelated things, that is two PRs.

## 2. Report the PR and stop

After opening a PR, the agent's job is done for that unit of work. Report:

- the PR URL,
- what the change does,
- what was **verified** versus merely asserted,
- anything the owner must decide.

Do not merge. Do not push follow-up commits to `main` to "fix CI after the
fact" — push another commit to the same branch instead.

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

## 6. Definition of done for a PR

- [ ] `make verify` passes locally (fixture freshness + full suite)
- [ ] `make lint` passes
- [ ] Coverage gate 85% still met
- [ ] `scripts/verify_docs.py` reports 0 errors
- [ ] No new ungrounded claim in `docs/`
- [ ] Fixture-mode degradation still works with Cloudinary credentials unset
- [ ] Any new threshold or constant is justified by a measurement, in a comment
      or a test, not asserted

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
