# Test Fixtures, Mock Data & Demo Asset Specifications (Data Fixtures)
## Project Name: VERITAS dMRV
**Document Version:** 1.0.0 (Master Release)  
**Target:** Full-Stack Engineers, QA, and Hackathon Presenters  

---

## 1. Objective: Zero-Latency Demo Readiness
In high-stakes hackathon demos, attempting to download random images from the web or relying on live field uploads creates points of failure. This document defines **3 calibrated, pre-packaged test fixture scenarios** with exact GPS coordinates, timestamps, and synthetic metadata designed to showcase the platform's full capabilities without risk.

---

## 2. Test Fixture Scenario 1: The Fraud Catch (Potemkin Nursery Spoof)

### 2.1 The Narrative
An untrusted contractor claims to have planted 500 indigenous Acacia trees in the Tsavo East Conservation Corridor, Kenya, submitting a photo at 2:30 PM local time. In reality, the photo was taken at an urban nursery in Nairobi at 8:15 AM to simulate planting.

### 2.2 Telemetry & EXIF Fixture Payload
```json
{
  "scenario_id": "SCENARIO_01_SPOOF_FRAUD",
  "project_id": "KEN-042",
  "project_name": "Tsavo East Wildlife Corridor Reforestation",
  "claimed_location": {
    "latitude": -2.854120,
    "longitude": 38.452140,
    "cadastral_polygon_id": "PARCEL-TSAVO-B"
  },
  "claimed_timestamp_utc": "2026-09-22T11:30:00Z",
  "reported_local_time": "14:30:00 (East Africa Time)",
  "observed_shadow_azimuth_deg": 274.5,
  "phash": "a3f8c1249b6d0e14",
  "expected_triage_verdict": "QUARANTINE_FRAUD",
  "forensic_breakdown": {
    "calculated_sun_azimuth_deg": 284.2,
    "calculated_sun_elevation_deg": 42.1,
    "expected_shadow_azimuth_deg": 104.2,
    "angular_error_deg": 170.3,
    "physics_verdict": "VIOLATION_SHADOW_POINTS_EAST_BUT_AFTERNOON_SUN_PRODUCES_WEST_SHADOW",
    "phash_corpus_match": "DUPLICATE_FOUND_IN_NURSERY_DATABASE (Hamming distance = 1)"
  }
}
```

### 2.3 Visual Demonstration
* **User Action:** Drag-and-drop `fixture_fraud_nursery.jpg`.
* **Instant Reaction (<150ms):** 
  * The image is outlined in bold crimson red (`#EF4444`).
  * A **Forensic Compass Dial HUD** overlays the image, displaying a yellow sun ray at $284^\circ$ and a red warning arrow showing the physical shadow pointing at $274^\circ$ ($\Delta = 170^\circ$).
  * Banner reads: `[QUARANTINED BY JEV: Solar Ephemeris Violation — Claimed 2:30 PM, Shadow Proves 8:15 AM]`.

---

## 3. Test Fixture Scenario 2: The Core Magic (Month 0 to Month 18 Reforestation)

### 3.1 The Narrative
A genuine, community-led mangrove restoration project in the Kilifi Creek Delta, Kenya. The Baseline Anchor ($T_1$) was captured in March 2025 (arid, cleared tidal mudflat). The Progress Update ($T_2$) was captured in September 2026 (dense canopy recovery). However, the volunteer stood 4 meters further back and angled the camera $22^\circ$ to the right.

### 3.2 Registration & Geometric Fixture Payload
```json
{
  "scenario_id": "SCENARIO_02_GENUINE_PROGRESS",
  "project_id": "KEN-MANGROVE-08",
  "project_name": "Kilifi Creek Mangrove Restoration Zone",
  "baseline_asset": {
    "public_id": "veritas_demo/kilifi_month0_baseline",
    "capture_date": "2025-03-14",
    "canopy_pixels_baseline": 42800,
    "latitude": -3.631240,
    "longitude": 39.849120
  },
  "progress_asset": {
    "public_id": "veritas_demo/kilifi_month18_progress",
    "capture_date": "2026-09-20",
    "camera_pose_offset": "22 deg azimuth shift, 4m translation back",
    "latitude": -3.631238,
    "longitude": 39.849125
  },
  "homography_registration_results": {
    "sift_keypoints_found": 4120,
    "good_flann_matches": 684,
    "magsac_inliers": 578,
    "inlier_ratio": 0.845,
    "homography_condition_number": 421.4,
    "is_geometrically_valid": true
  },
  "canopy_metrics": {
    "registered_canopy_pixels": 78240,
    "net_canopy_growth_pct": 82.8,
    "estimated_tco2e_per_ha": 12.4,
    "jev_decision": "VERIFIED_PASS",
    "jev_calibrated_confidence": 0.98
  }
}
```

### 3.3 Visual Demonstration
* **User Action:** Select "Kilifi Creek Mangrove Zone" $\rightarrow$ Click "Verify Month 18 Milestone".
* **Instant Reaction (<800ms):**
  * The screen smoothly loads the **Interactive Before/After Split Slider**.
  * The camera perspective shift is completely eliminated; horizon landmarks and mangrove creek banks align seamlessly.
  * Moving the slider reveals barren grey mud transitioning into lush green canopy.
  * HUD badge displays: `+82.8% Verified Canopy Growth | SIFT Inliers: 84.5% | C2PA Certified`.

---

## 4. Test Fixture Scenario 3: 4K Drone Inspection with Interactive Hotspots

### 4.1 The Narrative
A 15-second high-resolution drone flight transect inspecting a replanted corridor. Demonstrates Cloudinary’s **Interactive Video Player** with clickable spatial telemetry hotspots (*the #1 Devpost hackathon winning pattern*) and automated visual transcriptions.

### 4.2 Video Metadata & Telemetry Pins
```json
{
  "scenario_id": "SCENARIO_03_DRONE_HOTSPOTS",
  "drone_video_public_id": "veritas_demo/drone_transect_kilifi_4k",
  "visual_transcription_vtt_url": "https://res.cloudinary.com/veritas-demo/raw/upload/veritas_demo/drone_visual_transcript.vtt",
  "hotspots": [
    {
      "productId": "pin-mangrove-cluster-alpha",
      "title": "Rhizophora Mangle Cohort A",
      "start": 2.0,
      "end": 8.5,
      "hotspot": { "x": "38%", "y": "48%" },
      "info": {
        "title": "Zone A: 8,400 Mangrove Saplings",
        "species": "Rhizophora mangle (Native Red Mangrove)",
        "canopy_closure": "74.2%",
        "survival_rate": "91.4% (Year 1.5)",
        "action": "View Biomass Calculation"
      }
    },
    {
      "productId": "pin-tidal-channel-beta",
      "title": "Restored Tidal Hydrology Channel",
      "start": 7.0,
      "end": 14.0,
      "hotspot": { "x": "62%", "y": "35%" },
      "info": {
        "title": "Tidal Inflow Channel B",
        "salinity_level": "28 ppt (Optimal)",
        "hydrology_status": "RESTORED",
        "action": "View Water Telemetry"
      }
    }
  ]
}
```

### 4.3 Visual Demonstration
* **User Action:** Switch to "Drone Aerial Inspection" tab.
* **Instant Reaction:**
  * Drone footage begins playing smoothly in dark-mode Cloudinary player.
  * Pulsing emerald target rings (hotspots) track the mangrove clusters.
  * Clicking a ring opens an informative telemetry modal with species taxonomy and biomass stock calculations.
  * Below the player, a live visual transcription track displays:  
    `[00:04] AI Visual Log: Drone entering Parcel B-4. High canopy density observed. Tidal channels unobstructed.`

---

## 5. Sample Dataset Asset Staging Script
A pre-packaged staging script to load sample test fixtures into your Cloudinary cloud instance with a single command:

```typescript
// scripts/seed_demo_fixtures.ts
import { v2 as cloudinary } from 'cloudinary';

cloudinary.config({
  cloud_name: process.env.CLOUDINARY_CLOUD_NAME,
  api_key: process.env.CLOUDINARY_API_KEY,
  api_secret: process.env.CLOUDINARY_API_SECRET,
});

export async function seedDemoAssets() {
  console.log('[SEED] Seeding verified demo fixtures into Cloudinary...');

  // Upload Baseline Anchor
  const baseline = await cloudinary.uploader.upload(
    'https://images.unsplash.com/photo-1509316975850-ff9c5deb0cd9?auto=format&fit=crop&w=1200&q=80',
    {
      public_id: 'veritas_demo/kilifi_month0_baseline',
      folder: 'veritas_demo',
      context: {
        caption: 'Baseline Month 0 - Arid Land',
        project: 'KEN-MANGROVE-08',
      },
      tags: ['demo', 'baseline', 'kenya'],
    }
  );
  console.log('[SEED] Uploaded Baseline:', baseline.secure_url);

  // Upload Progress Update
  const progress = await cloudinary.uploader.upload(
    'https://images.unsplash.com/photo-1542601906990-b4d3fb778b09?auto=format&fit=crop&w=1200&q=80',
    {
      public_id: 'veritas_demo/kilifi_month18_progress',
      folder: 'veritas_demo',
      context: {
        caption: 'Progress Month 18 - Restored Canopy',
        project: 'KEN-MANGROVE-08',
      },
      tags: ['demo', 'progress', 'kenya'],
    }
  );
  console.log('[SEED] Uploaded Progress:', progress.secure_url);

  console.log('[SEED] Demo assets seeded successfully!');
}

if (require.main === module) {
  seedDemoAssets().catch(console.error);
}
```
