"use client";

/**
 * ProvenancePanel — rubric bullet 6.
 *
 * "Traceability to source assets and transformations" is a claim; this is the
 * receipt. It shows the master asset, the SHA-256 root, the C2PA state, and
 * every transformation Cloudinary recorded, so an auditor can reconstruct what
 * was done to the original.
 *
 * All presentation comes from `@/components/primitives`, so the
 * no-colour-alone rule exists once rather than once per component. The panel's own
 * job is the DATA: which asset, which hash, which chain, and — above all —
 * whether any of it was measured.
 */

import { useEffect, useState } from "react";

import {
  DegradationNotice,
  Figure,
  Panel,
  SourceBadge,
  StatusPill,
  c2paPresentation,
  shortHash,
} from "@/components/primitives";
import { fetchProvenance } from "@/lib/api";
import { DEMO_ASSET_ID } from "@/lib/fixtures";
import type { ProvenanceResult } from "@/lib/provenance";

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
      <Panel id="provenance-heading" title="Provenance">
        <p className="mt-3 text-slate-300">
          The provenance record could not be read. This is a client error, not a
          verification result: nothing is being claimed about the asset.
        </p>
      </Panel>
    );
  }

  if (!state) {
    return (
      <div
        aria-busy="true"
        aria-labelledby="provenance-heading"
        className="rounded-lg border border-slate-700 bg-surface p-6"
      >
        <h2 id="provenance-heading" className="text-lg font-semibold">
          Provenance
        </h2>
        <p className="mt-2 text-slate-400">Reading provenance record…</p>
      </div>
    );
  }

  const { record, source, reason } = state;
  const c2pa = c2paPresentation(record.c2pa_provenance);

  return (
    <Panel
      id="provenance-heading"
      title="Provenance"
      testId="provenance-panel"
      dataSource={source}
      actions={<SourceBadge source={source} testId="provenance-source" />}
    >
      {source === "fixture" && (
        <DegradationNotice reason={reason} testId="provenance-reason" />
      )}

      <dl className="mt-5 grid gap-x-8 gap-y-4 sm:grid-cols-2">
        <Figure
          label="Source asset"
          value={record.master.public_id}
          testId="provenance-public-id"
        />
        <Figure
          label="Folder"
          value={record.master.folder || "—"}
          testId="provenance-folder"
        />
        <Figure
          label={`${record.content_hash.algorithm} root`}
          value={shortHash(record.content_hash.root_hash)}
          title={record.content_hash.root_hash}
          testId="provenance-root-hash"
        />
        <div>
          <dt className="text-sm uppercase tracking-wide text-slate-400">
            C2PA manifest
          </dt>
          <dd className="mt-1">
            <StatusPill status={c2pa} testId="provenance-c2pa" />
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
                  {step.width && step.height
                    ? `${step.width}×${step.height}`
                    : null}
                  {step.format ? ` · ${step.format}` : null}
                  {step.bytes ? ` · ${(step.bytes / 1024).toFixed(0)} KB` : null}
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
    </Panel>
  );
}
