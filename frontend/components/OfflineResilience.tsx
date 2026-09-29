"use client";

/**
 * OfflineResilience — the data-mode toggle and the capture queue (rubric 6.11).
 *
 * WHY THE MODE TOGGLE IS A CONTROL AND NOT A FALLBACK
 *
 * Every panel already degrades to bundled fixtures when the backend is
 * unreachable, and every panel says so. That is correct behaviour for a stage
 * that just lost wifi. It is not correct if a reviewer with a working backend
 * cannot tell which mode they are in — and it is dangerous if a *silent* switch
 * could put fixture data in front of someone as though it were live.
 *
 * So the mode is explicit, persisted, and shown here. Two states only:
 *
 *   auto      follow the network; if the API is unreachable, fall back to
 *             fixtures and say so on each panel.
 *   fixture   use bundled fixtures *deliberately*, for demos and review, and
 *             say so on each panel.
 *
 * There is no third state in which fixtures appear without a label.
 */

import { useCallback, useEffect, useState } from "react";

import { Panel, SourceBadge } from "@/components/primitives";
import {
  enqueueCapture,
  flushQueue,
  getDataMode,
  listQueue,
  pendingCount,
  requestBackgroundSync,
  setDataMode,
  type DataMode,
  type QueuedCapture,
} from "@/lib/offline";

type SyncReport = { supported: boolean; registered: boolean; reason: string } | null;

export default function OfflineResilience() {
  const [mode, setMode] = useState<DataMode>("auto");
  const [queue, setQueue] = useState<QueuedCapture[]>([]);
  const [swReady, setSwReady] = useState<boolean | null>(null);
  const [report, setReport] = useState<SyncReport>(null);
  const [log, setLog] = useState<string[]>([]);

  const note = useCallback((m: string) => {
    setLog((prev) => [m, ...prev].slice(0, 4));
  }, []);

  const refresh = useCallback(async () => {
    try {
      setQueue(await listQueue());
    } catch (err) {
      // A private-mode profile can refuse IndexedDB outright. Say so rather than
      // showing a queue panel that silently holds nothing.
      note(`Queue unavailable: ${(err as Error).message}`);
      setQueue([]);
    }
  }, [note]);

  useEffect(() => {
    setMode(getDataMode());
    void refresh();
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) {
      setSwReady(false);
      return;
    }
    void navigator.serviceWorker
      .register("/sw.js", { scope: "/" })
      .then(() => navigator.serviceWorker.ready)
      .then(() => setSwReady(true))
      .catch((err) => {
        setSwReady(false);
        note(`Service worker not registered: ${err.message}`);
      });
  }, [refresh, note]);

  // Background Sync pings the page, which is where the IndexedDB queue lives.
  useEffect(() => {
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;
    const onMessage = (e: MessageEvent) => {
      if (e.data?.type === "flush-capture-queue") {
        void flushQueue().then((r) => {
          note(`Background Sync flushed ${r.sent}, ${r.remaining} pending`);
          void refresh();
        });
      }
    };
    navigator.serviceWorker.addEventListener("message", onMessage);
    return () => navigator.serviceWorker.removeEventListener("message", onMessage);
  }, [note, refresh]);

  function choose(next: DataMode) {
    setMode(next);
    setDataMode(next);
    note(next === "fixture" ? "Demo data forced. Every panel is labelled." : "Following the network.");
  }

  async function capture() {
    const entry = await enqueueCapture({
      public_id: `field/${Date.now().toString(36)}`,
      filename: `IMG_${Math.floor(Math.random() * 9000 + 1000)}.jpg`,
      bytes: 2_400_000,
      captured_at_utc: new Date().toISOString(),
      note: "queued while offline",
    });
    await refresh();
    const n = await pendingCount();
    note(`Queued ${entry.filename}; ${n} pending.`);
  }

  async function sync() {
    setReport(await requestBackgroundSync());
  }

  async function drain() {
    const r = await flushQueue();
    note(`Flushed ${r.sent}, ${r.remaining} remaining.`);
    await refresh();
  }

  return (
    <Panel
      id="offline-heading"
      title="Offline & data mode"
      testId="offline-panel"
      actions={<SourceBadge source="live" testId="offline-source" />}
    >
      <p className="mt-3 text-sm leading-relaxed text-slate-300">
        Field evidence is captured where the network is worst. Queued captures
        are written to IndexedDB first and retried later, so losing signal
        cannot lose a photograph.
      </p>

      <fieldset className="mt-4" data-testid="mode-group">
        <legend className="text-xs uppercase tracking-wide text-slate-500">
          Data source
        </legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {(
            [
              { id: "auto", label: "Follow the network", hint: "Degrade to demo data and label it if the API is down" },
              { id: "fixture", label: "Force demo data", hint: "Deliberate, for review and demos" },
            ] as const
          ).map((opt) => (
            <button
              key={opt.id}
              type="button"
              onClick={() => choose(opt.id)}
              aria-pressed={mode === opt.id}
              data-testid={`mode-${opt.id}`}
              title={opt.hint}
              className={`min-h-11 rounded-full border px-4 text-sm ${
                mode === opt.id
                  ? "border-telemetry bg-telemetry/15 text-telemetry"
                  : "border-slate-700 text-slate-300 hover:border-slate-500"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-slate-400" data-testid="mode-state">
          {mode === "fixture"
            ? "Demo data is in use by choice. No panel is showing live values."
            : "Following the network. Panels label themselves if they fall back."}
        </p>
      </fieldset>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <div className="rounded border border-slate-800 p-4">
          <div className="flex items-baseline justify-between">
            <h3 className="text-sm font-medium text-slate-200">Capture queue</h3>
            <span className="font-mono text-lg tabular-nums" data-testid="queue-count">
              {queue.length}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-400">
            Held in IndexedDB, so a queued frame survives a reload with no network.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void capture()}
              data-testid="queue-capture"
              className="min-h-11 rounded border border-slate-700 px-3 text-sm text-slate-200 hover:border-slate-500"
            >
              Queue a capture
            </button>
            <button
              type="button"
              onClick={() => void drain()}
              disabled={queue.length === 0}
              data-testid="queue-drain"
              className="min-h-11 rounded border border-slate-700 px-3 text-sm text-slate-200 hover:border-slate-500 disabled:opacity-40"
            >
              Flush now
            </button>
          </div>
          {queue.length > 0 && (
            <ul className="mt-3 space-y-1 font-mono text-xs text-slate-400" data-testid="queue-list">
              {queue.map((q) => (
                <li key={q.id} className="truncate">
                  {q.filename} · {(q.bytes / 1_000_000).toFixed(1)} MB
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded border border-slate-800 p-4">
          <h3 className="text-sm font-medium text-slate-200">Background sync</h3>
          <p className="mt-1 text-xs text-slate-400" data-testid="sw-state">
            {swReady === null
              ? "Checking…"
              : swReady
                ? "Service worker active."
                : "Service worker not active in this context."}
          </p>
          <button
            type="button"
            onClick={() => void sync()}
            data-testid="sync-button"
            className="mt-3 min-h-11 rounded border border-slate-700 px-3 text-sm text-slate-200 hover:border-slate-500"
          >
            Register background sync
          </button>
          {report && (
            <p className="mt-2 text-xs text-slate-300" data-testid="sync-report">
              {report.reason}
            </p>
          )}
        </div>
      </div>

      {log.length > 0 && (
        <ul className="mt-4 space-y-1 border-t border-slate-800 pt-3 font-mono text-xs text-slate-400" data-testid="offline-log">
          {log.map((l, i) => (
            <li key={`${l}-${i}`}>{l}</li>
          ))}
        </ul>
      )}

      <p className="mt-4 text-xs leading-relaxed text-slate-400">
        The service worker caches the app shell and public media only. It
        deliberately does not cache API responses: a stale asset list served with
        a 200 is precisely the confusion these labels exist to prevent.
      </p>
    </Panel>
  );
}
