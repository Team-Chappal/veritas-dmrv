import ConsoleHeaderSection from "@/components/ConsoleHeaderSection";
import CoreQuestionsSection from "@/components/CoreQuestionsSection";
import FooterSection from "@/components/FooterSection";
import VerificationConsole from "@/components/VerificationConsole";
import HeroSection from "@/components/HeroSection";
import Navbar from "@/components/Navbar";
import TechStackSection from "@/components/TechStackSection";
import WorkflowSection from "@/components/WorkflowSection";
import { TOUCH_TARGET } from "@/components/primitives";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-[#F8FAFC] dark:bg-canvas text-slate-900 dark:text-slate-100 transition-colors duration-200">
      {/* Floating Futuristic Command Bar */}
      <Navbar />

      <main className="flex-1">
        {/* Editorial Landing Hero */}
        <HeroSection />

        {/* Live System Console (Interactive Input & Output Sandbox for Judges) */}
        <section
          id="verification-lab"
          className="relative scroll-mt-24 px-4 sm:px-6 lg:px-8 max-w-6xl mx-auto -mt-6 sm:-mt-10 mb-16 w-full z-20"
          aria-label="Interactive System Console"
        >
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2 px-1">
            <div className="inline-flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
              </span>
              <span className="font-mono text-xs font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
                Live System Console · Real-Time Input & Output
              </span>
            </div>
            <a
              href="/console"
              className="inline-flex items-center gap-1 font-mono text-xs text-sky-600 dark:text-telemetry font-semibold hover:underline"
            >
              <span>Open Dedicated Cockpit (/console) ↗</span>
            </a>
          </div>

          <VerificationConsole />
        </section>

        {/* The Core Epistemological Questions & Veritas Answers (Architecture) */}
        <CoreQuestionsSection />

        {/* 5-Stage Scientific Architecture Workflow */}
        <WorkflowSection />

        {/* Architecture & Engineering Tech Stack */}
        <TechStackSection />

        {/* Dedicated Full Console Launch Banner */}
        <section aria-label="Full Forensic Console Launch" className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 py-16">
          <div className="relative overflow-hidden rounded-3xl border border-slate-200 dark:border-slate-800 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 text-white p-8 sm:p-12 shadow-xl">
            <div className="absolute top-0 right-0 -mt-10 -mr-10 h-64 w-64 rounded-full bg-sky-500/10 blur-3xl pointer-events-none" />
            <div className="absolute bottom-0 left-0 -mb-10 -ml-10 h-64 w-64 rounded-full bg-emerald-500/10 blur-3xl pointer-events-none" />

            <div className="relative z-10 max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded-full border border-sky-400/30 bg-sky-400/10 px-3 py-1 font-mono text-xs font-semibold text-sky-300 mb-4">
                <span className="h-1.5 w-1.5 rounded-full bg-sky-400 animate-pulse" />
                <span>STAGE 6 FORENSIC AUDIT SUITE</span>
              </div>

              <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white mb-4">
                Dedicated Multi-Instrument Forensic Console
              </h2>

              <p className="text-base sm:text-lg text-slate-300 leading-relaxed mb-8">
                Judges and auditors can enter the full cockpit workspace with dedicated tabs for Before/After Homography Sliders, Telemetry-Synced Video Players, 500-Asset Corpus Filtering, Semantic Search, and C2PA Provenance.
              </p>

              <div className="flex flex-wrap items-center gap-4">
                <a
                  href="/console"
                  className={`${TOUCH_TARGET} inline-flex items-center justify-center rounded-xl bg-white px-6 py-3.5 text-sm sm:text-base font-bold text-slate-900 hover:bg-slate-100 transition-all shadow-lg`}
                >
                  <span>Launch Forensic Console (/console)</span>
                  <svg className="ml-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                  </svg>
                </a>

                <a
                  href="#verification-lab"
                  className={`${TOUCH_TARGET} inline-flex items-center justify-center rounded-xl border border-slate-700 bg-slate-800/80 px-5 py-3.5 text-sm sm:text-base font-medium text-slate-200 hover:bg-slate-700 hover:text-white transition-colors`}
                >
                  <span>Quick Solar & Biomass Sandbox ↑</span>
                </a>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Comprehensive Footer */}
      <FooterSection />
    </div>
  );
}
