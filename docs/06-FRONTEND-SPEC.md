# Frontend UX & Interactive Component Specifications (Frontend Spec)
## Project Name: VERITAS dMRV
**Document Version:** 1.1.0 (Master Release — Taste & Impeccable Certified)  
**Target:** Frontend Engineers, UI/UX Designers, and Full-Stack Developers  
**Design Skills Applied:** `design-taste-frontend` + `impeccable` (v4.3.1)  

---

## 1. Design System & Aesthetic Principles (Taste & Impeccable Architecture)

### 1.1 The Design Read & Operating Mode
* **Surface Mode (from `impeccable`):** **`Operate`**  
  *The visitor completes high-stakes, legally binding forensic verification. Scanability, deterministic telemetry, and instant cognitive comprehension outrank decorative expression. Brand authority lives in mathematical precision and tactile responsiveness.*
* **Design Read (from `design-taste-frontend`):**  
  *“Reading this as: Mission-critical ESG ground-truth & climate compliance media platform for institutional carbon auditors and statutory regulators, with an aerospace-telemetry / Bloomberg visual language, leaning toward Tailwind utilities + Geist & Geist Mono + restrained spring physics + Lucide icons.”*
* **The Three Dials:**
  * **`DESIGN_VARIANCE: 6`** — Disciplined, authoritative operational command center (avoids chaotic Dribbble trends while steering clear of boring corporate bootstrap).
  * **`MOTION_INTENSITY: 5`** — Purposeful telemetry feedback, 150–250ms spring physics, interactive before/after split slider, zero gratuitous infinite-loop animations.
  * **`VISUAL_DENSITY: 8`** — Cockpit density: compact data badges, tabular numbers, cadastral coordinates, split visual diffing, zero wasted white-space.

---

### 1.2 Anti-Slop Discipline & Craft Floor Directives
1. **The Lila / AI Gradient Ban:** Absolutely zero generic purple/violet neon glows (`#8B5CF6`). All glows are strictly forbidden. The palette uses deep obsidian/zinc bases with surgical high-contrast accents:
   * **Canvas Void:** `#030712` (Zinc-950) — High-contrast operational floor ($> 16:1$ contrast against body text).
   * **Surface Layer 1:** `#0B0F19` (Deep Charcoal with 1px border `#1E293B`).
   * **Verified Ground-Truth:** `#10B981` (Forest Emerald) — AAA accessible ($> 7.2:1$).
   * **Quarantine Fraud Alert:** `#EF4444` (Crimson Alert) — Accompanied by explicit iconography & text; never color alone.
   * **Telemetry Coordinate Stream:** `#38BDF8` (Sky Cyan) — Dedicated to GPS, solar angles, and pHash strings.
2. **Typography Discipline:**
   * **Display & Body:** `Geist Sans` (`tracking-tight`, `leading-snug`).
   * **Numbers, Metrics & Hashes:** `Geist Mono` with `font-variant-numeric: tabular-nums` to guarantee **Zero Cumulative Layout Shift (CLS = 0)** during live streaming ticker updates.
   * **Serif Ban:** No arbitrary decorative serifs. Monospaced and clean grotesque sans convey forensic truth.
3. **Corner Radius System Lock:**
   * Containers & Cards: `rounded-xl` (12px) with `border border-slate-800`.
   * Buttons, Inputs & Controls: `rounded-lg` (8px).
   * Status Badges & Pills: `rounded-full`.
   * *Rule:* Never mix random radius values (e.g. no 32px pill buttons next to sharp square cards).
4. **Interactive Tactile Feedback:**
   * All clickable controls feature micro-scale physical pushback (`active:scale-[0.98] transition-transform duration-150`).
   * Button touch targets strictly adhere to $\ge 44 \times 44\text{ px}$.
   * CTA buttons strictly banned from wrapping to two lines on desktop viewports.
5. **Icon Family Standardization:**
   * Pinned exclusively to **Lucide** (`lucide-react`), which is the icon set in the pinned `package.json` and the set used by every component sample in this document and in `10-OFFLINE-PWA-AND-DEPLOYMENT.md`.
   > **CORRECTION (v1.2.0).** This section previously mandated **Phosphor Icons** (`@phosphor-icons/react`) while simultaneously (a) shipping a `package.json` containing `lucide-react` and not Phosphor, and (b) writing every code sample with `lucide-react` imports. A frontend engineer following this document literally would have installed two icon libraries. **Lucide is now the single standard.**
   * No emoji as UI icons. Status is never conveyed by colour alone — see §5.1.

---

## 2. Component Hierarchy & App Router Layout

```
frontend/
├── app/
│   ├── layout.tsx                    # Root Shell (Header, Navigation, Provider)
│   ├── page.tsx                      # Main Audit Command Center
│   ├── components/
│   │   ├── Header.tsx                # Status HUD, Network Mode, Sync Indicator
│   │   ├── IngestionZone.tsx         # Drag-and-drop upload with live triage feedback
│   │   ├── ProofOfImpactStudio.tsx   # Interactive before/after split-slider
│   │   ├── HotspotVideoPlayer.tsx    # Cloudinary Video Player with telemetry pins
│   │   ├── CadastralMap.tsx          # Leaflet/Mapbox GeoJSON geofence visualizer
│   │   ├── AuditDossierModal.tsx     # One-click EUDR/CSRD compliance export
│   │   └── FraudAlertBadge.tsx       # Live forensic alert notification
```

---

## 3. Interactive Component Specifications

### 3.1 Component 1: Interactive Before/After Split Slider (`ProofOfImpactStudio.tsx`)
Enables auditors to manually drag a split divider comparing the Baseline Anchor ($T_1$) with the SIFT-registered Progress Update ($T_2$):

```tsx
'use client';

import React, { useState } from 'react';
import { ReactCompareSlider, ReactCompareSliderImage } from 'react-compare-slider';
import { ShieldCheck, Sparkles, AlertTriangle } from 'lucide-react';

interface ProofOfImpactStudioProps {
  beforeUrl: string;
  afterWarpedUrl: string;
  canopyDeltaPct: number;
  inlierRatio: number;
  c2paVerified: boolean;
}

export const ProofOfImpactStudio: React.FC<ProofOfImpactStudioProps> = ({
  beforeUrl,
  afterWarpedUrl,
  canopyDeltaPct,
  inlierRatio,
  c2paVerified,
}) => {
  return (
    <div className="flex flex-col bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-2xl backdrop-blur-xl">
      <div className="flex items-center justify-between pb-4 border-b border-slate-800">
        <div>
          <h3 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-emerald-400" />
            Verified Geometric Diff & Biomass Delta
          </h3>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Registered via OpenCV SIFT + USAC_MAGSAC++ (Inlier Confidence: {(inlierRatio * 100).toFixed(1)}%)
          </p>
        </div>

        <div className="flex items-center gap-2">
          {c2paVerified && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-700/50">
              <ShieldCheck className="w-3.5 h-3.5" />
              C2PA Hardware Certified
            </span>
          )}
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-mono font-bold bg-slate-800 text-sky-300 border border-slate-700">
            Δ Canopy: {canopyDeltaPct > 0 ? `+${canopyDeltaPct}%` : `${canopyDeltaPct}%`}
          </span>
        </div>
      </div>

      <div className="relative mt-6 aspect-[16/10] w-full rounded-xl overflow-hidden border border-slate-800/80 shadow-inner">
        <ReactCompareSlider
          itemOne={<ReactCompareSliderImage src={beforeUrl} alt="Baseline Month 0" />}
          itemTwo={<ReactCompareSliderImage src={afterWarpedUrl} alt="Progress Month 18 (SIFT Warped)" />}
          className="w-full h-full object-cover"
        />
        <div className="absolute top-4 left-4 bg-black/75 px-2.5 py-1 rounded text-xs font-mono font-bold text-white border border-white/10 pointer-events-none">
          MONTH 0 (BASELINE)
        </div>
        <div className="absolute top-4 right-4 bg-emerald-950/90 px-2.5 py-1 rounded text-xs font-mono font-bold text-emerald-300 border border-emerald-500/30 pointer-events-none">
          MONTH 18 (WARPED)
        </div>
      </div>
    </div>
  );
};
```

---

### 3.2 Component 2: Cloudinary Interactive Hotspot Video Player (`HotspotVideoPlayer.tsx`)
Directly integrates the winning pattern from Devpost's 1st-place Cloudinary winner (*Purrfectly*), embedding interactive spatial telemetry hotspots over moving drone video:

```tsx
'use client';

import React, { useEffect } from 'react';

declare global {
  interface Window {
    cloudinary: any;
  }
}

interface HotspotVideoPlayerProps {
  cloudName: string;
  publicId: string;
  vttSubtitleUrl: string;
}

export const HotspotVideoPlayer: React.FC<HotspotVideoPlayerProps> = ({
  cloudName,
  publicId,
  vttSubtitleUrl,
}) => {
  useEffect(() => {
    // Dynamically load Cloudinary Video Player Script if not already loaded
    if (!window.cloudinary) {
      const script = document.createElement('script');
      script.src = 'https://unpkg.com/cloudinary-video-player@1.10.6/dist/cld-video-player.min.js';
      script.async = true;
      script.onload = initPlayer;
      document.body.appendChild(script);
    } else {
      initPlayer();
    }

    function initPlayer() {
      const player = window.cloudinary.videoPlayer('veritas-drone-video', {
        cloud_name: cloudName,
        showLogo: false,
        muted: true,
        controls: true,
        colors: {
          accent: '#10B981',
          base: '#030712',
          text: '#FFFFFF',
        },
        shoppable: {
          products: [
            {
              productId: 'sector-mangrove-cluster',
              title: 'Parcel B-4 Canopy Recovery Zone',
              start: 3,
              end: 18,
              hotspot: { x: '42%', y: '52%' },
              info: {
                title: 'Sector B-4: Rhizophora Mangle',
                description: 'Verified Canopy Area: +38.2%. C2PA Cryptographic Signature Confirmed.',
                action: 'View Audit Dossier'
              }
            }
          ]
        }
      });

      player.source(publicId, {
        textTracks: {
          captions: {
            label: 'AI Visual Transcription',
            language: 'en',
            default: true,
            url: vttSubtitleUrl,
          }
        }
      });
    }
  }, [cloudName, publicId, vttSubtitleUrl]);

  return (
    <div className="w-full flex flex-col bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
        <h4 className="text-base font-bold text-white flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
          Cloudinary 4K Interactive Drone Inspection
        </h4>
        <span className="text-xs font-mono text-slate-400">
          AI Video Analysis (Visual Transcription Active)
        </span>
      </div>

      <div className="relative aspect-video w-full rounded-xl overflow-hidden border border-slate-800">
        <video id="veritas-drone-video" className="cld-video-player w-full h-full" />
      </div>
    </div>
  );
};
```

---

## 4. Component 3: Direct Cloudinary Upload Widget with Chunked Streaming (`CloudinaryUploadWidget.tsx`)

Bypasses the application backend entirely for multi-gigabyte 4K drone media and field photos, uploading directly to Cloudinary via signed presets with chunked streaming and real-time progress callbacks:

```tsx
'use client';

import React, { useEffect, useRef } from 'react';
import { UploadCloud, CheckCircle2 } from 'lucide-react';

interface UploadWidgetProps {
  cloudName: string;
  uploadPreset: string;
  projectId: string;
  onUploadSuccess: (resultInfo: any) => void;
}

export const CloudinaryUploadWidget: React.FC<UploadWidgetProps> = ({
  cloudName,
  uploadPreset,
  projectId,
  onUploadSuccess,
}) => {
  const widgetRef = useRef<any>(null);

  useEffect(() => {
    if (typeof window !== 'undefined' && (window as any).cloudinary) {
      widgetRef.current = (window as any).cloudinary.createUploadWidget(
        {
          cloudName,
          uploadPreset,
          folder: `impact_evidence/${projectId}`,
          chunkSize: 6000000, // 6MB chunks for resilient mobile uploads
          maxFiles: 10,
          clientAllowedFormats: ['image', 'video'],
          sources: ['local', 'camera', 'url'],
          styles: {
            palette: {
              window: '#030712',
              sourceBg: '#0F172A',
              windowBorder: '#1E293B',
              tabIcon: '#10B981',
              inactiveTabIcon: '#64748B',
              menuIcons: '#10B981',
              link: '#38BDF8',
              action: '#10B981',
              inProgress: '#0284C7',
              complete: '#10B981',
              error: '#EF4444',
              textDark: '#030712',
              textLight: '#F8FAFC'
            }
          }
        },
        (error: any, result: any) => {
          if (!error && result && result.event === 'success') {
            onUploadSuccess(result.info);
          }
        }
      );
    }
  }, [cloudName, uploadPreset, projectId, onUploadSuccess]);

  return (
    <button
      type="button"
      onClick={() => widgetRef.current?.open()}
      className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 active:scale-95 text-white font-medium text-sm transition-all shadow-lg shadow-emerald-950/50 min-h-[44px] min-w-[44px]"
      aria-label="Upload field evidence photos or drone transect video"
    >
      <UploadCloud className="w-4 h-4" />
      <span>Upload Ground Evidence (Direct to Cloudinary)</span>
    </button>
  );
};
```

---

## 5. UI/UX Pro Max Design Token Specifications

To ensure mission-critical ergonomics conforming to **WCAG 2.2 AAA** and the **`ui-ux-pro-max`** design standards:

### 5.1 Color Tokens & Contrast Matrix
* **Canvas Background:** `#030712` (Zinc-950) — Ratio to body text $> 16:1$ (AAA Compliant).
* **Card Elevation 1:** `#0F172A` (Slate-900 / 80% opacity) with 1px border `#1E293B`.
* **Primary Interactive:** `#10B981` (Emerald-500) — Ratio to dark surface $> 7.2:1$ (AAA Compliant).
* **Warning / Quarantine:** `#EF4444` (Red-500) — High-contrast alert state with mandatory text & icon labels (never color alone).
* **Telemetry Data:** `#38BDF8` (Sky-400) — Accent color for spatial coordinates and physical azimuth angles.

### 5.2 Micro-Interactions & Motion Rhythm
* **Transition Durations:** 150ms for button hover/active states; 250ms with `cubic-bezier(0.16, 1, 0.3, 1)` for slider and modal reveals.
* **Layout Stability (CLS = 0):** All metrics, coordinates, and percentages use `font-variant-numeric: tabular-nums` (`font-mono`) to prevent horizontal layout jank during live ticker increments.
* **Touch Targets:** Minimum $48 \times 48\text{ dp}$ on mobile viewports for all buttons and hotspot pins, strictly avoiding phone screen edge collisions.

