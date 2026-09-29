import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Next >=15.5 infers the workspace root by looking for lockfiles, and warns
  // that the inference "may not be correct" when it finds more than one. The
  // backend has a requirements.txt and the frontend has package-lock.json, so
  // both exist and the warning fires on every build. Stating the root explicitly
  // removes the guess: tracing is scoped to the frontend, which is what is
  // actually being deployed.
  outputFileTracingRoot: here,
};

// A JUDGE-FACING STATIC BUNDLE, FOR THE DEMO -- not the production build.
//
// The app is already fully static: `next build` reports "prerendered as static
// content". Exporting it emits a folder of files that serves from anything --
// a static host, S3, GitHub Pages, or `python3 -m http.server` on a machine with
// no Node at all. 1.1 MB, and it removes the last runtime dependency between
// the product and a judge opening a URL.
//
// OPT-IN, AND IN THIS FILE RATHER THAN A SECOND ONE. Two earlier attempts failed
// and both are worth recording:
//
//   1. A separate next.export.config.mjs plus `next build --config ...`. There is
//      no --config flag -- Next reads next.config.mjs from the root and nothing
//      else -- so that target died with "unknown option".
//   2. Driving Next programmatically. `next({conf}).build()` does not exist in
//      Next 15; the programmatic API exposes prepare/close/handle, not build.
//
// A third option was a shell that swapped the production config, built, and
// restored it. That would leave the export config in place if anything
// interrupted the build, so it was not worth reaching for. One config with a
// branch is simpler than either duplicate-file approach and cannot drift.
//
// Production is unaffected: the variable is unset, so nothing below applies.
const isStaticDemo = process.env.VERITAS_STATIC_DEMO === "1";

if (isStaticDemo) {
  nextConfig.output = "export";
  // No image optimiser exists in a static export, so images ship as-is.
  nextConfig.images = { unoptimized: true };
  // Emit a trailing-slash directory per route, which is what a plain static file
  // server expects. Without it, any sub-path 404s on a dumb host.
  nextConfig.trailingSlash = true;
}

export default nextConfig;
