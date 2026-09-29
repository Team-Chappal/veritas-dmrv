import { TOUCH_TARGET } from "./primitives";

export default function TechStackSection() {
  const stack = [
    {
      category: "Astronomy & Physics",
      tech: "Python 3.12 · pvlib · NumPy · SciPy",
      desc: "Pure computational units with zero remote dependencies. Computes solar ephemeris, NOAA SPA sun vectors, atmospheric refraction corrections, and shadow coherence cones.",
      badge: "Pure Math Core",
    },
    {
      category: "Computer Vision",
      tech: "OpenCV · SIFT · USAC_MAGSAC++ · GLI",
      desc: "Multi-scale keypoint feature extraction, 3x3 projective homography estimation, Thin Plate Splines (TPS) parallax fallback, and Green Leaf Index Otsu canopy segmentation.",
      badge: "Sub-pixel Accuracy",
    },
    {
      category: "Media Intelligence",
      tech: "Cloudinary · AI Tagging · W3C WebVTT",
      desc: "Intelligent asset management, content-aware transformations, dynamic spatial hotspot overlays, and machine-generated WebVTT caption tracks.",
      badge: "Problem Statement 02",
    },
    {
      category: "Provenance & Security",
      tech: "C2PA Rust Toolchain · SHA-256 · pHash",
      desc: "Hardware-signed camera manifests, SHA-256 Merkle root trees, 64-bit perceptual hashing (pHash) against recompression tricks, and 2D-FFT Moire synthetic screen detection.",
      badge: "Cryptographic Root",
    },
    {
      category: "Carbon & Forestry Standards",
      tech: "Verra VM0047 · Chave 2014 · IPCC Tier 3",
      desc: "Chave et al. (2014) Eq. 4 allometric biomass models, wood specific gravity database, carbon conversion fractions (0.47), and VM0047 Section 8 uncertainty discounts.",
      badge: "Scientific Integrity",
    },
    {
      category: "Frontend & Test Rigor",
      tech: "Next.js 15 · React 19 · TypeScript · Playwright",
      desc: "Next.js 15 App Router static export, Tailwind CSS with dual-theme architecture, 183 Playwright e2e tests, zero layout shift (CLS = 0), and WCAG 2.2 AAA contrast.",
      badge: "183 Passing Specs",
    },
  ];

  return (
    <section
      id="techstack"
      aria-labelledby="techstack-heading"
      className="py-16 sm:py-24 border-b border-slate-200/80 dark:border-slate-800/80"
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mb-12 sm:mb-16">
          <span className="font-mono text-xs uppercase tracking-widest text-sky-600 dark:text-telemetry font-bold">
            ARCHITECTURE & ENGINEERING
          </span>
          <h2
            id="techstack-heading"
            className="mt-2 text-3xl sm:text-5xl font-extrabold tracking-tight text-slate-900 dark:text-white"
          >
            The Veritas Technology Stack
          </h2>
          <p className="mt-4 text-base sm:text-lg text-slate-700 dark:text-slate-300 leading-relaxed">
            Architected to work completely offline, degrading honestly when credentials are absent. Services never import routes; routes import services.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {stack.map((item) => (
            <div
              key={item.category}
              className="flex flex-col justify-between rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white/95 dark:bg-surface/95 p-6 sm:p-7 shadow-xs transition-all hover:border-slate-300 dark:hover:border-slate-700"
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-3">
                  <span className="font-mono text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    {item.category}
                  </span>
                  <span className="font-mono text-[11px] font-bold text-sky-600 dark:text-telemetry bg-sky-50 dark:bg-telemetry/10 px-2 py-0.5 rounded">
                    {item.badge}
                  </span>
                </div>

                <h3 className="text-base sm:text-lg font-bold text-slate-900 dark:text-white mb-2 font-mono">
                  {item.tech}
                </h3>

                <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                  {item.desc}
                </p>
              </div>

              <div className="mt-6 pt-4 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-xs font-mono text-slate-500 dark:text-slate-400">
                <span>Verified in CI</span>
                <span className="text-emerald-600 dark:text-emerald-400 font-bold">✓ 100% Tested</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
