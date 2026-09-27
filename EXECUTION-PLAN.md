# VERITAS dMRV — Execution Plan
**Derived from:** `docs/01–14` suite + `Code Cubicle 6.0 Problem Statements.pdf` (Problem Statement 02)
**Repo state at time of writing:** documentation only. No git, no source, no `backend/`, no `frontend/`.
**Round deadline (per problem statement PDF):** 3 OCT online · 11 OCT offline

---

## 0. READ THIS FIRST — RUBRIC REALIGNMENT

I read the actual Problem Statement 02 text. The `docs/` suite was written against a *self-invented* problem (carbon-credit fraud forensics) that only partially overlaps the graded one.

### 0.1 The actual graded brief

> **PROBLEM STATEMENT 02 · CLOUDINARY — AI-Powered Impact & Sustainability Media Platform**
>
> NGOs, governments, and sustainability organizations generate large volumes of photos and videos from field projects, environmental initiatives, infrastructure work, and community programs. Manually organizing, analyzing, verifying, and turning this media into meaningful evidence and reports is time-consuming and difficult to scale.
>
> **GOAL — Build a complete platform that can:**
> 1. Analyze and intelligently organize large collections of image and video evidence.
> 2. Identify relevant projects, activities, locations, and visual signals from media.
> 3. Compare before-and-after media to demonstrate visible project or environmental changes.
> 4. Generate visual reports, summaries, and campaign-ready content from collected evidence.
> 5. Make media searchable through AI-powered metadata, tagging, and semantic discovery.
> 6. Preserve traceability to the original source assets and transformations.
>
> **EXPECTED OUTCOME:** A scalable media intelligence product that transforms raw field media into searchable evidence, measurable impact, and compelling visual stories.
>
> Also stated in the intro: organize evidence by **project, location, and timeline**.

### 0.2 Rubric coverage audit

| # | Rubric requirement | Docs coverage | Verdict |
| :-- | :--- | :--- | :--: |
| 1 | Analyze + intelligently organize **large collections** | Structured metadata, folder taxonomy. Demo corpus is 2–3 assets. | ⚠️ Partial — no bulk path, no scale evidence |
| 2 | Identify projects, activities, **locations**, and **visual signals** | GPS/EXIF → location ✔. **Visual signals: no AI tagging pipeline at all.** | 🔴 Gap |
| 3 | Compare **before-and-after** media | SIFT + MAGSAC++ homography, GLI/Otsu delta, split slider | 🟢 Strongest asset |
| 4 | Generate **visual reports**, **summaries**, **campaign-ready content** | PDF dossier ✔, certificate PNG ✔, 9:16 reel ✔. **No summaries of any kind.** | ⚠️ Partial |
| 5 | **AI-powered** metadata, tagging, **semantic discovery** | Lucene keyword search over structured metadata only. No auto-tagging, no embeddings, no semantic/vector search. | 🔴 Gap |
| 6 | Traceability to original assets + transformations | C2PA, public IDs, SHA-256 roots, transformation logs | 🟢 Strong |
| — | Organize by **timeline** | `capture_timestamp` + `milestone_phase` in schema. **No timeline UI.** | 🔴 Gap |

### 0.3 Schedule misallocation — the core problem

The suite spends the majority of its engineering hours on things the rubric does not mention, and omits things it names twice:

| Invested heavily, **zero rubric points** | Unbuilt, **explicitly graded** |
| :--- | :--- |
| EUDR Article 9 polygon validation (M7) | AI visual tagging / auto-classification |
| Chave allometric biomass + VM0047 discount (M5/M5b) | Semantic / vector search ("semantic discovery") |
| C2PA ES256 signing chain | Media summarization ("summaries") |
| $40B carbon-market unit economics, 3-tier personas | Timeline organization UI |
| SAM instance segmentation (M4) | Bulk ingestion for "large collections" |
| Gyroscopic horizon leveler | Scale evidence (1,000+ asset corpus) |

**Recommendation:** keep the forensics (it is a genuine differentiator and serves rubric #3 "demonstrate visible change" better than a slider alone), but **demote** EUDR + allometric biomass + SAM to a "cut-first" tier, and **promote** enrichment/semantic/summary/timeline to P0.

### 0.4 A note on the LLM contradiction — it is resolvable

`02-ARCHITECTURE` Principle 2 forbids conversational LLMs from **binary verification or financial disbursement decisions**. Rubric #4 asks for **summaries**. These do not conflict: LLM-generated *narrative* is permitted, LLM-generated *verdicts* are not. State this explicitly in the architecture doc so a judge who notices the tension sees a designed boundary rather than an inconsistency.

---

## 1. Execution principles

1. **Numerics before infrastructure.** The physics must be provably correct before anything consumes it. S1 gates everything.
2. **Contract before code.** The mock server lands in S1 so the frontend can start in S2 while the CV track is still running.
3. **Offline-first verification.** Every core claim must be testable with `pytest` and no Cloudinary account. Credentialed features degrade, they do not break.
4. **Rubric-first sequencing.** Anything not traceable to a rubric bullet or a named judge question is cut before it is started.
5. **Every stage has a machine-checkable exit criterion.** No stage ends on "it looks right."

---

## 2. Stage 0 — Repo foundation

**Goal:** a runnable, versioned, single-command-developable skeleton. Nothing else starts until this is green.

| # | Task | Deliverable |
| :-- | :--- | :--- |
| 0.1 | Clean AppleDouble artifacts, add `.gitignore` | `.gitignore` (incl. `._*`, `venv/`, `.next/`, `__pycache__/`, `.env`) |
| 0.2 | `git init`, initial commit of `docs/` | repo history |
| 0.3 | Create directory skeleton | `backend/{core,models,services,api/v1/routes,tests}`, `frontend/`, `fixtures/`, `scripts/`, `cloudinary/` |
| 0.4 | Pin + **install** backend deps, verify each imports | `backend/requirements.txt`, `make bootstrap` |
| 0.5 | Pin + **install** frontend deps | `frontend/package.json` |
| 0.6 | Config loader with graceful credential absence | `backend/core/config.py` |
| 0.7 | Root orchestration | `Makefile` (`bootstrap`, `dev`, `test`, `lint`, `seed`, `e2e`) |

**Exit criteria**
```bash
make bootstrap                      # completes with no error
python -c "import cv2, numpy, pvlib, shapely, pyproj, fastapi, cloudinary"   # all import
npm --prefix frontend run build     # exits 0
```

**Decisions locked here**
- Icon library: **`lucide-react`** (already in the pinned manifest; amend `06` §1.2 which mandates Phosphor). Do not install two.
- Python 3.12, Node 22.
- `pytest` + `pytest-cov` gate at `--cov-fail-under=85`.

---

## 3. Stage 1 — Numerical core (the trust anchor)

**Goal:** every quantitative claim the platform makes is provably correct, and the two CRITICAL defects from the brief are fixed **before** any consumer is written.

> **This stage is the highest-risk work in the project and must not be parallelized away or deferred.** The allometric constant under-reports carbon by 8.72×, and all four Tier-1 solar fixtures are outside their own tolerances. Building on top of those numbers compounds the error.

| # | Task | Deliverable |
| :-- | :--- | :--- |
| 1.1 | Solar ephemeris as **ground truth** via `pvlib` | `services/solar_service.py` |
| 1.2 | Shadow-coherence verdict; **raise the low-sun gate** from `elev < 0` to `elev < 10°` and route below it to `REVIEW_AMBIGUOUS`, never hard-quarantine | in 1.1 |
| 1.3 | **Regenerate every fixture from `pvlib` output** — no hand-written azimuths. Store the generating call in a comment | `tests/fixtures/solar_vectors.json` |
| 1.4 | Correct the **NOAA derivation** in `03` §1.2 to match the code; delete the no-op ternary at `03` line 74 | doc patch |
| 1.5 | Fix the **allometric constant** `0.0673` → `exp(-0.533) ≈ 0.5868`; add a test asserting agreement with Chave within 1% | `services/biomass_service.py` |
| 1.6 | VM0047 §8.4 sampling-error discount | in 1.5 |
| 1.7 | Forgery detection: Laplacian variance + 2D FFT peak ratio + Sobel Moiré ratio | `services/forgery_service.py` |
| 1.8 | pHash + Hamming-distance corpus dedup | `services/dedup_service.py` |
| 1.9 | Mock server implementing **100%** of the API contract with CORS `*`; fix the `> 200` fraud branch that quarantines the documented success payload | `backend/mock_server.py` |

**Exit criteria**
```bash
make test TIER=1
# 1. All solar vectors generated from pvlib; every one within its own tolerance.
# 2. Chave test: |code − exp(-0.533)·(ρD²H)^0.976| / reference < 0.01
# 3. Fraud fixture (Tsavo 11:30 UTC) still yields Δθ > 150° -> QUARANTINE
# 4. Genuine fixture yields Δθ well under 12° with ≥ 5° margin  (currently 1.1° — must widen)
# 5. Low-sun (elev < 10°) returns REVIEW_AMBIGUOUS, never QUARANTINE
# 6. Mock server serves the 05-API-SPEC VERIFIED_PASS payload as VERIFIED_PASS
```

**Margin requirement (important):** the genuine fixture must clear the 12° threshold by **at least 5°**. A demo that passes by 1° is a coin flip on stage.

---

## 4. Stage 2 — Computer vision

**Goal:** the rubric's #3 ("compare before-and-after to demonstrate visible change") becomes a real, measured, reproducible number.

| # | Task | Deliverable | Rubric |
| :-- | :--- | :--- | :--: |
| 2.1 | Radiometric normalization (per-channel CDF quantile transfer) | `services/radiometric_service.py` | 3 |
| 2.2 | SIFT → FLANN → Lowe 0.75 → `USAC_MAGSAC` homography + condition-number guard | `services/homography_service.py` | 3 |
| 2.3 | Thin-Plate-Spline fallback for κ(H) > 85 or RMSE > 3.5 px | in 2.2 | 3 |
| 2.4 | **GLI + Otsu** canopy mask + surface-area delta | `services/canopy_service.py` | 3 |
| 2.5 | Reconcile the index naming: GLI everywhere. Amend `01` FR-2.4 and the `05` response body | doc patch | — |
| 2.6 | Synthetic image-pair generator for deterministic tests (tilt/rotate/translate/illumination-shift) | `tests/conftest.py` fixtures | — |
| 2.7 | Photogrammetry regression suite (~40 tests) | `tests/test_vision.py` | — |

**Exit criteria**
```bash
make test TIER=2
# 1. Synthetic 8°-rotation + 15px-shift pair registers at inlier_ratio > 0.70 in < 800 ms
# 2. Illumination-shifted pair: radiometric normalization brings mean luminance within 15% of baseline
# 3. Cloud-shadowed pair does NOT register negative canopy growth (the false-alarm test)
# 4. Degenerate (collinear) homography is rejected, not silently warped
# 5. Every response reports inlier_ratio — no silent failures
```

---

## 5. Stage 3 — Enrichment, AI tagging, semantic search, summaries  ← NEW, P0

**Goal:** close rubric gaps #2, #4, #5. **This stage did not exist in the original plan and is the highest-value addition.**

| # | Task | Deliverable | Rubric |
| :-- | :--- | :--- | :--: |
| 3.1 | Auto-tagging pipeline: fuse Cloudinary `categorization` / `google_tagging` / `google_video_tagging` with locally derived signals (canopy density from GLI, daylight/shadow class from 1.1, water/floodplain hints, forest-cover %) | `services/enrichment_service.py` | 2, 5 |
| 3.2 | Normalized tag vocabulary + confidence scores, written into Structured Metadata | in 3.1 | 5 |
| 3.3 | **Cloudinary Vector Search add-on** for embedding-based similarity ("find assets that look like this mangrove replanting") | `services/semantic_service.py` | 5 |
| 3.4 | **Offline semantic fallback:** deterministic weighted tag/text vector + cosine similarity, zero new dependencies, so the demo works with no account and no network | in 3.3 | 5 |
| 3.5 | Natural-language → Lucene expression compiler (`"mangrove plots in Sector 4 with canopy growth over 25%"` → valid expression) | `services/query_service.py` | 5 |
| 3.6 | Grounded, **deterministic** narrative summary per project from real metrics | `services/narrative_service.py` | 4 |
| 3.7 | Optional LLM augmentation for prose only, hard-gated behind an env key, with a deterministic fallback and an explicit "never used for verdicts" boundary | in 3.6 | 4 |
| 3.8 | Timeline extraction: group assets into milestone epochs; detect coverage gaps | `services/timeline_service.py` | intro |

**Design constraint:** 3.3 and 3.4 must produce the same interface. The Cloudinary path is primary (it satisfies "using Cloudinary"); the local path is the guarantee that the stage demo cannot fail.

**Exit criteria**
```bash
make test TIER=3
# 1. Ingest a fixture -> auto-tags derived from ACTUAL image content, not hardcoded
# 2. 4 semantically similar assets rank above 4 unrelated ones (nDCG @ 10 > 0.8)
# 3. NL query compiler emits a valid expression that executes against the Search API
# 4. Offline semantic path works with CLOUDINARY_* env vars unset
# 5. Summary text contains no number that is absent from the underlying metrics
#     (property test: every numeric token in the summary exists in the source data)
# 6. LLM path disabled -> deterministic summary still produced, byte-identical across runs
```

---

## 6. Stage 4 — Cloud-native platform

| # | Task | Deliverable | Rubric |
| :-- | :--- | :--- | :--: |
| 4.1 | Idempotent `metadata_fields` bootstrap script (11 fields, typed, re-runnable) | `scripts/init_cloudinary_schema.ts` | 1, 6 |
| 4.2 | Cloudinary client wrapper: signed upload, eager transforms, webhooks, transformation-log reads | `core/cloudinary_client.py` | 6 |
| 4.3 | Transformation **log ingestion** → an explicit `source → transformation` provenance table per asset | in 4.2 | **6** |
| 4.4 | Dynamic URL builders: split-diff, 9:16 reel, certificate PNG, vectorized PDF | `lib/cloudinary-urls.ts` | 4 |
| 4.5 | AI Video Analysis → VTT transcription track | in 4.2 | 2 |
| 4.6 | Fixture seeding: **scale corpus**, not 3 images | `scripts/seed_demo_fixtures.ts` | 1 |
| 4.7 | Degradation guard: every Cloudinary call has a local-fixture fallback path | `core/fallback.py` | — |

**Exit criteria**
```bash
make seed
# 1. Schema bootstrap is idempotent — run twice, no error, no duplicates
# 2. 500+ asset corpus seeded, spanning >= 3 projects, >= 4 timeline epochs
# 3. Split-diff URL renders at edge in < 50 ms (timed)
# 4. 9:16 reel + PDF certificate URLs both resolve to valid assets
# 5. With CLOUDINARY_* unset, `make seed && make dev` still serves a full demo
# 6. Provenance table correctly reconstructs every transformation applied to any asset
```

---

## 7. Stage 5 — API layer

| # | Task | Deliverable | Rubric |
| :-- | :--- | :--- | :--: |
| 5.1 | `POST /api/v1/media/ingest` — bulk upload + enrichment + auto-tagging | routes | 1, 2, 5 |
| 5.2 | `GET /api/v1/search` — semantic + structured hybrid, NL query accepted | routes | 5 |
| 5.3 | `POST /api/v1/media/compare` — SIFT registration + canopy delta | routes | 3 |
| 5.4 | `GET /api/v1/projects/{id}/timeline` | routes | intro |
| 5.5 | `GET /api/v1/projects/{id}/summary` | routes | 4 |
| 5.6 | `GET /api/v1/projects/{id}/report` — dossier + QR + PDF URL | routes | 4 |
| 5.7 | `POST /api/v1/cloudinary-webhooks/*` | routes | 6 |
| 5.8 | Auth: JWT with `mrv:field_upload` / `mrv:triage_review` / `mrv:vvb_signoff`; SlowAPI 60 req/min | `core/auth.py` | — |
| 5.9 | Integration + webhook suite (~25 tests) | `tests/test_integration.py` | — |

**Exit criteria:** 5.1–5.7 all reachable and tested; every response carries the provenance block; p95 latency on `/media/compare` < 800 ms.

---

## 8. Stage 6 — Frontend

**Goal:** the rubric's six bullets must each be *visibly* demonstrable in under 180 seconds.

| # | Task | Deliverable | Rubric |
| :-- | :--- | :--- | :--: |
| 6.1 | Next.js 15 shell + design system (tokens, `tabular-nums`, WCAG 2.2 AAA, no color-alone signalling) | `app/layout.tsx` | — |
| 6.2 | **Portfolio grid** — bulk-organized evidence at a glance | `components/PortfolioGrid.tsx` | 1 |
| 6.3 | **Timeline view** — project → epoch → asset, with coverage gaps visible | `components/Timeline.tsx` | intro |
| 6.4 | **Search with AI panel** — NL box + auto-tag chips + semantic matches | `components/SemanticSearch.tsx` | 5 |
| 6.5 | `ProofOfImpactStudio` split slider + inlier-ratio badge | as drafted | 3 |
| 6.6 | `ForensicPhysicsHUD` SVG overlay | as drafted | — |
| 6.7 | Cloudinary hotspot video player + VTT captions | as drafted | 2 |
| 6.8 | **Campaign content studio** — one-click 9:16 reel + certificate PNG + PDF | `components/CampaignStudio.tsx` | 4 |
| 6.9 | Project summary card with source-linked numbers | `components/SummaryCard.tsx` | 4 |
| 6.10 | **Provenance panel** — source asset + full transformation chain per asset | `components/ProvenancePanel.tsx` | **6** |
| 6.11 | Offline PWA: IndexedDB queue, service worker Background Sync, demo-cache toggle | `public/sw.js` | — |

**Exit criteria**
```bash
make build && make e2e
# 1. npm run build exits 0 with no hydration warnings
# 2. Every one of the 6 rubric bullets has a screenshot captured by Playwright
# 3. CLS == 0 during live metric ticker updates
# 4. All interactive targets >= 44x44 px
# 5. Full flow works with the backend entirely absent (demo-cache mode)
```

---

## 9. Stage 7 — Hardening, QA, delivery

| # | Task | Deliverable |
| :-- | :--- | :--- |
| 7.1 | 4-tier test pyramid complete (>100 / ~40 / ~25 / <10) | `tests/` |
| 7.2 | GitHub Actions: pytest + coverage 85% gate, `next build`, Playwright | `.github/workflows/ci.yml` |
| 7.3 | Docker Compose: backend + frontend | `docker-compose.yml` |
| 7.4 | 500-asset scale load test with timing report | `scripts/load_test.py` |
| 7.5 | Demo fail-safes: cache mode, pre-warmed eager transforms, `e_preview` short clips | per `07` §4 |
| 7.6 | Rubric traceability matrix: bullet → component → demo timestamp → test | `docs/15-RUBRIC-TRACEABILITY.md` |
| 7.7 | 180 s pitch script re-cut to lead with rubric #3 and #5, not the carbon-market hook | `docs/14` patch |
| 7.8 | Reset `08` §1.2 DoD checkboxes from `[x]` to `[ ]` | doc patch |

**Exit criteria:** CI green on a clean clone; `docker compose up` reaches a working demo; every rubric bullet traceable to a component, a demo timestamp, and a passing test.

---

## 10. Critical path and parallelism

```
S0 repo ─► S1 numerics ─┬─► S2 CV ──────────────┐
                        │                       ├─► S5 API ─► S6 frontend ─► S7 hardening
                        └─► S3 enrichment ─► S4 cloud ─┘
                                  │
                            S1.9 mock server ────► S6 frontend may start early
```

**Strictly serial (do not parallelize):** S0 → S1. Everything downstream inherits S1's correctness.

**Safe to run in parallel once S1 lands:**

| Track A — CV | Track B — Cloud-native | Track C — Frontend |
| :--- | :--- | :--- |
| S2 homography, S2 canopy | S4 schema, S4 seed, S4 URLs | S6.1 shell, 6.3 timeline, 6.4 search, 6.5 slider |
| S5.3 compare route | S3.1–3.3 tagging + semantic | 6.8 campaign studio, 6.10 provenance |

**If working solo:** execute strictly in the order S0 → S1 → S2 → S3 → S4 → S5 → S6 → S7, and apply the cut list in §11.

---

## 11. Cut list (in this order, if time runs short)

| Cut | Justification |
| :--- | :--- |
| 1. SAM instance segmentation (M4) | Zero rubric points. |
| 2. EUDR Article 9 validator (M7) | Zero rubric points. High implementation cost (pyproj edge cases). |
| 3. VM0047 discount + Chave biomass (M5/M5b) | Zero rubric points. *But keep the coefficient fix if the module stays* — a wrong constant shipped is worse than the module absent. |
| 4. Gyroscopic horizon leveler | Nice demo, no rubric point. |
| 5. Docker Compose | Only if CI alone is green. |
| 6. Cloudinary Vector Search add-on (3.3) | Fall back to the local semantic path (3.4), which is already built and credential-free. |

**Never cut:** S1 (all of it), S2.1–2.4, S3.4, S3.6, S4.3, S6.3, S6.4, S6.5, S6.8, S6.10. These carry rubric bullets 3, 4, 5, 6 and the intro timeline requirement.

---

## 12. Stage-to-rubric coverage after full execution

| Rubric | Stages that satisfy it | Demo surface |
| :-- | :--- | :--: |
| 1. Analyze + organize large collections | 3.1, 4.6, 5.1, 6.2 | Portfolio grid over 500 assets |
| 2. Identify projects / locations / visual signals | 1.1, 2.4, 3.1, 3.8, 6.7 | Auto-tag panel + hotspot player |
| 3. Before-and-after comparison | 2.1–2.4, 5.3, 6.5 | Split slider with measured Δ% |
| 4. Reports, summaries, campaign content | 3.6, 3.7, 4.4, 5.5, 5.6, 6.8, 6.9 | Campaign studio + summary card |
| 5. AI metadata, tagging, semantic discovery | 3.1–3.5, 5.2, 6.4 | NL search + tag chips + similar-assets |
| 6. Traceability to source + transformations | 4.2, 4.3, 5.7, 6.10 | Provenance panel |
| intro. Timeline | 3.8, 5.4, 6.3 | Timeline view |
