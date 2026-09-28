# VERITAS dMRV — Consolidated Engineering & Product Brief
**Derived synthesis of `docs/00–14` (15 documents, v1.0.0 Master Release)**
**Purpose:** Single reference for problem framing, architecture, tech stack, workflow, and solution traceability.
**Status:** Read-only analysis. Not part of the numbered 00–14 release suite.

---

## PART 1 — THE PROBLEM STATEMENT

### 1.1 One-Paragraph Formal Statement

> **Nature-based carbon and biodiversity projects cannot produce evidentiary proof of impact, so the entire $40B market rests on unauditable assertions — and has been systematically defrauded.** The Monitoring, Reporting and Verification (MRV) chain for carbon sequestration breaks at three independent points: **(a) perception** — satellites cannot detect early-stage sapling mortality, inspect drip irrigation, or confirm water-filtration hardware; **(b) evidence integrity** — ground truth is captured on field workers' phones and then rots in WhatsApp threads and Google Drive with stripped EXIF, spoofed GPS/timestamps, AI-generated foliage, and recycled nursery stock photos; **(c) verification economics** — third-party auditors (VVBs) manually sample sites over 6–18 month cycles at $12–18/hectare/year, which is economically incompatible with monitoring 70+ parcels across 4 continents. The result: 85–94% of nature-based credits are phantom, while EU CSRD (ESRS E1/E4) and EUDR (Reg. 2023/1115) have converted voluntary greenwashing into statutory liability carrying fines up to **4% of annual EU turnover**.

### 1.2 Root Cause Decomposition

| # | Root Cause | Evidence in Source Docs |
| :-- | :--- | :--- |
| RC-1 | **Satellite blindspots** — cannot see Years 1–2 sapling mortality, subsurface irrigation, or treatment infrastructure | `01-PRD` §1.2 |
| RC-2 | **Field media chaos** — proof stranded on personal devices, EXIF stripped, origin unverified | `01-PRD` §1.2 |
| RC-3 | **Forensic vulnerability** — photos are spoofable, recycled across plots, or diffusion-model generated | `01-PRD` §1.2, §8 |
| RC-4 | **Audit impossibility** — 6–18 month manual sampling cycle is an administrative bottleneck | `01-PRD` §1.2 |
| RC-5 | **Metadata/media desynchronization** — S3/GCS media + RDBMS business rows drift apart, breaking chain of custody | `04-DATA-AND-SCHEMA` §1 |
| RC-6 | **Non-reproducible measurement** — canopy change is asserted in prose, never computed from registered imagery | `01-PRD` §1.3, G2 |

### 1.3 Market & Regulatory Tailwinds

- **$40B** committed annual capital in VCM + corporate ESG compliance.
- **$2B+** phantom carbon credits exposed (Verra investigative reporting).
- **85–94%** of nature-based credits lack verified additionality or permanent biomass uplift.
- **CSRD / ESRS E1 & E4** — 50,000+ EU enterprises must audit Scope 3 upstream biodiversity impact; greenwashing outlawed.
- **EUDR Art. 9** — polygon-level geolocation + dated land-use history; fines to 4% of EU turnover.
- **Verra VM0047 §8.4** — ARR carbon estimates require 90% CI sampling error ≤ 15% or face mandatory discount.
- **C2PA** — tamper-evident provenance standard for capture authenticity.

### 1.4 The Six Questions the Product Must Answer

These are the answerable sub-problems extracted from the problem statement. Every requirement in the suite traces to one of them.

| ID | Question | Why it must be answered |
| :-- | :--- | :--- |
| **Q1** | **Authenticity:** Was this photo/video actually captured by a physical sensor, at the claimed location, at the claimed time, and never edited? | Defeats spoofed EXIF (RC-2), nursery photo reuse (RC-3), Midjourney/Stable-Diffusion generation, and screen re-photography fraud. |
| **Q2** | **Measurement:** Has the vegetation *actually* changed, and by exactly how much — computed from imagery, not narrated? | Replaces subjective textual MRV with a reproducible vegetation index delta (RC-6). |
| **Q3** | **Registration:** Volunteers cannot re-stand in the same spot. How do you compare a Month-0 photo to a Month-18 photo taken 4 m further back at 22° yaw? | Naive comparison yields 100% false change alarms from perspective, not biology. |
| **Q4** | **Scale & Field Viability:** Can 70+ parcels / 500,000 ha be monitored with 2G, no cellular coverage, low-end Android, and a possibly-hostile lighting environment? | RC-4 plus the operational reality in `10-OFFLINE-PWA` §1.1. |
| **Q5** | **Evidentiary & Legal Integrity:** Can a third-party auditor independently reproduce the result, and does the record survive repudiation? | CSRD/EUDR/ISSA-5000 liability. Addresses RC-5 and STRIDE tampering/repudiation. |
| **Q6** | **Unit Economics:** Does verification cost less than the fraud it prevents, and is it deliverable in a 48-hour build? | `01-PRD` §9, `13-JUDGE-DEFENSE` Q6/Q10. |

### 1.5 Explicit Non-Goals (Scope Boundary)

- **NG1** No custom drone/IoT hardware manufacturing — software ingestion over existing phones and drones.
- **NG2** No proprietary carbon tokenization — compliance dossiers mapped to Verra/Gold Standard, not new tokens.
- **NG3** No dense 3D LiDAR/NeRF reconstruction — planar homography (3×3) + orthomosaic diffing only.

---

## PART 2 — SOLUTION OVERVIEW

### 2.1 Thesis

VERITAS dMRV is an enterprise visual ground-truth intelligence platform. It ingests raw field media, applies **JEV (TypeSafe AI) RLCD** for sub-150 ms anti-fraud triage, uses **OpenCV SIFT + USAC_MAGSAC++** homography to normalize shifting camera perspective, extracts canopy metrics via **Green Leaf Index + Otsu**, and uses **Cloudinary** as an on-demand visual compute engine, structured-metadata store, and C2PA trust authority.

### 2.2 Strategic Goals

- **G1 Evidentiary Rigor** — tamper-evident, hardware-attested, astronomically validated media.
- **G2 Scientific Change Quantification** — mathematical canopy metrics across aligned longitudinal photos.
- **G3 Sponsor Engine Depth** — maximize native Cloudinary platform utilization (5 enterprise APIs).
- **G4 Audit Automation** — compress dossier compilation from 6 weeks manual → 60 seconds.

### 2.3 Three Pillars

1. **Forensic Physics Shield** — pvlib solar ephemeris shadow-vector verification (±12°), pHash corpus dedup, Laplacian/FFT/Moiré synthetic detection, C2PA device attestation.
2. **Geometric & Ecological Engine** — SIFT 128-D descriptors → FLANN kNN → Lowe ratio 0.75 → MAGSAC++ 3×3 homography → TPS parallax fallback → radiometric histogram normalization → GLI + Otsu canopy mask → surface-area delta.
3. **Cloudinary Visual Cloud & Trust Engine** — immutable asset vault, Admin Structured Metadata (Lucene index), chained URL transformation engine, AI Video Analysis, interactive hotspot player, serverless PDF certificates.

---

## PART 3 — ARCHITECTURE

### 3.1 Three Non-Negotiable Architectural Principles (`02-ARCHITECTURE` §1.1)

1. **Decoupled Compute Boundary** — heavy iterative math (SIFT, MAGSAC++, ephemeris) runs *only* in a Python async microservice; visual composition, format optimization, C2PA delivery, and search run *only* on Cloudinary's edge.
2. **Deterministic System-1 Gating** — conversational LLMs are **prohibited** from binary verification or financial decisions in high-liability statutory contexts. All triage is JEV/RLCD with mathematical probability bounds (P ≥ 0.95).
3. **Single Source of Truth via Schema Enforcement** — Cloudinary Structured Metadata (`metadata_fields`) is the authoritative, tamper-evident document store, queried sub-second via the Search API.

### 3.2 C4 Level 1 — System Context

```
Field Ranger / Drone Operator ──field media+GPS──▶ VERITAS dMRV
VERITAS ──dynamic media & metadata──▶ Cloudinary Visual Cloud
VERITAS ──calibrated decision req──▶ JEV Decision Engine (TypeSafe AI)
ESG Auditor / VVB ──dossier request──▶ VERITAS ──C2PA provenance──▶ Auditor
```

### 3.3 C4 Level 2 — Container Diagram (reconstructed)

| Tier | Containers | Responsibility |
| :--- | :--- | :--- |
| **Client** | Field PWA (offline-first) | Capture, compass/GPS/attestation, IndexedDB queue, service-worker sync |
| | Enterprise Audit Console (Next.js 15) | Split slider, hotspot player, cadastral map, dossier export, forensic HUD |
| **Python Compute Core** | API Gateway + Auth (FastAPI/Uvicorn, SlowAPI 60 req/min) | Routing, JWT RBAC, rate limiting |
| | Solar Ephemeris Service (pvlib) | Sun azimuth/elevation, shadow-coherence verdict |
| | Geometric Registration Service (OpenCV) | SIFT, FLANN, MAGSAC++, warpPerspective, TPS fallback |
| | Ecological Delta Engine (GLI/Otsu) | Radiometric normalization + canopy mask delta |
| | JEV Decision Client (RLCD) | Typed verdict + calibrated Brier confidence |
| | BioMetric Service (Chave/VM0047) | Allometric carbon, sampling-error discount |
| | EUDR Cadastral Validator (shapely/pyproj) | Article 9 polygon/precision/topology checks |
| **Cloudinary Tier** | Master Asset Vault | Immutable RAW + C2PA assets |
| | Admin Structured Metadata | Lucene inverted index — the source of truth |
| | URL Transformation Engine | Split-diffs, watermarks, PDFs, 9:16 reels, certs |
| | AI Video Analysis API | VTT visual transcription of silent drone footage |
| | Interactive Video Player | Spatial telemetry hotspots |

### 3.4 C4 Level 3 — Component Diagram (Python Core)

```
IngestionController
 ├─▶ SolarEphemerisService : calculate_sun_position(lat,lon,utc) → SunVector
 │                           verify_shadow_angle(sun_az, observed) → float
 ├─▶ HomographyService      : extract_sift_features / match_flann
 │                           solve_magsac → Matrix3x3 / warp_perspective
 ├─▶ BioMetricService       : compute_exg(image) → BinaryMask
 │                           calculate_surface_delta(m1, m2) → CanopyDelta
 └─▶ JevDecisionClient      : evaluate_rlcd_state(telemetry_vector) → JevDecision
```

### 3.5 End-to-End Data Flow

1. **Ingest** — PWA uploads master directly to Cloudinary (chunked, signed preset, `f_auto,q_auto:good`), bypassing the backend entirely. C2PA JUMBF manifest bound to SHA-256 of sensor stream + device attestation.
2. **Triage** — PWA posts asset ID + GPS + UTC + observed shadow azimuth → FastAPI computes true sun position → JEV RLCD emits `VERIFIED_PASS` / `REVIEW_AMBIGUOUS` / `QUARANTINE_FRAUD` with Brier confidence.
3. **Persist** — decision + all telemetry written back to Cloudinary Structured Metadata (single source of truth).
4. **Register** — auditor requests baseline/progress pair → SIFT/FLANN/MAGSAC++ → warped T₂ + inlier ratio.
5. **Quantify** — radiometric normalization → GLI + Otsu masks → net canopy Δ%.
6. **Render** — Cloudinary composes split-diff, overlays metrics, burns C2PA badge — all on edge.
7. **Export** — EUDR Article 9 + CSRD ESRS E4 dossier generated as a vectorized PDF via URL pipeline.
8. **Archive** — WORM storage with RFC 3161 timestamped SHA-256 root hash.

### 3.6 End-to-End Sequence (compressed)

```
Field ─▶ Cloudinary Vault   : chunked upload + C2PA
Field ─▶ FastAPI /triage    : asset_id, GPS, timestamp, shadow
FastAPI ▶ Solar check       : true azimuth vs observed vector
FastAPI ▶ JEV RLCD          : VERIFIED_PASS (0.96)
FastAPI ▶ Cloudinary Meta   : jev_decision=VERIFIED_PASS
Auditor▶ FastAPI /cv/align  : T1, T2
FastAPI ▶ OpenCV            : SIFT+FLANN+MAGSAC++ → +38.2% ExG
FastAPI ▶ Cloudinary Vault  : upload warped derivative + metadata
UI     ▶ Cloudinary URLs    : edge-composited split diff w/ watermarks
UI     ▶ Auditor            : interactive Proof-of-Impact dossier
```

---

## PART 4 — TECH STACK

### 4.1 Pinned Dependency Manifest

**Backend (`backend/requirements.txt`)**

| Category | Packages |
| :--- | :--- |
| Web | `fastapi==0.115.0`, `uvicorn[standard]==0.30.6`, `pydantic==2.9.2`, `python-multipart==0.0.9` |
| CV/Photogrammetry | `opencv-python-headless==4.10.0.84`, `numpy==2.1.1`, `scipy==1.14.1` |
| Physics/Geo | `pvlib==0.11.1`, `pandas==2.2.3`, `shapely==2.0.6`, `pyproj==3.6.1` |
| Media | `cloudinary==1.41.0`, `imagehash` (pHash) |
| Test | `pytest==8.3.3`, `httpx==0.27.2` |
| Optional/unspecified | `segment-anything` + `torch` (SAM), `pyclipper`, `pyshp` |

**Frontend (`frontend/package.json`)**

| Category | Packages |
| :--- | :--- |
| Framework | `next@15.0.0`, `react@19.0.0-rc`, `react-dom@19.0.0-rc`, `typescript@^5.6.2` |
| UI | `tailwindcss@^3.4.13`, `lucide-react@^0.453.0`, `clsx`, `tailwind-merge` |
| Components | `react-compare-slider@^3.0.1`, `@cloudinary/url-gen`, `cloudinary-video-player@1.10.6` (CDN) |
| E2E | `@playwright/test` |
| **PWA** | Service Worker + IndexedDB + Background Sync API (vanilla JS, no lib pinned) |

> ⚠️ **Icon-library conflict:** `06-FRONTEND-SPEC` §1.2 pins **Phosphor Icons** (`@phosphor-icons/react`) exclusively, but `package.json` in `11` and every code sample in `06`/`10` import **`lucide-react`**. Not in the dependency manifest either way. Pick one before building.

### 4.2 Runtime & Infrastructure

| Layer | Technology |
| :--- | :--- |
| Python runtime | 3.11 / 3.12 (`python:3.12-slim` image) |
| Node runtime | 20.x / 22.x (`node:22-alpine` image) |
| Orchestration | Docker Compose (backend:8000, frontend:3000) |
| OpenCV system libs | `libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1` |
| CI | GitHub Actions — pytest `--cov-fail-under=85`, `npm ci && next build` |
| Client persistence | IndexedDB stores: `pending_uploads`, `synced_assets` |
| Geospatial CRS | WGS84 EPSG:4326 (storage) → EPSG:6933 equal-area (area math) |

### 4.3 Cloudinary Feature Surface (5 Enterprise APIs — the sponsor thesis)

1. **Admin Structured Metadata API** — `metadata_fields` schema, typed + Lucene-searchable.
2. **Search API** — Lucene expressions, sub-second multi-dimensional queries.
3. **Dynamic URL Transformation Engine** — `c_fill`, `c_crop`, `g_west/east`, `l_` overlay, `fl_layer_apply`, `l_text`, `e_preview`, `e_improve`, `e_gen_restore`, `e_background_removal`, `b_gen_fill`, `f_auto`, `q_auto`.
4. **AI Video Analysis API** — `google_video_tagging` visual transcription → VTT caption track.
5. **Interactive Video Player + C2PA Content Credentials** — spatial hotspots, signed derivatives.

### 4.4 Data Schema — 11 Cloudinary Structured Metadata Fields (`04` §2)

| Field | Type | Validation | Mandatory | Searchable |
| :--- | :--- | :--- | :--: | :--- |
| `esg_project_id` | string | `^[A-Z]{3,6}-[0-9]{3,5}$` | ✔ | exact + prefix |
| `sustainability_domain` | enum | reforestation / mangrove / water / solar | ✔ | filter |
| `cadastral_polygon_id` | string | parcel ID | ✔ | exact |
| `capture_timestamp` | date | ISO 8601 | ✔ | range |
| `solar_azimuth_error` | integer | [-180, 180] | ✔ | range |
| `jev_triage_decision` | enum | VERIFIED_PASS / REVIEW_AMBIGUOUS / QUARANTINE_FRAUD | ✔ | filter |
| `jev_confidence_score` | integer | 0–100 | ✔ | range |
| `sift_inlier_ratio` | integer | 0–100 | — | range |
| `canopy_delta_pct` | integer | -100 to 500 | — | range |
| `c2pa_provenance` | enum | C2PA_VERIFIED / MISSING / MUTATED | ✔ | filter |
| `milestone_phase` | enum | baseline_m0 / progress_m6 / progress_m18 / certified_y3 | ✔ | filter |

Mirrored in Pydantic (`CloudinaryMetadataPayload`) and TypeScript (`VeritasAssetMetadata`) for strong typing across the boundary.

### 4.5 Security Posture (STRIDE coverage, `01-PRD` §8)

| Threat | Countermeasure |
| :--- | :--- |
| Spoofing | Solar ephemeris shadow verification ±12°; hardware-backed C2PA via Secure Enclave / Play Integrity |
| Tampering | 2D FFT checkerboard detection; Laplacian noise variance < 80.0 flagged |
| Repudiation | Ed25519 signed `audit_receipt_id`; SHA-256 manifests pinned in Structured Metadata; RFC 3161 timestamps |
| Info Disclosure | Signed delivery URLs (`s_...`); RBAC — public sees canopy deltas only, raw coordinates gated |
| DoS | Chunked direct-to-Cloudinary uploads (bypasses backend); SlowAPI 60 req/min |
| Elevation of Privilege | JWT scopes: `mrv:field_upload`, `mrv:triage_review`, `mrv:vvb_signoff` |

---

## PART 5 — THE SEVEN ALGORITHMIC MODULES (`03-SYSTEM-DESIGN`)

| # | Module | Mechanism | Verdict Gate |
| :-- | :--- | :--- | :--- |
| **M1** | Solar Ephemeris | Julian Day → fractional year γ → EoT → declination δ → True Solar Time → hour angle H → elevation α + azimuth θs → expected shadow = (θs+180) mod 360 | Δθ ≤ 12.0° → `PHYSICS_PASS`; else `QUARANTINE_SOLAR_MISMATCH` |
| **M2** | SIFT + MAGSAC++ Homography | CLAHE on L channel → SIFT (5000 feats) → FLANN kd-tree k=2 → Lowe ratio 0.75 → `findHomography(USAC_MAGSAC, 3.0px, 5000 iters, conf 0.999)` → condition-number check (reject > 1e6) → `warpPerspective` | Inlier ratio < 0.60 → flag for manual ground-stake calibration |
| **M2b** | TPS Parallax Fallback | **Original trigger measured wrong and API non-existent** (see §9.6). Now: inlier ratio < 0.70 + non-planarity > 1.5 px → NumPy TPS, kept only if control-point fit improves ≥20% | Non-rigid compensation for 3D canopy parallax |
| **M3** | Radiometric Normalization + GLI | Per-channel cumulative-histogram quantile transfer (PIF) → GLI = (2G−R−B)/(2G+R+B) → Otsu adaptive threshold → morphological open/close → valid-region mask (ignore warp borders) | `net_canopy_growth_pct` |
| **M4** | SAM Instance Segmentation | `segment-anything` SAM ViT-B, point-prompted per-sapling crown masks, per-instance pixel areas | Instance count, mean crown area, mean confidence |
| **M5** | Allometric Biomass | DBH ≈ 2.1·√(canopy_area_m²) → AGB → ×0.47 carbon → × 44/12 CO₂e | tCO₂e per hectare |
| **M5b** | VM0047 §8.4 Discount | E = (t₀.₉,ₙ₋₁ · s)/(√n · x̄)·100%; discount = max(0, (E−15)/100) | Net certified tCO₂e |
| **M6** | Synthetic / Screen-Replay Detection | Laplacian variance < 80.0 (diffusion smoothing) · FFT peak ratio > 3.8 (checkerboard) · Sobel-gradient Moiré ratio > 4.2 (subpixel beat vs RGB grid) | `QUARANTINE_SYNTHETIC` / `QUARANTINE_SCREEN_REPLAY_MOIRE` |
| **M7** | EUDR Article 9 Validator | shapely `is_valid` topology → pyproj EPSG:4326→6933 equal-area → hectare area → >4 ha must be Polygon → every vertex ≥6 decimal places | `EUDR_ARTICLE_9_COMPLIANT` |

### 5.1 API Surface (`05-API-SPEC`)

| Method | Endpoint | Latency Target | Purpose |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/triage/evaluate` | **< 150 ms** | M1 + pHash + C2PA → typed JEV decision |
| `POST` | `/api/v1/cv/align-and-diff` | **< 800 ms** | M2 + M3 → warped T₂, inlier ratio, canopy Δ% |
| `GET` | `/api/v1/audit/dossier/{project_id}` | — | EUDR/CSRD dossier + cadastral GeoJSON + biomass + C2PA root hash |
| `POST` | `/api/v1/cloudinary-webhooks/video-processed` | async | AI Video Analysis VTT ingestion |
| `POST` | `/api/v1/cloudinary-webhooks/eager-ready` | async | Pre-render completion → zero demo latency |
| `GET` | `/health` | — | `{status: UP, engine: VERITAS_CORE}` |

---

## PART 6 — WORKFLOW PLAN

### 6.1 Three-Stream Parallel Team Architecture (`11`)

Interface-first decoupling against the shared contract in `05-API-SPEC.md` so no teammate blocks on another or on API-key approval.

| Stream | Owner | Directory | Unblocked By | Owns |
| :--- | :--- | :--- | :--- | :--- |
| **A — Frontend** | Teammate A | `/frontend` | Standalone `mock_server.py` | Next.js 15 UI, compare slider, Cloudinary video player, forensic HUD, gyroscopic leveler |
| **B — Backend/CV** | Teammate B | `/backend` | Offline images in `/fixtures` | FastAPI, M1–M7 math, pytest suites |
| **C — Cloudinary/Demo** | Teammate C | `/cloudinary` | Cloudinary REST API + Node SDK | Metadata schema, eager presets, hotspot coordinates, PDF URL engine, demo seeding, pitch assets |

**Key DX mechanisms:** `mock_server.py` (implements 100% of the API contract with CORS `*` and an `X-Mock-Scenario` header), `fixtures/mock_db.json` (2 canonical projects), root `dev.ps1 -Mode mock|live`, strictly pinned `requirements.txt` / `package.json`.

### 6.2 Four-Phase Timeline (as specified in `08-PROJECT-PLAN`)

```
Phase 1  FOUNDATION     H0–6    [1.1 Cloudinary schema 3h] [1.2 FastAPI scaffold 3h] [1.3 Next shell 3h]
Phase 2  COMPUTE CORE   H6–18   [2.1 Solar+pHash 4h] [2.2 SIFT/MAGSAC 6h ★CP] [2.3 ExG+JEV 4h]
Phase 3  VISUAL/MEDIA   H16–26  [3.1 Split URL engine 3h] [3.2 Hotspot player 4h ★CP] [3.3 Compare slider 3h]
Phase 4  AUDIT/POLISH   H26–44  [4.1 Dossier gen 4h] [4.2 E2E+cache mode 4h] [4.3 Pitch rehearsal 4h]
Buffer: 8h
```

**Critical Path:** `1.1 Schema → 2.2 SIFT Homography → 3.1 URL Split Generator → 3.2 Video Hotspots → 4.2 Integration → 4.3 Pitch`

**Contingency:** if drone perspective defeats SIFT tuning, fall back to pre-computed homography matrices while keeping live JEV solar triage real-time.

### 6.3 Definition of Done (`08` §1.2)

1. Cloudinary `metadata_fields` schema initialized via Admin API.
2. FastAPI microservice passing solar physics, homography, and ExG delta tests.
3. Next.js 15 frontend rendering split-slider + video hotspots with zero CORS/hydration errors.
4. 180-second pitch rehearsed with fail-safe fallbacks.

### 6.4 Four-Tier Test Pyramid (`12`)

| Tier | Scope | Count | Tools |
| :-- | :--- | :-- | :--- |
| **1 — Unit & Physics** | Solar ephemeris vectors, EUDR geometry | > 100 | `pytest`, `pvlib`, `freezegun`, parametrize |
| **2 — CV & Vision** | SIFT registration, TPS, radiometric normalization | ~ 40 | `pytest`, `opencv`, synthetic fixture generator |
| **3 — Integration** | FastAPI TestClient, Cloudinary webhooks | ~ 25 | `fastapi.testclient`, `TestClient` |
| **4 — E2E** | Auditor browser flow | < 10 | `@playwright/test` |
| **CI gate** | `--cov-fail-under=85` + `next build` must pass | | GitHub Actions |

### 6.5 180-Second Pitch Run of Show (`07` §3 / `14`)

| Time | Beat | On-Screen |
| :--- | :--- | :--- |
| 00:00–00:30 | $40B greenwashing hook | Split slide: CSR headline vs barren mudflat |
| 00:30–01:15 | "Watch what happens when someone uploads a fake" | Drag fake nursery photo → **< 150 ms** crimson quarantine badge + metadata write |
| 01:15–02:05 | "Now verify authentic Month 18 progress" | 20°-tilt genuine photo → split slider snaps aligned → `+38.2% Canopy \| SIFT Inliers 84%` |
| 02:05–02:40 | "The Cloudinary superpower" | 4K drone video, click hotspot → species + C2PA modal, live VTT subtitles |
| 02:40–03:00 | "Chaos → legal compliance in one click" | Export EUDR/CSRD PDF + QR → "6 weeks → 60 seconds" |

**Fail-safes:** Demo Cache Mode toggle (live Cloudinary → local IndexedDB, no error dialog); `e_preview:duration_10` for slow video; pre-indexed 4K drone reel; pre-heated transcription tracks.

### 6.6 Judge-Defense Coverage (`13`)

10 pre-written adversarial answers: S3 vs Cloudinary · screen-replay attack · 45° drone angle · monsoon/cloud cover · Midjourney generation · 500k-ha credit scaling · LLM vs JEV · EUDR statutory compliance · team parallelism · unit economics.

---

## PART 7 — TRACEABILITY: HOW THE SOLUTION ANSWERS EACH PROBLEM QUESTION

This is the core of the brief. Each question from §1.4 is mapped to the specific mechanism, code module, UI surface, and proof artifact that answer it.

### Q1 — Authenticity: *"Is this media real, from where it claims, when it claims, unedited?"*

| Mechanism | Implementation | Evidence Artifact | Doc |
| :--- | :--- | :--- | :--- |
| **Astronomical impossibility check** | M1: pvlib/NOAA sun azimuth from (lat, lon, UTC); compare to observed shadow vector; quarantine if Δ > 12° | `solar_azimuth_error` metadata field; `ForensicPhysicsHUD` SVG sun-ray + shadow-vector overlay drawn *on the photo* | `03` §1, `10` §2, `09` §2.3 |
| **Nursery photo reuse** | pHash (DCT perceptual hash) at ingest; Hamming distance vs global corpus (quarantine if ≤ 12) | `deduplication.phash_min_distance_to_corpus` in triage response | `01` FR-1.3, `13` Q4 |
| **AI-generated foliage** | M6: Laplacian variance < 80.0 (diffusion over-smooths micro-noise); 2D FFT peak ratio > 3.8 (checkerboard harmonics) | `laplacian_noise_variance`, `fft_frequency_peak_ratio` | `03` §6, `13` Q5 |
| **Screen re-photography** | M6: Sobel gradient-energy ratio > 4.2 → Moiré beat frequency between camera sensor and RGB subpixel grid | `QUARANTINE_SCREEN_REPLAY_MOIRE` verdict | `03` §6, `13` Q2 |
| **Hardware origin + edit chain** | C2PA JUMBF manifest binding device fingerprint, OS attestation (Secure Enclave / Play Integrity), and SHA-256 of uncompressed sensor stream; Cloudinary re-signs derivatives as authenticated claim generator | `c2pa_provenance` field; `veritas.forensic.telemetry` C2PA assertion | `02` §5.1, `04` §5 |
| **Tight capture conditions** | PWA gyroscopic artificial-horizon leveler: shutter disabled unless pitch & roll within ±5° | Emerald "HORIZON LOCKED" HUD state | `10` §1.4 |
| **Deterministic verdict** | JEV RLCD emits typed `VERIFIED_PASS` / `REVIEW_AMBIGUOUS` / `QUARANTINE_FRAUD` with Brier-calibrated confidence (Brier < 0.08) in < 150 ms | `jev_triage_decision`, `jev_confidence_score`; `audit_receipt_id` (Ed25519) | `01` FR-1.4, `13` Q7 |

**Verdict:** Q1 is answered by a **six-layer independent defense in depth** (physics, hashing, frequency analysis, hardware attestation, capture discipline, calibrated decision engine) — deliberately redundant so no single attack defeats it, and so that overcast conditions degrade gracefully to layers 2/4/6 rather than failing open.

---

### Q2 — Measurement: *"Has the vegetation actually changed, by how much?"*

| Mechanism | Implementation | Evidence Artifact | Doc |
| :--- | :--- | :--- | :--- |
| **Shadow-invariant index** | GLI = (2G−R−B)/(2G+R+B) — chromatic foliage signal isolated from luminance drop (unlike fixed-threshold ExG) | `index_used: GLI_OTSU` | `03` §3.2 |
| **Adaptive segmentation** | Otsu bimodal thresholding separates foliage from soil/shadow; morphological open + close (5×5 ellipse) removes noise | `baseline_canopy_pixels`, `registered_progress_canopy_pixels` | `03` §3.2 |
| **Lighting invariance** | Radiometric normalization via per-channel cumulative-histogram quantile transfer against the baseline (PIF method) — cancels solar irradiance and Rayleigh scattering differences | `radiometric_normalized: true` | `03` §3.1 |
| **Invalid-region exclusion** | Warp border mask (`sum(axis=2) > 10`) prevents black-padding pixels from being counted as canopy loss | `valid_surface_area_pixels` | `03` §3.2 |
| **Carbon translation** | DBH ≈ 2.1·√(canopy_area_m²) → Chave allometric AGB → ×0.47 carbon → × 44/12 CO₂e | `estimated_tco2e_per_hectare` | `03` §5 |
| **Statutory uncertainty** | VM0047 §8.4: 90% CI sampling error, mandatory discount above 15% | `statistical_uncertainty_ci90`, `net_certified_tco2e` | `03` §5.2 |
| **Per-tree granularity (optional)** | SAM ViT-B point-prompted crown instance segmentation | `instance_count`, `crown_pixel_areas` | `03` §4 |

**Verdict:** Q2 is answered by replacing prose MRV with a **numerically derived, radiometrically normalized, luminance-invariant canopy surface-area delta** and converting that to certified tCO₂e with a regulatory uncertainty haircut. The measurement is a function of pixels, not of a field worker's narrative.

---

### Q3 — Registration: *"How do you compare photos taken from different positions and angles?"*

| Mechanism | Implementation | Evidence Artifact | Doc |
| :--- | :--- | :--- | :--- |
| **Scale-invariant local features** | SIFT, 5000 features, 128-D descriptors — invariant to scale and rotation, robust to the kind of viewpoint change volunteers introduce | `sift_keypoints_baseline`, `sift_keypoints_progress` | `03` §2.1, `01` FR-2.1 |
| **Illumination preconditioning** | CLAHE on the LAB L-channel (clip 2.0, 8×8 tiles) before grayscale — stabilizes keypoints under harsh outdoor sun | — | `03` §2.1 |
| **Correspondence filtering** | FLANN kd-tree (5 trees, 50 checks) k=2 neighbors → Lowe ratio test at 0.75 | `good_flann_matches` | `03` §2.1, `01` FR-2.2 |
| **Robust projective estimation** | `findHomography(USAC_MAGSAC, reproj 3.0 px, 5000 iters, conf 0.999)` — MAGSAC++ scores a minimal sample set instead of enumerating all combinations, so it does not blow up on 20% outlier contamination from new vegetation | `magsac_inliers`, `inlier_ratio` | `03` §2.1 |
| **Degeneracy guard** | Condition number check `κ(H) > 1e6` → reject as `DEGENERATE_HOMOGRAPHY_MATRIX` (collinear/collapsed transforms) | status message | `03` §2.1 |
| **Non-planar fallback** | κ(H) > 85.0 or RMSE > 3.5 px → Thin Plate Spline local mesh warp for 3D canopy parallax (tree tops shift relative to ground under drone translation/gimbal change) | — | `03` §2.2, `13` Q3 |
| **Confidence surfaced, not hidden** | Inlier ratio shown in UI; < 60% → flag for manual ground-stake benchmark calibration | `sift_inlier_ratio` metadata; `Inlier Confidence: 84.5%` HUD | `01` §7, `06` §3.1 |
| **Visual proof** | `ReactCompareSlider` drag UI + Cloudinary edge-composited split-diff with burned-in labels and metrics | split-screen URL | `06` §3.1, `05` §2.1 |

**Verdict:** Q3 is answered by a **projective geometry pipeline with an explicit confidence score and a non-planar escape hatch.** Crucially, VERITAS *shows its work*: the inlier ratio is displayed, so an auditor sees how much to trust the diff rather than being handed a number to accept.

---

### Q4 — Scale & Field Viability: *"Does this work on 2G, offline, on a $150 Android?"*

| Mechanism | Implementation | Evidence Artifact | Doc |
| :--- | :--- | :--- | :--- |
| **Offline capture** | IndexedDB `pending_uploads` stores RAW blob + unsigned sensor payload; UI confirms "Captured & Sealed Locally" | NFR-2: 500 queued photos without connectivity | `10` §1.2–1.3, `01` NFR-2 |
| **Deferred sync** | Service Worker Background Sync API — replays the queue when the device returns to base camp or regains 2G/3G | SW `sync` event handler | `10` §1.3 |
| **Server bypass** | PWA uploads **directly** to Cloudinary via signed preset — the FastAPI backend is never in the upload path, so no server can be the bottleneck or the single point of failure | chunked 6 MB chunks, `f_auto,q_auto:good` | `06` §4, `10` §1.3 |
| **Bandwidth tuning** | Cloudinary `f_auto,q_auto:good` + 6 MB chunking for resilient mobile uplinks | — | `06` §4 |
| **Cold-start elimination** | Eager transforms with `eager_async: true` + `eager_notification_url` — split-diff and 9:16 reel pre-rendered before they are ever requested | `eager-ready` webhook | `05` §4 |
| **Compute decoupled from app servers** | Heavy math in a lean Python service; all rendering at the CDN edge (< 50 ms vs 15–45 s FFmpeg cold start) | — | `02` §4 |
| **Zero-credit repeat views** | Transformed URLs cached globally across Cloudinary's CDN; 10,000 auditors viewing the same diff consume zero further transformation credits | `13` Q6 |
| **Diffusion fallback for bad light** | Overcast/no-shadow → fall back to pHash dedup + C2PA provenance + radiometric histogram equalization | risk matrix row 4 | `01` §7, `13` Q4 |
| **Ingestion tiering** | WhatsApp = Tier 0 unverified community alert; VERITAS PWA = Tier 1 C2PA-certified audit record — acknowledges reality instead of pretending to eliminate it | — | `01` §7 |

**Verdict:** Q4 is answered by **inverting the data path** — the field device never talks to the application server, the application server never renders media, and the network is treated as an intermittent, unreliable, optional component rather than a prerequisite.

---

### Q5 — Evidentiary & Legal Integrity: *"Can an auditor reproduce this and can the record survive challenge?"*

| Mechanism | Implementation | Evidence Artifact | Doc |
| :--- | :--- | :--- | :--- |
| **Media-bound metadata (kills RC-5)** | Cloudinary Admin Structured Metadata is the authoritative store; telemetry is bound to the asset inside the CDN's global index — no separate RDBMS to drift | 11 typed fields, Lucene-indexed | `04` §1–2 |
| **Queryable evidence** | Lucene expressions, e.g. `esg_project_id="KEN-042" AND jev_triage_decision="VERIFIED_PASS" AND milestone_phase="progress_month_18" AND canopy_delta_pct > 0 AND c2pa_provenance="C2PA_VERIFIED"` | sub-second search | `04` §4 |
| **Chain of custody** | C2PA JUMBF manifest; Cloudinary re-signs each derivative as an authenticated claim generator, preserving provenance through every transformation | `c2pa_manifest` JSON | `02` §5.1, `04` §5 |
| **Immutability / WORM** | Approved milestones archived to immutable storage with RFC 3161 qualified timestamps and SHA-256 root hashes | `c2pa_root_manifest_hash` | `02` §5.2, `05` §1.4 |
| **Repudiation resistance** | Ed25519 signed `audit_receipt_id`; SHA-256 manifests pinned in Structured Metadata | receipt IDs | `01` §8 |
| **Statutory geometry** | M7: EUDR Art. 9 — shapely topology validation, EPSG:6933 equal-area hectare computation, > 4 ha polygon requirement, ≥ 6 decimal-place vertex precision | `EUDR_ARTICLE_9_COMPLIANT` + `area_hectares` | `03` §7, `13` Q8 |
| **One-click filing** | Serverless vectorized PDF dossier generated by Cloudinary URL pipeline — no Puppeteer/Weasyprint, no template drift | `.pdf` delivery URL | `05` §2.6 |
| **Access control** | Signed delivery URLs; JWT RBAC scopes `mrv:field_upload` / `mrv:triage_review` / `mrv:vvb_signoff`; public sees canopy deltas, raw cadastral coordinates gated | — | `01` §8 |
| **Decision non-repudiation by LLM** | Principle 2 explicitly bans conversational LLMs from binary verification in high-liability contexts — removes hallucinated confidence from the legal chain | — | `02` §1.1, `13` Q7 |

**Verdict:** Q5 is answered by making the **media itself the database** and the **CDN the archive**. An auditor can query the evidence independently of the operator's servers, and every transformation is signed so provenance survives to the derivative.

---

### Q6 — Unit Economics & Deliverability: *"Is it profitable and can it actually be built?"*

| Mechanism | Figure | Doc |
| :--- | :--- | :--- |
| **Monitoring subscription** | **$1.20 / ha / year** | `01` §9.2, `13` Q10, `14` Slide 7 |
| **Displacement of manual audit** | Replaces **$12–18 / ha / year** physical auditor visits → **~85–92% cost reduction** | `01` §9.2 |
| **Statutory filing fee** | **$250 per EUDR/CSRD dossier export** | `01` §9.2 |
| **Cost per verification** | ~**$0.04** (Cloudinary edge transforms + lightweight Python SIFT/pvlib service) | `01` §9.2 |
| **Gross margin** | **> 88%** | `01` §9.2 |
| **LLM cost avoidance** | 500 images × LLM = 30 min and $15; × JEV = < 150 ms each on edge CPU | `13` Q7 |
| **Credit efficiency** | Eager pre-render + global CDN cache → repeat views consume zero transformation credits | `13` Q6 |
| **Build feasibility** | 45 person-hours of WBS against 144 person-hours available (3 people × 48 h) | `08` §2–3 |

**Verdict:** Q6 is answered on paper, but **see §9.3 — the WBS under-uses the available capacity and the economics rest on an incorrect allometric constant.**

---

## PART 8 — CONSOLIDATED VIEW: PROBLEM → SOLUTION

| Problem | Naive/legacy approach (rejected) | VERITAS mechanism | Answers |
| :--- | :--- | :--- | :--- |
| Can't trust a field photo | EXIF inspection / manual auditor eyeball | Solar ephemeris + pHash + Laplacian/FFT/Moiré + C2PA + JEV RLCD | **Q1** |
| Canopy change asserted in prose | Textual MRV reports | GLI + Otsu on radiometrically normalized, SIFT-registered pairs | **Q2** |
| Photos taken from different angles | Opacity slider (100% false alarms) | SIFT + FLANN + Lowe + MAGSAC++ homography, TPS fallback, inlier ratio shown | **Q3** |
| Field has no network | Server-dependent capture | IndexedDB queue + SW Background Sync + direct-to-CDN chunked upload | **Q4** |
| 6–18 month audit cycles | Manual VVB site sampling | Lucene search over structured metadata + one-click vectorized PDF dossier | **Q5** |
| Media/RDBMS drift | S3 + PostgreSQL | Cloudinary Structured Metadata as single source of truth + WORM archives | **Q5** |
| Audit trail can be denied | Mutable DB rows | Ed25519 receipts, C2PA re-signing, SHA-256 roots, RFC 3161 timestamps | **Q5** |
| Render costs blow up | AWS S3 + FFmpeg EC2 pool (15–45 s cold start) | Cloudinary edge URL pipeline (< 50 ms, globally cached) | **Q4, Q6** |
| LLM decisions aren't defensible | GPT-4o / Claude (3–6 s, non-deterministic, sycophantic) | JEV RLCD System-1, < 150 ms, Brier < 0.08, P ≥ 0.95 | **Q1, Q6** |
| Full 3D is infeasible in the field | NeRF / LiDAR Gaussian Splatting (100+ photos, 45 min GPU, GB downloads) | Planar homography + canopy height models | **Q2, Q3** |
| Bad lens / bad light ruins CV | Submit raw photo to SIFT | `e_gen_restore` + `e_improve:outdoor:60` + `e_auto_contrast` at the edge | **Q2** |

---

## PART 9 — DEFECTS AND RISKS FOUND IN THE SUITE

These are findings from reading all 15 documents and independently recomputing their numeric claims. Ordered by severity.

### 9.1 WITHDRAWN — "The allometric biomass equation is wrong by 8.72×"

**This finding was reported in the first pass of this brief and it was wrong.
It is retained here as a record rather than deleted.**

The original claim: `03-SYSTEM-DESIGN.md` §5 used a prefactor of `0.0673` and
described it as implementing Chave et al. pantropical allometry; I asserted the
correct prefactor was `exp(-0.533) ≈ 0.5868`, that the documented constant
under-reported carbon by 8.72×, and that `05-API-SPEC`'s advertised `+6.84
tCO₂e/ha` was therefore invalid.

**The correction was itself the error.** Chave et al. (2014) Eq. 4 is:

$$AGB = 0.0673 	imes (WD 	imes H 	imes D^2)^{0.976}$$

confirmed verbatim in the R `BIOMASS` package (`computeAGB`, Réjou-Méchain,
Tanguy & Perre), whose documentation cites it as "Eq. 4 in Chave et al., 2014".
The Chave 2014 model is fitted to 4,004 directly harvested trees ≥ 5 cm DBH
across 58 sites, so 6.8 cm mangroves are *inside* its calibration domain. The
spec's constant was correct all along.

The tell was available at the time and was not read: the "wrong" coefficient
produced ~6.7× the stem's own wood volume (`π/4·D²·H·ρ`) at **every** DBH from
4 cm to 40 cm. A constant multiplicative offset across the whole range is the
signature of a wrong coefficient, not of a regression whose residuals vary with
tree size. A plausibility envelope would have falsified the "correction"
immediately.

With the verified constant, DBH 6.8 cm / H 3.9 m / ρ 0.45 g/cm³ yields
AGB ≈ 4.91 kg against 6.42 kg for the cylinder model — 24% agreement, exactly
what a good harvest-fitted regression should produce.

**What changed:** `services/biomass_service.py` uses the verified `0.0673`;
`test_result_is_plausible_against_stem_geometry` pins AGB to within a factor of
a few of stem geometry; `scripts/verify_docs.py` now guards `0.0673` and flags
`0.5868`.

**The lesson is the transferable part.** In a project whose premise is
"replace assertion with mathematics," the most dangerous defect is a *correct-
looking* number attached to a real citation. Any coefficient in this codebase
must be pinned by an independent check — a second implementation, a published
reference, or a physical envelope — not by inspection.

### 9.2 CRITICAL — Two of the four Tier-1 solar test vectors are numerically wrong and will fail CI

`12-TESTING-AND-QA-STRATEGY` §2 `SOLAR_TEST_VECTORS` asserts `pytest.approx(expected, abs=tol)`. Recomputing with the standard NOAA/pvlib algorithm:

| Vector | Doc expected az | True az (NOAA) | Error | Tolerance | Result |
| :--- | :--: | :--: | :--: | :--: | :--- |
| Nairobi 2026-09-22T08:15:30Z | 94.2 | **85.06** | §WITHDRAWN§4° | ±2.0° | **FAIL** |
| Nairobi 2026-09-22T13:30:00Z | 268.4 | **270.91** | 2.51° | ±2.0° | **FAIL** |
| Ankara 2026-06-21T10:00:00Z | 138.5 | **187.74** | **49.24°** | ±2.5° | **FAIL** |
| Berlin 2026-12-21T11:00:00Z | 173.1 | **178.95** | 5.85° | ±2.5° | **FAIL** |

**All four vectors are outside their stated tolerances.** The Ankara case is the worst: at 10:00 UTC on the June solstice, solar noon at 32.85°E is 09:48 UTC, so the sun is 12 minutes past the meridian and the azimuth must be ≈188° (due south). A claimed 138.5° is physically impossible.

**Knock-on risk — the live demo.** The Nairobi morning vector is the *headline* pitch number ("claimed 2 PM, shadow proves 8:15 AM," sun azimuth 94.2). pvlib ground truth is 85.06°, so the expected shadow is 265.06° not 274.2°. The fixture's observed shadow of 274.5° therefore lands **9.44° of error against a 12.0° threshold — a 2.6° margin.** That "legitimate photo" passes by luck. Any small refactor, timezone slip, or pvlib-vs-hand-rolled divergence flips a *genuine* photo to `QUARANTINE_SOLAR_MISMATCH` on stage, in front of judges, in the one demo that must not fail.

**Fix:** regenerate every vector by calling `pvlib.solarposition.get_solarposition` and pasting the actual output, rather than hand-writing plausible-looking azimuths. The fraud fixture (`09` §2, Tsavo 11:30 UTC) *does* correctly produce a ~179° divergence, so the fraud narrative is sound — only the "pass" fixtures are miscalibrated.

---

### 9.3 HIGH — Scope specified in docs is ~50% absent from the project plan

The WBS in `08-PROJECT-PLAN` has 12 tasks (45 person-hours) and does **not** include modules that other documents specify as core deliverables:

| Missing from WBS | Specified in | Severity |
| :--- | :--- | :--- |
| SAM instance segmentation (M4) | `03` §4 | High (PRD-adjacent) |
| Allometric biomass + VM0047 discount (M5/M5b) | `03` §5 | **Critical** — feeds the dossier |
| Synthetic / Moiré fraud detection (M6) | `03` §6, `13` Q2/Q5 | **Critical** — a named judge question |
| EUDR Article 9 validator (M7) | `03` §7, `13` Q8 | **Critical** — a named judge question |
| Offline PWA + IndexedDB + service worker | `10` §1 | High — a whole NFR |
| Gyroscopic horizon leveler | `10` §1.4 | Medium |
| Forensic Physics HUD | `10` §2 | High — the demo's money shot |
| Docker Compose + Dockerfiles | `10` §3 | Medium |
| Mock server + fixture DB | `11` §3–4 | **Critical** — the entire unblocking strategy |
| 4-tier test suites + Playwright | `12` | High |
| GitHub Actions CI | `12` §6 | Medium |
| AI Video Analysis / VTT pipeline | `01` FR-3.3, `05` §3 | High — a named Cloudinary feature |

Running `08` as written would burn 44 hours and still be unable to answer Judge Questions Q2, Q5, or Q8, nor demonstrate the offline requirement.

**Fix:** rewrite the WBS. Note there is ample capacity — 45 person-hours planned against 144 available (3 × 48 h), so this is a **~69% capacity utilization problem**, not a time problem. Rebuild as 3 parallel 14-hour tracks (A/B/C above) with the mock server as the Hour-0 unblocking artifact.

---

### 9.4 MEDIUM — Vegetation index is specified three different ways

| Source | Method stated |
| :--- | :--- |
| `01-PRD` FR-2.4 | `ExG = 2G − R − B` (raw, fixed threshold) |
| `03-SYSTEM-DESIGN` §3.2 | `GLI = (2G−R−B)/(2G+R+B)` + Otsu, explicitly rejecting raw ExG |
| `05-API-SPEC` §1.3 response | `"Excess Green Index (2G - R - B)"` |
| `11` mock server response | `"Shadow-Invariant Green Leaf Index (GLI) + Otsu"` |

The LLD is right (GLI is shadow-invariant; raw ExG is not) but the PRD, the API response, and the mock disagree with it. The mock is what the frontend will display during the demo, so the UI will contradict the pitch script.

**Fix:** standardize on GLI + Otsu everywhere; amend PRD FR-2.4 and the `05` response body.

---

### 9.5 MEDIUM — The written solar derivation contradicts its own code

`03-SYSTEM-DESIGN` §1.2 step 4 states:

$$\cos(\theta_s) = \frac{\sin(\alpha)\sin(\phi) - \sin(\delta)}{\cos(\alpha)\cos(\phi)}$$

The implementation in §1.3 uses the NOAA form:

```python
cos_azimuth = (np.sin(decl) - np.sin(phi) * cos_zenith) / (np.cos(phi) * np.sin(zenith) + 1e-7)
```

These are different expressions. **The code is correct; the displayed math is wrong.** A judge or reviewer reading the derivation will conclude the physics is wrong even though the code is right — the worst possible failure mode.

Additionally, line 74 contains a **no-op conditional** where both branches are identical:

```python
ha = math.radians((tst / 4.0) - 180.0 if (tst / 4.0) < 0 else (tst / 4.0) - 180.0)
```

**Fix:** correct the derivation to the NOAA form, and delete the dead ternary.

---

### 9.6 MEDIUM — Nighttime guard threshold is too permissive

`03` §1.3 rejects only `elevation_deg < 0`. At 3° solar elevation the observed shadow is extremely elongated, low-contrast, and its azimuth is dominated by terrain slope rather than the sun — `Δθ` becomes noise, not signal, and genuine photos will be quarantined at dawn/dusk.

**Fix:** gate on a practical threshold (elevation ≥ 10–15°) and route below that to the `REVIEW_AMBIGUOUS` path (or the overcast fallback chain in `01` §7) rather than hard quarantine.

---

### 9.7 MEDIUM — Icon library contradiction

`06-FRONTEND-SPEC` §1.2 mandates "Pinned exclusively to **Phosphor Icons**," but the pinned `package.json` includes `lucide-react` and every code sample in `06` and `10` imports from `lucide-react`. `@phosphor-icons/react` is not in the manifest at all.

**Fix:** pick one. Given the manifest already ships `lucide-react`, amend §1.2 to standardise on Lucide.

---

### 9.8 LOW — Overclaimed statutory precision in the judge playbook

`13-JUDGE-DEFENSE` Q8 asserts: *"Under EUDR Article 9, any plot larger than 4 hectares must be submitted as a closed polygon … with coordinate vertices specified to at least **6 decimal places** (~11.1 cm accuracy)."*

The > 4 ha point-vs-polygon provision is genuine EUDR implementation practice. The **6-decimal-place mandate is a GeoJSON convention, not text found in Regulation 2023/1115.** Stating it as statutory law to an ESG-auditor judge who knows the regulation invites a credibility hit on an otherwise strong answer.

**Fix:** reword to "…and we enforce 6-decimal-place vertex precision (~11 cm), exceeding the Traces registry submission requirement."

---

### 9.9 LOW — Definition of Done is pre-checked

`08-PROJECT-PLAN` §1.2 marks all four DoD criteria `[x]` in a plan document written before implementation.

**Fix:** reset to `[ ]` so the checklist has signal.

---

### §WITHDRAWN§0 LOW — Dead mock-server logic branch

`11` §3 `mock_triage` treats `observed_shadow_azimuth_deg > 200` as a fraud signal. But `05-API-SPEC`'s own **VERIFIED_PASS** example uses an observed shadow of 274.5 — which trips the fraud branch. A frontend developer testing against the mock will get a quarantine response for the documented success payload.

**Fix:** gate on the `X-Mock-Scenario` header alone, or add an explicit `scenario` field to the payload.

---

## PART 10 — DOCUMENT INDEX & AUDIENCE MAP

| Doc | Title | Primary Audience |
| :-- | :--- | :--- |
| `README` | Suite overview + verification checklist | Everyone |
| `01-PRD` | Product Requirements — personas, FRs, NFRs, KPIs, STRIDE, unit economics | Product, all |
| `02-ARCHITECTURE` | C4 Context/Container/Component, trade-offs, rejected alternatives | Architects, backend |
| `03-SYSTEM-DESIGN` | 7 algorithm modules with full derivations + implementations | CV, backend, data |
| `04-DATA-AND-SCHEMA` | Cloudinary metadata schema, Pydantic/TS types, Lucene queries, C2PA manifest | Data, Cloudinary eng |
| `05-API-SPEC` | OpenAPI 3.1 endpoints + Cloudinary transformation engine (7 URL patterns) | Frontend, integration |
| `06-FRONTEND-SPEC` | Design system, 3 component specs, tokens, WCAG 2.2 AAA | Frontend, design |
| `07-RUNBOOK` | Local quickstart, solar test script, 180 s pitch script, fail-safes | Full stack, presenter |
| `08-PROJECT-PLAN` | WBS, 4-phase gantt, critical path, DoD | Leads, planners |
| `09-DATA-FIXTURES` | 3 calibrated demo scenarios + seeding script | Demo, QA |
| `10-OFFLINE-PWA-AND-DEPLOYMENT` | PWA/SW, gyroscopic leveler, forensic HUD, Docker, env | DevOps, frontend |
| `11-TEAM-PARALLEL-DX-AND-MOCKS` | 3-stream split, pinned deps, mock server, fixtures | All 3 teammates |
| `12-TESTING-AND-QA` | 4-tier pyramid, pytest/Playwright samples, GitHub Actions CI | QA, all |
| `13-JUDGE-DEFENSE-AND-FAQ` | 10 adversarial questions + answers | Presenter |
| `14-PITCH-DECK` | 8 slides, second-by-second scripts, Cloudinary rubric map | Presenter |

---

## PART 11 — EXECUTIVE SUMMARY

**The problem is well-chosen and genuinely important.** Every one of the six root causes in `01-PRD` §1.2 is real, current, and legally load-bearing. The mapping from problem to mechanism is unusually disciplined — there is almost no feature in the suite that cannot be traced to a specific root cause.

**The architecture is the strongest part of the suite.** The three C4 levels, the explicit decoupled-compute boundary, the single-source-of-truth-via-schema decision, and especially the *rejected alternatives table* in `02-ARCHITECTURE` §4 (S3+FFmpeg vs Cloudinary, LLM vs JEV, opacity slider vs homography, NeRF vs planar) read like a real design review rather than a pitch. That table alone is worth more to a technical judge than most hackathon demos.

**Where it is weak is verification.** The suite's central claim is that it replaces assertion with mathematics, and then its own mathematics does not check out:

- ~~the allometric constant under-reports carbon by 8.7×~~ — **withdrawn, see §9.1; the spec's constant was correct**,
- all four Tier-1 solar test vectors are outside their own tolerances, with one impossible by 50° (§9.2),
- the flagship "legitimate photo" fixture clears the fraud threshold by only 1.1° (§9.2),
- the written solar derivation contradicts the code that implements it (§9.5).

**And the plan does not match the spec.** Roughly half the specified system — including the modules that answer Judge Questions Q2, Q5, and Q8 — is absent from the WBS, while the plan consumes only 45 of 144 available person-hours (§9.3).

**Recommended order of work:**
1. Fix the allometric coefficient and regenerate every solar fixture from `pvlib` output (§§WITHDRAWN§, §9.2). *This is existential for the demo.*
2. Rebuild the WBS as three parallel 14-hour tracks seeded by the mock server (§9.3).
3. Correct the solar derivation in §1.2 and delete the dead ternary (§9.5).
4. Standardise on GLI + Otsu; reconcile PRD FR-2.4, `05`, and the mock (§9.4).
5. Soften the EUDR 6-decimal overclaim; fix the icon contradiction; reset the DoD checkboxes; fix the mock's fraud branch (§9.7–§WITHDRAWN§0).

The problem framing, the architecture, and the defense playbook are strong enough to win. The risk is entirely in the last mile of numerical rigor — and that is exactly the risk a product whose entire premise is "we replace trust with math" cannot afford to take.
