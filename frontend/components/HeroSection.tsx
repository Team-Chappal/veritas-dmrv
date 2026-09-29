import { TOUCH_TARGET } from "./primitives";

export default function HeroSection() {
  return (
    <section
      id="top"
      aria-labelledby="hero-heading"
      className="relative overflow-hidden pt-8 pb-16 sm:pt-14 sm:pb-24 border-b border-slate-200/80 dark:border-slate-800/80"
    >
      {/* Background Architectural Grid Lines */}
      <div
        className="absolute inset-0 -z-10 opacity-[0.03] dark:opacity-[0.05] pointer-events-none"
        style={{
          backgroundImage: `radial-gradient(circle at 1px 1px, currentColor 1px, transparent 0)`,
          backgroundSize: "32px 32px",
        }}
        aria-hidden="true"
      />

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col items-center text-center max-w-4xl mx-auto">
          {/* Top Eyebrow Badge */}
          <div className="inline-flex items-center gap-2 rounded-full border border-sky-500/30 bg-sky-50/80 dark:bg-telemetry/10 px-4 py-1.5 text-xs font-mono font-medium text-sky-800 dark:text-telemetry mb-6 shadow-xs">
            <span className="h-1.5 w-1.5 rounded-full bg-sky-600 dark:bg-telemetry animate-ping" aria-hidden="true" />
            <span>CODE CUBICLE 6.0 · PROBLEM STATEMENT 02 (CLOUDINARY)</span>
          </div>

          {/* Main Headline */}
          <h1
            id="hero-heading"
            className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-[-0.035em] text-slate-900 dark:text-white leading-[1.08] mb-6"
          >
            Planetary Ground Truth.{" "}
            <span className="block text-slate-500 dark:text-slate-400 font-bold">
              No Black Boxes. No Hallucinations.
            </span>
          </h1>

          {/* Strong Proposition */}
          <p className="text-base sm:text-xl text-slate-700 dark:text-slate-300 leading-relaxed max-w-3xl mb-8 font-normal">
            Global carbon markets trade billions on unverified claims. <strong className="font-semibold text-slate-900 dark:text-white">VERITAS dMRV</strong> is the open forensic media platform that proves whether a tree exists, when it was planted, and exactly how much carbon it sequestered — replacing human assertion with astronomical solar physics, computer vision homography, and cryptographic C2PA provenance.
          </p>

          {/* Interactive CTAs */}
          <div className="flex flex-wrap items-center justify-center gap-3 sm:gap-4 mb-14 w-full">
            <a
              href="#audit-console"
              className={`${TOUCH_TARGET} inline-flex items-center justify-center rounded-xl bg-slate-900 dark:bg-white px-6 py-3 text-sm sm:text-base font-semibold text-white dark:text-slate-900 hover:bg-slate-800 dark:hover:bg-slate-100 transition-all shadow-md`}
            >
              <span>Explore Live Audit Console</span>
              <svg className="ml-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
              </svg>
            </a>

            <a
              href="#questions"
              className={`${TOUCH_TARGET} inline-flex items-center justify-center rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-surface px-6 py-3 text-sm sm:text-base font-medium text-slate-800 dark:text-slate-200 hover:border-slate-400 dark:hover:border-slate-600 transition-colors shadow-xs`}
            >
              <span>The Core Dilemma & Answers</span>
              <svg className="ml-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
              </svg>
            </a>

            <a
              href="#methodology"
              className={`${TOUCH_TARGET} inline-flex items-center justify-center rounded-xl border border-transparent px-4 py-3 text-sm font-mono text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-colors`}
            >
              <span>Chave 2014 Allometry & Equations ↗</span>
            </a>
          </div>

          {/* Bento Grid Metrics Ribbon */}
          <div className="w-full grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4 text-left">
            <div className="rounded-xl border border-slate-200/90 dark:border-slate-800 bg-white/90 dark:bg-surface/90 p-4 sm:p-5 shadow-xs">
              <span className="block text-[11px] font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400 font-semibold mb-1">
                Physics Ephemeris
              </span>
              <span className="text-xl sm:text-2xl font-bold font-mono tabular-nums text-slate-900 dark:text-white block">
                105 Vectors
              </span>
              <span className="text-xs text-slate-600 dark:text-slate-400 mt-1 block">
                pvlib ground truth · NOAA SPA verified
              </span>
            </div>

            <div className="rounded-xl border border-slate-200/90 dark:border-slate-800 bg-white/90 dark:bg-surface/90 p-4 sm:p-5 shadow-xs">
              <span className="block text-[11px] font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400 font-semibold mb-1">
                Biomass Accounting
              </span>
              <span className="text-xl sm:text-2xl font-bold font-mono tabular-nums text-slate-900 dark:text-white block">
                Chave Eq. 4
              </span>
              <span className="text-xs text-slate-600 dark:text-slate-400 mt-1 block">
                0.0673 prefactor · VM0047 error discount
              </span>
            </div>

            <div className="rounded-xl border border-slate-200/90 dark:border-slate-800 bg-white/90 dark:bg-surface/90 p-4 sm:p-5 shadow-xs">
              <span className="block text-[11px] font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400 font-semibold mb-1">
                Hardware Provenance
              </span>
              <span className="text-xl sm:text-2xl font-bold font-mono tabular-nums text-slate-900 dark:text-white block">
                C2PA + SHA-256
              </span>
              <span className="text-xs text-slate-600 dark:text-slate-400 mt-1 block">
                Cryptographic Merkle audit trail
              </span>
            </div>

            <div className="rounded-xl border border-slate-200/90 dark:border-slate-800 bg-white/90 dark:bg-surface/90 p-4 sm:p-5 shadow-xs">
              <span className="block text-[11px] font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400 font-semibold mb-1">
                Testing Integrity
              </span>
              <span className="text-xl sm:text-2xl font-bold font-mono tabular-nums text-emerald-600 dark:text-emerald-400 block">
                183 Passing
              </span>
              <span className="text-xs text-slate-600 dark:text-slate-400 mt-1 block">
                0% LLM guessing · zero CLS layout shift
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
