import { useState } from "react";
import type { ParkGuide, PlanTarget, SearchResult, TimelinePlan, Trip } from "./types";
import { getTimeline } from "./api";
import SearchPanel from "./components/SearchPanel";
import TripForm from "./components/TripForm";
import TimelineView from "./components/TimelineView";
import LotteryExplorer from "./components/LotteryExplorer";
import ParkExplorer from "./components/ParkExplorer";
import ParkDetail from "./components/ParkDetail";
import Concierge from "./components/Concierge";
import WatchPanel from "./components/WatchPanel";

type Tab = "ideas" | "explore" | "plan" | "watches" | "lotteries";

export default function App() {
  const [tab, setTab] = useState<Tab>("ideas");
  const [openPark, setOpenPark] = useState<string | null>(null);
  const [target, setTarget] = useState<SearchResult | null>(null);
  const [defaultNights, setDefaultNights] = useState<number>(3);
  const [manualPrefill, setManualPrefill] = useState<{ name: string; park: string; type: string } | null>(null);
  const [plan, setPlan] = useState<TimelinePlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** A suggested trip's facility → hand off to the planner. */
  function planFromGuide(t: PlanTarget, park: ParkGuide, trip: Trip) {
    setPlan(null);
    setError(null);
    setDefaultNights(trip.nights);
    if (t.rec_gov_id) {
      setTarget({
        id: t.rec_gov_id,
        name: t.name,
        entity_type: t.entity_type,
        parent_name: `${park.name} National Park`,
      });
      setManualPrefill(null);
    } else {
      // No confirmed ID — open the planner with the name pre-filled so the
      // user completes it via search or the recreation.gov URL.
      setTarget(null);
      setManualPrefill({ name: t.name, park: `${park.name} National Park`, type: t.entity_type });
    }
    setTab("plan");
  }

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

  function resetPlanner() {
    setTarget(null);
    setPlan(null);
    setError(null);
    setManualPrefill(null);
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <img src="/icon.svg" alt="" width={40} height={40} />
          <div>
            <h1>Trailhead</h1>
            <p>National parks, planned to the minute</p>
          </div>
        </div>
        <nav className="tabs">
          <button className={tab === "ideas" ? "active" : ""} onClick={() => setTab("ideas")}>
            Trip ideas
          </button>
          <button className={tab === "explore" ? "active" : ""} onClick={() => setTab("explore")}>
            Explore parks
          </button>
          <button className={tab === "plan" ? "active" : ""} onClick={() => setTab("plan")}>
            Plan a booking
          </button>
          <button className={tab === "watches" ? "active" : ""} onClick={() => setTab("watches")}>
            Watches
          </button>
          <button className={tab === "lotteries" ? "active" : ""} onClick={() => setTab("lotteries")}>
            Lotteries
          </button>
        </nav>
      </header>

      <main className="content">
        {tab === "watches" && <WatchPanel />}
        {tab === "ideas" && (
          <Concierge
            onOpenPark={(slug) => {
              setOpenPark(slug);
              setTab("explore");
            }}
          />
        )}

        {tab === "explore" &&
          (openPark ? (
            <ParkDetail slug={openPark} onBack={() => setOpenPark(null)} onPlanTarget={planFromGuide} />
          ) : (
            <ParkExplorer onOpen={setOpenPark} />
          ))}

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
              <SearchPanel onSelect={setTarget} prefill={manualPrefill} />
            ) : (
              <div className="planning">
                <div className="selected-bar">
                  <div>
                    <span className={`badge ${target.entity_type}`}>{target.entity_type}</span>
                    <strong>{target.name}</strong>
                    {target.parent_name && <span className="muted"> · {target.parent_name}</span>}
                  </div>
                  <button className="link" onClick={resetPlanner}>
                    Change
                  </button>
                </div>

                <TripForm loading={loading} onBuild={buildTimeline} defaultNights={defaultNights} />
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
          Booking rules, lottery dates, and guide details are best-effort and change yearly — always
          confirm on{" "}
          <a href="https://www.recreation.gov" target="_blank" rel="noreferrer">
            recreation.gov
          </a>{" "}
          and the official park sites.
        </p>
      </footer>
    </div>
  );
}
