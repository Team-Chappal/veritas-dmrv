# High-Level Architecture & Technical RFC (HLD)
## Project Name: VERITAS dMRV
**Document Version:** 1.0.0 (Master Release)  
**Standard Compliance:** IEEE 1471 / ISO/IEC 42010 Architecture Standard  
**Target:** Engineering Leads & Systems Architects  

---

## 1. Architectural Principles & System Context

### 1.1 The Core Architectural Doctrine
The system architecture of **VERITAS dMRV** is governed by three non-negotiable engineering principles:

1. **Decoupled Compute Boundary:** Heavy, iterative mathematical processing (SIFT feature extraction, USAC_MAGSAC++ homography matrix inversion, solar astronomical ephemeris) runs exclusively in a **Python asynchronous microservice**. Dynamic visual composition, format optimization, C2PA delivery, and search query execution run exclusively on **Cloudinary's edge CDN infrastructure**.
2. **Deterministic System-1 Gating:** In high-liability statutory compliance (EU CSRD, EUDR), conversational Large Language Models (LLMs) are prohibited from making binary verification or financial disbursement decisions. All triage decisions are made by **JEV (TypeSafe AI)** using **RLCD (Reinforcement Learning for Calibrated Decisions)** with mathematical probability bounds ($P \ge 0.95$).
3. **Single Source of Truth via Schema Enforcement:** To eliminate drift between application databases and stored media, **Cloudinary Structured Metadata (`metadata_fields`)** serves as the authoritative, tamper-evident document store, queried with sub-second latency via Cloudinary’s Search API.

---

## 2. C4 Architectural Model

### 2.1 Level 1: System Context Diagram

```mermaid
flowchart TD
    UserField["Field Ranger / Drone Operator"] -->|Field Media + GPS| Veritas["VERITAS dMRV Platform"]
    Veritas -->|Dynamic Media & Metadata| Cloudinary["Cloudinary Visual Cloud Engine"]
    Veritas -->|Calibrated Decision Requests| JevAI["JEV Decision Engine (TypeSafe AI)"]
    Auditor["ESG Auditor / VVB Inspector"] -->|Audit Dossier Requests| Veritas
    Veritas -->|C2PA Provenance & Audit Reports| Auditor
```

### 2.2 Level 2: Container Diagram

```mermaid
flowchart TD
    subgraph ClientTier["Client Tier"]
        PWA["Lightweight Field PWA\n(Next.js / HTML5 Wasm)"]
        AdminWeb["Enterprise Audit Console\n(Next.js 15 App Router / Tailwind)"]
    end

    subgraph BackendTier["Compute Core (Python FastAPI Microservice)"]
        Gateway["API Gateway & Auth\n(FastAPI / Uvicorn)"]
        SolarModule["Solar Ephemeris Service\n(pvlib / Astronomical Math)"]
        CVModule["Geometric Registration Service\n(OpenCV SIFT / MAGSAC++)"]
        BioMetricModule["Ecological Delta Engine\n(ExG Vegetative Index)"]
        JevClient["JEV Decision Client\n(TypeSafe AI RLCD)"]
    end

    subgraph CloudinaryTier["Cloudinary Visual Cloud & Trust Engine"]
        MediaVault["Master Asset Vault\n(Immutable RAW & C2PA Assets)"]
        StructMeta["Admin Structured Metadata\n(Lucene Inverted Index)"]
        URLTransformer["Dynamic Functional URL Engine\n(Chained Split-Diffs & Watermarks)"]
        VideoEngine["AI Video Analysis API\n(Visual Transcription Track)"]
        HotspotPlayer["Interactive Cloudinary Video Player\n(Telemetry Hotspot Engine)"]
    end

    PWA -->|Direct Chunked Upload| MediaVault
    PWA -->|Sensor Payload| Gateway
    AdminWeb -->|REST API Requests| Gateway
    Gateway --> SolarModule
    Gateway --> CVModule
    Gateway --> BioMetricModule
    Gateway --> JevClient
    JevClient -->|Write Typed Decision| StructMeta
    CVModule -->|Upload Warped Derivative| MediaVault
    AdminWeb -->|Lucene Search Queries| StructMeta
    AdminWeb -->|Dynamic Split Renderings| URLTransformer
    AdminWeb -->|Interactive Playback| HotspotPlayer
    VideoEngine -->|Visual Subtitles .VTT| HotspotPlayer
```

### 2.3 Level 3: Component Diagram (Python Compute Core)

```mermaid
classDiagram
    class IngestionController {
        +evaluate_triage(payload: IngestionPayload) TriageResult
        +align_and_diff(before_id: str, after_id: str) RegistrationResult
    }
    class SolarEphemerisService {
        +calculate_sun_position(lat, lon, utc_time) SunVector
        +verify_shadow_angle(sun_azimuth, observed_shadow) float
    }
    class HomographyService {
        +extract_sift_features(image) Keypoints
        +match_flann(des1, des2) Matches
        +solve_magsac(pts1, pts2) Matrix3x3
        +warp_perspective(image, matrix) WarpedImage
    }
    class BioMetricService {
        +compute_exg(image_rgb) BinaryMask
        +calculate_surface_delta(mask1, mask2) CanopyDelta
    }
    class JevDecisionClient {
        +evaluate_rlcd_state(telemetry_vector) JevDecision
    }

    IngestionController --> SolarEphemerisService
    IngestionController --> HomographyService
    IngestionController --> BioMetricService
    IngestionController --> JevDecisionClient
```

---

## 3. Data Flow & End-to-End Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Field as Field Ranger (PWA)
    participant Cld as Cloudinary Vault
    participant API as FastAPI Backend
    participant JEV as JEV (TypeSafe AI)
    participant CV as OpenCV SIFT / MAGSAC
    participant UI as Enterprise Dashboard
    actor Auditor as Statutory Auditor

    Field->>Cld: Upload Master Asset (Chunked Upload with C2PA Manifest)
    Cld-->>Field: Return Asset Public ID & Metadata Token
    Field->>API: POST /api/v1/triage (Asset ID, GPS, Timestamp, Shadow Angle)
    API->>API: Solar Ephemeris Check (Calculates Sun Azimuth vs. Shadow Vector)
    API->>JEV: Query RLCD Calibrated Triage
    JEV-->>API: Emit Decision (VERIFIED_PASS, Score: 0.96)
    API->>Cld: Update Structured Metadata (jev_decision=VERIFIED_PASS)
    
    Auditor->>UI: Request Before/After Milestone Verification
    UI->>API: POST /api/v1/cv/align-and-diff (Baseline ID, Progress ID)
    API->>Cld: Fetch Baseline & Progress Media Buffers
    API->>CV: Execute SIFT Extraction + FLANN Matching + MAGSAC++ Homography
    CV-->>API: Return Aligned Image & Net ExG Canopy Growth (+38.2%)
    API->>Cld: Upload Warped Derivative & Update Structured Metadata
    UI->>Cld: Request Dynamic Split URL (l_asset:after_warped/c_fill/fl_layer_apply...)
    Cld-->>UI: Deliver Edge-Composited Split Comparison with Watermarks
    UI-->>Auditor: Display Interactive Proof-of-Impact Dossier
```

---

## 4. Trade-Off Analysis & Rejected Alternatives

In big-tech engineering RFCs, identifying **why alternative solutions were rejected** is as important as the chosen design:

| Architectural Component | Alternative Considered | Chosen Architecture | Technical Rationale for Rejection |
| :--- | :--- | :--- | :--- |
| **Media Compute & Storage** | AWS S3 + Custom FFmpeg EC2 Worker Pool | **Cloudinary Visual Compute Engine** | Running custom FFmpeg workers introduces massive infrastructure cost, cold-start latency (15–45s per split render), complex queue management (Celery/SQS), and lack of native C2PA Content Credentials. Cloudinary renders chained transformations in $< 50\text{ ms}$ on edge CDN nodes. |
| **Verification Decision Engine** | Conversational LLM (GPT-4o / Claude 3.5 Sonnet) | **JEV (TypeSafe AI) System 1 RLCD Model** | LLMs are non-deterministic, suffer from sycophancy (approving bad claims to be agreeable), incur 3,000–6,000ms latency, cost $0.03/call, and cannot satisfy statutory ISO/IEC 14064 or EU CSRD audit requirements. JEV responds in $< 150\text{ ms}$ with calibrated Brier probability bounds ($P \ge 0.95$). |
| **Before/After Image Alignment** | Naive Client-Side Opacity Slider | **OpenCV SIFT + USAC_MAGSAC++ Planar Homography** | Field volunteers cannot stand in the exact same spot months apart. Without geometric homography warping, camera tilt and perspective shifts trigger 100% false change alarms in vegetation metrics. |
| **3D Volumetric Reconstruction** | Full 3D NeRF / LiDAR Gaussian Splatting | **2D Homography + Drone Canopy Height Models (CHM)** | Full 3D NeRF/Splatting requires 100+ overlapping photos per site, 45 minutes of GPU compute, and multi-gigabyte client downloads, which is completely unfeasible for rural 2G/3G field operations. |

---

## 5. Security, Provenance & Statutory Compliance Boundaries

### 5.1 C2PA Cryptographic Content Credentials
* Every asset ingested through the VERITAS PWA contains a signed **JUMBF (JSON-LD Universal Metadata Box Format)** manifest.
* The manifest cryptographically binds:
  1. Shutter capture device fingerprint.
  2. Operating system hardware attestation token (Android Play Integrity / iOS Secure Enclave).
  3. SHA-256 bit-for-bit hash of the uncompressed sensor RAW/JPEG stream.
* When Cloudinary transforms the asset into derivatives, Cloudinary’s verified credential signer re-signs the manifest as an authenticated derivative claim generator, preserving legal provenance.

### 5.2 WORM (Write Once Read Many) Evidentiary Storage
* While dynamic Cloudinary URLs provide instant interactive rendering for dashboard users, statutory ESG audits (ISSA 5000 / Verra VM0047) require immutable archival.
* All approved project milestones generate an RFC 3161 qualified electronic time-stamped **Audit Dossier Package**, archived in immutable storage with tamper-evident SHA-256 root hashes.
