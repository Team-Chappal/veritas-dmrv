"use client";

import { useTheme } from "./ThemeContext";
import { TOUCH_TARGET } from "./primitives";

export default function Navbar() {
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-200/80 dark:border-slate-800/80 bg-white/80 dark:bg-[#030712]/80 backdrop-blur-md transition-colors duration-200">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8 h-16 sm:h-20">
        {/* Brand / Logo */}
        <a
          href="#top"
          className={`${TOUCH_TARGET} inline-flex items-center gap-3 focus:outline-none focus:ring-2 focus:ring-sky-500 rounded-lg px-2`}
          aria-label="VERITAS dMRV home"
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-900 dark:bg-white text-white dark:text-slate-900 font-mono font-black text-base shadow-sm">
            V
          </div>
          <div className="flex flex-col">
            <span className="font-display font-extrabold tracking-tight text-slate-900 dark:text-white text-base sm:text-lg leading-none">
              VERITAS <span className="text-sky-600 dark:text-telemetry font-mono font-normal text-xs uppercase tracking-widest ml-1">dMRV</span>
            </span>
            <span className="text-[10px] font-mono tracking-wider text-slate-500 dark:text-slate-400 leading-tight">
              ASTRONOMICAL & CRYPTOGRAPHIC GROUND TRUTH
            </span>
          </div>
        </a>

        {/* Center Navigation Links */}
        <nav
          className="hidden md:flex items-center gap-1 font-medium text-xs lg:text-sm text-slate-600 dark:text-slate-300"
          aria-label="Main Navigation"
        >
          <a
            href="#questions"
            className={`${TOUCH_TARGET} inline-flex items-center px-3 hover:text-slate-900 dark:hover:text-white transition-colors rounded-md`}
          >
            Core Questions
          </a>
          <a
            href="#methodology"
            className={`${TOUCH_TARGET} inline-flex items-center px-3 hover:text-slate-900 dark:hover:text-white transition-colors rounded-md`}
          >
            Methodology
          </a>
          <a
            href="#workflow"
            className={`${TOUCH_TARGET} inline-flex items-center px-3 hover:text-slate-900 dark:hover:text-white transition-colors rounded-md`}
          >
            Workflow
          </a>
          <a
            href="#techstack"
            className={`${TOUCH_TARGET} inline-flex items-center px-3 hover:text-slate-900 dark:hover:text-white transition-colors rounded-md`}
          >
            Tech Stack
          </a>
          <a
            href="#audit-console"
            className={`${TOUCH_TARGET} inline-flex items-center px-3 text-sky-600 dark:text-telemetry font-semibold hover:underline rounded-md`}
          >
            Audit Console
          </a>
        </nav>

        {/* Right Action Bar */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Live Status Pill */}
          <div className="hidden xl:inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-50/70 dark:bg-verified/10 px-3 py-1 text-xs font-mono text-emerald-800 dark:text-verified">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" aria-hidden="true" />
            <span>183 SPECS VERIFIED</span>
          </div>

          {/* Theme Switcher Toggle */}
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === "light" ? "Dark Blur" : "Light Minimalist"} theme`}
            title={`Switch to ${theme === "light" ? "Dark Blur" : "Light Minimalist"} theme`}
            className={`${TOUCH_TARGET} inline-flex items-center justify-center rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-slate-700 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-700 transition-colors shadow-xs px-3`}
          >
            {theme === "light" ? (
              <span className="inline-flex items-center gap-1.5 text-xs font-semibold">
                <svg className="w-4 h-4 text-amber-500" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                  <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
                </svg>
                <span className="hidden sm:inline">Dark Blur</span>
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-xs font-semibold">
                <svg className="w-4 h-4 text-sky-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <circle cx="12" cy="12" r="5" strokeWidth="2" />
                  <path strokeLinecap="round" strokeWidth="2" d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
                </svg>
                <span className="hidden sm:inline">Light Mode</span>
              </span>
            )}
          </button>

          {/* GitHub Link */}
          <a
            href="https://github.com/j4yop/veritas-dmrv"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="GitHub Repository"
            className={`${TOUCH_TARGET} inline-flex items-center justify-center rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 px-3 text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white transition-colors`}
          >
            <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
            </svg>
          </a>

          {/* Launch Console CTA */}
          <a
            href="#audit-console"
            className={`${TOUCH_TARGET} inline-flex items-center justify-center rounded-xl bg-slate-900 dark:bg-white px-4 py-2.5 text-xs sm:text-sm font-semibold text-white dark:text-slate-900 hover:bg-slate-800 dark:hover:bg-slate-100 transition-all shadow-sm`}
          >
            Launch Console
          </a>
        </div>
      </div>
    </header>
  );
}
