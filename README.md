# VERITAS dMRV

**AI-powered impact & sustainability media intelligence platform.**

Verification: for every field photograph, *is it real, from where it claims, when
it claims, and unedited?* Measurement: *has the vegetation actually changed, and
by exactly how much?* Evidence: *can an auditor reproduce the result and can the
record survive challenge?*

Built for **Code Cubicle 6.0 — Problem Statement 02 (Cloudinary)**.

### Live demo

**https://veritas-dmrv.vercel.app**

Opens in any browser, no install, no account, no keys. A static bundle of
1.1 MB served from a CDN — it works with the backend *entirely absent*, which is
the design, not a fallback: every panel is badged `Fixture` and says why.

> **Every number in that demo is a fixture.** There is no backend behind it, so
> no Cloudinary call is made. The panels label themselves accordingly, and
> `docs/14` separates what is measured from what is claimed on a stage.

To run the full stack locally instead — mock backend, real API, everything
degrading honestly when credentials are absent:

```bash
make verify-docker    # or: make dev-mock
```

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
    biomass_service.py    Chave 2014 Eq.4 allometry -> tCO2e -> VM0047 discount
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

The specification suite was audited before any code was written, and again
against live reference implementations while the code was being written. Two
defects were real. One "defect" was me.

### 1. Every hand-written solar test vector was wrong

Four vectors in the spec's test suite were all outside their own stated
tolerances, and one was physically impossible: Ankara, 2026-06-21T10:00Z was
documented at 138.5° when the sun is essentially on the meridian there, giving
187.74° — a 49.24° error that cannot occur at any time of day at that longitude.

Worse, the flagship "legitimate photo" demo fixture cleared the 12° fraud
threshold by only **2.56° of margin** — one refactor away from disqualifying a
genuine planting, live, on stage.

Fixtures are now *generated* from `pvlib` and the generator **refuses to write**
if any genuine case clears the fraud threshold by under 5°. It also probes for
the solar conditions each scenario actually needs, after three hand-picked
timestamps turned out to test the wrong thing (a Berlin "genuine" case that had
dropped below the abstention gate; a Nairobi "dawn" case with the sun 32° up;
a Pretoria case at local midnight).
→ `scripts/gen_solar_fixtures.py`; CI gate `make fixtures-check`.

### 2. The spec's written derivation contradicted its own code

The solar azimuth expression printed in the design document was not the NOAA
form and did not agree with the implementation beside it. The code was right;
the math was wrong — the worst failure mode, because a reviewer concludes the
physics is unsound when it is not.

The service now delegates to `pvlib` rather than re-deriving astronomy, and
`scripts/verify_docs.py` fails CI if the wrong expression reappears.
→ `services/solar_service.py`.

### 3. I "corrected" a correct constant, and it took external verification to catch

This one is worth keeping.

The spec's allometric code used a prefactor of `0.0673`. Reading the equation
rather than trusting it, I concluded this was wrong and replaced it with
`math.exp(-0.533) ≈ 0.5868`, documenting an "8.72× carbon understatement" across
the suite. It sounded right. It was wrong.

**Chave et al. (2014) Eq. 4 is `AGB = 0.0673 × (WD·H·D²)^0.976`.** The original
constant was correct. This is confirmed verbatim in the R `BIOMASS` package
(`computeAGB`, Réjou-Méchain, Tanguy & Perre, CRAN), whose documentation reads:

> If tree height data are available, the AGB is computed thanks to the following
> equation (Eq. 4 in Chave et al., 2014): `AGB = 0.0673 * (WD * H * D^2)^0.976`

The `exp(-0.533)` value produced ~6.7× the stem's own wood volume at every DBH
from 4 cm to 40 cm — a constant, systematic factor that should have read as
"coefficient is wrong" rather than "the regression behaves like that".

**What changed as a result:** the prefactor is reverted to the verified
constant, the detour is documented rather than deleted, and
`test_result_is_plausible_against_stem_geometry` now pins AGB to within a factor
of a few of `π/4·D²·H·ρ` — the check that would have caught this in seconds
instead of hours. `verify_docs.py` now *guards* `0.0673` and flags `0.5868`.

The failure mode was the seductive one: a plausible intercept, converted to a
prefactor, attached to a real paper, and wrong — in a project whose entire
premise is replacing assertion with mathematics. Writing the check down is the
point.

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

## Deployment

### Live

**https://veritas-dmrv.vercel.app** — a static bundle, no server runtime, no
credentials. The Vercel project's Root Directory is `frontend/` and
`vercel.json` lives there; a copy at the repo root is ignored **in silence**,
which cost a real deployment once (see `docs/S7-WORKFLOW.md`).

Every push to `main` redeploys through the GitHub integration, and
`scripts/ci-gate.py` refuses to merge while the resulting preview check is red.

### Locally

```bash
make verify-docker   # both images build, stack healthy, demo answers
make demo-export     # static bundle into frontend/out/ — serves with
                     # `python3 -m http.server` on a machine with no Node
```

`make demo-export` is the offline fallback: 1.1 MB of files that run anywhere,
which is what you want when the thing you do not trust is the network.

### Mirrors are optional

The spec volume is a **FAT32 USB drive**: case-insensitive and **~176× slower**
than APFS for small-file writes (26.35s vs 0.15s per 2000 files), so `npm install`
(~40,000 files) and `git` do not belong on it. It is not required, and
`make sync-usb` exits cleanly when it is absent.

Both mirror targets exclude `backend/.env`, `*.pem` and `*.key`. That is not a
convention: the mirrors once shipped live Cloudinary credentials and a C2PA
signing key onto removable media, because `.gitignore` protects a file from git
and does nothing about `rsync`.
