# API Specifications & Cloudinary Transformation Engine (API Spec)
## Project Name: VERITAS dMRV
**Document Version:** 1.0.0 (Master Release)  
**Standard Compliance:** OpenAPI 3.1.0 / RESTful Architecture  
**Target:** Frontend Engineers, Integration Developers, and Cloudinary Engineers  

---

## 1. REST API Specification (Python FastAPI Core)

### 1.1 Base URL
```
Production: https://api.veritas-dmrv.org/v1
Development: http://localhost:8000/v1
```

---

### 1.2 Endpoint 1: System-1 Forensic Triage
Executes astronomical physics verification and JEV RLCD triage on inbound field uploads.

* **URL:** `POST /api/v1/triage/evaluate`
* **Content-Type:** `application/json`
* **Latency Target:** $< 150\text{ ms}$

#### Request Body
```json
{
  "asset_public_id": "impact_evidence/KEN-042/raw_capture_month18",
  "latitude": -1.292145,
  "longitude": 36.821945,
  "capture_timestamp_utc": "2026-09-22T08:15:30Z",
  "observed_shadow_azimuth_deg": 274.5,
  "phash": "d8f1e2c4b8a91034",
  "has_c2pa_manifest": true
}
```

#### Response (200 OK — Verified Pass)
```json
{
  "status": "SUCCESS",
  "decision": "VERIFIED_PASS",
  "confidence_score": 96,
  "solar_physics": {
    "calculated_sun_azimuth_deg": 94.2,
    "calculated_sun_elevation_deg": 38.6,
    "expected_shadow_azimuth_deg": 274.2,
    "angular_error_deg": 0.3,
    "is_physically_coherent": true
  },
  "deduplication": {
    "phash_min_distance_to_corpus": 18,
    "is_duplicate_or_nursery_reuse": false
  },
  "c2pa_status": "C2PA_VERIFIED",
  "audit_receipt_id": "rec_8a91bc74e1"
}
```

#### Response (422 Unprocessable Entity — Spoof Quarantine)
```json
{
  "status": "QUARANTINED",
  "decision": "QUARANTINE_FRAUD",
  "confidence_score": 98,
  "solar_physics": {
    "calculated_sun_azimuth_deg": 284.1,
    "calculated_sun_elevation_deg": 41.2,
    "expected_shadow_azimuth_deg": 104.1,
    "angular_error_deg": 170.4,
    "is_physically_coherent": false
  },
  "quarantine_reason": "SOLAR_EPHEMERIS_PHYSICAL_DISCREPANCY: Reported capture at 2:00 PM but shadow angles prove morning sun orientation."
}
```

---

### 1.3 Endpoint 2: OpenCV SIFT Homography Registration & Canopy Delta
Extracts feature descriptors, computes the homography matrix, warps progress media, and outputs the biological vegetative canopy delta.

* **URL:** `POST /api/v1/cv/align-and-diff`
* **Content-Type:** `multipart/form-data`
* **Latency Target:** $< 800\text{ ms}$

#### Request Form Data
* `baseline_image`: Binary JPEG/PNG file ($T_1$ Baseline Anchor)
* `progress_image`: Binary JPEG/PNG file ($T_2$ Progress Update)
* `project_id`: String (e.g., `KEN-042`)

#### Response (200 OK)
```json
{
  "status": "REGISTRATION_COMPLETE",
  "homography_metrics": {
    "sift_keypoints_baseline": 3412,
    "sift_keypoints_progress": 2984,
    "good_flann_matches": 412,
    "magsac_inliers": 348,
    "inlier_ratio": 0.845,
    "is_geometrically_valid": true
  },
  "biological_canopy_delta": {
    "baseline_canopy_pixels": 142100,
    "registered_progress_canopy_pixels": 196420,
    "net_canopy_growth_pct": 38.23,
    "vegetative_index_method": "Shadow-Invariant Green Leaf Index (GLI) = (2G-R-B)/(2G+R+B) + Otsu adaptive thresholding"
  },
  "cloudinary_warped_asset_id": "impact_evidence/KEN-042/progress_month18_warped"
}
```

---

### 1.4 Endpoint 3: Statutory ESG Compliance Dossier Export
Generates a structured, EUDR/CSRD-compliant audit dossier mapped to regulatory schemas.

* **URL:** `GET /api/v1/audit/dossier/{project_id}`
* **Headers:** `Accept: application/json`

#### Response (200 OK)
```json
{
  "project_id": "KEN-042",
  "project_name": "Tsavo East Native Acacia Reforestation",
  "cadastral_polygon_geojson": {
    "type": "Polygon",
    "coordinates": [[[36.821945, -1.292145], [36.825120, -1.292145], [36.825120, -1.295400], [36.821945, -1.295400], [36.821945, -1.292145]]]
  },
  "eudr_compliance_status": "COMPLIANT_ARTICLE_9",
  "csrd_esrs_e4_biodiversity_score": 0.88,
  "verified_milestone": "Month 18 Canopy Closure",
  "allometric_biomass_estimate": {
    "species_mix": ["Acacia tortilis", "Commiphora africana"],
    "mean_dbh_cm": 8.4,
    "mean_height_m": 4.2,
    "estimated_tco2e_per_hectare": 6.84,
    "statistical_uncertainty_ci90": "9.4% (Within allowable <15% threshold)"
  },
  "c2pa_root_manifest_hash": "sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069",
  "immutable_cloudinary_archive_url": "https://res.cloudinary.com/veritas-dmrv/raw/upload/audits/KEN-042_month18_audit_pack.zip"
}
```

---

## 2. Cloudinary Dynamic Transformation Functional Engine

A primary reason VERITAS dMRV secures the Cloudinary sponsor prize is that **100% of visual diffing, split-screen views, watermarked certificates, and social cuts are computed on-demand via Cloudinary's functional URL pipeline**, eliminating expensive server-side video rendering.

### 2.1 The Dynamic Split-Screen Diff Specification
This single URL transformation composits the Baseline Anchor ($T_1$) on the left, overlays the OpenCV-registered Progress Update ($T_2$) on the right, burns high-contrast baseline/progress labels, prints live canopy metrics, and attaches a verified C2PA badge:

```
https://res.cloudinary.com/{cloud_name}/image/upload/
  c_fill,w_1200,h_800/
  c_crop,w_600,h_800,g_west/
  l_{after_warped_public_id}/c_fill,w_1200,h_800/c_crop,w_600,h_800,g_east/fl_layer_apply,g_east/
  l_text:Inter_22_bold:BASELINE%20(MONTH%200),co_white,b_rgb:000000_80,g_north_west,x_30,y_30/
  l_text:Inter_22_bold:PROGRESS%20(MONTH%2018),co_white,b_rgb:059669_90,g_north_east,x_30,y_30/
  l_text:Inter_26_black:%2B38.2%25%20CANOPY%20EXPANSION%20%7C%20C2PA%20VERIFIED,co_white,b_rgb:064e3b_95,g_south,y_30/
  f_auto,q_auto:good/
  {before_public_id}.jpg
```

### 2.2 Parameter Decomposition Matrix

| URL Segment | Operation | Functional Rationale |
| :--- | :--- | :--- |
| `c_fill,w_1200,h_800` | Canvas Normalization | Establishes a uniform $1200 \times 800$ resolution canvas for baseline image $I_1$. |
| `c_crop,w_600,h_800,g_west` | Left Crop | Crops $I_1$ to the left 600 pixels (West gravity), displaying the "Before" half. |
| `l_{after_warped_id}/.../fl_layer_apply,g_east` | Right Overlay | Overlays registered image $I_2$, crops it to 600px East, and applies it to the right half. |
| `l_text:Inter_22_bold:BASELINE...` | Left Label | Burns an unobtrusive dark pill badge in the top-left identifying baseline timing. |
| `l_text:Inter_22_bold:PROGRESS...` | Right Label | Burns an emerald pill badge in the top-right identifying progress timing. |
| `l_text:Inter_26_black:...` | Bottom HUD Metric | Burns the certified biological canopy delta ($+38.2\%$) directly over the bottom center. |
| `f_auto,q_auto:good` | Edge Delivery Tuning | Cloudinary auto-transcodes to AVIF/WebP and optimizes byte size for edge delivery. |

---

### 2.3 Automated 9:16 Mobile Donor Reel Generator (Dynamic Video URL)
Transforms horizontal drone footage into a vertical, campaign-ready 9:16 reel with smart focus tracking on the active planting sector:

```
https://res.cloudinary.com/{cloud_name}/video/upload/
  ar_9:16,c_fill,g_auto:subject/
  e_preview:duration_12:max_seg_3/
  l_text:Inter_34_black:COMMUNITY%20FOREST%20RESTORED,co_white,b_rgb:059669,g_north,y_80/
  l_text:Inter_24_bold:Tsavo%20East%20%7C%20Verified%20by%20VERITAS%20dMRV,co_white,g_south,y_60/
  f_auto,q_auto/
  {drone_footage_id}.mp4
```

---

### 2.4 Cloudinary Generative AI Pre-Processing Pipeline (`e_improve` & `e_gen_restore`)
Field photos captured in rural conservation zones are frequently compromised by muddy lenses, heavy rainfall, or poor lighting. We utilize Cloudinary's dynamic GenAI restoration to normalize assets before passing them to the SIFT feature detector:

```
https://res.cloudinary.com/{cloud_name}/image/upload/
  e_gen_restore/
  e_improve:outdoor:60/
  e_auto_contrast/
  f_auto,q_auto:best/
  {raw_field_photo_id}.jpg
```
* **`e_gen_restore`**: Automatically reconstructs compressed textures and removes sensor noise.
* **`e_improve:outdoor:60`**: Optimizes outdoor sunlight exposure and enhances edge contrast for SIFT keypoint detection.

---

### 2.5 Dynamic Institutional Impact Certificate Generator (One-Click Shareable PNG)
Generates an official-looking, branded ESG compliance certificate directly from a single Cloudinary transformation URL, complete with project details, verified canopy growth, and a dynamic QR code:

```
https://res.cloudinary.com/{cloud_name}/image/upload/
  w_1200,h_630,c_fill,b_rgb:030712/
  l_text:Inter_42_black:VERITAS%20dMRV%20IMPACT%20CERTIFICATE,co_white,g_north,y_60/
  l_text:Inter_24_bold:Project%3A%20{project_name},co_emerald_400,g_north,y_130/
  l_text:Inter_20:Verified%20Under%20EU%20CSRD%20ESRS%20E4%20%26%20Verra%20VM0047,co_slate_300,g_north,y_170/
  l_{after_warped_id}/w_450,h_300,c_fill,r_12/fl_layer_apply,g_west,x_60,y_40/
  l_text:Inter_36_black:%2B{growth_pct}%25%20CANOPY,co_white,b_rgb:059669,g_east,x_120,y_0/
  l_text:Inter_18_mono:C2PA%20Root%20Hash%3A%20{sha256_short},co_slate_400,g_south,y_40/
  f_auto,q_auto/
  certificate_background_template.png
```

---

### 2.6 Dynamic Statutory ESG Audit PDF Generation (.pdf URL Pipeline)
Eliminates heavy server-side PDF engines (e.g., Puppeteer/Weasyprint) by instructing Cloudinary to dynamically composite audit tables, C2PA cryptographic seal, and before/after imagery directly into a downloadable vector PDF:

```
https://res.cloudinary.com/{cloud_name}/image/upload/
  l_text:Inter_38_bold:VERITAS%20dMRV%20AUDIT%20DOSSIER,g_north,y_50/
  l_text:Inter_20:Statutory%20CSRD%20ESRS%20E4%20%26%20EUDR%20Article%209%20Verification,g_north,y_100/
  l_{after_warped_id}/w_500,h_320,c_fill,r_8/fl_layer_apply,g_west,x_50,y_0/
  l_text:Inter_18_bold:Parcel%20ID%3A%20KEN-042%0ARegion%3A%20Tsavo%20East%0ABiomass%20Gain%3A%20%2B6.84%20tCO2e%2Fha%0ASampling%20CI90%3A%209.4%25,g_east,x_80,y_0/
  l_veritas_assets:official_vvb_seal,w_120,h_120/fl_layer_apply,g_south_east,x_60,y_50/
  l_text:Inter_14_mono:SHA256%3A%20{root_hash},g_south_west,x_50,y_50/
  audit_dossier_base_template.pdf
```
*Note: Specifying `.pdf` as the extension on a composite template causes Cloudinary to deliver a fully vectorized, download-ready legal document.*

---

### 2.7 Generative Fill & Edge Canopy Background Removal
To maximize Cloudinary AI capabilities for aerial & satellite workflows:
* **Cadastral Boundary Expansion (`b_gen_fill`):** When a drone photo clips the perimeter of an EUDR cadastral polygon, Cloudinary Generative Fill expands the borders seamlessly:
  `c_pad,w_1600,h_1200,b_gen_fill/drone_clipped_parcel.jpg`
* **Automated Canopy Isolation (`e_background_removal`):** Automatically isolates green canopy vegetation from desert/soil backgrounds directly at the Cloudinary edge before passing to the GLI indexer:
  `e_background_removal/canopy_progress.png`

---

## 3. Asynchronous Cloudinary Webhook Endpoints

To prevent upload timeouts on high-resolution 4K drone footage, video transcriptions and eager transformations are decoupled using asynchronous webhooks.

### 3.1 Endpoint: AI Video Visual Transcription Webhook
* **URL:** `POST /api/v1/cloudinary-webhooks/video-processed`
* **Content-Type:** `application/json`

#### Payload (Sent by Cloudinary)
```json
{
  "notification_type": "upload",
  "public_id": "veritas_drones/KEN-042/transect_flight_01",
  "secure_url": "https://res.cloudinary.com/veritas-dmrv/video/upload/v1/veritas_drones/KEN-042/transect_flight_01.mp4",
  "info": {
    "categorization": {
      "google_video_tagging": {
        "data": [
          {"tag": "forest", "start_time_offset": 0.0, "end_time_offset": 14.5, "confidence": 0.98},
          {"tag": "canopy", "start_time_offset": 2.1, "end_time_offset": 12.0, "confidence": 0.95},
          {"tag": "watercourse", "start_time_offset": 8.0, "end_time_offset": 14.5, "confidence": 0.91}
        ]
      }
    }
  }
}
```

### 3.2 Endpoint: Eager Pre-Rendering Completion Webhook
* **URL:** `POST /api/v1/cloudinary-webhooks/eager-ready`
* **Purpose:** Updates database when the split-screen diff and 9:16 donor reel are pre-rendered, ensuring 0-latency live pitch demos.

---

## 4. Eager Upload Configuration (Zero Demo Latency)
When uploading progress imagery or drone reels, backend scripts must specify `eager` and `eager_async: true` with a `notification_url`:

```python
import cloudinary.uploader

def upload_monitoring_media_with_eager_transforms(file_path: str, project_id: str, warped_id: str):
    response = cloudinary.uploader.upload(
        file_path,
        folder=f"impact_evidence/{project_id}",
        eager=[
            # 1. 9:16 vertical donor reel
            {"width": 1080, "height": 1920, "crop": "fill", "gravity": "auto:subject"},
            # 2. Dynamic split-screen diff composite
            {
                "transformation": [
                    {"width": 1200, "height": 800, "crop": "fill"},
                    {"overlay": warped_id, "width": 600, "height": 800, "crop": "crop", "gravity": "east"},
                    {"flags": "layer_apply", "gravity": "east"}
                ]
            }
        ],
        eager_async=True,
        eager_notification_url="https://api.veritas-dmrv.org/v1/cloudinary-webhooks/eager-ready"
    )
    return response
```

