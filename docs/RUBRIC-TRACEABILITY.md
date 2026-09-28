# Rubric Traceability — Code Cubicle 6.0, Problem Statement 02

**Source:** the graded brief, quoted verbatim below. Re-read from
`Code Cubicle 6.0 Problem Statements.pdf` during S3 planning.

> **PROBLEM STATEMENT 02 · CLOUDINARY — AI-Powered Impact & Sustainability
> Media Platform**
>
> NGOs, governments, and sustainability organizations generate large volumes of
> photos and videos from field projects, environmental initiatives,
> infrastructure work, and community programs. Manually organizing, analyzing,
> verifying, and turning this media into meaningful evidence and reports is
> time-consuming and difficult to scale.
>
> The challenge is to build an AI-powered media intelligence platform **using
> Cloudinary** that can understand field media, organize evidence by project,
> location, and timeline, and help teams turn visual data into reliable insights
> and impact stories.
>
> **GOAL — Build a complete platform that can:**
> 1. Analyze and intelligently organize large collections of image and video
>    evidence.
> 2. Identify relevant projects, activities, locations, and **visual signals**
>    from media.
> 3. **Compare before-and-after media** to demonstrate visible project or
>    environmental changes.
> 4. Generate visual reports, **summaries**, and **campaign-ready content** from
>    collected evidence.
> 5. Make media searchable through **AI-powered metadata, tagging, and semantic
>    discovery**.
> 6. Preserve traceability to the original source assets and transformations.
>
> **EXPECTED OUTCOME:** A scalable media intelligence product that transforms
> raw field media into searchable evidence, measurable impact, and compelling
> visual stories.

---

## Why this document exists

The `docs/` suite was written against a self-invented problem — carbon-credit
fraud forensics — that only partially overlaps the graded one. The first audit
found the schedule heavily invested in things the rubric does not mention (EUDR
polygon validation, allometric carbon accounting, SAM segmentation) while
leaving things it names explicitly unbuilt.

This table is the answer to "does the product do what the brief asks", and it is
kept honest by construction: every row names a service, a test, and — where the
capability is only partly delivered — says so.

---

## Coverage

| # | Requirement | Status | Implementation | Tests |
| :-- | :--- | :--- | :--- | :--- |
| **1** | Analyze and intelligently organize large collections | 🟡 partial | Cloudinary Structured Metadata (11 typed fields, Lucene index); folder taxonomy by project; **`SemanticIndex`** over the whole corpus; `make seed` stages a 500-asset corpus | `TestSemanticIndex`, `TestQueryCompilation` |
| **2** | Identify projects, activities, locations, **visual signals** | 🟢 | `enrichment_service` — canopy cover, water, sky, soil, urban, overcast, harsh-sun, aerial-vs-ground, all measured from pixels; capture metadata contributes project/phase/domain; Cloudinary `categorization` fused. `video_service` turns AI Video Analysis segments into a WebVTT caption track and player hotspots | `TestEnrichment` (18), `TestHueBands` (4), `TestCloudinaryFusion` (4), `TestVttRendering` (12), `TestHotspots` (5) |
| **3** | **Compare before-and-after** to demonstrate change | 🟢 | `homography_service` (CLAHE→SIFT→FLANN→Lowe→USAC_MAGSAC++→warp, NumPy TPS fallback) + `canopy_service` (GLI+Otsu, warp-border exclusion) | `TestRegistration` (8), `TestParallaxTrigger` (7), `TestThinPlateSpline` (8), `TestCanopyMeasurement` (10) |
| **4** | Visual reports, **summaries**, **campaign-ready content** | 🟢 | Reports and campaign content: split-diff, 9:16 donor reel, impact certificate and vector audit PDF, all composed as transformation URLs with no server-side render. Summaries: `narrative_service` with enforced grounding and an LLM-prose boundary | `TestUrlEngine` (18), `TestGrounding` (13), `TestLlmBoundary` (5), `TestMockCloudinaryRoutes` (9) |
| **5** | **AI-powered metadata, tagging, semantic discovery** | 🟡 partial | Tagging: `enrichment_service`. Similarity: `semantic_service` (**tf-idf lexical**, not a neural model) with a Cloudinary Vector Search adapter. Structured: `query_service` NL→validated Lucene | `TestSemanticIndex` (15), `TestQueryCompilation` (14) |
| **6** | Traceability to source assets and transformations | 🟡 partial | C2PA manifests, SHA-256 roots, `audit_receipt_id`; `/assets/{id}/provenance` reports the master asset and its transformation chain, live against the Cloudinary API. **Live read unproven** — see below | `TestMockDossier` (4), `TestMockCloudinaryRoutes` (9) |
| intro | Organize by **timeline** | 🟢 | `timeline_service` — milestone epochs, single-epoch asset assignment, coverage gaps, and the count-trap case | `TestTimeline` (12), `TestDateHelpers` (5) |

### Legend
🟢 delivered and tested · 🟡 partially delivered, gap named · 🔴 not built

---

## The two gaps, stated plainly

### 1. The live paths now run, and the transformation grammar was WRONG

`scripts/validate_cloudinary_live.py` has been run against a real free-tier
account: **18 checks pass, 0 fail, 2 skipped.** That run is the most valuable
thing this project has done, because it disproved a claim the unit tests were
green about. The composed transformation URLs had never rendered, and the
defects were only findable against the real API:

| Defect | Real symptom | Fix |
| :--- | :--- | :--- |
| `fl_layer_apply` in a delivery URL | `Cannot find matching layer start` | upload-time flag; gravity belongs inside `l_` |
| folder-qualified layer reference | `Resource not found` | Cloudinary uses a **colon**, not a slash: `l_a:b:c` |
| `b_rgb:000000_80` | `Invalid color name` | alpha is 8 hex digits: `b_rgb:00000080` |
| font `Inter` | `Unsupported font family Inter` | not on Cloudinary's servers; `Lato` verified |
| `co_emerald_400`, `co_slate_300` | `Invalid color name` | no such named colours; `co_rgb:` |
| `\n` and `/` inside overlay text | `public_id (...) is invalid` | both terminate the layer, even encoded |

Nine tests asserted the shape of these URL strings and passed throughout. They
checked the builder's output, never asked Cloudinary whether it was valid. That
is the failure mode this project exists to catch, and it happened to us.

**Still unproven, and stated rather than assumed:**

- **`audit_pdf` is plan-gated.** `f_pdf` output returns `401 deny or ACL failure`
  on a free plan. Separately verified: Cloudinary does **not** composite text onto
  a `raw` PDF — the file comes back byte-identical, so the layer stack is
  silently discarded. The builder now uses the only form that composites (`f_pdf`
  on the image) and the harness reports the check as SKIP with the reason, rather
  than calling a paywall a defect.
- **`donor_reel` now renders** (200, `video/mp4`). Closing it found a further
  real defect: the builder used `g_auto:subject`, which is **image-only** and
  400s on a `/video/` delivery. Every other builder targets images, so this was
  invisible until a video probe existed. Verified live:

  | gravity | result |
  | :--- | :--- |
  | `g_auto:subject` | 400 — `Invalid g_auto for video param` |
  | `center` | **200** (now the default) |
  | `g_auto` / `g_auto:faces` | 423 "Video tracking-crop is pending" — retryable, not malformed |
  | `g_auto:ocr_text` | 420 — paid subscription required |

  `g_auto` is exposed as a parameter but is not the default, because it can
  answer 423 on a cold asset. The harness generates the video probe with ffmpeg
  and SKIPs with that reason when ffmpeg is absent.
- **The webhook signature is implemented per the documentation** — see below.

### 2. Semantic search is lexical, not neural (bullet 5)

`SemanticIndex` serves a **tf-idf vector space with cosine similarity**. That
captures term overlap weighted by corpus rarity. It does **not** capture
synonymy or visual resemblance, except where a domain synonym table bridges it
(`Rhizophora`→`mangrove`, `sapling`→`tree`).

The Cloudinary Vector Search adapter is implemented and selected automatically
when credentials are configured, and it uses genuine server-side embeddings.
The backend name is reported in every response and the local path is described
as lexical in the response `notes`, so it is never presented as more than it is.

### 3. The webhook signature: documented scheme, still not confirmed live

Cloudinary's documentation gives the construction explicitly:

```
signature = HEX( HASH( raw_body + X-Cld-Timestamp + api_secret ) )
```

A plain hash with the secret **concatenated on** — not HMAC — with the timestamp
part of the signed string, in a header rather than the body, SHA-1 by default.
`webhook_service.py` implemented `hmac(secret, body)` for all three of its
schemes, so **it would have rejected every genuine notification it exists to
accept.** Two of the three schemes were also byte-identical to each other.

It now delegates to `cloudinary.utils.verify_notification_signature` — the vendor's
own verifier — and falls back to a local implementation only when the SDK is
absent or the configured secret is not the globally configured one (a dedicated
webhook key would otherwise be verified against the wrong secret). A freshness
window rejects replays.

**Not yet confirmed against a real notification**, because Cloudinary has to POST
to a publicly reachable URL. Step 9 of the harness reports the headers to watch
for. Treat signature verification as unverified until that runs, and rely on the
fixture-mode degradation meanwhile.

---

## Where the "using Cloudinary" requirement is met

The brief says *"using Cloudinary"*, so the Cloudinary surface is tracked
separately:

| Capability | Where it runs | Stage |
| :--- | :--- | :--- |
| Master asset vault, immutable RAW + C2PA | Cloudinary CDN | S4 |
| Admin Structured Metadata as system of record | Cloudinary | S4 |
| Lucene Search API execution | Cloudinary | S4 (expressions compiled and validated in S3) |
| AI Video Analysis → VTT transcription | Cloudinary | S4 |
| Dynamic URL transformation engine | Cloudinary edge | S4 |
| Interactive video player + spatial hotspots | Cloudinary | S6 |
| Vector Search / embeddings | Cloudinary, when configured | S3 (adapter) |
| Solar ephemeris, homography, GLI, allometry | Local Python | S1–S2 (by design) |

The compute split is deliberate and stated in `docs/02-ARCHITECTURE.md`: heavy
matrix mathematics runs in the Python microservice, everything visual runs at
the CDN edge. Cloudinary is the media intelligence and trust backbone, not the
numerical engine.

---

## What is deliberately NOT claimed

Carried forward from the S1/S2 audit, because a rubric gap is a scheduling fact
and an overclaim is a correctness failure:

- **Screen-replay detection is unvalidated.** The specified Moiré threshold was
  measured as unachievable by the phenomenon it detects, and is exceeded by
  clean photographs. It routes to human review. It cannot be demonstrated as a
  working fraud detector, so no rubric row depends on it.
- **The canopy DBH-from-crown-area relation is a proxy**, labelled as such in
  every record. Real field survey bypasses it.
- **At 8K the registration's detection downscale drops the SIFT inlier ratio
  below the trust floor.** The pipeline reports this rather than returning a
  confident result from a degraded keypoint set.
- **8K is not a committed target**; see `docs/LATENCY-BASELINE.md`.

---

## Test coverage of the graded capabilities

```
Tier 1  physics & forensics         solar ephemeris, allometry, VM0047,
                                    forgery signals, pHash dedup
Tier 2  computer vision             SIFT/MAGSAC++, TPS, detection scaling,
                                    radiometric, GLI canopy, GLI invariance
Tier 3  enrichment & semantics     auto-tagging, hue bands, Cloudinary fusion,
                                    semantic index, query compiler, narrative
                                    grounding, LLM boundary, timeline
Tier 4  integration & API           mock-server contract for every route above
```

Full suite: **286 tests**, coverage gate 85%.
