# Data Architecture & Cloudinary Metadata Schema
## Project Name: VERITAS dMRV
**Document Version:** 1.0.0 (Master Release)  
**Target:** Data Engineers, Cloudinary Solutions Engineers, and Database Architects  

---

## 1. Architectural Philosophy: Cloudinary as the Primary Data Store

In typical web architectures, media files are stored passively in object storage (AWS S3 / Google Cloud Storage), while business metadata resides in an external relational database (PostgreSQL / MySQL). 

This split creates severe vulnerabilities for high-compliance ESG reporting:
* **Metadata Desynchronization:** Media updates, crops, and deletions drift out of sync with database rows.
* **Integrity Breaks:** Relational database records can be altered without altering the media file, violating chain-of-custody audits.

**VERITAS dMRV eliminates this vulnerability by utilizing Cloudinary Admin Structured Metadata (`metadata_fields`) as the single, schema-enforced source of truth.** All telemetry, algorithmic verification results, and spatial boundaries are cryptographically bound directly to the media asset inside Cloudinary's global index.

---

## 2. Cloudinary Admin Structured Metadata Fields

The following fields are registered at the Cloudinary account level via the Admin API:

| External ID | Display Label | Type | Validation / Schema Rules | Mandatory | Searchable |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `esg_project_id` | Project Code | `string` | Regex: `^[A-Z]{3,6}-[0-9]{3,5}$` | Yes | Yes (Exact & Prefix) |
| `sustainability_domain` | Sector | `enum` | `reforestation`, `mangrove_restoration`, `clean_water`, `solar_microgrid` | Yes | Yes (Filter) |
| `cadastral_polygon_id`| Geofence Plot | `string` | Alphanumeric Parcel ID (e.g., `PARCEL-KEN-042`) | Yes | Yes (Exact) |
| `capture_timestamp` | Field Capture Date | `date` | ISO 8601 (YYYY-MM-DD) | Yes | Yes (Range) |
| `solar_azimuth_error` | Shadow Angle Error | `integer` | Degrees offset $[-180, 180]$ | Yes | Yes (Range) |
| `jev_triage_decision` | JEV Action | `enum` | `VERIFIED_PASS`, `REVIEW_AMBIGUOUS`, `QUARANTINE_FRAUD` | Yes | Yes (Filter) |
| `jev_confidence_score`| RLCD Confidence | `integer` | Value between $0$ and $100$ | Yes | Yes (Range) |
| `sift_inlier_ratio` | Homography Inliers| `integer` | Value between $0$ and $100$ (Percentage) | No | Yes (Range) |
| `canopy_delta_pct` | Net Canopy Growth | `integer` | Value between $-100$ and $500$ (%) | No | Yes (Range) |
| `c2pa_provenance` | C2PA Status | `enum` | `C2PA_VERIFIED`, `C2PA_MISSING`, `C2PA_MUTATED` | Yes | Yes (Filter) |
| `milestone_phase` | Reporting Epoch | `enum` | `baseline_month_0`, `progress_month_6`, `progress_month_18`, `certified_year_3` | Yes | Yes (Filter) |

---

## 3. Strong Typing Specifications

### 3.1 Pydantic Models (Python Compute Core)

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import date

class CloudinaryMetadataPayload(BaseModel):
    esg_project_id: str = Field(..., pattern=r'^[A-Z]{3,6}-[0-9]{3,5}$')
    sustainability_domain: Literal[
        'reforestation', 'mangrove_restoration', 'clean_water', 'solar_microgrid'
    ]
    cadastral_polygon_id: str
    capture_timestamp: date
    solar_azimuth_error: int = Field(..., ge=-180, le=180)
    jev_triage_decision: Literal['VERIFIED_PASS', 'REVIEW_AMBIGUOUS', 'QUARANTINE_FRAUD']
    jev_confidence_score: int = Field(..., ge=0, le=100)
    sift_inlier_ratio: Optional[int] = Field(None, ge=0, le=100)
    canopy_delta_pct: Optional[int] = Field(None, ge=-100, le=500)
    c2pa_provenance: Literal['C2PA_VERIFIED', 'C2PA_MISSING', 'C2PA_MUTATED']
    milestone_phase: Literal[
        'baseline_month_0', 'progress_month_6', 'progress_month_18', 'certified_year_3'
    ]
```

### 3.2 TypeScript Interfaces (Next.js 15 Client & Cloudinary SDK)

```typescript
export type SustainabilityDomain = 
  | 'reforestation' 
  | 'mangrove_restoration' 
  | 'clean_water' 
  | 'solar_microgrid';

export type JevTriageDecision = 
  | 'VERIFIED_PASS' 
  | 'REVIEW_AMBIGUOUS' 
  | 'QUARANTINE_FRAUD';

export type C2paStatus = 
  | 'C2PA_VERIFIED' 
  | 'C2PA_MISSING' 
  | 'C2PA_MUTATED';

export type MilestonePhase = 
  | 'baseline_month_0' 
  | 'progress_month_6' 
  | 'progress_month_18' 
  | 'certified_year_3';

export interface VeritasAssetMetadata {
  esg_project_id: string;
  sustainability_domain: SustainabilityDomain;
  cadastral_polygon_id: string;
  capture_timestamp: string; // YYYY-MM-DD
  solar_azimuth_error: number;
  jev_triage_decision: JevTriageDecision;
  jev_confidence_score: number;
  sift_inlier_ratio?: number;
  canopy_delta_pct?: number;
  c2pa_provenance: C2paStatus;
  milestone_phase: MilestonePhase;
}
```

---

## 4. High-Performance Lucene Search Queries

Cloudinary’s Search API uses Lucene expression syntax, enabling the web frontend to execute complex, multi-dimensional queries directly against the global CDN index without querying a secondary database:

### Query 1: Retrieve All Verified Month 18 Reforestation Assets with Positive Canopy Growth
```typescript
import { v2 as cloudinary } from 'cloudinary';

export async function fetchVerifiedProgressAssets(projectId: string) {
  return await cloudinary.search
    .expression(
      `metadata.esg_project_id="${projectId}" AND ` +
      `metadata.jev_triage_decision="VERIFIED_PASS" AND ` +
      `metadata.milestone_phase="progress_month_18" AND ` +
      `metadata.canopy_delta_pct > 0 AND ` +
      `metadata.c2pa_provenance="C2PA_VERIFIED"`
    )
    .with_field('metadata')
    .with_field('context')
    .sort_by('created_at', 'desc')
    .max_results(50)
    .execute();
}
```

### Query 2: Retrieve Quarantined Fraudulent Assets for Compliance Auditing
```typescript
export async function fetchQuarantinedAssets(projectId: string) {
  return await cloudinary.search
    .expression(
      `metadata.esg_project_id="${projectId}" AND ` +
      `metadata.jev_triage_decision="QUARANTINE_FRAUD"`
    )
    .with_field('metadata')
    .sort_by('created_at', 'desc')
    .max_results(20)
    .execute();
}
```

---

## 5. C2PA Content Credentials Manifest Schema

Every master asset includes a standard **C2PA (Coalition for Content Provenance and Authenticity)** JUMBF manifest structure:

```json
{
  "c2pa_manifest": {
    "version": "2.1",
    "claim_generator": "VERITAS_dMRV_Client/1.0.0",
    "title": "Field_Evidence_Parcel_KEN_042_Month_18.jpg",
    "format": "image/jpeg",
    "instance_id": "urn:uuid:8f3c7a91-4d1e-48a2-97b5-24e62a1b918f",
    "assertions": [
      {
        "label": "c2pa.actions",
        "data": {
          "actions": [
            {
              "action": "c2pa.created",
              "when": "2026-09-22T08:15:32Z",
              "softwareAgent": "VERITAS_PWA_Hardware_Sealed"
            }
          ]
        }
      },
      {
        "label": "c2pa.location",
        "data": {
          "latitude": -1.292145,
          "longitude": 36.821945,
          "altitude_m": 1682.4,
          "coordinate_precision": 6
        }
      },
      {
        "label": "veritas.forensic.telemetry",
        "data": {
          "solar_azimuth_calculated": 94.2,
          "solar_elevation_calculated": 38.6,
          "shadow_azimuth_observed": 274.5,
          "angular_discrepancy_deg": 0.3,
          "device_attestation_status": "STRONG_INTEGRITY_CONFIRMED"
        }
      }
    ],
    "signature": {
      "format": "es256",
      "cert_chain": ["-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----"],
      "issuer": "Veritas Trust CA Authority"
    }
  }
}
```
