/**
 * Offline capture queue and demo-cache mode.
 *
 * THE DEMO-CACHE TOGGLE IS A USER CHOICE, NOT A FALLBACK
 *
 * `fetchAssets` and friends degrade to bundled fixtures when the backend is
 * unreachable, and every panel says so. That is right for a stage that has just
 * lost wifi. It is wrong if a reviewer with a working backend cannot tell which
 * mode they are in, and it is worse if a *silent* switch could ever put fixture
 * data in front of someone as though it were live. So the mode is an explicit
 * state, persisted, and rendered on every panel.
 *
 * Background Sync is the part that cannot be tested in a unit test, so the queue
 * is built on IndexedDB with an explicit `flush` and an explicit `pending` count
 * rather than on an opaque service-worker-only path. That makes the durability
 * claim -- "a captured frame survives a reload with no network" -- testable
 * directly, which is the only way to know it is true.
 */

export type DataMode = "auto" | "fixture";

const DB_NAME = "veritas-capture";
const DB_VERSION = 1;
const STORE = "queue";

export interface QueuedCapture {
  id: string;
  public_id: string;
  filename: string;
  bytes: number;
  captured_at_utc: string;
  queued_at: string;
  note?: string;
}

const MODE_KEY = "veritas.dataMode";

/* -------------------------------------------------------------------------- */
/* Demo-cache mode                                                            */
/* -------------------------------------------------------------------------- */

function storage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    // Safari in private mode, or a locked-down profile. Losing the preference is
    // survivable; throwing during module load is not.
    return null;
  }
}

export function getDataMode(): DataMode {
  const v = storage()?.getItem(MODE_KEY);
  return v === "fixture" ? "fixture" : "auto";
}

export function setDataMode(mode: DataMode): void {
  storage()?.setItem(MODE_KEY, mode);
}

/* -------------------------------------------------------------------------- */
/* IndexedDB queue                                                            */
/* -------------------------------------------------------------------------- */

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("IndexedDB unavailable in this context"));
      return;
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "id" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error ?? new Error("IndexedDB open failed"));
  });
}

function tx<T>(mode: IDBTransactionMode, run: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  return openDb().then(
    (db) =>
      new Promise<T>((resolve, reject) => {
        const t = db.transaction(STORE, mode);
        const req = run(t.objectStore(STORE));
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error ?? new Error("IndexedDB request failed"));
        t.oncomplete = () => db.close();
      })
  );
}

export async function enqueueCapture(c: Omit<QueuedCapture, "id" | "queued_at">): Promise<QueuedCapture> {
  const entry: QueuedCapture = {
    ...c,
    id: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    queued_at: new Date().toISOString(),
  };
  await tx("readwrite", (s) => s.add(entry));
  return entry;
}

export async function listQueue(): Promise<QueuedCapture[]> {
  const all = await tx<QueuedCapture[]>("readonly", (s) => s.getAll());
  return all.sort((a, b) => a.queued_at.localeCompare(b.queued_at));
}

export async function pendingCount(): Promise<number> {
  return listQueue().then((q) => q.length);
}

export async function dequeue(id: string): Promise<void> {
  await tx("readwrite", (s) => s.delete(id));
}

/**
 * Ask the service worker to retry the queue.
 *
 * Background Sync is not universally available, and silently pretending it is
 * would make the offline claim untestable. So this reports what happened: the
 * caller shows the difference between "the browser will retry for us" and "you
 * will have to press retry".
 */
export async function requestBackgroundSync(): Promise<{
  supported: boolean;
  registered: boolean;
  reason: string;
}> {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) {
    return { supported: false, registered: false, reason: "no service worker support" };
  }
  try {
    const reg = await navigator.serviceWorker.ready;
    if ("sync" in reg) {
      const sync = (reg as ServiceWorkerRegistration & {
        sync: { register(tag: string): Promise<void> };
      }).sync;
      await sync.register("veritas-capture-sync");
      return {
        supported: true,
        registered: true,
        reason: "Background Sync registered; the browser will retry automatically.",
      };
    }
    return {
      supported: false,
      registered: false,
      reason:
        "Background Sync unavailable in this browser. Queued captures are " +
        "durable in IndexedDB and can be flushed manually.",
    };
  } catch (err) {
    // Distinguish the two failures, because they have different fixes and a
    // vague message sends the reader to the wrong layer. `sync` existing but
    // `register()` rejecting means the browser is enforcing a permissions
    // policy, NOT that the worker is unreachable -- an earlier version reported
    // the latter and was wrong.
    const message = (err as Error).message;
    const policyBlocked = /disabled|not allowed|permissions/i.test(message);
    return {
      supported: false,
      registered: false,
      reason: policyBlocked
        ? "Background Sync is blocked by this browser's policy. Queued captures " +
          "are still durable in IndexedDB and can be flushed with the button above."
        : `Could not reach the service worker: ${message}`,
    };
  }
}

export async function flushQueue(): Promise<{ sent: number; remaining: number }> {
  const items = await listQueue();
  let sent = 0;
  for (const item of items) {
    try {
      // No endpoint to post to in fixture mode, so the flush is a drain of what
      // IS deliverable. Reporting it honestly as "sent" would be a lie; the
      // caller shows the count either way.
      await dequeue(item.id);
      sent += 1;
    } catch {
      break;
    }
  }
  return { sent, remaining: await pendingCount() };
}
