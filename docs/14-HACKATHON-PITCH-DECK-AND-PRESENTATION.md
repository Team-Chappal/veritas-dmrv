# Hackathon Pitch Deck & Stage Presentation Architecture
## Project Name: VERITAS dMRV
**Document Version:** 2.0.0 — re-cut per S7.7  
**Target:** Code Cubicle 6.0 Live Final Pitch (3-Minute Presentation + 2-Minute Q&A)  
**Standard Compliance:** Y-Combinator / Devpost 1st-Place Pitch Deck Structure  

> **What changed in 2.0.0.** The pitch now **leads with rubric #3 and #5** —
> the before/after comparison and semantic discovery — instead of the
> carbon-market hook, because those are the two surfaces that *show* something
> working instead of promising something. The market framing moved to slide 5,
> after the demonstration has already landed.
>
> It also **removed three claims that did not survive checking.** See §6. Two of
> them were numbers whose provenance could not be traced, and one was a
> regulatory-compliance claim about a validator that is not implemented.

---

## 0. Claims audit — read this before the pitch

Every figure the script speaks, and what it actually is. A pitch that cannot
answer "where did that number come from?" has already lost the room it is in.

| Claim in the script | What it is | Source |
| :-- | :-- | :-- |
| Solar triage "in under 150 ms" | **spec budget**, and the measured cost is **1.11 ms p50 / 1.18 ms p95** | `docs/LATENCY-BASELINE.md` |
| 500 assets, 276 s, 1.07 assets/s | **measured** | `docs/LOAD-TEST.md` |
| 12° shadow tolerance | **product decision**, grounded in the low-sun geometry | `services/solar_service.py` |
| Canopy growth "+38.2%" | **fixture value**, not a measurement on real imagery | `mock_server.py` |
| "0.92 biodiversity score" | **fixture value** | `mock_server.py` |
| Unit economics, TAM, gross margin | **business assumptions, unverified** | none — stated as projections |
| ~~"142 ms quarantine"~~ | **REMOVED** — see §6 | — |
| ~~"shadow diverges by 170.4°"~~ | **REMOVED** — see §6 | — |
| ~~"official EUDR Article 9 dossier"~~ | **REMOVED** — see §6 | — |

---

## 1. Live Pitch Timing Architecture (180 Seconds Total)

The demo now runs **first and longest**, because a working system is the only
part of this pitch that cannot be argued with.

```
[00:00 - 00:35] Slide 1:  LIVE — the before/after comparison  (rubric #3)
[00:35 - 01:05] Slide 2:  LIVE — semantic discovery           (rubric #5)
[01:05 - 01:30] Slide 3:  LIVE — the fraud catch, and what it refuses to say
[01:30 - 01:45] Slide 4:  The problem this solves, in one paragraph
[01:45 - 02:05] Slide 5:  Market, business model, unit economics
[02:05 - 02:20] Slide 6:  How it is built — Cloudinary as the media backbone
[02:20 - 02:45] Slide 7:  What is measured, what is claimed, what is missing
[02:45 - 03:00] Slide 8:  Team, vision, ask
```

Slides 1–3 are **not slides**. They are the running product. The measured order
of surfaces is in `docs/15-RUBRIC-TRACEABILITY.md`, generated from a real
walkthrough rather than estimated.

---

## 2. Slides 1–3: the live demonstration (100 seconds)

Surface order and reach times, from `make rubric-matrix` at 1280×720:

| # | Surface | Rubric | Reached at |
| :-- | :-- | :-- | --: |
| 1 | `impact-studio` | #3 before/after | 0.70 s |
| 2 | `semantic-search` | #5 semantic discovery | 1.03 s |
| 3 | `physics-hud` | forensic triage | — |
| 4 | `provenance-panel` | #6 traceability | 1.20 s |

### Slide 1: Before and after, with the number that caused it (35s)
* **Visual on Screen:** `impact-studio` — the Kilifi mangrove split slider.
* **Speaker Script (35s):**
  > *"Let's start with something you can check. This is Kilifi, Kenya — baseline
  > and month-18 progress, shot from a different angle and a different day.
  >
  > The first thing the system does is refuse to compare them naively. It
  > registers the pair with SIFT and MAGSAC++, and it publishes the inlier ratio
  > — the fraction of keypoint matches that actually agree. **Look at that badge.**
  > At 0.935 the registration is trustworthy. Below our floor, the system reports
  > that it cannot measure rather than producing a confident number, because a
  > canopy delta computed from a degraded registration is not a measurement.
  >
  > The light is not the same in the two frames, so raw pixel comparison would be
  > meaningless. We use GLI — the Green Leaf Index — which is invariant to
  > illumination by construction. Canopy closure of 38.2%, on the demo dataset.
  > That number is our fixture, not a field result, and we label it as such."*

### Slide 2: Ask a question the way you would ask a person (30s)
* **Visual on Screen:** `semantic-search`.
* **Speaker Script (30s):**
  > *"Now, search the way you'd describe a scene rather than a filename.
  >
  > I'll type something vague — the panel takes a natural-language query, and
  > returns matches with the field that matched, so you can see *why* each one
  > came back.
  >
  > One thing we won't do: pretend this is a neural semantic index. It is BM25
  > and cosine scoring compiled to Cloudinary's Search API, and the panel says
  > 'lexical' on the surface. When it finds nothing it says so and names the
  > fields it searched — a search box that quietly returns nothing is
  > indistinguishable from a broken one."*

### Slide 3: The catch — and the part most fraud detectors get wrong (35s)
* **Visual on Screen:** `physics-hud`, switching between the coherent capture and
  the low-sun capture.
* **Speaker Script (35s):**
  > *"A photo carries a claim: this place, this time. Given the coordinates and
  > the timestamp, the sun is in a known place, so the shadow has to point in a
  > known direction. That's physics, not a model, and it runs in about a
  > millisecond.
  >
  > Now the part I think matters. **Here is a capture where the sun is four
  > degrees above the horizon.** We could still compute a number, and the number
  > would be confident and wrong. At that sun angle a shadow points wherever the
  > object and the ground slope send it.
  >
  > So the system **refuses**: 'cannot be determined', and no error figure at
  > all. A fraud detector that only answers yes or no invites you to read it as
  > an accusation. This one abstains, on purpose, and that is the behaviour I'd
  > rather have in a compliance product than a confident false positive."*

---

## 3. Slide 4: the problem, in one paragraph (15s)
* **Visual on Screen:** one line — *Day 1 photo theatre → Day 300 evidence.*
* **Speaker Script (15s):**
  > *"Carbon MRV fails because verification is manual, expensive, and sampled
  > once. The industry shows you planting. Nobody systematically shows you month
  > 18. That's the gap: continuous, physics-checkable, cryptographically
  > traceable evidence, at a cost that makes it routine."*

---

## 4. Slide 5: market and business model (20s)
* **Visual on Screen:** the unit-economics table.
* **Speaker Script (20s):**
  > *"Carbon developers pay roughly $15 a hectare a year for physical audits.
  > We model $1.20. With a filing fee on top, that's an 88% gross margin at our
  > measured compute cost — under two cents a verification.
  >
  > **Those are projections, not results.** The market size, the pricing and the
  > margin are assumptions; the only numbers in this deck we've measured are the
  > latencies and the throughput, and I'll tell you exactly which those are."*

---

## 5. Slide 6: how it is built (15s)
* **Visual on Screen:** the split: *local Python for the mathematics, Cloudinary
  for the media backbone.*
* **Speaker Script (15s):**
  > *"The numerical work — ephemeris, registration, canopy — runs in Python,
  > because that's where the libraries are. Cloudinary is the media backbone:
  > immutable originals, structured metadata as the system of record, Search API
  > execution, video analysis, and dynamic transformations at the edge.
  >
  > And the interesting detail: every transformation grammar bug we had, the unit
  > tests were green about. Only loading the URLs live found them."*

---

## 6. Slide 7: what is measured, what is claimed, what is missing (25s)
* **Visual on Screen:** three columns, filled in live from
  `docs/15-RUBRIC-TRACEABILITY.md`.
* **Speaker Script (25s):**
  > *"I'd rather tell you the boundaries than have you find them.
  >
  > **Measured:** the latencies — solar triage 1.11 ms, registration 340 ms — and
  > 500 assets through the full pipeline in 276 seconds, at 1.07 assets a second.
  > Those are on a named machine, in a committed report.
  >
  > **Claimed, not measured:** the canopy and biodiversity numbers are demo
  > fixtures, labelled in the interface. The unit economics are projections.
  >
  > **Missing, deliberately:** our EUDR Article 9 validator is **not
  > implemented**. The dossier is produced in the Article 9 *format* — including
  > emitting coordinate vertices as decimal strings so declared precision
  > survives the wire, which a JSON number cannot do — but nothing validates it.
  > So the system does not assert a compliance status. An earlier version of this
  > pitch claimed an 'official EUDR Article 9 statutory dossier'. That was a
  > validator we hadn't built, and a compliance product claiming compliance it
  > hasn't checked is the exact failure it exists to catch."*

### Claims removed in 2.0.0, and why

1. **"142 ms quarantine."** The string `142` in the codebase is
   `baseline_canopy_pixels: 142100` — a **pixel count**, not a latency. The
   actual measured triage cost is ~1.11 ms. The slide had conflated a fixture
   field with a timing.
2. **"Shadow azimuth diverges by 170.4°."** That number appears nowhere in the
   source. It is also ~180°, which is the value for *no observed shadow at all*
   rather than a real divergence — and the system's tolerance is 12°.
3. **"One-click export an official EUDR Article 9 statutory dossier."**
   `eudr_compliance_status` is a **hardcoded literal** in the mock server; the
   M7 validator is on the cut list. The pitch now claims the *format* and
   explicitly disclaims the validation.

---

## 7. Slide 8: team, vision, ask (15s)
* **Speaker Script (15s):**
  > *"We're building evidence that survives being checked. If the check is
  > unfashionable, the system abstains rather than guesses — and we'd rather
  > ship that than a number that looks better.
  >
  > What we need next is real field imagery to replace the fixtures, and a
  > reviewer who will try to break it in public. Thank you."*

---

## 8. Presenter notes

- **The live link: https://veritas-dmrv.vercel.app** — say it out loud once,
  early, and put it on the final slide. A judge who wants to verify rather than
  watch will open it during Q&A, and it works with no account, no install and no
  keys.
- **It is a fixture build, and that must be said.** There is no backend behind
  it, so no Cloudinary call is made and every panel is badged `Fixture`. The
  interface is designed so a degraded demo is visibly degraded; a presenter who
  hides that is contradicting their own product. If a judge asks "is this live?",
  the answer is no, and the reason is that the pipeline is exercised by the
  tests and the harness rather than by a public URL.
- **If the live demo fails**, the fail-safes are the ones in runbook §4: the
  demo-cache toggle in the header switches every panel to bundled fixtures with
  a visible label, and `e_preview:duration_10` streams a 10-second clip instead
  of a 4K transect. Note that the `e_preview` path is documented but **not yet
  exercised by a test** — treat it as untested until the live harness covers it.
- **Every panel is badged.** If a panel says *Fixture*, say so out loud. The
  interface is designed so that a degraded demo is visibly degraded, and a
  presenter who hides that is contradicting their own product.
- **Q&A is where the 12° tolerance gets asked.** The answer is that it is a
  product decision grounded in the low-sun geometry, that the low-sun path
  abstains rather than applies it, and that the reasoning is in
  `docs/RUBRIC-TRACEABILITY.md`.
