import { useState } from "react";
import type { SearchResult, TimelinePlan } from "./types";
import { getTimeline } from "./api";
import SearchPanel from "./components/SearchPanel";
import TripForm from "./components/TripForm";
import TimelineView from "./components/TimelineView";
import LotteryExplorer from "./components/LotteryExplorer";

type Tab = "plan" | "lotteries";

export default function App() {
  const [tab, setTab] = useState<Tab>("plan");
  const [target, setTarget] = useState<SearchResult | null>(null);
  const [plan, setPlan] = useState<TimelinePlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function buildTimeline(input: {
    arrival: string;
    departure: string;
    force_strategy?: "campground" | "lottery";
  }) {
    if (!target) return;
    setLoading(true);
    setError(null);
    try {
      const p = await getTimeline({
        id: target.id,
        name: target.name,
        entity_type: target.entity_type,
        parent_name: target.parent_name ?? null,
        ...input,
      });
      setPlan(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong building the timeline.");
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setTarget(null);
    setPlan(null);
    setError(null);
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <img src="/icon.svg" alt="" width={34} height={34} />
          <div>
            <h1>Trailhead</h1>
            <p>Campsite &amp; backcountry booking planner</p>
          </div>
        </div>
        <nav className="tabs">
          <button className={tab === "plan" ? "active" : ""} onClick={() => setTab("plan")}>
            Plan a trip
          </button>
          <button className={tab === "lotteries" ? "active" : ""} onClick={() => setTab("lotteries")}>
            Browse lotteries
          </button>
        </nav>
      </header>

      <main className="content">
        {tab === "plan" && (
          <>
            {!target && (
              <section className="intro">
                <h2>When should you book to actually get the spot?</h2>
                <p>
                  Pick a campground or a backcountry permit, choose your dates, and get an exact
                  timeline — when the reservation window opens, when a lottery closes, and what to do
                  on each date so you don't miss it.
                </p>
              </section>
            )}

            {!target ? (
              <SearchPanel onSelect={setTarget} />
            ) : (
              <div className="planning">
                <div className="selected-bar">
                  <div>
                    <span className={`badge ${target.entity_type}`}>{target.entity_type}</span>
                    <strong>{target.name}</strong>
                    {target.parent_name && <span className="muted"> · {target.parent_name}</span>}
                  </div>
                  <button className="link" onClick={reset}>
                    Change
                  </button>
                </div>

                <TripForm loading={loading} onBuild={buildTimeline} />
                {error && <div className="error">{error}</div>}
                {plan && <TimelineView plan={plan} />}
              </div>
            )}
          </>
        )}

        {tab === "lotteries" && <LotteryExplorer />}
      </main>

      <footer className="footer">
        <p>
          Booking rules and lottery dates are best-effort and change yearly — always confirm on{" "}
          <a href="https://www.recreation.gov" target="_blank" rel="noreferrer">
            recreation.gov
          </a>
          . Milestone 1 of 2: the timeline planner. Next up: last-minute availability alerts.
        </p>
      </footer>
    </div>
  );
}
