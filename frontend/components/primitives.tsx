/**
 * Shared presentational primitives.
 *
 * These exist so one rule is implemented ONCE. The rule is that a status in this
 * product is never signalled by colour alone, because an audit pack gets printed
 * in greyscale and a green dot on white paper carries no information. Every
 * status therefore carries a glyph AND a word.
 *
 * The cost of not extracting this: 6.2, 6.3, 6.7, 6.8 and 6.9 all need a status
 * row, and a rule re-implemented five times is a rule that is quietly broken in
 * four of them. ProvenancePanel had its own inline copy, which is what this
 * replaces.
 *
 * All colour pairs below were chosen for >= 7:1 contrast on the `surface`
 * background (#0B0F19) rather than the 4.5:1 minimum, per the WCAG 2.2 AAA
 * target in the S6 spec.
 */

import type { ReactNode } from "react";

/* -------------------------------------------------------------------------- */
/* Source badge                                                               */
/* -------------------------------------------------------------------------- */

/**
 * Live vs fixture. THE most important badge in the product.
 *
 * `●`/`◐` are decoration and are hidden from assistive tech; the word carries the
 * meaning, so a screen reader announces "Fixture" and not a glyph name.
 */
export function SourceBadge({
  source,
  testId = "source-badge",
}: {
  source: "live" | "fixture";
  testId?: string;
}) {
  return (
    <span
      data-testid={testId}
      data-source={source}
      className={
        source === "live"
          ? "inline-flex items-center gap-1 rounded border border-verified px-2 py-1 text-sm text-verified"
          : "inline-flex items-center gap-1 rounded border border-telemetry px-2 py-1 text-sm text-telemetry"
      }
    >
      <span aria-hidden="true">{source === "live" ? "●" : "◐"}</span>
      {source === "live" ? "Live" : "Fixture"}
    </span>
  );
}

/* -------------------------------------------------------------------------- */
/* Status pill                                                                */
/* -------------------------------------------------------------------------- */

export type StatusTone = "verified" | "quarantine" | "review" | "neutral";

const TONE_CLASS: Record<StatusTone, string> = {
  verified: "border-verified text-verified",
  quarantine: "border-quarantine text-quarantine",
  review: "border-amber-400 text-amber-300",
  neutral: "border-slate-500 text-slate-300",
};

export type StatusPresentation = {
  glyph: string;
  word: string;
  tone: StatusTone;
};

/**
 * The C2PA states, in one place.
 *
 * A string is deliberately not accepted as a tone: an unmapped status must fail
 * at review time, not render as an unstyled box that looks neutral when it is
 * actually an error.
 */
export const C2PA_PRESENTATION: Record<string, StatusPresentation> = {
  C2PA_VERIFIED: { glyph: "✔", word: "Content verified", tone: "verified" },
  C2PA_MUTATED: { glyph: "✖", word: "Content altered", tone: "quarantine" },
  C2PA_MISSING: { glyph: "—", word: "No manifest", tone: "neutral" },
};

export const UNKNOWN_C2PA: StatusPresentation = {
  glyph: "?",
  word: "Unrecognised manifest state",
  tone: "quarantine",
};

export function c2paPresentation(status: string): StatusPresentation {
  return C2PA_PRESENTATION[status] ?? UNKNOWN_C2PA;
}

/** Glyph + word. Never colour alone. */
export function StatusPill({
  status,
  testId,
}: {
  status: StatusPresentation;
  testId?: string;
}) {
  return (
    <span
      data-testid={testId}
      data-tone={status.tone}
      className={`inline-flex items-center gap-1 rounded border px-2 py-1 text-sm font-medium ${TONE_CLASS[status.tone]}`}
    >
      <span aria-hidden="true">{status.glyph}</span>
      <span className="sr-only">Status: </span>
      {status.word}
    </span>
  );
}

/* -------------------------------------------------------------------------- */
/* Figures                                                                    */
/* -------------------------------------------------------------------------- */

/**
 * A labelled measurement.
 *
 * `tabular-nums` is not cosmetic here: hashes and coordinates are read
 * character by character against a printed record, and proportional digits make
 * a transposed character hard to spot.
 */
export function Figure({
  label,
  value,
  title,
  mono = true,
  testId,
}: {
  label: string;
  value: ReactNode;
  title?: string;
  mono?: boolean;
  testId?: string;
}) {
  return (
    <div>
      <dt className="text-sm uppercase tracking-wide text-slate-400">{label}</dt>
      <dd
        data-testid={testId}
        title={title}
        className={`mt-1 break-all ${mono ? "font-mono tabular-nums" : "tabular-nums"}`}
      >
        {value}
      </dd>
    </div>
  );
}

/** Full SHA-256/SHA-1 is unreadable; show the ends and keep the whole in `title`. */
export function shortHash(hash: string, keep = 12): string {
  return hash.length <= keep * 2 + 1 ? hash : `${hash.slice(0, keep)}…${hash.slice(-8)}`;
}

/* -------------------------------------------------------------------------- */
/* Degradation notice                                                         */
/* -------------------------------------------------------------------------- */

/**
 * The banner that says why this data is not measured.
 *
 * `role="status"` so it is announced when it appears, which is the difference
 * between a screen-reader user knowing the numbers are synthetic and a
 * sighted-only user knowing.
 */
export function DegradationNotice({
  reason,
  testId = "degradation-notice",
}: {
  reason: string;
  testId?: string;
}) {
  return (
    <p
      data-testid={testId}
      role="status"
      className="mt-3 rounded border border-telemetry/40 bg-telemetry/10 p-3 text-sm text-slate-200"
    >
      <span aria-hidden="true">◐ </span>
      {reason}
    </p>
  );
}

/* -------------------------------------------------------------------------- */
/* Surfaces                                                                   */
/* -------------------------------------------------------------------------- */

export function Panel({
  id,
  title,
  actions,
  children,
  className = "",
  testId,
  dataSource,
}: {
  id: string;
  title: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  /** Set on the <section> itself, so the test hook and the ARIA landmark are
   *  the SAME element. A wrapper div carrying the hook while the landmark sits
   *  inside makes "is this labelled?" ambiguous to assert and easy to break. */
  testId?: string;
  /** "live" | "fixture", when the panel's contents have a known origin. Kept on
   *  the landmark so "what am I looking at?" is answerable from one node. */
  dataSource?: "live" | "fixture";
}) {
  return (
    <section
      data-testid={testId}
      data-source={dataSource}
      aria-labelledby={id}
      className={`rounded-lg border border-slate-700 bg-surface p-6 ${className}`}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id={id} className="text-lg font-semibold">
          {title}
        </h2>
        {actions}
      </div>
      {children}
    </section>
  );
}

/**
 * Minimum interactive target size.
 *
 * 44px is the S6 requirement. Sizing the hit area rather than the visual box is
 * what makes a small chip tappable without making it look oversized.
 */
export const TOUCH_TARGET = "min-h-11 min-w-11";
