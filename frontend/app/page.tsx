import CampaignStudio from "@/components/CampaignStudio";
import ConsoleHeaderSection from "@/components/ConsoleHeaderSection";
import CoreQuestionsSection from "@/components/CoreQuestionsSection";
import FeaturesBentoSection from "@/components/FeaturesBentoSection";
import FooterSection from "@/components/FooterSection";
import ForensicPhysicsHUD from "@/components/ForensicPhysicsHUD";
import HeroSection from "@/components/HeroSection";
import HotspotVideoPlayer from "@/components/HotspotVideoPlayer";
import MethodologySection from "@/components/MethodologySection";
import MetricTicker from "@/components/MetricTicker";
import Navbar from "@/components/Navbar";
import OfflineResilience from "@/components/OfflineResilience";
import PortfolioGrid from "@/components/PortfolioGrid";
import ProjectTimeline from "@/components/ProjectTimeline";
import ProofOfImpactStudio from "@/components/ProofOfImpactStudio";
import ProvenancePanel from "@/components/ProvenancePanel";
import SemanticSearch from "@/components/SemanticSearch";
import TechStackSection from "@/components/TechStackSection";
import WorkflowSection from "@/components/WorkflowSection";

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

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-[#F8FAFC] dark:bg-canvas text-slate-900 dark:text-slate-100 transition-colors duration-200">
      {/* Futuristic Floating Command Bar */}
      <Navbar />

      <main className="flex-1">
        {/* Editorial Landing Hero */}
        <HeroSection />

        {/* The Core Epistemological Questions & Veritas Answers */}
        <CoreQuestionsSection />

        {/* Pure Mathematical Methodology */}
        <MethodologySection />

        {/* 5-Stage Scientific Architecture Workflow */}
        <WorkflowSection />

        {/* Core Forensic Capabilities */}
        <FeaturesBentoSection />

        {/* Architecture & Engineering Tech Stack */}
        <TechStackSection />

        {/* Stage 6 Live Audit Command Center */}
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-4 sm:px-6 lg:px-8 py-12">
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

          {/* Rubric intro & timeline */}
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

          {/* Solar Ephemeris & Shadow Coherence HUD */}
          <ForensicPhysicsHUD />

          {/* Rubric bullet 6: Cryptographic Provenance Panel */}
          <ProvenancePanel />

          {/* Live Telemetry Metric Ticker */}
          <MetricTicker />

          {/* Offline Resilience & Data Mode Switcher */}
          <OfflineResilience />
        </div>
      </main>

      {/* Comprehensive Footer & Open-Source Specifications */}
      <FooterSection />
    </div>
  );
}
