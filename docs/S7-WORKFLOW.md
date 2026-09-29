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
| 7.4 | 500-asset load test | **Done** — `docs/LOAD-TEST.md`, 500 assets at 1920×1080 |
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

## S7.4 — measured, and the measurement was wrong three times first

500 assets at 1920×1080 through the full local pipeline: **1.07 assets/s,
end-to-end p95 552 ms, 276 s for 500, peak 218 MB.** Solar triage p50 **1.19 ms**,
which agrees with the isolated microbenchmark in `LATENCY-BASELINE.md` (1.11 ms)
now that the methodology is fixed.

Three defects had to be found before those numbers meant anything:

1. **`tracemalloc` was running during the timed loop.** Profiling allocations and
   timing in one pass inflated the solar stage from 1.115 ms to **3.920 ms** — a
   3.5× factor, uniform across the distribution, which is the shape of a
   systematic error rather than a slow tail. It would have shipped as a latency
   regression that did not exist. Peak memory is now a separate, labelled sample.
2. **A fixed capture time of 08:15 UTC is physically impossible across the
   corpus.** The corpus stores a date and no time, and spans 84° of longitude, so
   at that hour the Brazil site sits at 05:15 local with the sun **15° below the
   horizon** — and the pipeline correctly answered
   `QUARANTINE_NIGHTTIME_CAPTURE_ANOMALY` for 7 of 52 assets. The physics was
   right; the assumption was wrong. Captures are now placed at **local solar
   noon**, which is valid everywhere in the corpus and is the best-posed moment
   for shadow geometry.
3. **The two fault injections selected the same assets** (`i % stride == 0`), so
   the low-sun abstention pre-empted a third of the quarantine injections: 50
   faults in, 40 quarantines out, with nothing in the report to explain the ten.

### The finding that shaped the design

The corpus's `|solar_azimuth_error|` **maxes out at 11.4° against a 12°
tolerance**, so on its own this corpus can *never* quarantine. Its 47
`QUARANTINE_FRAUD` decisions come from forgery and provenance signals, not from
solar geometry. A scale test that therefore only measures the pass path is a
scale test of the pass path — so a configurable fraction gets a large injected
error, and a further fraction is captured near the horizon to load the
abstention, which is the product's central claim and cannot be triggered at solar
noon at all.

17 specs pin all of this, including that **every injected fault becomes exactly
one quarantine**, that the two selections are disjoint by construction, and that
abstentions never appear at solar noon.

**Not established:** container-level or multi-process behaviour, the API under
concurrency (`RATE_LIMIT_PER_MINUTE=60` would bind long before throughput did,
so reporting that as throughput would be measuring the limiter), and
registration cost on photographic rather than synthetic imagery.

## Carried forward — an unverified claim

Runbook §4 promises an `e_preview:duration_10` fail-safe for slow drone video.
Nothing in the suite loads one. Per the evidence standard in `AGENTS.md` §2, a
promised path that is never exercised is a liability, so it gets folded into
`scripts/validate_cloudinary_live.py`: verified, or removed from the runbook.

## Load test shape (7.4)

Synthetic 500 assets in fixture mode as the committed, CI-safe gate, with a live
Cloudinary path available as an opt-in script. CI cannot depend on credentials,
and a load test that needs them will silently stop being run.

## S7.3 — VERIFIED

Run on the maintainer's host (Apple Silicon, macOS 26.6.2, Docker 29.8.1,
Compose v5.5.1) on 2026-09-29:

```
docker compose config --quiet     # valid
docker compose build              # 7m37s
docker compose up -d --wait       # both services Healthy
curl -fsS http://localhost:8000/health   # 200, "ONLINE"
curl http://localhost:3000/              # HTTP 200, 83 787 bytes
make verify-docker                 # full cycle, exit 0
```

| Check | Result |
| :-- | :-- |
| Both images build | yes, 7m37s |
| Backend health | `ONLINE`, all capabilities true |
| Frontend | HTTP 200, 83 787 bytes, 11ms |
| Containers healthy | backend and frontend, both `healthy` |
| Unprivileged | `uid=10001(veritas)` / `uid=10002(veritas)` |
| Cross-container API | `/v1/projects/p1/summary` returns facts |

**The rendered compose config confirms the two build-time traps were avoided:**

```
NEXT_PUBLIC_API_URL: http://localhost:8000   # published port, not "backend"
CLOUDINARY_API_KEY: ""                       # empty -> fixture mode, no secrets
```

and the built client bundle contains the literal `http://localhost:8000`, so the
URL really is inlined rather than left to a runtime variable that would have been
ignored.

**Still not established:** that the images build on a *clean* machine or on
non-Apple hardware, and that the pinned wheels resolve for `python:3.12-slim` on
those platforms. One verified host is one data point, and the build took 7m37s,
so CI is not a reasonable place to check it.

**Note for the next person:** `docker compose` fails with `unknown command` until
Docker Desktop has been *launched at least once*. The CLI alone does not provide
the compose plugin — Docker Desktop installs it into `~/.docker/cli-plugins/` on
startup — so the symptom looks like two separate faults when it is one.

## Definition of done

Every rubric bullet traceable to a component, a demo timestamp, and a passing
test; `docker compose up` reaching a working demo on a clean clone.
