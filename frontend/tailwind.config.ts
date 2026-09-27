import type { Config } from 'tailwindcss';

/**
 * Design tokens per docs/06-FRONTEND-SPEC.md §5.1.
 *
 * Palette rules that are load-bearing, not decorative:
 *  - #10B981 verified / #EF4444 quarantine are NEVER the only signal; every
 *    status carries an icon and a text label too (WCAG 2.2, "use of colour").
 *  - #38BDF8 is reserved for telemetry (coordinates, azimuths, hashes) so a
 *    number is never confused with a status.
 *  - All numeric metrics render in Geist Mono with tabular-nums so live ticker
 *    updates cause zero layout shift.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#030712",
        surface: "#0B0F19",
        verified: "#10B981",
        quarantine: "#EF4444",
        telemetry: "#38BDF8",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
