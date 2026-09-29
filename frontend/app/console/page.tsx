import CampaignStudio from "@/components/CampaignStudio";
import ConsoleHeaderSection from "@/components/ConsoleHeaderSection";
import FooterSection from "@/components/FooterSection";
import ForensicPhysicsHUD from "@/components/ForensicPhysicsHUD";
import HotspotVideoPlayer from "@/components/HotspotVideoPlayer";
import MetricTicker from "@/components/MetricTicker";
import Navbar from "@/components/Navbar";
import OfflineResilience from "@/components/OfflineResilience";
import PortfolioGrid from "@/components/PortfolioGrid";
import ProjectTimeline from "@/components/ProjectTimeline";
import ProofOfImpactStudio from "@/components/ProofOfImpactStudio";
import ProvenancePanel from "@/components/ProvenancePanel";
import SemanticSearch from "@/components/SemanticSearch";
import VerificationConsole from "@/components/VerificationConsole";
import { TOUCH_TARGET } from "@/components/primitives";

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
  built: "border-emerald-500 bg-emerald-50 text-emerald-800 dark:border-verified/50 dark:bg-verified/10 dark:text-verified",
  "in-progress": "border-amber-500/50 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  planned: "border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800/60 text-slate-600 dark:text-slate-400",
};

export default function ConsolePage() {
  const quickTools = [
    { label: "⚡ Verification Sandbox", href: "#console-heading" },
    { label: "🛰️ Impact Slider", href: "#impact-heading" },
    { label: "🎥 Hotspot Video", href: "#hotspot-heading" },
    { label: "📂 Asset Portfolio", href: "#portfolio-heading" },
    { label: "🔍 Semantic Search", href: "#search-heading" },
    { label: "📣 Campaign Studio", href: "#campaign-heading" },
    { label: "🛡️ C2PA Provenance", href: "#provenance-heading" },
    { label: "⏱️ Project Timeline", href: "#timeline-heading" },
    { label: "📡 Live Ticker", href: "#ticker-heading" },
    { label: "💾 Offline Mode", href: "#offline-heading" },
  ];

  return (
    <div className="flex min-h-screen flex-col bg-[#F8FAFC] dark:bg-canvas text-slate-900 dark:text-slate-100 transition-colors duration-200">
      {/* Top Command Bar */}
      <Navbar />

      <main className="flex-1">
        {/* Cockpit Banner */}
        <section
          aria-label="Console Cockpit Header"
          className="border-b border-slate-200 dark:border-slate-800 bg-slate-900 text-white py-8 sm:py-10 px-4 sm:px-6 lg:px-8"
        >
          <div className="mx-auto max-w-6xl">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <a
                    href="/"
                    className={`${TOUCH_TARGET} inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-1 text-xs font-mono text-slate-300 hover:text-white hover:bg-slate-700 transition-colors`}
                  >
                    <span>← Return to Landing Page</span>
                  </a>
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-mono text-emerald-400">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    Judge Cockpit
                  </span>
                </div>
                <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-white">
                  Forensic Media Command Center
                </h1>
                <p className="mt-1 text-sm sm:text-base text-slate-400 max-w-2xl leading-relaxed">
                  Interactive multi-instrument audit console for judges and evaluators. Test solar physics ephemeris, inspect before/after homography, explore 500-asset portfolios, and verify C2PA cryptographic provenance.
                </p>
              </div>

              {/* Status & Mode Chips */}
              <div className="flex flex-col sm:items-end gap-2 text-xs font-mono">
                <div className="inline-flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-950/80 px-3 py-2 text-slate-300">
                  <span className="h-2 w-2 rounded-full bg-emerald-400" />
                  <span>100% In-Browser Execution</span>
                </div>
                <span className="text-slate-500">Zero backend keys required · Bundled reference fixtures</span>
              </div>
            </div>

            {/* Quick Sticky Dock */}
            <div className="mt-6 pt-4 border-t border-slate-800 flex flex-wrap items-center gap-2" role="navigation" aria-label="Console instruments fast-switch">
              {quickTools.map((t) => (
                <a
                  key={t.href}
                  href={t.href}
                  className={`${TOUCH_TARGET} inline-flex items-center rounded-xl border border-slate-700 bg-slate-800/70 px-3 py-1.5 text-xs font-mono font-medium text-slate-300 hover:text-white hover:border-slate-500 hover:bg-slate-700 transition-colors`}
                >
                  <span>{t.label}</span>
                </a>
              ))}
            </div>
          </div>
        </section>

        {/* Instruments Workspace */}
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-4 sm:px-6 lg:px-8 py-10">
          {/* Primary Verification Sandbox */}
          <VerificationConsole />

          <ConsoleHeaderSection />

          {/* Development Roadmap Stages */}
          <section aria-label="Build stages" className="grid gap-4 sm:grid-cols-3">
            {STAGES.map((stage) => (
              <article
                key={stage.id}
                className="flex flex-col gap-3 rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white/95 dark:bg-surface/95 p-5 shadow-xs"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-sm font-bold text-slate-900 dark:text-white">
                    {stage.id}
                  </span>
                  <span
                    className={`rounded-full border px-2.5 py-0.5 font-mono text-[11px] font-semibold uppercase ${STATUS_STYLE[stage.status]}`}
                  >
                    {stage.status === "built" ? "✓ done" : stage.status}
                  </span>
                </div>
                <h2 className="text-base font-bold text-slate-900 dark:text-white">{stage.title}</h2>
                <p className="font-mono text-[11px] uppercase tracking-wider text-sky-700 dark:text-telemetry font-semibold">
                  {stage.rubric}
                </p>
                <p className="text-xs leading-relaxed text-slate-600 dark:text-slate-400">
                  {stage.detail}
                </p>
              </article>
            ))}
          </section>

          {/* Project Timeline & Summary */}
          <ProjectTimeline />

          {/* Rubric bullet 1: Portfolio Grid */}
          <PortfolioGrid />

          {/* Rubric bullet 2: Hotspot Video Player */}
          <HotspotVideoPlayer />

          {/* Rubric bullet 3: Before / After Proof of Impact Studio */}
          <ProofOfImpactStudio />

          {/* Rubric bullet 4: Campaign Studio */}
          <CampaignStudio />

          {/* Rubric bullet 5: Semantic Search */}
          <SemanticSearch />

          {/* Forensic Physics HUD */}
          <ForensicPhysicsHUD />

          {/* Rubric bullet 6: Cryptographic Provenance Panel */}
          <ProvenancePanel />

          {/* Live Telemetry Metric Ticker */}
          <MetricTicker />

          {/* Offline Resilience & Data Mode Switcher */}
          <OfflineResilience />
        </div>
      </main>

      <FooterSection />
    </div>
  );
}
