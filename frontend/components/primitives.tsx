/**
 * Shared presentational primitives.
 *
 * These exist so one rule is implemented ONCE. The rule is that a status in this
 * product is never signalled by colour alone, because an audit pack gets printed
 * in greyscale and a green dot on white paper carries no information. Every
 * status therefore carries a glyph AND a word.
 *
 * All colour pairs below are chosen for >= 7:1 contrast on both the light surface
 * (#FFFFFF) and dark surface (#0B0F19), exceeding the WCAG 2.2 AAA target.
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
          ? "inline-flex items-center gap-1.5 rounded-full border border-emerald-500 bg-emerald-50/80 px-2.5 py-1 text-xs font-semibold uppercase tracking-wider text-emerald-800 dark:border-verified dark:bg-verified/10 dark:text-verified"
          : "inline-flex items-center gap-1.5 rounded-full border border-sky-500 bg-sky-50/80 px-2.5 py-1 text-xs font-semibold uppercase tracking-wider text-sky-800 dark:border-telemetry dark:bg-telemetry/10 dark:text-telemetry"
      }
    >
      <span aria-hidden="true" className="text-[10px]">{source === "live" ? "●" : "◐"}</span>
      {source === "live" ? "Live" : "Fixture"}
    </span>
  );
}

/* -------------------------------------------------------------------------- */
/* Status pill                                                                */
/* -------------------------------------------------------------------------- */

export type StatusTone = "verified" | "quarantine" | "review" | "neutral";

const TONE_CLASS: Record<StatusTone, string> = {
  verified: "border-emerald-500 bg-emerald-50 text-emerald-800 dark:border-verified dark:bg-verified/10 dark:text-verified",
  quarantine: "border-rose-500 bg-rose-50 text-rose-800 dark:border-quarantine dark:bg-quarantine/10 dark:text-quarantine",
  review: "border-amber-500 bg-amber-50 text-amber-800 dark:border-amber-400 dark:bg-amber-400/10 dark:text-amber-300",
  neutral: "border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-300",
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
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-wider ${TONE_CLASS[status.tone]}`}
    >
      <span aria-hidden="true" className="font-bold">{status.glyph}</span>
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
      <dt className="text-xs font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400 font-semibold">{label}</dt>
      <dd
        data-testid={testId}
        title={title}
        className={`mt-1 break-all text-slate-900 dark:text-slate-100 font-semibold ${mono ? "font-mono tabular-nums" : "tabular-nums"}`}
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
      className="mt-4 rounded-xl border border-sky-300 bg-sky-50/80 p-3.5 text-xs sm:text-sm text-sky-950 dark:border-telemetry/40 dark:bg-telemetry/10 dark:text-slate-200 flex items-start gap-2 shadow-sm"
    >
      <span aria-hidden="true" className="font-bold text-sky-600 dark:text-telemetry">◐</span>
      <span>{reason}</span>
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
  dataQuery,
  dataResultQuery,
}: {
  id: string;
  title: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  testId?: string;
  dataSource?: "live" | "fixture";
  dataQuery?: string;
  dataResultQuery?: string;
}) {
  return (
    <section
      data-testid={testId}
      data-source={dataSource}
      data-query={dataQuery}
      data-result-query={dataResultQuery}
      aria-labelledby={id}
      className={`rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white/95 dark:bg-surface/95 shadow-sm p-6 sm:p-8 transition-all duration-200 ${className}`}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-3 border-b border-slate-100 dark:border-slate-800/80 pb-4 mb-5">
        <h2 id={id} className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
          {title}
        </h2>
        {actions}
      </div>
      {children}
    </section>
  );
}

export const TOUCH_TARGET = "min-h-11 min-w-11";
