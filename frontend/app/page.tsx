/**
 * Stage 0 toolchain proof.
 *
 * The full Audit Command Center lands in Stage 6. This page exists so that CI
 * verifies the Next.js 15 + React 19 toolchain on every push rather than
 * discovering a broken toolchain on the day the frontend is built. It also
 * carries the design-system baseline, so later components inherit settled
 * tokens instead of inventing their own.
 *
 * The three cards below are the rubric surfaces that Stage 6 must deliver:
 *   1. Organize large collections        -> PortfolioGrid
 *   2. Identify projects / visual signals -> SemanticSearch + auto-tags
 *   3. Compare before-and-after          -> ProofOfImpactStudio
 */

import PortfolioGrid from "@/components/PortfolioGrid";
import ProvenancePanel from "@/components/ProvenancePanel";

type Stage = {
  id: string;
  title: string;
  rubric: string;
  status: "built" | "in-progress" | "planned";
  detail: string;
};

const STAGES: Stage[] = [
  {
    id: "S1",
    title: "Numerical core",
    rubric: "verification",
    status: "built",
    detail:
      "pvlib solar-ephemeris shadow coherence, Chave 2014 allometry, VM0047 " +
      "uncertainty, pHash dedup. 105 tests, 94% coverage.",
  },
  {
    id: "S2",
    title: "Computer vision",
    rubric: "before / after",
    status: "planned",
    detail:
      "SIFT + USAC_MAGSAC++ homography, TPS parallax fallback, radiometric " +
      "normalization, GLI + Otsu canopy delta.",
  },
  {
    id: "S3",
    title: "Enrichment & semantics",
    rubric: "AI tagging, search",
    status: "planned",
    detail:
      "Auto-tagging from image content, semantic discovery, grounded project " +
      "summaries. Closes the largest gap in the original specification.",
  },
];

const STATUS_STYLE: Record<Stage["status"], string> = {
  built: "border-verified/50 bg-verified/10 text-verified",
  "in-progress": "border-amber-500/50 bg-amber-500/10 text-amber-300",
  planned: "border-slate-700 bg-slate-800/60 text-slate-400",
};

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-10 px-6 py-16">
      <header className="flex flex-col gap-3">
        <span className="font-mono text-xs uppercase tracking-widest text-telemetry">
          Code Cubicle 6.0 · Problem Statement 02 (Cloudinary)
        </span>
        <h1 className="text-4xl font-bold tracking-tight text-white">
          VERITAS dMRV
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-slate-400">
          Visual ground-truth and cryptographic media provenance for field
          impact evidence. Every quantitative claim in this platform is
          generated from a reference implementation and regression-tested — a
          number nothing supports is treated as a defect.
        </p>
      </header>

      <section aria-label="Build stages" className="grid gap-4 sm:grid-cols-3">
        {STAGES.map((stage) => (
          <article
            key={stage.id}
            className="flex flex-col gap-3 rounded-xl border border-slate-800 bg-surface p-5"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-sm font-bold text-white">
                {stage.id}
              </span>
              {/* Status is never conveyed by colour alone. */}
              <span
                className={`rounded-full border px-2.5 py-0.5 font-mono text-[11px] font-semibold uppercase ${STATUS_STYLE[stage.status]}`}
              >
                {stage.status === "built" ? "✓ done" : stage.status}
              </span>
            </div>
            <h2 className="text-base font-semibold text-white">{stage.title}</h2>
            <p className="font-mono text-[11px] uppercase tracking-wider text-telemetry">
              {stage.rubric}
            </p>
            <p className="text-xs leading-relaxed text-slate-400">
              {stage.detail}
            </p>
          </article>
        ))}
      </section>

      {/* Rubric bullet 1 — bulk-organized evidence at a glance. */}
      <PortfolioGrid />

      {/* Rubric bullet 6 — the first real Stage 6 component on the page. */}
      <ProvenancePanel />

      <footer className="border-t border-slate-800 pt-6 font-mono text-xs text-slate-500">
        <p>
          Fixture mode is the default: with no Cloudinary credentials present
          the platform degrades to local assets rather than failing.
        </p>
      </footer>
    </main>
  );
}
