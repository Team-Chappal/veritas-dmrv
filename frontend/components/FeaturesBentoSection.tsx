import { TOUCH_TARGET } from "./primitives";

export default function FeaturesBentoSection() {
  const features = [
    {
      id: "physics-hud",
      title: "Solar Physics & Shadow Coherence HUD",
      tag: "Rubric 3 · Astronomy",
      desc: "Interactive compass projecting NOAA solar azimuth and elevation. Measures angular divergence of cast shadows against expected physics, with strict 12° fraud gate and low-sun abstention.",
      cta: "Test Physics HUD →",
      link: "#physics-hud",
    },
    {
      id: "impact-studio",
      title: "Proof of Impact Split Slider",
      tag: "Rubric 3 · Computer Vision",
      desc: "Multitemporal before-and-after registration via SIFT + USAC_MAGSAC++ homography. Interactive keyboard-friendly split slider displaying Otsu canopy segmentation and inlier ratio.",
      cta: "Scrub Impact Slider →",
      link: "#impact-studio",
    },
    {
      id: "hotspot-player",
      title: "Spatial Hotspot Video & WebVTT",
      tag: "Rubric 2 · Media Intelligence",
      desc: "Full video player with dynamically generated WebVTT caption tracks. Clickable spatial markers seek video directly to identified saplings, canopy anomalies, and monitoring points.",
      cta: "Play Hotspot Video →",
      link: "#hotspot-player",
    },
    {
      id: "semantic-search",
      title: "Honest Semantic Search Engine",
      tag: "Rubric 5 · Discovery",
      desc: "Natural language query engine across the impact corpus. Unlike opaque search boxes, it explicitly discloses query terms that matched nothing and reports its own engine limitations.",
      cta: "Run Search Query →",
      link: "#semantic-search",
    },
    {
      id: "portfolio-grid",
      title: "Intelligent Portfolio & Dynamic Triage",
      tag: "Rubric 1 · Organization",
      desc: "Scalable 500+ asset grid with filter chips displaying real-time facet counts from the filtered subset. Triage status badges carry both text labels and icons for full accessibility.",
      cta: "Filter Portfolio →",
      link: "#portfolio-grid",
    },
    {
      id: "provenance-panel",
      title: "C2PA Provenance & Merkle Ledger",
      tag: "Rubric 6 · Cryptography",
      desc: "Complete chain-of-custody verification showing master asset hashes, C2PA JUMBF manifest validity, Cloudinary transformations, and the SHA-256 Merkle root.",
      cta: "Inspect Provenance →",
      link: "#provenance-panel",
    },
  ];

  return (
    <section
      id="features"
      aria-labelledby="features-heading"
      className="py-16 sm:py-24 border-b border-slate-200/80 dark:border-slate-800/80 bg-slate-50/30 dark:bg-black/10"
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mb-12 sm:mb-16">
          <span className="font-mono text-xs uppercase tracking-widest text-sky-600 dark:text-telemetry font-bold">
            PLATFORM CAPABILITIES
          </span>
          <h2
            id="features-heading"
            className="mt-2 text-3xl sm:text-5xl font-extrabold tracking-tight text-slate-900 dark:text-white"
          >
            Core Forensic Instruments
          </h2>
          <p className="mt-4 text-base sm:text-lg text-slate-700 dark:text-slate-300 leading-relaxed">
            Six purpose-built forensic tools designed for regulatory auditors, carbon market registries, and field verification agents.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <div
              key={f.id}
              className="flex flex-col justify-between rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white/95 dark:bg-surface/95 p-6 sm:p-7 shadow-sm transition-all hover:shadow-md hover:border-slate-300 dark:hover:border-slate-700"
            >
              <div>
                <span className="font-mono text-xs font-semibold px-2.5 py-1 rounded-md border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-slate-600 dark:text-slate-400 inline-block mb-3">
                  {f.tag}
                </span>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-2">
                  {f.title}
                </h3>
                <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed mb-6">
                  {f.desc}
                </p>
              </div>

              <div className="pt-4 border-t border-slate-100 dark:border-slate-800/80">
                <a
                  href={f.link}
                  className={`${TOUCH_TARGET} inline-flex items-center text-xs font-mono font-semibold uppercase tracking-wider text-sky-600 dark:text-telemetry hover:underline`}
                >
                  {f.cta}
                </a>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
