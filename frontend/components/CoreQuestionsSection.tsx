import { TOUCH_TARGET } from "./primitives";

export default function CoreQuestionsSection() {
  return (
    <section
      id="questions"
      aria-labelledby="questions-heading"
      className="py-16 sm:py-24 border-b border-slate-200/80 dark:border-slate-800/80"
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="max-w-3xl mb-12 sm:mb-16">
          <span className="font-mono text-xs uppercase tracking-widest text-sky-600 dark:text-telemetry font-bold">
            THE EPISTEMOLOGICAL FOUNDATION
          </span>
          <h2
            id="questions-heading"
            className="mt-2 text-3xl sm:text-5xl font-extrabold tracking-tight text-slate-900 dark:text-white"
          >
            Three Questions That Break Carbon Markets.{" "}
            <span className="text-slate-500 dark:text-slate-400">
              Three Mathematical Answers.
            </span>
          </h2>
          <p className="mt-4 text-base sm:text-lg text-slate-700 dark:text-slate-300 leading-relaxed">
            Carbon credits fail because registries confuse <em className="italic">assertion</em> with <strong className="font-semibold text-slate-900 dark:text-white">proof</strong>. Here is the exact ground truth VERITAS dMRV calculates:
          </p>
        </div>

        {/* 3 Interactive Cards / Interrogation Grid */}
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Card 1: Authenticity */}
          <article className="flex flex-col justify-between rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white/95 dark:bg-surface/95 p-6 sm:p-8 shadow-sm transition-all hover:shadow-md hover:border-slate-300 dark:hover:border-slate-700">
            <div>
              <div className="flex items-center justify-between gap-2 mb-4">
                <span className="font-mono text-xs font-bold uppercase tracking-wider text-sky-600 dark:text-telemetry bg-sky-50 dark:bg-sky-950/50 border border-sky-200 dark:border-sky-800 px-2.5 py-1 rounded-md">
                  Question 01 · Authenticity
                </span>
                <span className="text-xs font-mono text-slate-500 dark:text-slate-400">
                  Solar Physics
                </span>
              </div>

              <h3 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white mb-3">
                “Is this photo genuine, from where and when it claims, and unmanipulated?”
              </h3>

              <div className="mb-4 rounded-lg bg-rose-50/80 dark:bg-rose-950/20 border border-rose-200/80 dark:border-rose-900/40 p-3 text-xs text-rose-900 dark:text-rose-300">
                <strong className="font-semibold block mb-0.5">The Carbon Market Blindspot:</strong>
                EXIF GPS stamps can be forged in five seconds. Stock photos or pictures of a phone screen are repeatedly submitted as freshly planted hectares.
              </div>

              <div className="space-y-3 text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                <p>
                  <strong className="font-semibold text-slate-900 dark:text-white">Veritas Answer:</strong> We compute the exact NOAA solar ephemeris via <code className="font-mono text-xs bg-slate-100 dark:bg-slate-800 px-1 py-0.5 rounded">pvlib</code> for the claimed latitude, longitude, and UTC timestamp.
                </p>
                <p>
                  The cast shadow angle in the photograph must align with the astronomical sun vector. A divergence greater than <strong className="font-semibold text-slate-900 dark:text-white">12.0°</strong> triggers an immediate quarantine verdict. If the sun is below 10° elevation, the detector honestly withholds judgment.
                </p>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-xs font-mono text-slate-500 dark:text-slate-400">
              <span>Gate: 12.0° Tolerance</span>
              <a href="#physics-hud" className={`${TOUCH_TARGET} inline-flex items-center text-sky-600 dark:text-telemetry font-semibold hover:underline`}>
                Test Compass →
              </a>
            </div>
          </article>

          {/* Card 2: Measurement */}
          <article className="flex flex-col justify-between rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white/95 dark:bg-surface/95 p-6 sm:p-8 shadow-sm transition-all hover:shadow-md hover:border-slate-300 dark:hover:border-slate-700">
            <div>
              <div className="flex items-center justify-between gap-2 mb-4">
                <span className="font-mono text-xs font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/50 border border-emerald-200 dark:border-emerald-800 px-2.5 py-1 rounded-md">
                  Question 02 · Measurement
                </span>
                <span className="text-xs font-mono text-slate-500 dark:text-slate-400">
                  CV + Allometry
                </span>
              </div>

              <h3 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white mb-3">
                “Has the vegetation actually changed, and by exactly how much carbon?”
              </h3>

              <div className="mb-4 rounded-lg bg-rose-50/80 dark:bg-rose-950/20 border border-rose-200/80 dark:border-rose-900/40 p-3 text-xs text-rose-900 dark:text-rose-300">
                <strong className="font-semibold block mb-0.5">The Carbon Market Blindspot:</strong>
                Handheld before-and-after photos have different angles, focal lengths, and seasonal leaf cover, leading to exaggerated carbon issuance.
              </div>

              <div className="space-y-3 text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                <p>
                  <strong className="font-semibold text-slate-900 dark:text-white">Veritas Answer:</strong> SIFT keypoint detection and USAC_MAGSAC++ projective homography mathematically project the monitoring image onto the baseline pixel plane.
                </p>
                <p>
                  Canopy growth is segmented via Green Leaf Index (GLI) Otsu thresholding. Biomass is computed using <strong className="font-semibold text-slate-900 dark:text-white">Chave et al. (2014) Eq. 4</strong> with a strict <strong className="font-semibold text-slate-900 dark:text-white">VM0047</strong> conservative 15% uncertainty deduction.
                </p>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-xs font-mono text-slate-500 dark:text-slate-400">
              <span>Eq: Chave 2014 (0.0673)</span>
              <a href="#impact-studio" className={`${TOUCH_TARGET} inline-flex items-center text-emerald-600 dark:text-emerald-400 font-semibold hover:underline`}>
                Scrub Split Slider →
              </a>
            </div>
          </article>

          {/* Card 3: Evidence */}
          <article className="flex flex-col justify-between rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white/95 dark:bg-surface/95 p-6 sm:p-8 shadow-sm transition-all hover:shadow-md hover:border-slate-300 dark:hover:border-slate-700">
            <div>
              <div className="flex items-center justify-between gap-2 mb-4">
                <span className="font-mono text-xs font-bold uppercase tracking-wider text-purple-700 dark:text-purple-400 bg-purple-50 dark:bg-purple-950/50 border border-purple-200 dark:border-purple-800 px-2.5 py-1 rounded-md">
                  Question 03 · Reproducibility
                </span>
                <span className="text-xs font-mono text-slate-500 dark:text-slate-400">
                  C2PA Provenance
                </span>
              </div>

              <h3 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white mb-3">
                “Can an auditor reproduce this result and survive legal scrutiny 10 years later?”
              </h3>

              <div className="mb-4 rounded-lg bg-rose-50/80 dark:bg-rose-950/20 border border-rose-200/80 dark:border-rose-900/40 p-3 text-xs text-rose-900 dark:text-rose-300">
                <strong className="font-semibold block mb-0.5">The Carbon Market Blindspot:</strong>
                Carbon companies rely on private servers and non-reproducible LLM summaries. When contested in regulatory court, the audit paper trail collapses.
              </div>

              <div className="space-y-3 text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                <p>
                  <strong className="font-semibold text-slate-900 dark:text-white">Veritas Answer:</strong> Media is bound to hardware-signed C2PA manifests, with every transformation cryptographically hashed in a SHA-256 Merkle root.
                </p>
                <p>
                  Zero black-box LLMs generate verdicts. The entire platform functions with zero backend credentials, degrading honestly to public reference fixtures that anyone can verify on a disconnected laptop.
                </p>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-xs font-mono text-slate-500 dark:text-slate-400">
              <span>Standard: C2PA v1.4</span>
              <a href="#provenance-panel" className={`${TOUCH_TARGET} inline-flex items-center text-purple-600 dark:text-purple-400 font-semibold hover:underline`}>
                Inspect Root Hash →
              </a>
            </div>
          </article>
        </div>
      </div>
    </section>
  );
}
