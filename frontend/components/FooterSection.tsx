import { TOUCH_TARGET } from "./primitives";

export default function FooterSection() {
  const docLinks = [
    { title: "01 Rubric Mapping", file: "docs/01-RUBRIC-MAPPING.md" },
    { title: "04 Solar Ephemeris Spec", file: "docs/04-SOLAR-EPHEMERIS-SPEC.md" },
    { title: "05 Biomass Allometry Spec", file: "docs/05-BIOMASS-ALLOMETRY-SPEC.md" },
    { title: "06 Frontend Design Tokens", file: "docs/06-FRONTEND-SPEC.md" },
    { title: "Execution Plan", file: "EXECUTION-PLAN.md" },
    { title: "Demo & Pitch Walkthrough", file: "docs/DEMO.md" },
  ];

  return (
    <footer
      id="docs"
      className="mt-20 border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-canvas pt-16 pb-12 transition-colors duration-200"
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid gap-10 md:grid-cols-2 lg:grid-cols-4 pb-12 border-b border-slate-200/80 dark:border-slate-800/80">
          {/* Col 1: Brand & Thesis */}
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-900 dark:bg-white text-white dark:text-slate-900 font-mono font-black text-sm">
                V
              </div>
              <span className="font-display font-extrabold text-base text-slate-900 dark:text-white">
                VERITAS dMRV
              </span>
            </div>
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
              Open digital Measurement, Reporting, and Verification platform. Built for Code Cubicle 6.0 Problem Statement 02 (Cloudinary).
            </p>
            <div className="text-xs font-mono text-slate-500 dark:text-slate-400">
              License: MIT · Reproducible Science
            </div>
          </div>

          {/* Col 2: Specifications Suite */}
          <div className="space-y-3">
            <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-900 dark:text-white">
              Specification Suite
            </h3>
            <ul className="space-y-1 text-xs sm:text-sm text-slate-600 dark:text-slate-400">
              {docLinks.map((d) => (
                <li key={d.file}>
                  <a
                    href={`https://github.com/Team-Chappal/veritas-dmrv/blob/main/${d.file}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`${TOUCH_TARGET} inline-flex items-center hover:text-slate-900 dark:hover:text-white transition-colors hover:underline`}
                  >
                    <span>{d.title} ↗</span>
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Col 3: Reproducibility & CLI */}
          <div className="space-y-3">
            <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-900 dark:text-white">
              Zero-Key Reproducibility
            </h3>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              To verify every single claim and run the offline test suite locally on your machine:
            </p>
            <div className="rounded-lg bg-slate-900 text-slate-200 p-2.5 font-mono text-[11px] leading-tight">
              make verify
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              Degrades to bundled pvlib ground truth fixtures with no credentials required.
            </p>
          </div>

          {/* Col 4: Contact & Project Submission */}
          <div className="space-y-3">
            <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-900 dark:text-white">
              Project & Contact
            </h3>
            <div className="text-xs text-slate-600 dark:text-slate-400 space-y-2">
              <div className="flex items-center gap-1.5 flex-wrap">
                <strong className="text-slate-900 dark:text-white">Developer / Maintainer:</strong>{" "}
                <span>Jay Gopal</span>
                <a
                  href="https://github.com/j4yop"
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`${TOUCH_TARGET} inline-flex items-center text-sky-600 dark:text-telemetry underline font-mono text-xs`}
                >
                  @j4yop
                </a>
              </div>
              <p>
                <strong className="text-slate-900 dark:text-white">Hackathon:</strong>{" "}
                Code Cubicle 6.0
              </p>
              <p>
                <strong className="text-slate-900 dark:text-white">Challenge:</strong>{" "}
                PS02 — Cloudinary Media Intelligence
              </p>
              <div className="pt-2">
                <a
                  href="https://github.com/Team-Chappal/veritas-dmrv"
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`${TOUCH_TARGET} inline-flex items-center gap-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 px-3 py-1.5 font-mono text-xs font-semibold text-slate-800 dark:text-slate-200 hover:text-slate-900 dark:hover:text-white hover:border-slate-400 transition-colors`}
                >
                  <span>★ Star on GitHub</span>
                </a>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Notice */}
        <div className="pt-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs font-mono text-slate-500 dark:text-slate-400 text-center sm:text-left">
          <p>
            VERITAS dMRV · Epistemic Truth Engine · 100% Deterministic Physics & Mathematics
          </p>
          <p>
            Fixture mode is the default: remote calls degrade safely rather than crashing.
          </p>
        </div>
      </div>
    </footer>
  );
}
