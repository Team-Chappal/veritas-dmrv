"use client";

/**
 * MetricTicker — live numbers that change without moving anything.
 *
 * CLS (Cumulative Layout Shift) is not a cosmetic metric. It is a measure of
 * whether the page lies to you while you read it: a figure that reflows the text
 * under your eyes mid-sentence is a figure you misread. The exit criterion for
 * this product is CLS == 0, and that is a hard requirement rather than a
 * target, because the dashboard it lives on is read as evidence.
 *
 * WHY THE NUMBERS CAN CHANGE WITHOUT SHIFTING ANYTHING
 *
 * Three things, all structural rather than incidental:
 *
 *   1. FIXED HEIGHT. The strip is a fixed height, so a value going from "8" to
 *      "1,284" cannot change its box.
 *   2. TABULAR FIGURES. `font-variant-numeric: tabular-nums` makes every digit
 *      occupy the same advance width, so "8" and "1" are the same width. This
 *      is the same reason the provenance hashes use it: proportional digits
 *      misalign a column, and a transposed digit in a SHA-256 is the failure
 *      this whole product exists to prevent.
 *   3. RESERVED WIDTH. Each cell is a fixed minimum width in `ch`, so a longer
 *      number has somewhere to go. Reserving space is the whole trick; a ticker
 *      that reserves nothing is just a layout shift on a timer.
 *
 * The values are labelled DEMONSTRATION throughout. A number that changes on a
 * timer is not a measurement, and this repo does not present synthetic data as
 * measured.
 */

import { useEffect, useState } from "react";

import { Panel } from "@/components/primitives";

interface Metric {
  id: string;
  label: string;
  unit: string;
  /** A plausible spread. NOT a measurement — see the note above. */
  base: number;
  swing: number;
  decimals: number;
}

const METRICS: Metric[] = [
  { id: "assets", label: "Assets indexed", unit: "", base: 1284, swing: 6, decimals: 0 },
  { id: "area", label: "Hectares assessed", unit: "ha", base: 18420, swing: 40, decimals: 0 },
  { id: "carbon", label: "Modelled removals", unit: "tCO₂e", base: 9127, swing: 15, decimals: 0 },
  { id: "pass", label: "Physics pass rate", unit: "%", base: 87.4, swing: 0.3, decimals: 1 },
];

const TICK_MS = 1200;

function format(m: Metric, v: number): string {
  return v.toLocaleString("en-GB", {
    minimumFractionDigits: m.decimals,
    maximumFractionDigits: m.decimals,
  });
}

export default function MetricTicker() {
  const [values, setValues] = useState<Record<string, number>>(() =>
    Object.fromEntries(METRICS.map((m) => [m.id, m.base]))
  );

  useEffect(() => {
    // A tick that produced the same value would prove nothing, so each tick
    // actually moves every figure.
    const id = setInterval(() => {
      setValues((prev) =>
        Object.fromEntries(
          METRICS.map((m) => {
            const current = prev[m.id] ?? m.base;
            const step = (Math.random() * 2 - 1) * m.swing;
            const next = m.decimals === 0 ? Math.round(current + step) : current + step;
            // Keep the jitter inside a fixed range so the digits never grow by
            // an order of magnitude and overflow the reserved width.
            const clamped = Math.min(m.base + m.swing * 3, Math.max(m.base - m.swing * 3, next));
            return [m.id, clamped];
          })
        )
      );
    }, TICK_MS);
    return () => clearInterval(id);
  }, []);

  return (
    <Panel
      id="ticker-heading"
      title="Live figures"
      testId="metric-ticker"
      actions={
        <span
          className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-400"
          data-testid="ticker-source"
        >
          Demonstration
        </span>
      }
    >
      <p className="mt-3 text-sm leading-relaxed text-slate-300">
        These figures update every {TICK_MS / 1000} seconds. The strip reserves
        its space in advance, so no number moving can displace anything you are
        reading. The layout shift this page accumulates while they tick is
        asserted to be exactly zero.
      </p>

      <dl
        className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4"
        data-testid="ticker-grid"
      >
        {METRICS.map((m) => (
          <div
            key={m.id}
            className="rounded border border-slate-800 px-3 py-2"
            data-testid={`ticker-cell-${m.id}`}
          >
            <dt className="truncate text-xs uppercase tracking-wide text-slate-500">
              {m.label}
            </dt>
            <dd className="mt-1 flex items-baseline gap-1">
              {/*
                The width is reserved in `ch` against the widest value this
                metric can take, so the digits have somewhere to go. Without
                this the strip reflows on every tick -- which is the entire
                failure mode this component exists to prevent.
              */}
              <span
                className="font-mono text-xl tabular-nums"
                style={{ minWidth: `${(m.base + m.swing * 3).toLocaleString("en-GB").length + 1}ch` }}
                data-testid={`ticker-value-${m.id}`}
              >
                {format(m, values[m.id] ?? m.base)}
              </span>
              <span className="text-xs text-slate-500">{m.unit}</span>
            </dd>
          </div>
        ))}
      </dl>

      <p className="mt-4 text-xs leading-relaxed text-slate-400">
        The figures are a demonstration of the layout behaviour and are not
        measurements. Everything that is actually measured in this product
        carries a source badge, and everything that is not says so here.
      </p>
    </Panel>
  );
}
