import { useCallback, useEffect, useState } from "react";
import type { ParkGuide, PlanTarget, SearchResult, TimelinePlan, Trip } from "./types";
import { getTimeline, getWatches } from "./api";
import { loadPersisted, savePersisted } from "./lib/persistedState";
import SearchPanel from "./components/SearchPanel";
import TripForm from "./components/TripForm";
import TimelineView from "./components/TimelineView";
import LotteryExplorer from "./components/LotteryExplorer";
import ParkExplorer from "./components/ParkExplorer";
import ParkDetail from "./components/ParkDetail";
import Concierge from "./components/Concierge";
import WatchPanel from "./components/WatchPanel";

type Tab = "plan" | "explore" | "watches";

type ManualPrefill = { name: string; park: string; type: string } | null;

interface PersistedPlannerState {
  tab: Tab;
  openPark: string | null;
  target: SearchResult | null;
  manualPrefill: ManualPrefill;
  plan: TimelinePlan | null;
  arrival: string | null;
  departure: string | null;
}

const PLANNER_STATE_KEY = "trailhead.plannerState.v1";

const DEFAULT_PLANNER_STATE: PersistedPlannerState = {
  tab: "plan",
  openPark: null,
  target: null,
  manualPrefill: null,
  plan: null,
  arrival: null,
  departure: null,
};

const todayISO = () => new Date().toISOString().slice(0, 10);

/** Map tab values persisted before the nav collapsed from 5 tabs to 2 + bell. */
function migrateTab(t: unknown): Tab {
  if (t === "explore" || t === "lotteries") return "explore";
  if (t === "watches") return "watches";
  return "plan"; // "ideas", "plan", or anything unrecognized
}

/** Load the persisted snapshot, dropping a stale plan/dates whose arrival has already passed. */
function loadInitialPlannerState(): PersistedPlannerState {
  const stored = loadPersisted<Partial<PersistedPlannerState>>(PLANNER_STATE_KEY, {});
  const state: PersistedPlannerState = { ...DEFAULT_PLANNER_STATE, ...stored, tab: migrateTab(stored.tab) };
  if (state.arrival && state.arrival < todayISO()) {
    // The restored trip already happened — keep the target so the user only
    // has to re-pick dates, but don't show a booking timeline for the past.
    state.plan = null;
    state.arrival = null;
    state.departure = null;
  }
  return state;
}

export default function App() {
  const [initial] = useState(loadInitialPlannerState);
  const [tab, setTab] = useState<Tab>(initial.tab);
  const [openPark, setOpenPark] = useState<string | null>(initial.openPark);
  const [showLotteries, setShowLotteries] = useState(false);
  const [showDirect, setShowDirect] = useState(initial.manualPrefill != null);
  const [target, setTarget] = useState<SearchResult | null>(initial.target);
  const [defaultNights, setDefaultNights] = useState<number>(3);
  const [manualPrefill, setManualPrefill] = useState<ManualPrefill>(initial.manualPrefill);
  const [plan, setPlan] = useState<TimelinePlan | null>(initial.plan);
  const [arrival, setArrival] = useState<string | null>(initial.arrival);
  const [departure, setDeparture] = useState<string | null>(initial.departure);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [alertCount, setAlertCount] = useState(0);

  useEffect(() => {
    savePersisted<PersistedPlannerState>(PLANNER_STATE_KEY, {
      tab,
      openPark,
      target,
      manualPrefill,
      plan,
      arrival,
      departure,
    });
  }, [tab, openPark, target, manualPrefill, plan, arrival, departure]);

  // Keep the bell's alert badge fresh so a fired watch is visible from anywhere.
  const refreshWatchBadge = useCallback(async () => {
    try {
      const res = await getWatches();
      setAlertCount(res.watches.filter((w) => w.alert).length);
    } catch {
      /* badge is best-effort */
    }
  }, []);

  useEffect(() => {
    void refreshWatchBadge();
    const t = setInterval(refreshWatchBadge, 90_000);
    return () => clearInterval(t);
  }, [refreshWatchBadge]);

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
      setShowDirect(true);
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
    setArrival(null);
    setDeparture(null);
    // Write the cleared snapshot immediately rather than waiting on the
    // persistence effect, so declining a plan can't leave stale data behind.
    savePersisted<PersistedPlannerState>(PLANNER_STATE_KEY, {
      tab,
      openPark,
      target: null,
      manualPrefill: null,
      plan: null,
      arrival: null,
      departure: null,
    });
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
        <div className="nav-row">
          <nav className="tabs">
            <button className={tab === "plan" ? "active" : ""} onClick={() => setTab("plan")}>
              Plan a trip
            </button>
            <button className={tab === "explore" ? "active" : ""} onClick={() => setTab("explore")}>
              Explore parks
            </button>
          </nav>
          <button
            className={`bell-btn ${tab === "watches" ? "active" : ""}`}
            onClick={() => setTab("watches")}
            title="Cancellation watches"
            aria-label="Cancellation watches"
          >
            🔔
            {alertCount > 0 && <span className="bell-badge">{alertCount}</span>}
          </button>
        </div>
      </header>

      <main className="content">
        {tab === "watches" && <WatchPanel />}

        {tab === "plan" &&
          (!target ? (
            <>
              <Concierge
                onOpenPark={(slug) => {
                  setOpenPark(slug);
                  setShowLotteries(false);
                  setTab("explore");
                }}
              />
              <section className="direct-plan card">
                <div className="direct-head">
                  <div>
                    <strong>Already know the exact campground or permit?</strong>
                    <p className="muted small">
                      Skip the ideas — search it directly and get your booking timeline.
                    </p>
                  </div>
                  <button className="primary slim" onClick={() => setShowDirect((s) => !s)}>
                    {showDirect ? "Hide" : "Search directly"}
                  </button>
                </div>
                {showDirect && <SearchPanel onSelect={setTarget} prefill={manualPrefill} />}
              </section>
            </>
          ) : (
            <div className="planning">
              <div className="selected-bar">
                <div className="selected-facility">
                  <span className={`badge ${target.entity_type}`}>{target.entity_type}</span>
                  <div className="selected-text">
                    <strong>{target.name}</strong>
                    {target.parent_name && <span className="muted">{target.parent_name}</span>}
                  </div>
                </div>
                <button className="link" onClick={resetPlanner}>
                  Change
                </button>
              </div>

              <TripForm
                loading={loading}
                onBuild={buildTimeline}
                defaultNights={defaultNights}
                initialArrival={arrival}
                initialDeparture={departure}
                onDatesChange={(a, d) => {
                  setArrival(a);
                  setDeparture(d);
                }}
              />
              {error && <div className="error">{error}</div>}
              {plan && (
                <TimelineView
                  plan={plan}
                  onOpenWatches={() => setTab("watches")}
                  onWatchCreated={refreshWatchBadge}
                />
              )}
            </div>
          ))}

        {tab === "explore" &&
          (openPark ? (
            <ParkDetail slug={openPark} onBack={() => setOpenPark(null)} onPlanTarget={planFromGuide} />
          ) : showLotteries ? (
            <div>
              <button className="link back" onClick={() => setShowLotteries(false)}>
                ← All parks
              </button>
              <LotteryExplorer />
            </div>
          ) : (
            <>
              <ParkExplorer onOpen={setOpenPark} />
              <section className="card lottery-link-card">
                <div>
                  <strong>Chasing a backcountry permit instead?</strong>
                  <p className="muted small">
                    Half Dome, The Wave, Angels Landing… browse every big lottery's application
                    windows and key dates.
                  </p>
                </div>
                <button className="primary slim" onClick={() => setShowLotteries(true)}>
                  Browse lotteries
                </button>
              </section>
            </>
          ))}
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
