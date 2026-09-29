import { TOUCH_TARGET } from "./primitives";

export default function MethodologySection() {
  return (
    <section
      id="methodology"
      aria-labelledby="methodology-heading"
      className="py-16 sm:py-24 border-b border-slate-200/80 dark:border-slate-800/80 bg-slate-50/50 dark:bg-black/20"
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mb-12 sm:mb-16">
          <span className="font-mono text-xs uppercase tracking-widest text-emerald-600 dark:text-verified font-bold">
            HOW WE DO IT · MATHEMATICAL FORMULAS
          </span>
          <h2
            id="methodology-heading"
            className="mt-2 text-3xl sm:text-5xl font-extrabold tracking-tight text-slate-900 dark:text-white"
          >
            The Physics & Mathematics of Verified Ground Truth
          </h2>
          <p className="mt-4 text-base sm:text-lg text-slate-700 dark:text-slate-300 leading-relaxed">
            VERITAS dMRV eliminates subjective estimation. Every measurement is governed by published allometric forestry regressions, astronomical ephemeris equations, and computer vision geometry.
          </p>
        </div>

        {/* Bento Grid of Equations & Science */}
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {/* Equation 1: Chave 2014 Eq. 4 */}
          <div className="rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white dark:bg-surface p-6 sm:p-7 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs font-mono uppercase tracking-wider text-emerald-700 dark:text-emerald-400 font-bold bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 rounded">
                Biomass Allometry
              </span>
              <span className="text-xs font-mono text-slate-500 dark:text-slate-400">
                Chave et al. (2014)
              </span>
            </div>

            <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-2">
              Tropical Forest Aboveground Biomass
            </h3>

            {/* LaTeX style formatted formula */}
            <div className="my-4 rounded-xl bg-slate-900 dark:bg-slate-950 text-slate-100 p-4 font-mono text-sm leading-relaxed overflow-x-auto shadow-inner">
              <div className="text-sky-300 font-bold">
                AGB = 0.0673 × (WD · H · D²)<sup>0.976</sup>
              </div>
              <div className="mt-2 text-xs text-slate-400 border-t border-slate-800 pt-2 space-y-1">
                <div><span className="text-slate-300">AGB:</span> Dry biomass (kg dry weight)</div>
                <div><span className="text-slate-300">WD:</span> Wood specific gravity (g/cm³)</div>
                <div><span className="text-slate-300">H:</span> Tree height (m)</div>
                <div><span className="text-slate-300">D:</span> Diameter at breast height (cm)</div>
              </div>
            </div>

            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
              Verified verbatim against CRAN R package <code className="font-mono bg-slate-100 dark:bg-slate-800 px-1 py-0.5 rounded">BIOMASS</code>. Guarded in CI via <code className="font-mono text-xs">scripts/verify_docs.py</code> to prevent regression.
            </p>
          </div>

          {/* Equation 2: NOAA Solar Shadow Coherence */}
          <div className="rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white dark:bg-surface p-6 sm:p-7 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs font-mono uppercase tracking-wider text-sky-700 dark:text-sky-400 font-bold bg-sky-50 dark:bg-sky-950/40 px-2 py-0.5 rounded">
                Forensic Astronomy
              </span>
              <span className="text-xs font-mono text-slate-500 dark:text-slate-400">
                NOAA SPA & pvlib
              </span>
            </div>

            <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-2">
              Shadow Vector & Coherence Cone
            </h3>

            <div className="my-4 rounded-xl bg-slate-900 dark:bg-slate-950 text-slate-100 p-4 font-mono text-sm leading-relaxed overflow-x-auto shadow-inner">
              <div className="text-emerald-300 font-bold">
                θ<sub>expected</sub> = (α<sub>sun</sub> + 180°) mod 360°
              </div>
              <div className="text-amber-300 font-semibold mt-1">
                Δθ = min(|θ<sub>obs</sub> - θ<sub>exp</sub>|, 360° - |θ<sub>obs</sub> - θ<sub>exp</sub>|)
              </div>
              <div className="mt-2 text-xs text-slate-400 border-t border-slate-800 pt-2 space-y-1">
                <div><span className="text-slate-300">Δθ ≤ 12.0°:</span> Physics Consistent (Pass)</div>
                <div><span className="text-slate-300">Δθ &gt; 12.0°:</span> Quarantined for Fraud</div>
                <div><span className="text-slate-300">Elev &lt; 10.0°:</span> Review (Abstention Gate)</div>
              </div>
            </div>

            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
              Every solar vector is generated directly from <code className="font-mono bg-slate-100 dark:bg-slate-800 px-1 py-0.5 rounded">pvlib</code> ground truth. The test suite rejects test fixtures if genuine cases clear by under 5.0°.
            </p>
          </div>

          {/* Equation 3: Carbon & VM0047 Deduction */}
          <div className="rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white dark:bg-surface p-6 sm:p-7 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs font-mono uppercase tracking-wider text-purple-700 dark:text-purple-400 font-bold bg-purple-50 dark:bg-purple-950/40 px-2 py-0.5 rounded">
                Carbon Accounting
              </span>
              <span className="text-xs font-mono text-slate-500 dark:text-slate-400">
                Verra VM0047 §8
              </span>
            </div>

            <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-2">
              Carbon Stock & Risk Deductions
            </h3>

            <div className="my-4 rounded-xl bg-slate-900 dark:bg-slate-950 text-slate-100 p-4 font-mono text-sm leading-relaxed overflow-x-auto shadow-inner">
              <div className="text-purple-300 font-bold">
                tCO₂e = AGB × 0.47 × (44/12) / 1000
              </div>
              <div className="text-rose-300 font-semibold mt-1">
                Issuance = Net Carbon × (1 - 0.15)
              </div>
              <div className="mt-2 text-xs text-slate-400 border-t border-slate-800 pt-2 space-y-1">
                <div><span className="text-slate-300">0.47:</span> IPCC carbon fraction of dry wood</div>
                <div><span className="text-slate-300">44/12:</span> Molecular weight ratio of CO₂ to C</div>
                <div><span className="text-slate-300">15%:</span> Mandatory VM0047 error buffer discount</div>
              </div>
            </div>

            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
              Verra VM0047 Methodology Section 8 mandates explicit deductions for crown-to-DBH estimation uncertainty and registration error before issuing verified carbon units.
            </p>
          </div>
        </div>

        {/* The 3 Codebase Findings Callout Box */}
        <div className="mt-10 rounded-2xl border border-amber-300 dark:border-amber-800/80 bg-amber-50/70 dark:bg-amber-950/20 p-6 sm:p-8">
          <div className="flex items-start gap-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-500/20 text-amber-700 dark:text-amber-300 font-mono font-bold text-lg">
              !
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                The 3 Audits That Shaped This Codebase (Why Veritas Is Different)
              </h3>
              <p className="mt-1 text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                Before writing production code, the specification suite was subjected to adversarial peer review:
              </p>
              <ul className="mt-4 space-y-2.5 text-xs sm:text-sm text-slate-700 dark:text-slate-300">
                <li className="flex items-start gap-2">
                  <span className="font-mono text-amber-600 dark:text-amber-400 font-bold">01.</span>
                  <span><strong className="text-slate-900 dark:text-white">Fixed Invalid Solar Vectors:</strong> Four hand-written solar vectors in the original proposal violated physics (e.g. Ankara at local solar noon documented at 138° instead of 187°). Now, all fixtures are generated strictly from <code className="font-mono text-xs">pvlib</code> with a 5° minimum safety margin.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="font-mono text-amber-600 dark:text-amber-400 font-bold">02.</span>
                  <span><strong className="text-slate-900 dark:text-white">Corrected Solar Azimuth Formulas:</strong> The NOAA mathematical derivation was verified against spherical astronomy to guarantee that reviewers cannot find mathematical defects.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="font-mono text-amber-600 dark:text-amber-400 font-bold">03.</span>
                  <span><strong className="text-slate-900 dark:text-white">Verified Chave 2014 Prefactor:</strong> The constant <code className="font-mono text-xs">0.0673</code> in Eq. 4 was verified against the French CRAN <code className="font-mono text-xs">BIOMASS</code> package, preventing a disastrous 6.7× carbon estimation overstatement.</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
