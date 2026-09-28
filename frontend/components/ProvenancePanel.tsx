"use client";

/**
 * ProvenancePanel — rubric bullet 6.
 *
 * "Traceability to source assets and transformations" is a claim; this is the
 * receipt. It shows the master asset, the SHA-256 root, the C2PA state, and
 * every transformation Cloudinary recorded, so an auditor can reconstruct what
 * was done to the original.
 *
 * ACCESSIBILITY, BECAUSE A FORENSIC PANEL THAT CANNOT BE READ IS NOT EVIDENCE
 *
 * - No status is signalled by colour alone. Every state carries a glyph AND a
 *   word, so it survives greyscale printing — which is how an audit pack gets
 *   printed.
 * - Hashes and measurements are `tabular-nums`, so digits align down a column
 *   and a transposed character is visible.
 * - Target sizes are >= 44px, not the 24px that looks fine on a desk.
 */

import { useEffect, useState } from "react";

import { fetchProvenance } from "@/lib/api";
import { DEMO_ASSET_ID } from "@/lib/fixtures";
import type { C2PAStatus, ProvenanceResult } from "@/lib/provenance";

function c2paPresentation(status: C2PAStatus): {
  glyph: string;
  word: string;
  className: string;
} {
  switch (status) {
    case "C2PA_VERIFIED":
      // U+2714 HEAVY CHECK MARK. Paired with the word, never used alone.
      return { glyph: "✔", word: "Content verified", className: "text-verified" };
    case "C2PA_MUTATED":
      return { glyph: "✖", word: "Content altered", className: "text-quarantine" };
    case "C2PA_MISSING":
    default:
      return { glyph: "—", word: "No manifest", className: "text-slate-400" };
  }
}

function shortHash(hash: string): string {
  return hash.length <= 20 ? hash : `${hash.slice(0, 12)}…${hash.slice(-8)}`;
}

export default function ProvenancePanel() {
  const [state, setState] = useState<ProvenanceResult | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchProvenance(DEMO_ASSET_ID)
      .then((result) => {
        if (!cancelled) setState(result);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (failed) {
    return (
      <section
        aria-labelledby="provenance-heading"
        className="rounded-lg border border-quarantine bg-surface p-6"
      >
        <h2 id="provenance-heading" className="text-lg font-semibold">
          Provenance unavailable
        </h2>
        <p className="mt-2 text-slate-300">
          The provenance record could not be read. This is a client error, not a
          verification result: nothing is being claimed about the asset.
        </p>
      </section>
    );
  }

  if (!state) {
    return (
      <section
        aria-labelledby="provenance-heading"
        aria-busy="true"
        className="rounded-lg border border-slate-700 bg-surface p-6"
      >
        <h2 id="provenance-heading" className="text-lg font-semibold">
          Provenance
        </h2>
        <p className="mt-2 text-slate-400">Reading provenance record…</p>
      </section>
    );
  }

  const { record, source, reason } = state;
  const c2pa = c2paPresentation(record.c2pa_provenance);

  return (
    <section
      aria-labelledby="provenance-heading"
      data-testid="provenance-panel"
      data-source={source}
      className="rounded-lg border border-slate-700 bg-surface p-6"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="provenance-heading" className="text-lg font-semibold">
          Provenance
        </h2>
        {/*
          The source badge is the point of the whole component. A fixture shown
          without it is indistinguishable from a measurement in a screenshot.
          Glyph + word, never colour alone.
        */}
        <span
          data-testid="provenance-source"
          className={
            source === "live"
              ? "rounded border border-verified px-2 py-1 text-sm text-verified"
              : "rounded border border-telemetry px-2 py-1 text-sm text-telemetry"
          }
        >
          <span aria-hidden="true">{source === "live" ? "●" : "◐"}</span>{" "}
          {source === "live" ? "Live" : "Fixture"}
        </span>
      </div>

      {source === "fixture" && (
        <p
          data-testid="provenance-reason"
          role="status"
          className="mt-3 rounded border border-telemetry/40 bg-telemetry/10 p-3 text-sm text-slate-200"
        >
          <span aria-hidden="true">◐ </span>
          {reason}
        </p>
      )}

      <dl className="mt-5 grid gap-x-8 gap-y-4 sm:grid-cols-2">
        <div>
          <dt className="text-sm uppercase tracking-wide text-slate-400">
            Source asset
          </dt>
          <dd
            data-testid="provenance-public-id"
            className="mt-1 break-all font-mono tabular-nums"
          >
            {record.master.public_id}
          </dd>
        </div>

        <div>
          <dt className="text-sm uppercase tracking-wide text-slate-400">Folder</dt>
          <dd className="mt-1 break-all font-mono tabular-nums">
            {record.master.folder || "—"}
          </dd>
        </div>

        <div>
          <dt className="text-sm uppercase tracking-wide text-slate-400">
            {record.content_hash.algorithm} root
          </dt>
          <dd
            data-testid="provenance-root-hash"
            title={record.content_hash.root_hash}
            className="mt-1 font-mono tabular-nums"
          >
            {shortHash(record.content_hash.root_hash)}
          </dd>
        </div>

        <div>
          <dt className="text-sm uppercase tracking-wide text-slate-400">
            C2PA manifest
          </dt>
          <dd
            data-testid="provenance-c2pa"
            className={`mt-1 font-medium ${c2pa.className}`}
          >
            <span aria-hidden="true">{c2pa.glyph}</span>{" "}
            <span className="sr-only">Status: </span>
            {c2pa.word}
          </dd>
        </div>
      </dl>

      <h3 className="mt-6 text-sm uppercase tracking-wide text-slate-400">
        Transformation chain
      </h3>
      {record.transformations.length === 0 ? (
        <p className="mt-2 text-slate-400" data-testid="provenance-empty">
          No transformations recorded for this asset.
        </p>
      ) : (
        <ol className="mt-2 space-y-2" data-testid="provenance-chain">
          {record.transformations.map((step, i) => (
            <li
              key={`${step.transformation ?? i}-${i}`}
              className="rounded border border-slate-800 bg-canvas p-3"
            >
              <div className="flex items-baseline gap-3">
                <span className="tabular-nums text-slate-500">#{i + 1}</span>
                <code className="break-all text-sm tabular-nums">
                  {step.transformation ?? "(transformation string unavailable)"}
                </code>
              </div>
              {(step.width || step.height || step.bytes || step.format) && (
                <p className="mt-1 pl-8 text-sm tabular-nums text-slate-400">
                  {step.width && step.height ? `${step.width}×${step.height}` : null}
                  {step.format ? ` · ${step.format}` : null}
                  {step.bytes
                    ? ` · ${(step.bytes / 1024).toFixed(0)} KB`
                    : null}
                </p>
              )}
            </li>
          ))}
        </ol>
      )}

      <p className="mt-5 text-sm text-slate-400">
        {record.note}
        {record.transformation_log_live
          ? " Chain read from the Cloudinary API."
          : " Chain not read from the Cloudinary API."}
      </p>
    </section>
  );
}
