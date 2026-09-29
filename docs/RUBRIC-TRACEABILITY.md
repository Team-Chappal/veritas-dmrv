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
account: **20 checks pass, 0 fail, 0 warnings, 1 skipped** (`f_pdf`, paid plan only). That run is the most valuable
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

## S6 frontend: what the interface actually claims

Six bullets, and for each one the question worth asking is not "is there a
component" but "what does it say when it cannot do its job". A verification tool
that is confident in every situation is not a verification tool.

Baseline at the end of S6: **672 backend tests, 166 e2e, 95% coverage, five green
CI jobs, no build warnings.**

### 4. The portfolio grid organises, rather than lists

Assets are grouped by project and epoch with a visible count per group, because
"180 rows in one list" is a filing cabinet, not an organisation. Coverage gaps are
shown as gaps rather than omitted, so an absent group reads as absent instead of
silently blending into what is present.

### 5. The search panel reports what it could not find

The backend is lexical, not neural — Cosine and BM25 scoring over the Search API,
not embeddings — and the panel says so rather than implying semantics it does not
have. When a query returns nothing, the panel reports the empty result and names
the fields that were searched. A search box that quietly returns nothing is
indistinguishable from one that is broken.

### 6. The provenance panel labels its own degradation

Every response carries a provenance block, and the UI renders it. Panels whose
data came from bundled fixtures are badged **Fixture**; only genuinely live
responses are badged **Live**. The badge is never inferred from whether a request
appears to have succeeded.

### 7. The provenance panel's sibling checks

Auth is enforced on every mutating route with JWT scopes (`mrv:field_upload`,
`mrv:triage_review`, `mrv:vvb_signoff`), no implicit escalation between them, and
production fails closed rather than degrading to open. The 44×44 target minimum,
WCAG AAA contrast and the no-colour-alone signalling rule are asserted against
computed styles and measured boxes, not against CSS class names — a class can be
overridden later, and a test asserting a class exists would keep passing after
someone overrode it.

### 3a. The webhook secret, which was empty and is not a small detail

The rotation on 2026-09-29 set `CLOUDINARY_WEBHOOK_SECRET`, and the harness went
from **19 pass / 0 fail / 1 warn** to **20 pass / 0 fail / 0 warn**.

The warning it removed was this: with the secret empty, the webhook processor
**ACCEPTED UNVERIFIED NOTIFICATIONS**. Anyone who could reach the route could POST
a payload and have an unauthenticated request mark an asset as verified — the exact
failure the signature check exists to prevent, and it was disabled by default
rather than by accident.

Same shape as the §3 caveat above: the CODE PATH was correct, and the
CONFIGURATION was what left it open.

### 3b. The C2PA signing key is empty, and that is the honest state

`C2PA_SIGNING_PRIVATE_KEY` used to be set and is now empty. Nothing regressed,
because **nothing ever signed with it**: the codebase reads it into config and
reduces it to one boolean, `c2pa_signing_configured`. There is no
`ClaimGenerator`, no manifest, no certificate.

So the `C2PA_VERIFIED` values in this product come from seeded fixture weights
and a Cloudinary metadata default, and `/triage/evaluate` returns
`"C2PA_VERIFIED" if payload.has_c2pa_manifest` — a **client-supplied flag**, not a
verification. An empty key makes `c2pa_signing_configured` report `false`, which
is true. That is an open honesty question, not a defect in the rotation, and it
belongs in front of a judge before they ask about C2PA.

### 8. The physics HUD refuses to answer when answering would be a guess

Below ~12° of solar elevation a shadow's direction is dominated by the object and
the slope, so the comparison is **withheld**: the panel says "Cannot be determined"
and shows `— withheld —` rather than a number. The ordering is pinned in the
maths, not just the UI — a low-sun case whose observed shadow sits 111° from
expected would be *quarantined* by an implementation that compared first, so a
spec asserts it is not.

Two defects were found and fixed while building it, and both are the same mistake:

- The component carried a `??` fallback that **recomputed the very figure the
  abstention exists to withhold**, so the panel printed "3.4°" on a capture it
  had just said it could not measure.
- The fixture's low-sun observed bearing was only 3° from expected, so the case
  did not demonstrate the hazard it exists to demonstrate — a naive
  implementation would have quietly *passed* it.

### 9. The hotspot player is a player, not a caption generator

The backend derived hotspots and the TypeScript library built and validated their
WebVTT, but **nothing rendered a `<track>`, no marker was positioned over the
video, and nothing was clickable.** Rubric bullet 2 was a missing component, not
an imperfect one. `HotspotVideoPlayer` closes it.

**Clicking a hotspot SEEKS the video**, asserted to land within 1.5s of the
hotspot's start. An overlay that cannot affect the video is decoration
pretending to be an instrument. A hotspot is clickable only while the playhead is
inside its window, because an object that has left the frame should not be
selectable.

**The track had no `src` at all** — the blob URL was built in a `useMemo` behind a
`typeof window` guard, so the server rendered it empty. Now a data URL computed
identically on both sides, with the spec decoding it and asserting the body begins
`WEBVTT` rather than merely that an attribute exists.

**Marker geometry is asserted, not styled.** An earlier spec checked
`getComputedStyle().left` for a `%`, which can never pass, because computed style
always *resolves* a percentage to pixels. It now asserts the authored value **and**
that the marker lands on the same *fraction* of the frame at two viewport widths.

**The player arrived with a layout shift, and the criterion caught it.** A
`<video>` has no intrinsic size until its metadata arrives, so the box was
zero-height and then jumped to 16:9 — a measured CLS of **0.0025**. It surfaced
only in CI, because it depends on how slow the metadata is: exactly the defect a
"CLS is zero" claim made from a fast local run misses. The ratio is now reserved
on the wrapper, which also guarantees the overlay and the video always occupy the
identical rectangle. The failure message now names the shifted elements, which is
what turned "CLS is not zero" into "<video> has no intrinsic size" on the first
attempt.

### 10. The layout shift is measured, not styled

The exit criterion is CLS == 0, measured with the browser's own `layout-shift`
performance entries rather than asserted from markup. `hadRecentInput` entries are
excluded, since the specification already drops shifts within 500ms of a click and
leaving them in would let a shift hide behind one.

**The values must move or the measurement is vacuous** — a ticker that did not
update would report a perfect zero while proving nothing, so a spec asserts the
figures genuinely changed across four ticks. Three structural reasons the numbers
can move without displacing anything: fixed height, `tabular-nums` so every digit
shares an advance width, and width **reserved in `ch`** — tabular figures stop
digits *changing* width but do not stop a longer number *needing* room. The
figures are labelled *Demonstration*; a number that changes on a timer is not a
measurement.

### 11. The screenshots are evidence, and they are reproducible

All six rubric bullets have a capture in `docs/screenshots/`, plus a seventh for
the physics **abstention**, which is the strongest claim in the product and would
be lost inside a wider shot.

Captures are per-panel with the volatile state pinned (data mode set, capture
queue cleared, fonts settled, animations disabled) and **verified byte-identical
across consecutive runs** — md5-compared, not asserted. A `fullPage` dump of a
page with a live ticker on it is not evidence, because the next run produces a
different file. So a diff in that directory means a real visual change rather than
a different random number. Each capture is also size-checked, since a screenshot
that silently produced nothing would otherwise still pass.

### 12. Offline is a durability claim, and degradation is a labelled choice

**The durability claim is tested as a durability claim.** A queued capture is
written, the page is **reloaded**, and the row is asserted still there. An
enqueue-then-list-back test would pass even if nothing were persisted, because
both operations would be served from the same in-memory handle.

**Background Sync is allowed to be absent, and its absence names the right
layer.** The browser exposing `sync` but rejecting registration is a *permissions
policy* outcome, not an unreachable worker; an earlier version reported both as
"could not reach the service worker" and sent the reader to the wrong place — in a
tool whose subject is not blaming the wrong thing.

**Demo data is a user choice, not a network side effect.** Two states only:
`auto` (follow the network, label any fallback) and `fixture` (deliberate, and
described as deliberate), persisted. There is no third state in which fixtures
appear without a label.

**The service worker deliberately does not cache API responses**, asserted rather
than assumed: a cached `/api/v1/assets` would let a reviewer see yesterday's
collection believing it is today's, which is the exact confusion every provenance
badge exists to prevent. Error responses are not cached either, because a cached
404 becomes a ghost asset for the rest of the session.

### 13. A test-harness trap worth recording

`reuseExistingServer` is enabled outside CI, so a spec can silently run against a
**stale build** left listening on the test port. One spec passed in the full suite
and failed when its file was run alone — not flaky, but build-dependent. A green
local suite is only meaningful when the server it hit was built from the current
tree. CI always builds fresh, which is why this never appeared there.

This file was itself out of date for several merged stages: the S6 sections above
were announced as written by commits that had, in fact, matched nothing, because
the edits printed success unconditionally instead of checking they had applied.
`verify_docs.py` reports "clean" regardless, since it checks for unsupported
*claims* rather than missing ones. Recorded here rather than quietly fixed.

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
