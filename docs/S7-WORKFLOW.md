# S7 — Hardening, QA, delivery

`main` at `fcfa31a`: 672 backend tests, 166 e2e, 95% coverage, five green CI
jobs, zero build warnings. S0–S6 are complete.

## Status audit

Four of the eight tasks were already done before planning began, so they are
marked complete rather than re-implemented:

| # | Task | Status |
| :-- | :-- | :-- |
| 7.1 | 4-tier test pyramid | **Done** — 672 unit, 166 e2e; all four tier targets exceeded |
| 7.2 | GitHub Actions | **Done** — 5 jobs, coverage gate, `scripts/ci-gate.py` |
| 7.5 | Demo fail-safes | **Done** — cache mode (6.11), `e_preview` clip, runbook §4 |
| 7.8 | Reset `08` §1.2 checkboxes | **Done** — already `[ ]`, with the v1.2.0 correction note |
| 7.3 | Docker Compose | **Built, unverified** — no Docker daemon on this host |
| 7.4 | 500-asset load test | Pending |
| 7.6 | Rubric matrix with demo timestamps | Partial — traceability exists, timestamps do not |
| 7.7 | Re-cut 180s pitch to lead with rubric #3/#5 | Pending |

## Ordering, and why

**7.3 → 7.4 → 7.6 → 7.7.**

7.3 first because it is an exit criterion (`docker compose up` reaches a working
demo) and the only task that can fail for reasons unrelated to this codebase —
Docker absent, ports taken, build ordering. Better to find that out now. It is
also cut-list item 5, so it is the first thing to drop if time runs short.

7.4 next because **it may change the design**. 500 assets through the real
pipeline could surface a performance problem needing a fix, and discovering that
after writing the pitch script and demo timestamps would mean rewriting claims
already on the page.

7.6 and 7.7 last because both are claims *about* the finished system. They should
be written once nothing else can move.

## Carried forward — an unverified claim

Runbook §4 promises an `e_preview:duration_10` fail-safe for slow drone video.
Nothing in the suite loads one. Per the evidence standard in `AGENTS.md` §2, a
promised path that is never exercised is a liability, so it gets folded into
`scripts/validate_cloudinary_live.py`: verified, or removed from the runbook.

## Load test shape (7.4)

Synthetic 500 assets in fixture mode as the committed, CI-safe gate, with a live
Cloudinary path available as an opt-in script. CI cannot depend on credentials,
and a load test that needs them will silently stop being run.

## S7.3 — what is and is not established

**Established.** Two Dockerfiles, a compose stack, and `.dockerignore`; the
backend `CMD` booted locally and `/health` answered; 17 deployment-contract
specs, each **mutation-tested** — ten deliberate misconfigurations were each
caught by exactly the spec that claims to catch them:

| Injected fault | Caught by |
| :-- | :-- |
| API URL used the compose service name | browser-resolvability spec |
| API URL moved to a runtime env var | build-arg spec |
| frontend waited only for `service_started` | health-ordering spec |
| a credential made required (`${VAR}`) | no-hard-requirement spec |
| backend bound `127.0.0.1` | all-interfaces spec |
| healthcheck probed a non-existent path | route cross-check |
| healthcheck port ≠ CMD port | port-agreement spec |
| `backend/.env` removed from the build context | build-context spec |
| image moved to Python 3.13 | wheel-pin spec |
| `npm install` instead of `npm ci` | frontend-install spec |

**Not established.** That either image **builds**, that the pinned wheels resolve
for the image's Python, and that `docker compose up` reaches a working demo.
Docker is not installed on this host, so **the S7.3 exit criterion is UNVERIFIED**
and `make verify-docker` says so rather than passing quietly. It is deliberately
not wired into `make verify`, because CI has no daemon and a target that always
fails there is a target nobody runs.

Run on a host with Docker:

```
make verify-docker
```

## Definition of done

Every rubric bullet traceable to a component, a demo timestamp, and a passing
test; `docker compose up` reaching a working demo on a clean clone.
