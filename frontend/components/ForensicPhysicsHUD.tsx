"use client";

/**
 * ForensicPhysicsHUD — the shadow-coherence check, drawn.
 *
 * Shadow coherence is the one verification in this product that is a PHYSICS
 * argument rather than a model: given a latitude, a longitude and a claimed
 * timestamp, the sun is in a known place, so a shadow in the image points in a
 * known direction. A large disagreement means the timestamp or the light was
 * altered, and either is disqualifying.
 *
 * TWO THINGS THE DRAWDING REFUSES TO DO
 *
 * 1. Accuse when it cannot tell. Below about 12 degrees of solar elevation the
 *    shadow's direction is dominated by the object and the slope, so the
 *    comparison is WITHHELD and the panel says "cannot be determined". A tool
 *    that only says pass or fail invites the reading that it is accusing.
 * 2. Hide the margin. The badge says "inside tolerance" and the number says by
 *    how much, because "consistent" and "consistent with 1 degree to spare" are
 *    different claims.
 *
 * The SVG is drawn to a fixed 200x200 viewBox and scaled by CSS, so it is
 * resolution-independent and occupies reserved space before anything paints --
 * which is what keeps the CLS at zero.
 */

import { useState } from "react";

import { Panel, SourceBadge, type StatusPresentation } from "@/components/primitives";
import {
  DEMO_CASES,
  decide,
  type PhysicsCase,
  type SolarVerdict,
} from "@/lib/physics";

const SIZE = 200;
const CX = SIZE / 2;
const CY = SIZE / 2;
const R = 74;

/** Compass bearing (deg clockwise from north) to SVG point. North is -Y. */
function point(bearingDeg: number, radius = R): { x: number; y: number } {
  const rad = (bearingDeg * Math.PI) / 180;
  return { x: CX + radius * Math.sin(rad), y: CY - radius * Math.cos(rad) };
}

function presentation(v: SolarVerdict): StatusPresentation {
  switch (v) {
    case "PHYSICS_PASS":
      return { glyph: "✔", word: "Physically consistent", tone: "verified" };
    case "QUARANTINE_SOLAR_MISMATCH":
      return { glyph: "✖", word: "Shadow inconsistent", tone: "quarantine" };
    case "QUARANTINE_NIGHTTIME_CAPTURE_ANOMALY":
      return { glyph: "✖", word: "Sun below horizon", tone: "quarantine" };
    case "REVIEW_LOW_SUN_UNDETERMINED":
      return { glyph: "?", word: "Cannot be determined", tone: "review" };
    default:
      return { glyph: "?", word: `Unrecognised verdict: ${v}`, tone: "quarantine" };
  }
}

function Compass({
  active,
  c,
}: {
  active: boolean;
  /** The case to draw. Passed explicitly: a module-level mutable ref set
   *  during render happens to work only because of render ordering, which is
   *  not a property anyone should depend on. */
  c: PhysicsCase;
}) {
  return (
    <svg
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      className="h-56 w-56"
      role="img"
      aria-label={
        active
          ? "Compass showing the calculated sun direction, the expected shadow direction and the observed shadow direction"
          : "Compass with no shadow comparison available"
      }
      data-testid="hud-compass"
    >
      <circle cx={CX} cy={CY} r={R} fill="#030712" stroke="#334155" strokeWidth="1.5" />

      {/* Cardinal ticks and labels. */}
      {[
        { deg: 0, label: "N" },
        { deg: 90, label: "E" },
        { deg: 180, label: "S" },
        { deg: 270, label: "W" },
      ].map(({ deg, label }) => {
        const p = point(deg, R);
        const mid = point(deg, R - 12);
        return (
          <g key={deg}>
            <line x1={CX} y1={CY} x2={p.x} y2={p.y} stroke="#1e293b" strokeWidth="1" />
            <text
              x={mid.x}
              y={mid.y}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize="10"
              fontFamily="monospace"
              fill={label === "N" ? "#94a3b8" : "#475569"}
            >
              {label}
            </text>
          </g>
        );
      })}

      {active && <Arrows c={c} />}
    </svg>
  );
}

/** The three rays. Drawn only when a comparison is actually available. */
function Arrows({ c }: { c: PhysicsCase }) {
  const sun = point(c.sun_azimuth_deg, R - 8);
  const exp = point(c.expected_shadow_azimuth_deg, R - 22);
  const obs =
    c.observed_shadow_azimuth_deg === null
      ? null
      : point(c.observed_shadow_azimuth_deg, R - 34);
  const errorArc =
    c.observed_shadow_azimuth_deg === null
      ? null
      : angularPath(c.expected_shadow_azimuth_deg, c.observed_shadow_azimuth_deg, R - 28);

  return (
    <g>
      {/* Sun: a filled disc, because it is the light source, not a bearing. */}
      <circle cx={sun.x} cy={sun.y} r="7" fill="#fbbf24" data-testid="hud-sun" />

      {/* Expected shadow. */}
      <line
        x1={CX}
        y1={CY}
        x2={exp.x}
        y2={exp.y}
        stroke="#38bdf8"
        strokeWidth="2"
        strokeDasharray="5 3"
        data-testid="hud-expected"
      />

      {obs && (
        <>
          {/* Observed shadow. */}
          <line
            x1={CX}
            y1={CY}
            x2={obs.x}
            y2={obs.y}
            stroke={c.angular_error_deg !== null && c.angular_error_deg > c.tolerance_deg
              ? "#ef4444"
              : "#10b981"}
            strokeWidth="2.5"
            data-testid="hud-observed"
          />
          {errorArc && (
            <path d={errorArc} fill="none" stroke="#f59e0b" strokeWidth="3" data-testid="hud-error-arc" />
          )}
        </>
      )}
      <circle cx={CX} cy={CY} r="3" fill="#94a3b8" />
    </g>
  );
}

function angularPath(a: number, b: number, radius: number): string {
  const sweep = ((b - a + 540) % 360) - 180;
  const start = point(a, radius);
  const end = point(b, radius);
  const large = Math.abs(sweep) > 180 ? 1 : 0;
  // Compass bearings increase clockwise, which is the opposite of SVG's default.
  return `M ${start.x.toFixed(2)} ${start.y.toFixed(2)} A ${radius} ${radius} 0 ${large} 0 ${end.x.toFixed(2)} ${end.y.toFixed(2)}`;
}

export default function ForensicPhysicsHUD() {
  const [selected, setSelected] = useState(DEMO_CASES[0].id);
  const c = DEMO_CASES.find((x) => x.id === selected) ?? DEMO_CASES[0];

  // The verdict is COMPUTED, not read from the fixture, so a fixture that
  // disagreed with its own numbers would be visible rather than authoritative.
  const decided = decide(c);
  // Use the error `decide` produced, or null. There is deliberately NO
  // fallback that recomputes it: a `??` clause here re-derived the very figure
  // the abstention exists to withhold, so the panel printed "3.4 degrees" on a
  // capture it had just said it could not measure. The component contradicted
  // its own stated principle, and a spec caught it.
  const error = decided.error;
  const status = presentation(decided.verdict);
  const determinable = decided.verdict === "PHYSICS_PASS" || decided.verdict === "QUARANTINE_SOLAR_MISMATCH";
  const shown = { ...c, angular_error_deg: error };

  return (
    <Panel
      id="physics-heading"
      title="Shadow coherence"
      testId="physics-hud"
      actions={<SourceBadge source="fixture" testId="physics-source" />}
    >
      <p className="mt-3 text-sm leading-relaxed text-slate-300">
        Given a location and a claimed time, the sun is in a known place, so a
        shadow must point in a known direction. A large disagreement means the
        timestamp or the light was altered.
      </p>

      <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Capture to inspect">
        {DEMO_CASES.map((x) => (
          <button
            key={x.id}
            type="button"
            onClick={() => setSelected(x.id)}
            aria-pressed={selected === x.id}
            data-testid={`physics-case-${x.id}`}
            className={`min-h-11 rounded-full border px-4 text-sm ${
              selected === x.id
                ? "border-telemetry bg-telemetry/15 text-telemetry"
                : "border-slate-700 text-slate-300 hover:border-slate-500"
            }`}
          >
            {x.label}
          </button>
        ))}
      </div>

      <div className="mt-5 flex flex-wrap items-start gap-6">
        <div className="shrink-0">
          <Compass active={determinable} c={shown} />
        </div>

        <div className="min-w-0 flex-1">
          <p
            data-testid="physics-verdict"
            className={`inline-flex items-center gap-2 rounded border px-3 py-1.5 text-sm font-medium ${
              status.tone === "verified"
                ? "border-verified text-verified"
                : status.tone === "quarantine"
                  ? "border-quarantine text-quarantine"
                  : "border-amber-400 text-amber-300"
            }`}
          >
            <span aria-hidden="true">{status.glyph}</span> {status.word}
          </p>

          <p className="mt-3 text-sm leading-relaxed text-slate-300" data-testid="physics-meaning">
            {c.meaning}
          </p>

          <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-500">Sun azimuth</dt>
              <dd className="font-mono tabular-nums">{c.sun_azimuth_deg.toFixed(2)}°</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-500">Sun elevation</dt>
              <dd className="font-mono tabular-nums">{c.sun_elevation_deg.toFixed(2)}°</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-500">
                Expected shadow
              </dt>
              <dd className="font-mono tabular-nums">
                {c.expected_shadow_azimuth_deg.toFixed(2)}°
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-500">Observed shadow</dt>
              <dd className="font-mono tabular-nums">
                {c.observed_shadow_azimuth_deg === null
                  ? "—"
                  : `${c.observed_shadow_azimuth_deg.toFixed(2)}°`}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-500">Error</dt>
              <dd className="font-mono tabular-nums" data-testid="physics-error">
                {error === null ? "— withheld —" : `${error.toFixed(1)}°`}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-500">Tolerance</dt>
              <dd className="font-mono tabular-nums">±{c.tolerance_deg}°</dd>
            </div>
          </dl>

          {error !== null && (
            <p className="mt-3 text-sm text-slate-300" data-testid="physics-margin">
              {error <= c.tolerance_deg
                ? `Inside tolerance, with ${(c.tolerance_deg - error).toFixed(1)}° to spare.`
                : `Outside tolerance by ${(error - c.tolerance_deg).toFixed(1)}°.`}
            </p>
          )}

          {error === null && (
            <p
              data-testid="physics-withheld"
              className="mt-3 rounded border border-amber-400/50 bg-amber-400/10 p-3 text-sm text-amber-200"
            >
              <span aria-hidden="true">? </span>
              The comparison is withheld because it would not be evidence. No
              error figure is shown, because there is no error to show.
            </p>
          )}
        </div>
      </div>

      <p className="mt-4 text-xs leading-relaxed text-slate-400">
        Positions are computed with pvlib from the stated coordinates and time,
        and the expected shadow bearing is the sun bearing plus 180°. The verdict
        badge is recomputed in the browser from the same rule the backend uses, so
        a fixture that disagreed with its own numbers would be visible rather
        than authoritative.
      </p>
    </Panel>
  );
}
