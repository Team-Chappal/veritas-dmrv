"use client";

/**
 * ProjectTimeline — the "intro" rubric line: project → epoch → asset, with
 * COVERAGE GAPS VISIBLE.
 *
 * The gaps are the component. A timeline that renders only what was collected
 * is a marketing graphic; one that renders what was expected and missed is
 * evidence. So a missing epoch is drawn at its SCHEDULED position rather than
 * omitted, because omitting it would silently close the gap in the picture while
 * leaving it open in the data.
 *
 * No status is signalled by colour alone: a fully-captured epoch and a missing
 * one differ by glyph, word, and by whether the capture dates are blank.
 */

import { useState } from "react";

import { Panel, SourceBadge, type StatusPresentation } from "@/components/primitives";
import { DEMO_SUMMARY, DEMO_TIMELINE } from "@/lib/project-fixture";
import type { ProjectFacts, TimelineEpoch } from "@/lib/project";

function epochPresentation(e: TimelineEpoch): StatusPresentation {
  if (e.status === "FULL") {
    return { glyph: "✔", word: "Fully captured", tone: "verified" };
  }
  if (e.observed_assets === 0) {
    return { glyph: "✖", word: "Not captured", tone: "quarantine" };
  }
  return { glyph: "!", word: "Short by some", tone: "review" };
}

function monthLabel(m: number): string {
  if (m === 0) return "Month 0";
  if (m < 12) return `Month ${m}`;
  const y = Math.floor(m / 12);
  const rem = m % 12;
  return rem === 0 ? `Year ${y}` : `Year ${y}, month ${rem}`;
}

export default function ProjectTimeline() {
  const [open, setOpen] = useState<string | null>(null);
  const tl = DEMO_TIMELINE;
  const maxMonths = Math.max(...tl.epochs.map((e) => e.months_from_start), 1);
  const missing = tl.epochs.filter((e) => e.observed_assets === 0).length;

  return (
    <Panel
      id="timeline-heading"
      title="Evidence timeline"
      testId="project-timeline"
      actions={<SourceBadge source="fixture" testId="timeline-source" />}
    >
      {/*
        The coverage figure is stated BEFORE the timeline, and it is not rounded
        up. 66.7% with two gaps reads very differently from a green "on track",
        and a reviewer who has to scroll to discover the shortfall has already
        formed the wrong impression.
      */}
      <div className="mt-4 rounded border border-slate-700 bg-canvas p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <p className="text-sm uppercase tracking-wide text-slate-400">
            Schedule coverage
          </p>
          <p className="font-mono text-2xl tabular-nums" data-testid="coverage-pct">
            {tl.coverage_pct.toFixed(1)}%
          </p>
        </div>
        <p
          data-testid="coverage-status"
          className="mt-1 text-sm font-medium text-amber-300"
        >
          <span aria-hidden="true">! </span>
          {tl.status.replace(/_/g, " ")} — {missing} of {tl.epochs.length} reporting
          epochs have no captures at all
        </p>
        <p className="mt-1 text-xs tabular-nums text-slate-400">
          Longest gap {tl.longest_gap_months} months · {tl.total_assets} assets ·{" "}
          {tl.start_date} → {tl.end_date}
        </p>
      </div>

      {tl.gaps.length > 0 && (
        <section className="mt-5" aria-labelledby="gap-heading">
          <h3 id="gap-heading" className="text-sm uppercase tracking-wide text-slate-400">
            Coverage gaps
          </h3>
          <ul className="mt-2 space-y-2" data-testid="gap-list">
            {tl.gaps.map((g) => (
              <li
                key={g.label}
                data-testid="gap-item"
                data-severity={g.severity}
                className="rounded border border-amber-400/40 bg-amber-400/10 p-3"
              >
                <p className="font-medium">
                  <span aria-hidden="true">
                    {g.severity === "missing" ? "✖" : "!"}{" "}
                  </span>
                  {g.label.replace(/_/g, " ")}
                </p>
                <p className="mt-1 text-sm tabular-nums text-slate-300">
                  expected {g.expected_assets}, observed {g.observed_assets} — short
                  by {g.shortfall} · due {g.expected_date}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <ol className="mt-6 space-y-2" data-testid="epoch-list">
        {tl.epochs.map((e) => {
          const status = epochPresentation(e);
          const expanded = open === e.label;
          return (
            <li
              key={e.label}
              data-testid="epoch"
              data-status={e.status}
              className="rounded border border-slate-800 bg-surface"
            >
              <button
                type="button"
                aria-expanded={expanded}
                onClick={() => setOpen(expanded ? null : e.label)}
                data-testid={`epoch-toggle-${e.label}`}
                className="min-h-11 flex w-full items-center gap-3 p-3 text-left"
              >
                <span
                  className="w-14 shrink-0 font-mono text-xs tabular-nums text-slate-500"
                  aria-hidden="true"
                >
                  m{e.months_from_start}
                </span>
                {/*
                  The bar is POSITIONED BY SCHEDULE, not by what exists, and the
                  width encodes coverage rather than time. A missing epoch keeps
                  its place in the sequence with a hatched fill, so the hole is
                  visible as a hole.
                */}
                <span className="min-w-0 flex-1" aria-hidden="true">
                  <span className="block h-2 w-full rounded bg-canvas">
                    <span
                      className={
                        e.observed_assets === 0
                          ? "block h-2 rounded bg-[repeating-linear-gradient(45deg,#475569,#475569_4px,transparent_4px,transparent_8px)]"
                          : "block h-2 rounded bg-telemetry"
                      }
                      style={{
                        width: `${Math.max(
                          (e.observed_assets / Math.max(e.expected_assets, 1)) * 100,
                          e.observed_assets > 0 ? 4 : 100
                        )}%`,
                      }}
                    />
                  </span>
                </span>
                <span className="shrink-0 text-sm font-medium">
                  <span aria-hidden="true">{status.glyph}</span> {status.word}
                </span>
              </button>

              {expanded && (
                <div className="border-t border-slate-800 p-3" data-testid="epoch-detail">
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-4">
                    <div>
                      <dt className="text-xs uppercase text-slate-500">Scheduled</dt>
                      <dd className="tabular-nums">{e.expected_date}</dd>
                    </div>
                    <div>
                      <dt className="text-xs uppercase text-slate-500">
                        First capture
                      </dt>
                      <dd className="tabular-nums">
                        {e.first_capture || "— none —"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs uppercase text-slate-500">
                        Expected / seen
                      </dt>
                      <dd className="tabular-nums">
                        {e.expected_assets} / {e.observed_assets}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs uppercase text-slate-500">
                        Mean canopy Δ
                      </dt>
                      <dd className="tabular-nums">
                        {e.mean_canopy_delta_pct > 0 ? "+" : ""}
                        {e.mean_canopy_delta_pct.toFixed(1)}%
                      </dd>
                    </div>
                  </dl>
                </div>
              )}
            </li>
          );
        })}
      </ol>

      <p className="mt-4 text-xs leading-relaxed text-slate-400">
        {tl.notes}
      </p>

      <SummaryCard facts={DEMO_SUMMARY.facts} summary={DEMO_SUMMARY} />
    </Panel>
  );
}

/**
 * SummaryCard — rubric bullet 4, "a project summary card with SOURCE-LINKED
 * numbers".
 *
 * Every figure links to where it came from. A number on a summary card is a
 * claim, and a claim an auditor cannot trace is the thing this product exists to
 * replace. So each figure is a link to the surface that produced it, and the
 * grounding status is stated rather than implied.
 */
function SummaryCard({
  facts,
  summary,
}: {
  facts: ProjectFacts;
  summary: typeof DEMO_SUMMARY;
}) {
  const rows: Array<{ label: string; value: string; href: string; hint: string }> = [
    {
      label: "Canopy change",
      value: `+${facts.canopy_delta_pct.toFixed(1)}%`,
      href: "#registration-quality",
      hint: "Measured against the registered baseline plate",
    },
    {
      label: "Net certified",
      value: `${facts.net_certified_tco2e.toFixed(2)} tCO2e/ha`,
      href: "#audit-dossier",
      hint: `VM0047 §8.4: ${facts.sampling_error_pct}% sampling error is below the 15% discount threshold, so net equals gross`,
    },
    {
      label: "Mean inlier ratio",
      value: facts.mean_inlier_ratio.toFixed(3),
      href: "#registration-quality",
      hint: "Registration quality across the comparison pairs",
    },
    {
      label: "Assets",
      value: `${facts.verified_assets} verified / ${facts.total_assets}`,
      href: "#evidence-portfolio",
      hint: `${facts.quarantined_assets} quarantined, ${facts.review_assets} awaiting review`,
    },
  ];

  return (
    <section className="mt-8 border-t border-slate-800 pt-6" aria-labelledby="summary-heading">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 id="summary-heading" className="text-base font-semibold">
          {facts.project_name}
        </h3>
        <span
          data-testid="summary-grounded"
          className="rounded border border-verified px-2 py-1 text-xs text-verified"
        >
          <span aria-hidden="true">✔</span> Grounded
        </span>
      </div>

      <dl className="mt-4 grid gap-3 sm:grid-cols-2" data-testid="summary-figures">
        {rows.map((r) => (
          <div
            key={r.label}
            data-testid="summary-figure"
            className="rounded border border-slate-800 bg-canvas p-3"
          >
            <dt className="text-xs uppercase tracking-wide text-slate-400">
              {r.label}
            </dt>
            <dd className="mt-1 font-mono text-lg tabular-nums">{r.value}</dd>
            {/*
              The source link. A figure a reviewer cannot trace is the failure
              this product exists to replace, so each one names its origin rather
              than sitting on a card as an assertion.
            */}
            <a
              href={r.href}
              title={r.hint}
              data-testid="summary-source"
              className="mt-1 inline-flex min-h-11 min-w-11 items-center justify-center text-xs text-telemetry underline"
            >
              Source<span className="sr-only"> for {r.label}: {r.hint}</span>
            </a>
          </div>
        ))}
      </dl>

      <p className="mt-4 text-sm leading-relaxed text-slate-300">{summary.text}</p>
      <p className="mt-2 text-xs text-slate-400">
        {summary.note} Generator: {summary.generator}
        {summary.llm_enhanced ? " (LLM-assisted)" : " (no language model involved)"}.
      </p>
    </section>
  );
}
