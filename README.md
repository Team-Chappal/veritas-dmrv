# VERITAS dMRV

**AI-powered impact & sustainability media intelligence platform.**

Verification: for every field photograph, *is it real, from where it claims, when
it claims, and unedited?* Measurement: *has the vegetation actually changed, and
by exactly how much?* Evidence: *can an auditor reproduce the result and can the
record survive challenge?*

Built for **Code Cubicle 6.0 — Problem Statement 02 (Cloudinary)**.

---

## Quickstart

```bash
make bootstrap        # venv + pinned deps + import verification
make fixtures         # generate solar fixtures from pvlib ground truth
make test             # full suite
make dev-mock         # mock server on :8000 (no credentials needed)
```

Everything works with **no Cloudinary credentials**. Absent credentials select
fixture mode, where every remote call degrades to a local fallback. Credential
absence is a supported state, not a crash — a stage demo must never depend on a
key.

---

## Where things live

```
docs/          Product + engineering specification suite (15 documents)
EXECUTION-PLAN.md   Rubric-first build order, with cut list
backend/
  services/    Pure computational units. No FastAPI, no Cloudinary imports.
    solar_service.py      pvlib ephemeris -> shadow-coherence verdict
    biomass_service.py    Chave 2014 allometry -> tCO2e -> VM0047 discount
    forgery_service.py    Laplacian + FFT + Moire synthetic/screen detection
    dedup_service.py      pHash corpus, resize/recompress invariant
  core/        Config, auth, Cloudinary client
  tests/       Tier 1 physics, Tier 2 vision, fixtures
  mock_server.py        High-fidelity dev server (delegates to real services)
scripts/
  gen_solar_fixtures.py  Fixtures GENERATED from pvlib, never hand-written
  verify_docs.py         Lints docs for unverified claims (zero deps)
frontend/      Next.js 15 App Router console
```

**Dependency rule:** services never import routes; routes import services.
Every service is independently testable with `pytest` and no credentials.

---

## The three findings that shaped this codebase

The specification suite was audited before any code was written. Three defects
were material enough to change the implementation, and all three are now
regression-tested.

### 1. The allometric constant understated carbon by 8.72×

The original equation used a prefactor of `0.0673` and was described as
implementing Chave et al. (2014) pantropical allometry. The published regression
is `ln(AGB) = -0.533 + 0.976·ln(ρD²H)`, so the prefactor is
`exp(-0.533) ≈ 0.5868`.

For a 100 m² canopy at 4 m height: original `0.1005 tCO₂e`, correct `0.8762 tCO₂e`.

This is a commercial defect, not an academic one — the platform would have
systematically under-credited every project it certified.
→ `services/biomass_service.py`, tested in `test_physics.py::TestAllometricCarbon`.

### 2. Every hand-written solar test vector was wrong

Four vectors in the spec's test suite were all outside their own stated
tolerances, and one was physically impossible: Ankara, 2026-06-21T10:00Z was
documented at 138.5° when solar noon there is 09:48 UTC, so the azimuth **must**
be ≈188°.

Worse, the flagship "legitimate photo" demo fixture cleared the 12° fraud
threshold by **1.1° of margin** — one refactor away from disqualifying a genuine
planting, live, on stage.

Fixtures are now *generated* from `pvlib` and the generator **refuses to write**
if any genuine case clears the fraud threshold by under 5°.
→ `scripts/gen_solar_fixtures.py`; CI gate `make fixtures-check`.

### 3. The spec's written derivation contradicted its own code

The solar azimuth expression printed in the design document was not the NOAA
form and did not agree with the implementation beside it. The code was right; the
math was wrong — the worst failure mode, because a reviewer concludes the physics
is unsound when it is not.

The service now delegates to `pvlib` rather than re-deriving astronomy, and
`scripts/verify_docs.py` fails CI if the wrong expression reappears.

---

## Design commitments

**Abstention is a feature.** Below 10° of solar elevation a cast shadow is
dominated by terrain slope, not the sun, so the detector returns
`REVIEW_LOW_SUN_UNDETERMINED` and defers to C2PA provenance and pHash dedup. A
forensic tool that always returns a confident verdict is a liability; a ranger
photographing at dawn must not be falsely accused.

**Heuristics are labelled as heuristics.** The forgery detectors are tuned
engineering defaults, not classifiers trained on a labelled corpus. Their
confidence reflects detector agreement, not a calibrated posterior. The
statistically honest place for a calibrated number is the decision layer, which
consumes these features alongside others.

**Proxies are labelled as proxies.** `DBH = 2.1·√(canopy_area)` is a
crown-projection estimate, not a dendrometer measurement at 1.3 m. Every emitted
record carries a `dbh_source` field, and the audit dossier cannot present one as
the other.

**LLMs write prose, never verdicts.** Narrative summarisation is permitted;
binary verification decisions are not. Both are rubric requirements and they do
not conflict.

**Docs are linted like code.** A document that states a number nothing supports
is a defect. `make lint` fails on it.

---

## Verification

```bash
make fixtures-check   # committed solar fixtures match a fresh pvlib run
make test-tier1       # physics + forensics
make test-tier2       # computer vision
make test-cov         # 85% coverage gate
make lint             # import + doc-claim linter
make verify           # fixtures-check + full suite
```

## Deployment note

The specification volume is a **FAT32 USB drive**, which is case-insensitive and
measures **~176× slower** than APFS for small-file writes (26.35s vs 0.15s per
2000 files). An `npm install` creates ~40,000 files. Development therefore
happens on local APFS; `make sync-usb` mirrors source to the volume for
portability. Do not run `npm install` or `git` on the FAT32 volume.
