import { TOUCH_TARGET } from "./primitives";

export default function WorkflowSection() {
  const steps = [
    {
      num: "01",
      title: "Field Ingestion & Cryptographic Provenance",
      tag: "C2PA + EXIF + pHash",
      color: "border-sky-500 text-sky-600 dark:text-sky-400 bg-sky-50 dark:bg-sky-950/40",
      description:
        "Field agent captures imagery on mobile/drone. The edge client parses the hardware-signed C2PA JUMBF manifest, verifies cryptographic signing keys, extracts UTC timestamp and GPS coordinates, and computes a 64-bit perceptual hash (pHash) against the deduplication corpus.",
      guarantee: "Prevents duplicate submissions, synthetic displays & recompression tricks.",
    },
    {
      num: "02",
      title: "Astronomical Solar Forensics",
      tag: "pvlib Ephemeris",
      color: "border-amber-500 text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40",
      description:
        "The claimed GPS coordinates and timestamp are passed to the pvlib NOAA Solar Position Algorithm. The platform derives the sun's exact altitude and azimuth. The computer vision layer isolates cast sapling shadows and computes the angular error against the solar vector.",
      guarantee: "Enforces 12° fraud tolerance gate; abstains honestly if sun elevation < 10°.",
    },
    {
      num: "03",
      title: "Multitemporal Computer Vision Registration",
      tag: "SIFT + USAC_MAGSAC++",
      color: "border-emerald-500 text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40",
      description:
        "To compare before/after images accurately across seasons and angles, SIFT feature extraction detects invariant keypoints. USAC_MAGSAC++ computes a projective 3x3 homography matrix H (with TPS parallax fallback) to align pixels into an identical spatial coordinate frame.",
      guarantee: "Labels registration quality above delta; flags low inlier ratios (< 0.50).",
    },
    {
      num: "04",
      title: "Biomass Allometry & VM0047 Deductions",
      tag: "Chave 2014 Eq. 4",
      color: "border-purple-500 text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-950/40",
      description:
        "Canopy masks are isolated via Green Leaf Index (GLI) Otsu adaptive thresholding. Crown area is converted to DBH proxy via D = 2.1·√(area). Aboveground biomass is computed with Chave 2014 Eq. 4, converted to tCO2e, and penalized with a 15% VM0047 uncertainty buffer.",
      guarantee: "No carbon over-crediting; conservative scientific error discounting.",
    },
    {
      num: "05",
      title: "Cloudinary Intelligence & Tamper-Proof Dossier",
      tag: "SHA-256 Merkle Root",
      color: "border-indigo-500 text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/40",
      description:
        "Evidence is indexed using Cloudinary Media Intelligence (AI semantic tagging, spatial video hotspot transforms, WebVTT track generation). The full audit record is bound to a SHA-256 Merkle tree root hash and exported as a machine-verifiable audit dossier.",
      guarantee: "100% offline fixture degradation if credentials or internet are absent.",
    },
  ];

  return (
    <section
      id="workflow"
      aria-labelledby="workflow-heading"
      className="py-16 sm:py-24 border-b border-slate-200/80 dark:border-slate-800/80"
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mb-12 sm:mb-16">
          <span className="font-mono text-xs uppercase tracking-widest text-sky-600 dark:text-telemetry font-bold">
            END-TO-END PIPELINE
          </span>
          <h2
            id="workflow-heading"
            className="mt-2 text-3xl sm:text-5xl font-extrabold tracking-tight text-slate-900 dark:text-white"
          >
            The 5-Stage Verification Workflow
          </h2>
          <p className="mt-4 text-base sm:text-lg text-slate-700 dark:text-slate-300 leading-relaxed">
            From field shutter click to cryptographic carbon retirement: every byte travels through five automated, reproducible verification gates.
          </p>
        </div>

        {/* Workflow Steps */}
        <div className="relative border-l-2 border-slate-200 dark:border-slate-800 ml-4 sm:ml-6 pl-6 sm:pl-10 space-y-10">
          {steps.map((step) => (
            <div key={step.num} className="relative group">
              {/* Step Marker Circle */}
              <div className="absolute -left-[35px] sm:-left-[51px] top-1 flex h-8 w-8 sm:h-10 sm:w-10 items-center justify-center rounded-full border-2 border-white dark:border-canvas bg-slate-900 dark:bg-white text-white dark:text-slate-900 font-mono text-xs sm:text-sm font-bold shadow-sm">
                {step.num}
              </div>

              {/* Card Container */}
              <div className="rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white/95 dark:bg-surface/95 p-6 sm:p-7 shadow-xs transition-all hover:border-slate-300 dark:hover:border-slate-700">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                  <h3 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-white">
                    {step.title}
                  </h3>
                  <span className={`font-mono text-xs font-semibold px-2.5 py-1 rounded-full border ${step.color}`}>
                    {step.tag}
                  </span>
                </div>

                <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed mb-4">
                  {step.description}
                </p>

                <div className="flex items-center gap-2 text-xs font-mono text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-900/60 p-2.5 rounded-lg border border-slate-100 dark:border-slate-800/80">
                  <span className="text-emerald-600 dark:text-emerald-400 font-bold">✓ Guarantee:</span>
                  <span>{step.guarantee}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
