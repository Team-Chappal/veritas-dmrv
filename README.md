# VERITAS dMRV · Planetary Ground Truth & Forensic Media Intelligence

[![Code Cubicle 6.0](https://img.shields.io/badge/Hackathon-Code%20Cubicle%206.0-blue.svg)](https://github.com/j4yop/veritas-dmrv)
[![Problem Statement 02](https://img.shields.io/badge/Challenge-PS02%20Cloudinary%20Media%20Intelligence-8A2BE2.svg)](https://cloudinary.com)
[![CI Gate](https://github.com/j4yop/veritas-dmrv/actions/workflows/ci.yml/badge.svg)](https://github.com/j4yop/veritas-dmrv/actions)
[![Backend Tests](https://img.shields.io/badge/Pytest-759%20Passing%20(95%25%20Coverage)-emerald.svg)](backend/tests)
[![Playwright E2E](https://img.shields.io/badge/Playwright-214%20Specs%20Passing-emerald.svg)](frontend/e2e)
[![Zero Key Mode](https://img.shields.io/badge/Execution-Zero--Key%20In--Browser%20Deterministic-sky.svg)](https://veritas-dmrv.vercel.app/console)

> **An open, epistemically grounded digital Measurement, Reporting, and Verification (dMRV) platform.**
> Built for **Code Cubicle 6.0 — Problem Statement 02 (Cloudinary Media Intelligence)**.
> Replaces subjective human assertion and black-box LLM hallucinations with astronomical solar physics, computer vision projective homography, published forestry allometry regressions, and hardware-signed cryptographic provenance.

---

### Quick Links

- 🌐 **Live Website**: [https://veritas-dmrv.vercel.app](https://veritas-dmrv.vercel.app)
- 🎛️ **Dedicated Judge Console**: [https://veritas-dmrv.vercel.app/console](https://veritas-dmrv.vercel.app/console)
- 📦 **GitHub Repository**: [https://github.com/j4yop/veritas-dmrv](https://github.com/j4yop/veritas-dmrv)
- 📑 **Rubric Traceability Matrix**: [`docs/15-RUBRIC-TRACEABILITY.md`](docs/15-RUBRIC-TRACEABILITY.md)

---

## 1. What Problem We Are Solving

Global voluntary carbon markets trade billions of dollars on self-reported assertions. Registries face a catastrophic credibility collapse caused by:

1. **Phantom Forests & Double Issuance**: The exact same tree or plot photographed from slightly different angles, or existing forest stands re-photographed and submitted across multiple registries as newly planted hectares.
2. **Fabricated Field Evidence**: EXIF GPS and timestamps are trivial to spoof with standard software in seconds. Stock photos, screenshots of tablet monitors, and altered photos repeatedly clear legacy registry checks.
3. **The Black-Box AI Fallacy**: Emerging "AI-based MRV" systems prompt large language models to estimate biomass from images. LLMs hallucinate numbers without geometric constraint, cannot explain their derivations, and collapse when challenged in a regulatory audit.

**VERITAS dMRV** solves this by establishing **Planetary Ground Truth**: an end-to-end forensic media pipeline where every claim is validated against physical laws, mathematical regressions, and cryptographic hardware signatures.

---

## 2. The Core Questions We Answer & Our Solutions

| # | The Core Question | Carbon Market Blindspot | Veritas Mathematical Solution |
| :--- | :--- | :--- | :--- |
| **Q1** | **Authenticity**: *Did this photograph happen when, where, and how it claims?* | EXIF metadata is unauthenticated plain text. Anyone can forge GPS coordinates or claim a photo was taken at noon when it was taken at dusk. | **Astronomical Solar Ephemeris & Shadow Coherence**: We compute the exact solar azimuth and elevation via the NOAA Solar Position Algorithm (`pvlib`) for the claimed latitude, longitude, and UTC timestamp. The cast shadow in the image must align with the astronomical sun vector within a strict **12.0° tolerance**. Below 10° elevation, the system scientifically withholds judgment rather than false accusation. |
| **Q2** | **Measurement**: *Has the vegetation actually changed, and by exactly how much carbon?* | Handheld before/after photos have different vantage points, focal lengths, and camera tilt. Simple pixel subtraction conflates perspective shifts with tree growth. | **Projective Homography & Chave 2014 Allometry**: SIFT keypoint feature detection and `USAC_MAGSAC++` projective homography mathematically project monitoring photos onto baseline coordinates. Canopy growth is segmented via Green Leaf Index ($\text{GLI} = \frac{2G - R - B}{2G + R + B}$) with Otsu thresholding. Biomass is computed with **Chave et al. (2014) Eq. 4**: $$\text{AGB} = 0.0673 \times (\text{WD} \cdot H \cdot D^2)^{0.976}\quad [\text{kg}]$$ and discounted with **Verra VM0047** sampling uncertainty deductions. |
| **Q3** | **Deduplication**: *Has this tree or photo been submitted to another registry?* | Cropped, resized, or color-adjusted photos evade simple SHA-256 byte comparisons. | **Perceptual Hashing (`pHash`)**: 64-bit DCT perceptual hash corpus matching. Invariant to image scaling, compression artifacts, and format re-encoding. |
| **Q4** | **Evidence & Integrity**: *Can an auditor verify the chain of custody without trusting our servers?* | Centralized databases can alter records or vanish. Audit trails depend on trusting private operators. | **C2PA Hardware Provenance & Merkle Root**: Photographs are bound to hardware-signed C2PA manifests (v1.4) signed by camera secure enclaves. Every transformation step produces a SHA-256 digest linked into a deterministic Merkle tree leaf. |

---

## 3. Scientific Architecture & 5-Stage Workflow

```
[ Field Evidence Ingestion ]
           │
           ▼
[ Stage 1: Hardware Provenance & Dedup ]
  ├── C2PA v1.4 Hardware Manifest & Enclave Signature Check
  └── 64-bit DCT Perceptual Hashing (pHash) against Corpus
           │
           ▼
[ Stage 2: Astronomical Solar Physics Gate ]
  ├── NOAA Solar Position Algorithm (pvlib) Azimuth (α) & Elevation (h)
  ├── Expected Shadow Azimuth θ = (α + 180°) mod 360°
  └── Coherence Check: |θ_obs - θ_exp| ≤ 12.0° (Low sun < 10°: WITHHOLD)
           │
           ▼
[ Stage 3: Computer Vision Homography & Canopy Segmentation ]
  ├── SIFT Keypoint Extraction & FLANN Matcher
  ├── USAC_MAGSAC++ Projective Homography Matrix H
  └── Green Leaf Index (GLI) + Otsu Thresholding → Pixel Canopy Delta
           │
           ▼
[ Stage 4: Biomass Allometry & Carbon Accounting ]
  ├── Chave et al. 2014 Eq. 4: AGB = 0.0673 · (WD · H · D²)^0.976
  ├── Carbon Fraction stoichiometric conversion (47% C → 44/12 CO₂e)
  └── Verra VM0047 Conservative Uncertainty Deduction (15% baseline)
           │
           ▼
[ Stage 5: Cloudinary Media Delivery & Audit Dossier ]
  ├── Automated WebVTT Telemetry Captions for Video Monitoring
  ├── Dynamic Signed Media Transformations & Social Campaign Cards
  └── Cryptographic Audit Receipt & Exportable Verification Proof
```

---

## 4. Technical Architecture & Tech Stack

```
veritas-dmrv/
├── frontend/                  # Next.js 15 App Router Console & Landing
│   ├── app/
│   │   ├── page.tsx          # Streamlined Landing Page (Overview, Arch, Tech, Quick Console)
│   │   ├── console/page.tsx  # Dedicated Multi-Instrument Forensic Command Center
│   │   └── layout.tsx        # Token Baseline (#030712 canvas), Theme Provider
│   ├── components/           # UI Components (Strict >=44px touch targets, zero CLS)
│   │   ├── VerificationConsole.tsx  # Live Solar, Biomass & C2PA Sandbox
│   │   ├── ProofOfImpactStudio.tsx  # Before/After Homography Split Slider
│   │   ├── HotspotVideoPlayer.tsx   # Video Player with WebVTT hotspot sync
│   │   ├── PortfolioGrid.tsx        # 500-Asset Corpus Grid with filters
│   │   ├── SemanticSearch.tsx       # Natural Language Query Parser & Gaps
│   │   ├── CampaignStudio.tsx       # Cloudinary transformation layers
│   │   └── ProvenancePanel.tsx      # C2PA Manifest & Merkle Leaf Inspector
│   ├── lib/                  # Browser math (NOAA solar ephemeris, WebVTT parser)
│   └── e2e/                  # 214 Playwright E2E specs across 20 suites
├── backend/                   # Pure Computational Engine & Python Services
│   ├── services/
│   │   ├── solar_service.py     # pvlib ephemeris → shadow coherence verdict
│   │   ├── biomass_service.py   # Chave 2014 Eq. 4 + VM0047 uncertainty discount
│   │   ├── cv_service.py        # SIFT + USAC_MAGSAC++ homography + GLI
│   │   ├── forgery_service.py   # Laplacian gradient + Moire + frequency analysis
│   │   ├── dedup_service.py     # 64-bit pHash deduplication corpus
│   │   └── report_service.py    # Segno QR verification audit receipts
│   ├── core/                    # Config, rate limiting, Cloudinary signed client
│   └── tests/                   # 759 pytest unit & integration tests (95% coverage)
└── scripts/
    ├── ci-gate.py               # CI Gate blocker (prevents unverified merges)
    ├── deploy_demo.sh           # Vercel deployment & public URL verification
    ├── verify_docs.py           # Zero-dependency doc claim & constant linter
    └── gen_solar_fixtures.py    # Ground truth pvlib solar vector generator
```

### Technology Highlights

- **Frontend Framework**: Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS.
- **Client-Side Cryptography**: Web Crypto API (`crypto.subtle.digest`) for real-time SHA-256 Merkle leaf calculations.
- **Computer Vision & Physics**: Python 3.13, OpenCV (`cv2`), `pvlib-python`, NumPy, SciPy, Pillow, `imagehash`.
- **Media Cloud**: Cloudinary Media Intelligence API, dynamic transformation chains (`c_fill,g_auto,e_gen_background_replace`), signed URLs, WebVTT dynamic tracks.
- **Quality & Performance**: Playwright (214 tests), Pytest (759 tests), Strict 0.000 Cumulative Layout Shift (`cls.spec.ts`), WCAG 2.2 AAA $\ge 44\text{px}$ touch targets (`design-system.spec.ts`).

---

## 5. Code Cubicle 6.0 Hackathon Alignment (PS02 — Cloudinary)

| Hackathon Rubric Requirement | How VERITAS dMRV Implements It | Dedicated Surface |
| :--- | :--- | :--- |
| **1. Asset Corpus & Portfolio** | Filterable grid of 500 media assets with status indicators, metadata badges, and pagination. | [`/console#portfolio-heading`](https://veritas-dmrv.vercel.app/console#portfolio-heading) |
| **2. Hotspot Video Player & Auto-Tags** | HTML5 video player with real-time WebVTT cues, clickable bounding-box hotspots, and telemetry sync. | [`/console#hotspot-heading`](https://veritas-dmrv.vercel.app/console#hotspot-heading) |
| **3. Before / After Proof of Impact** | Interactive dual-canvas split slider with SIFT homography alignment, inlier ratio, and GLI canopy delta. | [`/console#impact-heading`](https://veritas-dmrv.vercel.app/console#impact-heading) |
| **4. Campaign Media Studio** | Dynamic Cloudinary URL generation with generative layer replacements, multi-channel aspect ratios (16:9, 9:16 reels), and QR verification badges. | [`/console#campaign-heading`](https://veritas-dmrv.vercel.app/console#campaign-heading) |
| **5. Semantic Search & Gap Analysis** | Natural language search engine across claims, dates, and coordinates with automated schedule gap detection. | [`/console#search-heading`](https://veritas-dmrv.vercel.app/console#search-heading) |
| **6. Cryptographic Provenance** | C2PA hardware manifest validation with tamper detection and SHA-256 Merkle root verification. | [`/console#provenance-heading`](https://veritas-dmrv.vercel.app/console#provenance-heading) |

---

## 6. Reproducibility & Zero-Key Verification

VERITAS dMRV is engineered for **Zero-Key Determinism**: a judge or auditor opening the deployment needs zero credentials, zero accounts, and zero cloud API keys.

```bash
# 1. Clone the repository
git clone https://github.com/j4yop/veritas-dmrv.git
cd veritas-dmrv

# 2. Run documentation and claim verification (zero external dependencies)
python3 scripts/verify_docs.py

# 3. Run full backend physics and ephemeris test suite (759 tests)
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q

# 4. Run full frontend Playwright test suite (214 tests)
cd frontend
npm ci
npx playwright test

# 5. Launch local development server
npm run dev
# Open http://localhost:3000 (Landing) or http://localhost:3000/console (Judge Cockpit)
```

---

## 7. License & Credits

- **Developer**: Jay Gopal ([@j4yop](https://github.com/j4yop))
- **Hackathon**: Code Cubicle 6.0 · Problem Statement 02 (Cloudinary Media Intelligence)
- **Scientific References**:
  - Chave, J. et al. (2014). *Improved allometric models to estimate the aboveground biomass of tropical trees.* Global Change Biology, 20(10), 3177-3190.
  - Reda, I., & Andreas, A. (2004). *Solar position algorithm for solar radiation applications.* Solar Energy, 76(5), 577-589 (NOAA SPA / `pvlib`).
  - Coalition for Content Provenance and Authenticity (C2PA) Specification v1.4.
  - Verra VM0047 Methodology for Improved Forest Management.
