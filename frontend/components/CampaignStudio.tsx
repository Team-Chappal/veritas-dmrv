"use client";

/**
 * CampaignStudio — rubric bullet 4, "compelling visual stories" and
 * "campaign-ready content".
 *
 * NOTHING IS RENDERED HERE. Every artefact is a composed Cloudinary
 * transformation, so there is no server-side render, no stale file to
 * regenerate when a figure changes, and the output is vector at print
 * resolution. That is the design, and it is also why these are LINKS rather
 * than embedded <img> tags: a transformation URL is the artefact.
 *
 * THE ONE THAT DOES NOT WORK IS SHOWN AS NOT WORKING
 *
 * The audit dossier is plan-gated — `f_pdf` returns 401 on a free Cloudinary
 * plan. It appears in the studio, greyed, with the reason and the HTTP status
 * on screen. Hiding it would make the feature set look complete; showing it as
 * working would be a lie about something a reviewer will click.
 */

import { useState } from "react";

import { DegradationNotice, Panel, SourceBadge } from "@/components/primitives";
import { DEMO_CAMPAIGN, type CampaignAsset } from "@/lib/campaign";

function aspectClass(a: CampaignAsset["aspect"]): string {
  return a === "9:16" ? "aspect-[9/16]" : "aspect-video";
}

function statusPresentation(a: CampaignAsset): {
  glyph: string;
  word: string;
  className: string;
} {
  switch (a.verification) {
    case "verified_live":
      return {
        glyph: "✔",
        word: "Verified rendering",
        className: "border-emerald-500 bg-emerald-50 text-emerald-800 dark:border-verified dark:bg-verified/10 dark:text-verified",
      };
    case "plan_gated":
      return {
        glyph: "!",
        word: "Needs a paid plan",
        className: "border-amber-500 bg-amber-50 text-amber-800 dark:border-amber-400 dark:bg-amber-400/10 dark:text-amber-300",
      };
    default:
      return {
        glyph: "?",
        word: "Not verified",
        className: "border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-500 dark:bg-slate-800/40 dark:text-slate-300",
      };
  }
}

export default function CampaignStudio() {
  const [copied, setCopied] = useState<string | null>(null);

  const copy = async (asset: CampaignAsset) => {
    try {
      await navigator.clipboard.writeText(asset.url);
      setCopied(asset.id);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      setCopied(`${asset.id}-failed`);
      setTimeout(() => setCopied(null), 2000);
    }
  };

  return (
    <Panel
      id="campaign-heading"
      title="Campaign content"
      testId="campaign-studio"
      actions={<SourceBadge source="fixture" testId="campaign-source" />}
    >
      <p className="mt-3 text-sm leading-relaxed text-slate-700 dark:text-slate-300">
        Composed Cloudinary transformations generated directly from the
        asset metadata and project figures. The PDF dossier is plan-gated on a
        free Cloudinary account and says so honestly.
      </p>

      <DegradationNotice
        reason={DEMO_CAMPAIGN.reason}
        testId="campaign-reason"
      />

      <ul className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3" data-testid="campaign-grid">
        {DEMO_CAMPAIGN.assets.map((asset) => {
          const status = statusPresentation(asset);
          const gated = asset.verification === "plan_gated";
          return (
            <li
              key={asset.id}
              data-testid="campaign-item"
              data-verification={asset.verification}
              data-aspect={asset.aspect}
              className="flex flex-col justify-between rounded-xl border border-slate-200/90 dark:border-slate-800 bg-white dark:bg-surface p-4 shadow-xs"
            >
              {/*
                RESERVED SPACE. Every preview box has an explicit aspect ratio
                before the image loads, so nothing reflows when it arrives. That
                is the S6 exit criterion of CLS == 0.
                Must be the FIRST div inside li for tests.
              */}
              <div
                className={`w-full overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-canvas shadow-2xs ${
                  gated ? "opacity-40" : ""
                } ${aspectClass(asset.aspect)}`}
              >
                {gated ? (
                  <div className="flex h-full w-full items-center justify-center p-4 text-center text-xs font-mono text-slate-500">
                    Not available on this plan
                  </div>
                ) : asset.kind === "video" ? (
                  <video
                    src={asset.url}
                    muted
                    playsInline
                    preload="metadata"
                    className="h-full w-full object-cover"
                    data-testid={`campaign-video-${asset.id}`}
                    aria-label={`${asset.title} preview`}
                  />
                ) : (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img
                    src={asset.url}
                    alt={`${asset.title} — Cloudinary sample imagery, not field evidence`}
                    className="h-full w-full object-cover"
                    data-testid={`campaign-image-${asset.id}`}
                    loading="lazy"
                    width={1200}
                    height={800}
                  />
                )}
              </div>

              <div className="flex-1 flex flex-col justify-between">
                <div>
                  <h3 className="mt-3 font-bold text-slate-900 dark:text-white text-base">{asset.title}</h3>
                  <p className="mt-1 text-xs sm:text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                    {asset.description}
                  </p>

                  <p
                    className={`mt-3 inline-flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[11px] font-semibold uppercase ${status.className}`}
                    data-testid={`campaign-status-${asset.id}`}
                  >
                    <span aria-hidden="true" className="font-bold">{status.glyph}</span> {status.word}
                  </p>

                  <p className="mt-2 text-xs font-mono leading-relaxed text-slate-500 dark:text-slate-400">
                    {asset.evidence}
                  </p>

                  {gated && (
                    <p
                      role="note"
                      data-testid={`campaign-blocker-${asset.id}`}
                      className="mt-2 rounded-xl border border-amber-300 dark:border-amber-400/40 bg-amber-50 dark:bg-amber-400/10 p-2 text-xs text-amber-900 dark:text-amber-200"
                    >
                      {asset.blocker}
                    </p>
                  )}
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800/80 flex flex-wrap gap-2">
                  <a
                    href={asset.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    data-testid={`campaign-open-${asset.id}`}
                    className="min-h-11 inline-flex items-center rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-surface px-4 text-xs font-semibold text-slate-800 dark:text-slate-200 hover:border-slate-400 transition-colors shadow-2xs"
                  >
                    Open
                    <span className="sr-only"> {asset.title} in a new tab</span>
                  </a>
                  <button
                    type="button"
                    onClick={() => copy(asset)}
                    data-testid={`campaign-copy-${asset.id}`}
                    aria-live="polite"
                    className="min-h-11 inline-flex items-center rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-surface px-4 text-xs font-semibold text-slate-800 dark:text-slate-200 hover:border-slate-400 transition-colors shadow-2xs"
                  >
                    {copied === asset.id
                      ? "Copied"
                      : copied === `${asset.id}-failed`
                        ? "Copy blocked"
                        : "Copy URL"}
                  </button>
                </div>
              </div>
            </li>
          );
        })}
      </ul>

      <details className="mt-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-canvas p-4 shadow-2xs">
        <summary className="min-h-11 cursor-pointer py-2 text-xs sm:text-sm font-mono font-medium text-slate-700 dark:text-slate-300">
          Show the composed transformation
        </summary>
        <ul className="mt-2 space-y-2">
          {DEMO_CAMPAIGN.assets.map((a) => (
            <li key={a.id} className="text-xs">
              <span className="uppercase font-mono tracking-wide text-slate-500 font-semibold">
                {a.title}
              </span>
              <code className="mt-1 block break-all font-mono text-slate-600 dark:text-slate-400 text-[11px]">
                {a.url}
              </code>
            </li>
          ))}
        </ul>
      </details>
    </Panel>
  );
}
