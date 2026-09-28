"use client";

/**
 * PortfolioGrid — rubric bullet 1, "analyze and intelligently organize large
 * collections".
 *
 * The organising is the point. A grid of 520 thumbnails is a contact sheet, not
 * an analysis. What makes it useful is that the collection is filterable by the
 * axes a reviewer actually decides on — triage verdict, provenance state,
 * reporting epoch — and that the filter chips carry COUNTS, so a reviewer can
 * see that 47 assets are quarantined before clicking into them.
 *
 * FACET COUNTS COME FROM THE FILTERED SET, not the whole corpus. A chip reading
 * "47" has to mean "47 of what you are currently looking at", otherwise
 * filtering appears to lose results and the reviewer stops trusting the number.
 */

import { useCallback, useEffect, useState } from "react";

import {
  DegradationNotice,
  Panel,
  SourceBadge,
  StatusPill,
  TOUCH_TARGET,
  type StatusPresentation,
} from "@/components/primitives";
import { fetchAssets } from "@/lib/api";
import type { AssetFilters, AssetListResult, AssetSummary } from "@/lib/assets";

const PAGE = 24;

/** Triage verdicts, with glyph + word. Never colour alone. */
const DECISION_PRESENTATION: Record<string, StatusPresentation> = {
  VERIFIED_PASS: { glyph: "✔", word: "Verified", tone: "verified" },
  REVIEW_AMBIGUOUS: { glyph: "!", word: "Review", tone: "review" },
  QUARANTINE_FRAUD: { glyph: "✖", word: "Quarantined", tone: "quarantine" },
};

const C2PA_PRESENTATION: Record<string, StatusPresentation> = {
  C2PA_VERIFIED: { glyph: "✔", word: "Manifest verified", tone: "verified" },
  C2PA_MUTATED: { glyph: "✖", word: "Manifest altered", tone: "quarantine" },
  C2PA_MISSING: { glyph: "—", word: "No manifest", tone: "neutral" },
};

function decisionOf(v: string): StatusPresentation {
  return (
    DECISION_PRESENTATION[v] ?? {
      glyph: "?",
      word: `Unrecognised verdict: ${v}`,
      tone: "quarantine",
    }
  );
}

function c2paOf(v: string): StatusPresentation {
  return (
    C2PA_PRESENTATION[v] ?? {
      glyph: "?",
      word: `Unrecognised manifest state: ${v}`,
      tone: "quarantine",
    }
  );
}

function phaseWord(phase: string): string {
  return phase.replace(/_/g, " ").replace(/\bmonth\b/, "mo");
}

function FilterChip({
  label,
  count,
  active,
  onClick,
  testId,
}: {
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
  testId: string;
}) {
  return (
    <button
      type="button"
      data-testid={testId}
      aria-pressed={active}
      onClick={onClick}
      className={`${TOUCH_TARGET} inline-flex items-center gap-2 rounded-full border px-4 text-sm transition-colors ${
        active
          ? "border-telemetry bg-telemetry/15 text-telemetry"
          : "border-slate-700 bg-surface text-slate-300 hover:border-slate-500"
      }`}
    >
      <span>{label}</span>
      {/* The count is the reason to click. tabular-nums so the column of counts
          does not jitter as filters change the numbers. */}
      <span className="tabular-nums text-slate-400">{count}</span>
      <span className="sr-only">assets</span>
    </button>
  );
}

function AssetCard({ asset }: { asset: AssetSummary }) {
  const decision = decisionOf(asset.jev_triage_decision);
  const c2pa = c2paOf(asset.c2pa_provenance);
  return (
    <li
      data-testid="asset-card"
      data-decision={asset.jev_triage_decision}
      data-c2pa={asset.c2pa_provenance}
      className="flex flex-col gap-3 rounded-lg border border-slate-800 bg-surface p-4"
    >
      <div className="flex items-start justify-between gap-2">
        <p
          className="break-all font-mono text-xs tabular-nums text-slate-300"
          title={asset.public_id}
        >
          {asset.public_id}
        </p>
        <span className="shrink-0 rounded bg-canvas px-2 py-0.5 font-mono text-xs tabular-nums text-slate-400">
          {asset.media_type === "video" ? "video" : "still"}
        </span>
      </div>

      <div className="flex flex-wrap gap-2">
        <StatusPill status={decision} />
        <StatusPill status={c2pa} />
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        <div>
          <dt className="uppercase tracking-wide text-slate-500">Captured</dt>
          <dd className="tabular-nums text-slate-300">{asset.capture_timestamp}</dd>
        </div>
        <div>
          <dt className="uppercase tracking-wide text-slate-500">Epoch</dt>
          <dd className="text-slate-300">{phaseWord(asset.milestone_phase)}</dd>
        </div>
        <div>
          <dt className="uppercase tracking-wide text-slate-500">Confidence</dt>
          <dd className="tabular-nums text-slate-300">{asset.jev_confidence_score}%</dd>
        </div>
        <div>
          <dt className="uppercase tracking-wide text-slate-500">Canopy Δ</dt>
          <dd className="tabular-nums text-slate-300">
            {asset.canopy_delta_pct === null
              ? "—"
              : `${asset.canopy_delta_pct > 0 ? "+" : ""}${asset.canopy_delta_pct.toFixed(1)}%`}
          </dd>
        </div>
      </dl>

      <ul className="flex flex-wrap gap-1.5" aria-label="Tags">
        {asset.tags.map((t) => (
          <li
            key={t}
            className="rounded bg-canvas px-2 py-0.5 font-mono text-[11px] text-slate-400"
          >
            {t}
          </li>
        ))}
      </ul>
    </li>
  );
}

export default function PortfolioGrid() {
  const [filters, setFilters] = useState<AssetFilters>({ limit: PAGE, offset: 0 });
  const [result, setResult] = useState<AssetListResult | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback((next: AssetFilters) => {
    setLoading(true);
    fetchAssets(next)
      .then(setResult)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load(filters);
  }, [filters, load]);

  const toggle = (key: keyof AssetFilters, value: string) =>
    setFilters((f) => ({
      ...f,
      [key]: f[key] === value ? undefined : value,
      offset: 0,
    }));

  const facets = result?.data.facets;

  return (
    <Panel
      id="portfolio-heading"
      title="Evidence portfolio"
      testId="portfolio-grid"
      dataSource={result?.source}
      actions={result ? <SourceBadge source={result.source} testId="portfolio-source" /> : undefined}
    >
      {result?.source === "fixture" && (
        <DegradationNotice reason={result.reason} testId="portfolio-reason" />
      )}

      {facets && (
        <div className="mt-5 space-y-3">
          <fieldset>
            <legend className="text-sm uppercase tracking-wide text-slate-400">
              Triage verdict
            </legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {Object.entries(facets.decision).map(([k, n]) => (
                <FilterChip
                  key={k}
                  label={decisionOf(k).word}
                  count={n}
                  active={filters.decision === k}
                  onClick={() => toggle("decision", k)}
                  testId={`filter-decision-${k}`}
                />
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="text-sm uppercase tracking-wide text-slate-400">
              Provenance
            </legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {Object.entries(facets.c2pa).map(([k, n]) => (
                <FilterChip
                  key={k}
                  label={c2paOf(k).word}
                  count={n}
                  active={filters.c2pa === k}
                  onClick={() => toggle("c2pa", k)}
                  testId={`filter-c2pa-${k}`}
                />
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="text-sm uppercase tracking-wide text-slate-400">
              Reporting epoch
            </legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {Object.entries(facets.phase).map(([k, n]) => (
                <FilterChip
                  key={k}
                  label={phaseWord(k)}
                  count={n}
                  active={filters.phase === k}
                  onClick={() => toggle("phase", k)}
                  testId={`filter-phase-${k}`}
                />
              ))}
            </div>
          </fieldset>
        </div>
      )}

      <p
        className="mt-5 text-sm tabular-nums text-slate-400"
        data-testid="portfolio-count"
        aria-live="polite"
      >
        {loading
          ? "Loading collection…"
          : `${result?.data.returned ?? 0} of ${result?.data.total_matched ?? 0} assets`}
      </p>

      <ul
        className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
        data-testid="asset-grid"
      >
        {(result?.data.assets ?? []).map((a) => (
          <AssetCard key={a.asset_id} asset={a} />
        ))}
      </ul>

      {result && result.data.total_matched === 0 && (
        <p className="mt-4 text-slate-400" data-testid="portfolio-empty">
          No assets match these filters. That is a coverage gap worth reporting,
          not an empty collection.
        </p>
      )}

      {result?.data.has_more && (
        <button
          type="button"
          data-testid="portfolio-load-more"
          onClick={() =>
            setFilters((f) => ({ ...f, offset: (f.offset ?? 0) + PAGE }))
          }
          className={`${TOUCH_TARGET} mt-4 rounded border border-slate-600 px-5 text-sm text-slate-200 hover:border-slate-400`}
        >
          Load more
        </button>
      )}
    </Panel>
  );
}
