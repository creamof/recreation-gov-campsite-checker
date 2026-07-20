import { Fragment, useEffect, useRef, useState } from "react";
import type { ConciergeResponse, TimelinePlan, TripOption } from "../types";
import { askConcierge, preparePlan } from "../api";
import ParkArt from "./ParkArt";
import TimelineView from "./TimelineView";

const EXAMPLES = [
  "Waterfalls and granite in Yosemite with the kids in July",
  "I finally want to summit Half Dome this summer",
  "Somewhere with geysers and wildlife in June",
  "Desert stargazing weekend with friends this winter",
];

const STATUS_META: Record<string, { label: string; cls: string }> = {
  "act-now": { label: "act now", cls: "timing-act" },
  upcoming: { label: "upcoming", cls: "timing-upcoming" },
  passed: { label: "passed", cls: "timing-passed" },
  info: { label: "note", cls: "timing-info" },
};

export default function Concierge({ onOpenPark }: { onOpenPark: (slug: string) => void }) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<ConciergeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [plan, setPlan] = useState<TimelinePlan | null>(null);
  const [planFor, setPlanFor] = useState<string | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);
  const planRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (plan) planRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [plan]);

  async function ask(text?: string) {
    const q = (text ?? query).trim();
    if (!q) return;
    if (text) setQuery(text);
    setLoading(true);
    setError(null);
    setPlan(null);
    setPlanFor(null);
    try {
      // Month/season is parsed straight from the free text by the backend.
      setResult(await askConcierge({ query: q }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  async function buildPrep(opt: TripOption) {
    setPlanLoading(true);
    setPlanFor(`${opt.park_slug}:${opt.trip_title}`);
    setPlanError(null);
    setPlan(null);
    try {
      const monthNum = result ? new Date(result.arrival + "T00:00:00").getMonth() + 1 : undefined;
      const yearNum = result ? new Date(result.arrival + "T00:00:00").getFullYear() : undefined;
      setPlan(
        await preparePlan({
          park_slug: opt.park_slug,
          trip_title: opt.trip_title,
          month: monthNum,
          year: yearNum,
        })
      );
    } catch (e) {
      // A bare "Failed to fetch" almost always means the server never
      // answered — the most common cause on a free-tier host is that the
      // instance was asleep and is still waking up.
      const raw = e instanceof Error ? e.message : "Could not build the prep calendar.";
      const hint = /failed to fetch|networkerror|load failed/i.test(raw)
        ? "Couldn't reach the server. If this app was just deployed (or has been idle a while) it may still be waking up — wait a few seconds and try again."
        : raw;
      setPlanError(hint);
    } finally {
      setPlanLoading(false);
    }
  }

  return (
    <section className="concierge">
      <div className="hero">
        <p className="eyebrow">Trip concierge</p>
        <h2>Tell me what you're dreaming about.</h2>
        <p className="lede">
          A place, a month, a vibe — in your own words. You'll get curated trips that fit, with the
          booking windows and lottery deadlines already worked out, and reminders you can put on
          your calendar.
        </p>
      </div>

      <div className="ask-box card">
        <textarea
          rows={2}
          placeholder='e.g. "Waterfalls in Yosemite with the kids in July" or "finally do Half Dome this summer"'
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              ask();
            }
          }}
        />
        <div className="ask-controls">
          <p className="muted small">
            Mention a month or season if you have one in mind — "in July", "this summer" — or leave
            it out and I'll suggest the best timing.
          </p>
          <button className="primary slim" onClick={() => ask()} disabled={loading || !query.trim()}>
            {loading ? "Thinking…" : "Find my trips"}
          </button>
        </div>
        {!result && (
          <div className="examples">
            {EXAMPLES.map((ex) => (
              <button key={ex} className="example-chip" onClick={() => ask(ex)}>
                {ex}
              </button>
            ))}
          </div>
        )}
      </div>

      {error && <div className="error">{error}</div>}

      {result && (
        <>
          <div className="intent-echo">
            <span className="chip">Heard: {result.intent.summary}</span>
            <span className="chip">Planning for {result.target_month}</span>
            {result.engine === "claude" && <span className="chip chip-high">AI parsed</span>}
          </div>

          <div className="option-list">
            {result.options.map((opt) => {
              const key = `${opt.park_slug}:${opt.trip_title}`;
              const active = planFor === key;
              return (
                <Fragment key={key}>
                  <article className={`option-card card ${active ? "active" : ""}`}>
                    <button className="option-art" onClick={() => onOpenPark(opt.park_slug)} title={`Open the ${opt.park_name} guide`}>
                      <ParkArt slug={opt.park_slug} />
                    </button>
                    <div className="option-body">
                      <div className="option-head">
                        <div>
                          <p className="eyebrow">{opt.park_name} · {opt.state}</p>
                          <h3>{opt.trip_title}</h3>
                        </div>
                        <span className={`chip style-${opt.style}`}>{opt.style}</span>
                      </div>
                      <p className="muted">{opt.summary}</p>
                      <ul className="why-list">
                        {opt.why.map((w, i) => (
                          <li key={i}>{w}</li>
                        ))}
                      </ul>
                      <div className="timing-list">
                        {opt.timing.map((t, i) => (
                          <div key={i} className={`timing-item ${STATUS_META[t.status]?.cls ?? ""}`}>
                            <span className="timing-status">{STATUS_META[t.status]?.label ?? t.status}</span>
                            <div>
                              <strong>{t.label}</strong>
                              <p className="muted small">{t.detail}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                      <button
                        className="primary slim"
                        onClick={() => buildPrep(opt)}
                        disabled={planLoading}
                        aria-busy={active && planLoading}
                      >
                        {active && planLoading ? "Building…" : "📅 Build my prep calendar"}
                      </button>
                      {active && planError && (
                        <div className="error" role="alert">
                          {planError}{" "}
                          <button className="link" onClick={() => buildPrep(opt)}>
                            Retry
                          </button>
                        </div>
                      )}
                    </div>
                  </article>
                  {active && plan && (
                    <div className="prep-plan" ref={planRef}>
                      <TimelineView plan={plan} />
                    </div>
                  )}
                </Fragment>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}
