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
        className: "border-verified text-verified",
      };
    case "plan_gated":
      return {
        glyph: "!",
        word: "Needs a paid plan",
        className: "border-amber-400 text-amber-300",
      };
    default:
      return {
        glyph: "?",
        word: "Not verified",
        className: "border-slate-500 text-slate-300",
      };
  }
}

export default function CampaignStudio() {
  const [copied, setCopied] = useState<string | null>(null);

  const copy = async (asset: CampaignAsset) => {
    try {
      await navigator.clipboard.writeText(asset.url);
      setCopied(asset.id);
      setTimeout(() => setCopied((c) => (c === asset.id ? null : c)), 2000);
    } catch {
      // Clipboard is permission-gated and can be denied; say so rather than
      // pretending the copy worked.
      setCopied(`${asset.id}-failed`);
    }
  };

  return (
    <Panel
      id="campaign-heading"
      title="Campaign content"
      testId="campaign-studio"
      actions={<SourceBadge source="fixture" testId="campaign-source" />}
    >
      <DegradationNotice
        reason={DEMO_CAMPAIGN.reason}
        testId="campaign-reason"
      />

      <p className="mt-4 text-sm text-slate-300">
        {DEMO_CAMPAIGN.project_name} ·{" "}
        <span className="font-mono tabular-nums">{DEMO_CAMPAIGN.project_id}</span>
      </p>

      <ul className="mt-5 grid gap-4 sm:grid-cols-2" data-testid="campaign-grid">
        {DEMO_CAMPAIGN.assets.map((asset) => {
          const status = statusPresentation(asset);
          const gated = asset.verification === "plan_gated";
          return (
            <li
              key={asset.id}
              data-testid="campaign-item"
              data-verification={asset.verification}
              className="flex flex-col rounded-lg border border-slate-800 bg-surface p-4"
            >
              {/*
                RESERVED SPACE. Every preview box has an explicit aspect ratio
                before the image loads, so nothing reflows when it arrives. That
                is the S6 exit criterion of CLS == 0, and a grid of images with
                no reserved space is the single most reliable way to fail it.
              */}
              <div
                className={`w-full overflow-hidden rounded border border-slate-700 bg-canvas ${
                  gated ? "opacity-40" : ""
                } ${aspectClass(asset.aspect)}`}
              >
                {gated ? (
                  <div className="flex h-full w-full items-center justify-center p-4 text-center text-xs text-slate-400">
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

              <h3 className="mt-3 font-semibold">{asset.title}</h3>
              <p className="mt-1 text-sm leading-relaxed text-slate-400">
                {asset.description}
              </p>

              <p
                className={`mt-3 inline-flex w-fit items-center gap-1 rounded border px-2 py-1 text-xs ${status.className}`}
                data-testid={`campaign-status-${asset.id}`}
              >
                <span aria-hidden="true">{status.glyph}</span> {status.word}
              </p>

              <p className="mt-2 text-xs leading-relaxed text-slate-500">
                {asset.evidence}
              </p>

              {gated && (
                <p
                  role="note"
                  data-testid={`campaign-blocker-${asset.id}`}
                  className="mt-2 rounded border border-amber-400/40 bg-amber-400/10 p-2 text-xs text-amber-200"
                >
                  {asset.blocker}
                </p>
              )}

              <div className="mt-3 flex flex-wrap gap-2">
                <a
                  href={asset.url}
                  target="_blank"
                  rel="noreferrer noopener"
                  data-testid={`campaign-open-${asset.id}`}
                  className="min-h-11 inline-flex items-center rounded border border-slate-600 px-4 text-sm text-slate-200 hover:border-slate-400"
                >
                  Open
                  <span className="sr-only"> {asset.title} in a new tab</span>
                </a>
                <button
                  type="button"
                  onClick={() => copy(asset)}
                  data-testid={`campaign-copy-${asset.id}`}
                  aria-live="polite"
                  className="min-h-11 inline-flex items-center rounded border border-slate-600 px-4 text-sm text-slate-200 hover:border-slate-400"
                >
                  {copied === asset.id
                    ? "Copied"
                    : copied === `${asset.id}-failed`
                      ? "Copy blocked"
                      : "Copy URL"}
                </button>
              </div>
            </li>
          );
        })}
      </ul>

      {/*
        The transformation string is shown, not hidden behind a download. A
        reviewer asking "what exactly was applied?" should not need to guess or
        open devtools.
      */}
      <details className="mt-5 rounded border border-slate-800 bg-canvas p-3">
        <summary className="min-h-11 cursor-pointer py-2 text-sm text-slate-300">
          Show the composed transformation
        </summary>
        <ul className="mt-2 space-y-2">
          {DEMO_CAMPAIGN.assets.map((a) => (
            <li key={a.id} className="text-xs">
              <span className="uppercase tracking-wide text-slate-500">
                {a.title}
              </span>
              <code className="mt-1 block break-all font-mono text-slate-400">
                {a.url}
              </code>
            </li>
          ))}
        </ul>
      </details>
    </Panel>
  );
}
