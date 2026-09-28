"use client";

/**
 * ProofOfImpactStudio — rubric bullet 3, before/after comparison.
 *
 * TWO THINGS THIS COMPONENT REFUSES TO DO
 *
 * 1. Present a canopy delta without the registration quality that produced it.
 *    A +31.7% figure with a 0.42 inlier ratio is a number about a bad alignment,
 *    not about trees, so the inlier verdict is rendered ABOVE the delta and the
 *    delta is explicitly downgraded to "indicative" when the verdict is not
 *    `trusted`.
 *
 * 2. Hide the slider behind a mouse. It is a real `role="slider"` with
 *    arrow/Home/End/PageUp/PageDown handling, because a comparison you can only
 *    scrub with a mouse is unusable for a keyboard operator reviewing evidence.
 */

import { useCallback, useRef, useState } from "react";

import {
  DegradationNotice,
  Panel,
  SourceBadge,
  StatusPill,
  TOUCH_TARGET,
  type StatusPresentation,
} from "@/components/primitives";
import { DEMO_COMPARISON } from "@/lib/impact-fixture";
import { inlierVerdict, type ImpactComparison } from "@/lib/impact";

/** Keyboard nudge. Coarse steps are the width of a typical thumb-travel. */
const KEY_STEP = 5;
const COARSE_STEP = 10;

export default function ProofOfImpactStudio() {
  const [split, setSplit] = useState(50);
  const comparison: ImpactComparison = DEMO_COMPARISON.data;
  const { source, reason } = DEMO_COMPARISON;
  const trackRef = useRef<HTMLDivElement>(null);

  const verdict = inlierVerdict(comparison.registration.inlier_ratio);

  const setFromClientX = useCallback((clientX: number) => {
    const el = trackRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    if (rect.width === 0) return;
    const pct = ((clientX - rect.left) / rect.width) * 100;
    setSplit(Math.max(0, Math.min(100, pct)));
  }, []);

  const onKeyDown = (e: React.KeyboardEvent) => {
    const map: Record<string, number> = {
      ArrowLeft: -KEY_STEP,
      ArrowRight: KEY_STEP,
      ArrowDown: -KEY_STEP,
      ArrowUp: KEY_STEP,
      PageDown: -COARSE_STEP,
      PageUp: COARSE_STEP,
    };
    if (e.key === "Home") {
      e.preventDefault();
      setSplit(0);
      return;
    }
    if (e.key === "End") {
      e.preventDefault();
      setSplit(100);
      return;
    }
    const delta = map[e.key];
    if (delta === undefined) return;
    e.preventDefault();
    setSplit((s) => Math.max(0, Math.min(100, s + delta)));
  };

  const trusted = verdict.verdict === "trusted";

  return (
    <Panel
      id="impact-heading"
      title="Before and after"
      testId="impact-studio"
      dataSource={source}
      actions={<SourceBadge source={source} testId="impact-source" />}
    >
      <DegradationNotice reason={reason} testId="impact-reason" />

      {/*
        THE REGISTRATION VERDICT COMES FIRST. It qualifies everything below it,
        so reading order matters: a reviewer who sees the canopy delta before
        knowing the alignment is marginal has already drawn the wrong conclusion.
      */}
      <div className="mt-5 rounded border border-slate-700 bg-canvas p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-sm uppercase tracking-wide text-slate-400">
            Registration quality
          </h3>
          <p
            className="font-mono text-lg tabular-nums text-slate-100"
            data-testid="inlier-ratio"
          >
            {comparison.registration.inlier_ratio.toFixed(3)}
          </p>
        </div>
        <div className="mt-2">
          <StatusPill
            status={
              {
                glyph: verdict.glyph,
                word: verdict.word,
                tone: verdict.tone,
              } as StatusPresentation
            }
            testId="inlier-verdict"
          />
        </div>
        <p className="mt-2 text-sm leading-relaxed text-slate-300">
          {verdict.meaning}
        </p>
        <p className="mt-2 text-xs tabular-nums text-slate-400">
          {comparison.registration.sift_matches.toLocaleString()} SIFT matches ·
          mean reprojection error{" "}
          {comparison.registration.mean_reprojection_error_px.toFixed(1)} px ·{" "}
          {comparison.registration.status}
        </p>
      </div>

      {/* The slider. */}
      <div className="mt-6">
        <div className="flex items-baseline justify-between text-sm">
          <span className="text-slate-300">{comparison.baseline.label}</span>
          <span
            className="font-mono tabular-nums text-slate-400"
            data-testid="split-position"
          >
            {Math.round(split)}%
          </span>
          <span className="text-slate-300">{comparison.progress.label}</span>
        </div>

        <div
          ref={trackRef}
          data-testid="slider-track"
          onPointerDown={(e) => {
            (e.target as Element).setPointerCapture?.(e.pointerId);
            setFromClientX(e.clientX);
          }}
          onPointerMove={(e) => {
            if (e.buttons === 1) setFromClientX(e.clientX);
          }}
          className="relative mt-2 h-56 w-full cursor-ew-resize touch-none select-none overflow-hidden rounded border border-slate-700"
          style={{ backgroundImage: `url("${comparison.baseline.src}")`, backgroundSize: "cover" }}
        >
          {/*
            CLIPPED, not sized. The previous version put the progress image in a
            half-width overflow container and pinned its width to the track's
            clientWidth, falling back to 800px before the ref resolved. In a
            602px track that rendered the progress frame at 800px while the
            baseline was cover-scaled to 602 -- so the two halves showed the same
            scene at DIFFERENT MAGNIFICATIONS. A before/after comparison whose
            halves are not the same field of view is not a comparison, and it
            reads as canopy growth that is not there.

            clip-path on a full-size image removes the measurement entirely:
            both frames are the same size and the same scale by construction.
          */}
          <div
            className="absolute inset-0"
            style={{ clipPath: `inset(0 0 0 ${split}%)` }}
            data-testid="slider-progress-layer"
          >
            <img
              src={comparison.progress.src}
              // "Synthetic" is in the ALT, not just painted into the SVG. It
              // was only in the pixels, so a screen-reader user was told the
              // frame was real field evidence from month 18 -- exactly the
              // misreading this label exists to prevent, and it was hidden from
              // the one user least able to check the pixels.
              alt={`Synthetic scene: ${comparison.progress.label}, captured ${comparison.progress.captured}. Not field evidence.`}
              className="h-full w-full object-cover"
              draggable={false}
            />
          </div>

          <div
            className="absolute inset-y-0 w-0.5 bg-telemetry"
            style={{ left: `${split}%` }}
            aria-hidden="true"
          />

          {/*
            The handle is a real slider control: focusable, arrow-key operable,
            and labelled with what it controls. A div with a mousedown handler
            would pass a screenshot review and fail every keyboard user.
          */}
          <div
            role="slider"
            tabIndex={0}
            aria-label={`Comparison position between ${comparison.baseline.label} and ${comparison.progress.label}`}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(split)}
            aria-valuetext={`${Math.round(split)}% ${comparison.baseline.label}, ${
              100 - Math.round(split)
            }% ${comparison.progress.label}`}
            onKeyDown={onKeyDown}
            data-testid="slider-handle"
            className={`absolute top-1/2 flex h-11 w-11 -translate-x-1/2 -translate-y-1/2 cursor-ew-resize items-center justify-center rounded-full border-2 border-telemetry bg-surface text-telemetry focus:outline-none focus:ring-2 focus:ring-telemetry`}
            style={{ left: `${split}%` }}
          >
            <span aria-hidden="true">◀▶</span>
          </div>
        </div>

        <p className="mt-2 text-xs text-slate-400">
          Drag, or focus the handle and use ← → (5%), Page Up / Page Down (10%),
          Home and End.
        </p>
      </div>

      {/* The delta, explicitly qualified by the verdict above. */}
      <div className="mt-6 rounded border border-slate-700 bg-surface p-4">
        <h3 className="text-sm uppercase tracking-wide text-slate-400">
          Canopy cover
        </h3>
        <p className="mt-1 font-mono text-2xl tabular-nums" data-testid="canopy-delta">
          {comparison.canopy.delta_pct > 0 ? "+" : ""}
          {comparison.canopy.delta_pct.toFixed(1)}%
        </p>
        <p className="mt-1 text-sm tabular-nums text-slate-400">
          {comparison.canopy.baseline_cover_pct.toFixed(1)}% →{" "}
          {comparison.canopy.progress_cover_pct.toFixed(1)}%
        </p>
        {!trusted && (
          <p
            data-testid="delta-caveat"
            role="note"
            className="mt-2 rounded border border-amber-400/50 bg-amber-400/10 p-2 text-sm text-amber-200"
          >
            <span aria-hidden="true">! </span>
            Indicative only — the registration is{" "}
            {verdict.verdict === "not_trusted" ? "not trusted" : "below target"}.
            This figure is not suitable for a compliance filing.
          </p>
        )}
      </div>
    </Panel>
  );
}
