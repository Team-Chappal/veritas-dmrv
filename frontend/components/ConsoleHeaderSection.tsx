import { TOUCH_TARGET } from "./primitives";

export default function ConsoleHeaderSection() {
  const tools = [
    { label: "Verification Lab", href: "#verification-lab" },
    { label: "Solar Physics HUD", href: "#physics-heading" },
    { label: "Impact Split Slider", href: "#impact-heading" },
    { label: "Hotspot Video", href: "#hotspot-heading" },
    { label: "Live Ticker", href: "#ticker-heading" },
    { label: "Timeline & Gaps", href: "#timeline-heading" },
    { label: "Campaign Studio", href: "#campaign-heading" },
    { label: "Semantic Search", href: "#search-heading" },
    { label: "Portfolio Grid", href: "#portfolio-heading" },
    { label: "C2PA Provenance", href: "#provenance-heading" },
    { label: "Offline Resilience", href: "#offline-heading" },
  ];

  return (
    <div id="audit-console" className="pt-16 pb-8 border-t-2 border-slate-200 dark:border-slate-800">
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-widest text-sky-600 dark:text-telemetry font-bold">
              <span className="h-2 w-2 rounded-full bg-emerald-500" aria-hidden="true" />
              <span>LIVE AUDIT COMMAND CENTER · STAGE 6 SUITE</span>
            </div>
            <h2 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-slate-900 dark:text-white mt-1">
              Interactive Forensic Workspace
            </h2>
          </div>

          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-sky-300 dark:border-telemetry/40 bg-sky-50 dark:bg-telemetry/10 px-3 py-1 font-mono text-xs text-sky-900 dark:text-telemetry">
              <span aria-hidden="true">◐</span>
              <span>Default Fixture Mode (Zero Keys Needed)</span>
            </span>
          </div>
        </div>

        <p className="text-sm sm:text-base text-slate-700 dark:text-slate-300 max-w-3xl leading-relaxed">
          Every instrument below is live and interactive. It functions with the backend entirely absent — degrading gracefully to reference fixtures rather than failing. Test the solar ephemeris, drag the before/after homography slider, inspect C2PA manifests, and search the corpus.
        </p>

        {/* Quick Instrument Jump Chips */}
        <div
          role="navigation"
          aria-label="Audit instruments quick jump"
          className="flex flex-wrap items-center gap-2 pt-2"
        >
          {tools.map((t) => (
            <a
              key={t.href}
              href={t.href}
              className={`${TOUCH_TARGET} inline-flex items-center rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-surface px-3.5 text-xs font-mono font-medium text-slate-700 dark:text-slate-300 hover:border-slate-400 dark:hover:border-slate-600 hover:text-slate-900 dark:hover:text-white transition-colors shadow-2xs`}
            >
              <span>{t.label}</span>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
