import { useCallback, useEffect, useRef, useState } from "react";
import type { Watch } from "../types";
import {
  checkWatch,
  createWatch,
  deleteWatch,
  dismissWatchAlert,
  getPushConfig,
  getWatches,
  subscribePush,
} from "../api";

const POLL_MS = 45_000;

const STATUS_META: Record<Watch["status"], { label: string; cls: string }> = {
  available: { label: "sites open!", cls: "st-available" },
  unavailable: { label: "sold out", cls: "st-unavailable" },
  unknown: { label: "checking…", cls: "st-unknown" },
  error: { label: "check failed", cls: "st-error" },
  expired: { label: "trip passed", cls: "st-expired" },
};

function fmtDate(iso: string): string {
  return new Date(iso + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function fmtTime(iso: string | null): string {
  if (!iso) return "never";
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

function urlB64ToUint8(base64: string): Uint8Array {
  const pad = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

export default function WatchPanel() {
  const [watches, setWatches] = useState<Watch[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notifState, setNotifState] = useState<NotificationPermission | "unsupported">(
    typeof Notification === "undefined" ? "unsupported" : Notification.permission
  );
  const [pushReady, setPushReady] = useState(false);
  const knownAlerts = useRef<Set<string>>(new Set());

  // Fire an OS notification for alerts we haven't announced yet.
  const announceNewAlerts = useCallback(async (list: Watch[]) => {
    const fresh = list.filter((w) => w.alert && !knownAlerts.current.has(`${w.id}:${w.alert.at}`));
    for (const w of fresh) {
      knownAlerts.current.add(`${w.id}:${w.alert!.at}`);
      if (typeof Notification !== "undefined" && Notification.permission === "granted") {
        try {
          const reg = await navigator.serviceWorker?.ready;
          await reg?.showNotification(`🏕 ${w.name}: site available!`, {
            body: `${w.alert!.available} site(s) open for ${fmtDate(w.arrival)} – book before it's gone.`,
            icon: "/icon.svg",
            badge: "/icon.svg",
            data: { url: `https://www.recreation.gov/camping/campgrounds/${w.campground_id}` },
          });
        } catch {
          /* notification is best-effort */
        }
      }
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      const res = await getWatches();
      setWatches(res.watches);
      setError(null);
      void announceNewAlerts(res.watches);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load watches.");
    }
  }, [announceNewAlerts]);

  useEffect(() => {
    // Seed known alerts so we don't re-notify old ones on page load.
    getWatches()
      .then((res) => {
        res.watches.forEach((w) => w.alert && knownAlerts.current.add(`${w.id}:${w.alert.at}`));
        setWatches(res.watches);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load watches."));
    const t = setInterval(refresh, POLL_MS);
    return () => clearInterval(t);
  }, [refresh]);

  async function enableNotifications() {
    if (typeof Notification === "undefined") return;
    const perm = await Notification.requestPermission();
    setNotifState(perm);
    if (perm !== "granted") return;
    // Progressive enhancement: real Web Push if the server has VAPID keys.
    try {
      const cfg = await getPushConfig();
      if (cfg.enabled && cfg.public_key && "serviceWorker" in navigator) {
        const reg = await navigator.serviceWorker.ready;
        const sub =
          (await reg.pushManager.getSubscription()) ??
          (await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlB64ToUint8(cfg.public_key).buffer as ArrayBuffer,
          }));
        await subscribePush(sub);
        setPushReady(true);
      }
    } catch {
      /* in-app notifications still work without push */
    }
  }

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  const alerts = watches.filter((w) => w.alert);

  return (
    <section className="watches">
      <div className="hero">
        <p className="eyebrow">Cancellation watch</p>
        <h2>Sold out isn't the end of the story.</h2>
        <p className="lede">
          People cancel constantly. Watch a campground for your dates and the moment sites free up
          you'll see it here — and get a notification so you can grab it.
        </p>
      </div>

      {notifState !== "granted" && notifState !== "unsupported" && (
        <div className="notice notif-cta">
          <span>Get an OS notification the moment a site opens up.</span>
          <button className="primary slim" onClick={enableNotifications}>
            🔔 Enable notifications
          </button>
        </div>
      )}
      {notifState === "granted" && (
        <p className="muted small">
          ✅ Notifications on{pushReady ? " (server push active — works even when the app is closed)" : " while the app is open"}.
        </p>
      )}

      {alerts.length > 0 && (
        <div className="alert-banner">
          {alerts.map((w) => (
            <div key={w.id} className="alert-row">
              <div>
                <strong>🎉 {w.name} has {w.alert!.available} site(s) open</strong>
                <span className="muted"> for {fmtDate(w.arrival)} → {fmtDate(w.departure)}</span>
              </div>
              <div className="alert-actions">
                <a
                  className="primary slim book-link"
                  href={`https://www.recreation.gov/camping/campgrounds/${w.campground_id}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Book it now →
                </a>
                <button className="link" onClick={() => act(() => dismissWatchAlert(w.id))}>
                  dismiss
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <NewWatchForm onCreate={(body) => act(() => createWatch(body))} busy={busy} />

      {error && <div className="error">{error}</div>}

      <div className="watch-list">
        {watches.length === 0 && (
          <p className="muted">No watches yet. Add the campground you couldn't get — cancellations happen every day.</p>
        )}
        {watches.map((w) => {
          const meta = STATUS_META[w.status];
          return (
            <article key={w.id} className={`watch-card card ${w.alert ? "has-alert" : ""}`}>
              <div className="watch-main">
                <div className="watch-title">
                  <strong>{w.name}</strong>
                  <span className="muted small"> · #{w.campground_id}</span>
                </div>
                <span className="muted small">
                  {fmtDate(w.arrival)} → {fmtDate(w.departure)}
                </span>
              </div>
              <div className="watch-status">
                <span className={`status-pill ${meta.cls}`}>{meta.label}</span>
                {w.available != null && w.total != null && w.status !== "error" && (
                  <span className="muted small">{w.available}/{w.total} sites</span>
                )}
                <span className="muted small">checked {fmtTime(w.last_checked)}</span>
              </div>
              <div className="watch-actions">
                <button className="link" onClick={() => act(() => checkWatch(w.id))} disabled={busy}>
                  check now
                </button>
                <button className="link danger" onClick={() => act(() => deleteWatch(w.id))} disabled={busy}>
                  remove
                </button>
              </div>
              {w.status === "error" && w.error && (
                <p className="muted small watch-error">Last check failed: {w.error}</p>
              )}
            </article>
          );
        })}
      </div>

      <p className="muted small">
        The server re-checks every watch automatically (every 5 minutes by default). Keep the
        backend running — that's what does the watching.
      </p>
    </section>
  );
}

function NewWatchForm({
  onCreate,
  busy,
}: {
  onCreate: (body: { campground_id: string; name: string; arrival: string; departure: string }) => void;
  busy: boolean;
}) {
  const [name, setName] = useState("");
  const [cgId, setCgId] = useState("");
  const [arrival, setArrival] = useState("");
  const [departure, setDeparture] = useState("");
  const valid = cgId.trim().match(/^\d+$/) && arrival && departure && departure > arrival;

  return (
    <form
      className="card new-watch"
      onSubmit={(e) => {
        e.preventDefault();
        if (!valid) return;
        onCreate({
          campground_id: cgId.trim(),
          name: name.trim() || `Campground ${cgId.trim()}`,
          arrival,
          departure,
        });
        setName("");
        setCgId("");
      }}
    >
      <h3>Watch a campground</h3>
      <p className="muted small">
        The ID is the number in the recreation.gov URL: <code>/camping/campgrounds/<b>232447</b></code>
      </p>
      <div className="grid2">
        <label>
          Campground name
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Upper Pines" />
        </label>
        <label>
          Recreation.gov ID
          <input value={cgId} onChange={(e) => setCgId(e.target.value)} placeholder="232447" inputMode="numeric" />
        </label>
        <label>
          Arrival
          <input type="date" value={arrival} onChange={(e) => setArrival(e.target.value)} />
        </label>
        <label>
          Departure
          <input type="date" value={departure} onChange={(e) => setDeparture(e.target.value)} />
        </label>
      </div>
      <button className="primary" type="submit" disabled={!valid || busy}>
        {busy ? "Adding…" : "Start watching"}
      </button>
    </form>
  );
}
