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

export default nextConfig;
