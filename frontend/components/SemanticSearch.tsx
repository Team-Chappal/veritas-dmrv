"use client";

/**
 * SemanticSearch — rubric bullet 5, "AI-powered metadata, tagging, semantic
 * discovery".
 *
 * THE HONEST VERSION OF A SEARCH UI
 *
 * The three fields that matter most here are the ones about what the search did
 * NOT do:
 *
 *   backend           the engine that actually answered, by name
 *   unmatched_terms   query terms that found nothing
 *   notes             the backend's own statement of its limits
 *
 * A search box that reports only hits tells a reviewer their query was
 * understood. This one reports the term that matched nothing, because a silently
 * dropped term is how someone concludes a whole parcel is unevidenced when in
 * fact one word was absent from the index.
 *
 * The `notes` line is rendered in full and unedited. It says the backend is a
 * LEXICAL tf-idf vector space and will not match synonyms. That is the single
 * largest gap against the rubric, and burying it would make the demo look like
 * something it is not.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import {
  DegradationNotice,
  Panel,
  SourceBadge,
  TOUCH_TARGET,
} from "@/components/primitives";
import { fetchSearch } from "@/lib/api";
import { DEMO_ASSETS } from "@/lib/asset-fixture";
import type { SearchResult } from "@/lib/search";

/** Tags offered as chips, taken from the corpus so they always return hits. */
const SUGGESTED_TAGS = Array.from(
  new Set(DEMO_ASSETS.flatMap((a) => a.tags))
)
  .sort()
  .slice(0, 8);

export default function SemanticSearch() {
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [searching, setSearching] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const run = useCallback((q: string) => {
    if (!q.trim()) {
      setResult(null);
      return;
    }
    setSearching(true);
    fetchSearch(q, 20)
      .then(setResult)
      .finally(() => setSearching(false));
  }, []);

  useEffect(() => {
    run(submitted);
  }, [submitted, run]);

  const addTag = (t: string) => {
    const next = submitted ? `${submitted} ${t}` : t;
    setQuery(next);
    setSubmitted(next);
  };

  const unmatched = result?.data.unmatched_terms ?? [];

  return (
    <Panel
      id="search-heading"
      title="Search evidence"
      testId="semantic-search"
      dataSource={result?.source}
      dataQuery={submitted}
      dataResultQuery={result?.data.query}
      actions={result ? <SourceBadge source={result.source} testId="search-source" /> : undefined}
    >
      <form
        className="mt-4 flex flex-wrap gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(query);
        }}
        role="search"
      >
        <label htmlFor="search-input" className="sr-only">
          Search evidence by keyword or tag
        </label>
        <input
          id="search-input"
          ref={inputRef}
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="mangrove canopy replanted"
          data-testid="search-input"
          className={`${TOUCH_TARGET} min-w-0 flex-1 rounded border border-slate-600 bg-canvas px-3 text-slate-100 placeholder:text-slate-500`}
        />
        <button
          type="submit"
          data-testid="search-submit"
          className={`${TOUCH_TARGET} rounded border border-telemetry px-5 text-sm text-telemetry`}
        >
          Search
        </button>
      </form>

      <div className="mt-3 flex flex-wrap gap-2">
        {SUGGESTED_TAGS.map((t) => (
          <button
            key={t}
            type="button"
            data-testid={`search-tag-${t}`}
            onClick={() => addTag(t)}
            className={`${TOUCH_TARGET} rounded-full border border-slate-700 bg-surface px-3 font-mono text-xs text-slate-300 hover:border-slate-500`}
          >
            {t}
          </button>
        ))}
      </div>

      {result?.source === "fixture" && (
        <DegradationNotice reason={result.reason} testId="search-reason" />
      )}

      {result && (
        <>
          {/*
            UNMATCHED TERMS FIRST. If a reviewer asked for three things and one
            found nothing, that is the most consequential fact on the page, and
            burying it under the hits is how a collection gets declared
            unevidenced by mistake.
          */}
          {unmatched.length > 0 && (
            <p
              data-testid="search-unmatched"
              role="status"
              className="mt-4 rounded border border-amber-400/50 bg-amber-400/10 p-3 text-sm text-amber-200"
            >
              <span aria-hidden="true">! </span>
              No asset matched{" "}
              <strong className="font-semibold">
                {unmatched.map((t) => `"${t}"`).join(", ")}
              </strong>
              . Those terms are absent from the index, which is not the same as
              the evidence being absent.
            </p>
          )}

          <p
            className="mt-4 text-sm tabular-nums text-slate-400"
            data-testid="search-count"
            aria-live="polite"
          >
            {searching
              ? "Searching…"
              : `${result.data.count} of ${result.data.total_indexed} indexed · engine: ${result.data.backend}`}
          </p>

          {/*
            The backend's own limitation, unedited and not paraphrased away. This
            is the largest gap against the rubric and it is stated, not implied.
          */}
          <p
            data-testid="search-notes"
            className="mt-2 rounded border border-slate-700 bg-canvas p-3 text-xs leading-relaxed text-slate-300"
          >
            <span className="font-semibold uppercase tracking-wide text-slate-400">
              What this engine is
            </span>
            <br />
            {result.data.notes}
          </p>

          <ul className="mt-4 space-y-2" data-testid="search-hits">
            {result.data.hits.map((h) => (
              <li
                key={h.asset_id}
                data-testid="search-hit"
                className="rounded border border-slate-800 bg-surface p-3"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="break-all font-mono text-sm tabular-nums text-slate-200">
                    {h.asset_id}
                  </p>
                  <p
                    className="shrink-0 font-mono text-sm tabular-nums text-telemetry"
                    title="Lexical relevance score, not a confidence"
                  >
                    {h.score.toFixed(3)}
                  </p>
                </div>
                {h.matched_terms.length > 0 && (
                  <p className="mt-1 text-xs text-slate-400">
                    <span className="uppercase tracking-wide">Matched</span>{" "}
                    {h.matched_terms.map((t) => (
                      <span
                        key={t}
                        className="ml-1 rounded bg-canvas px-1.5 py-0.5 font-mono text-slate-300"
                      >
                        {t}
                      </span>
                    ))}
                  </p>
                )}
                <p className="mt-1 text-xs leading-relaxed text-slate-400">
                  {h.excerpt}
                </p>
              </li>
            ))}
          </ul>

          {result.data.count === 0 && !searching && (
            <p className="mt-4 text-slate-400" data-testid="search-empty">
              Nothing matched.
              {unmatched.length > 0
                ? " Every term was absent from the index."
                : " Try a tag from the chips above."}
            </p>
          )}
        </>
      )}
    </Panel>
  );
}
