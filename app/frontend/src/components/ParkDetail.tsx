import { useEffect, useState } from "react";
import type { ParkGuide, PlanTarget, Trip } from "../types";
import { getPark } from "../api";
import ParkArt from "./ParkArt";

const STYLE_LABEL: Record<string, string> = {
  classic: "Classic",
  backcountry: "Backcountry",
  family: "Family",
  adventure: "Adventure",
};

const ACTIVITY_ICON: Record<string, string> = {
  hike: "🥾",
  scenic: "🏞️",
  water: "🛶",
  wildlife: "🦌",
  town: "🏘️",
  night: "🌌",
};

interface Props {
  slug: string;
  onBack: () => void;
  onPlanTarget: (target: PlanTarget, park: ParkGuide, trip: Trip) => void;
}

export default function ParkDetail({ slug, onBack, onPlanTarget }: Props) {
  const [park, setPark] = useState<ParkGuide | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setPark(null);
    getPark(slug)
      .then((p) => alive && setPark(p))
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [slug]);

  if (error) return <div className="error">{error}</div>;
  if (!park) return <div className="loading-block">Loading the guide…</div>;

  return (
    <article className="park-detail">
      <button className="link back" onClick={onBack}>
        ← All parks
      </button>

      <header className="park-hero">
        <div className="park-hero-art">
          <ParkArt slug={park.slug} />
        </div>
        <div className="park-hero-text">
          <p className="eyebrow">
            {park.state} · est. {park.established}
          </p>
          <h2>{park.name}</h2>
          <p className="tagline">{park.tagline}</p>
          <p className="lede">{park.description}</p>
          <div className="fact-row">
            <div className="fact">
              <span className="fact-label">Best seasons</span>
              <span>{park.best_seasons}</span>
            </div>
            <div className="fact">
              <span className="fact-label">Beat the crowds</span>
              <span>{park.crowd_tip}</span>
            </div>
          </div>
          <a className="verify" href={park.official_url} target="_blank" rel="noreferrer">
            Official park site →
          </a>
        </div>
      </header>

      {/* ---- Suggested trips ---- */}
      <section className="guide-section">
        <h3 className="section-title">Suggested trips</h3>
        <div className="trip-cards">
          {park.trips.map((trip) => (
            <div key={trip.title} className="trip-card card">
              <div className="trip-card-head">
                <span className={`chip style-${trip.style}`}>{STYLE_LABEL[trip.style] ?? trip.style}</span>
                <span className="muted small">
                  {trip.nights} night{trip.nights > 1 ? "s" : ""} · {trip.best_months}
                </span>
              </div>
              <h4>{trip.title}</h4>
              <p className="muted">{trip.summary}</p>
              <ol className="itinerary">
                {trip.itinerary.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
              <div className="trip-targets">
                {trip.targets.map((t) => (
                  <button
                    key={t.name}
                    className="target-btn"
                    onClick={() => onPlanTarget(t, park, trip)}
                    title={t.note || undefined}
                  >
                    <span className={`badge ${t.entity_type}`}>{t.entity_type}</span>
                    <span className="target-name">{t.name}</span>
                    <span className="target-plan">Plan booking →</span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className="guide-columns">
        {/* ---- Things to do ---- */}
        <section className="guide-section">
          <h3 className="section-title">Beyond the campsite</h3>
          <ul className="feature-list">
            {park.activities.map((a) => (
              <li key={a.name}>
                <span className="feature-icon">{ACTIVITY_ICON[a.kind] ?? "📍"}</span>
                <div>
                  <strong>{a.name}</strong>
                  <p className="muted">{a.detail}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>

        {/* ---- Eats ---- */}
        <section className="guide-section">
          <h3 className="section-title">Eat well</h3>
          <ul className="feature-list">
            {park.eats.map((e) => (
              <li key={e.name}>
                <span className="feature-icon">🍽️</span>
                <div>
                  <strong>{e.name}</strong>
                  <span className="muted small"> — {e.where}</span>
                  <p className="muted">{e.detail}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>

      {/* ---- Camp logistics ---- */}
      <section className="guide-section">
        <h3 className="section-title">Camp logistics</h3>
        <div className="logistics-grid">
          <div className="card logistics-card">
            <h4>🚿 Showers</h4>
            <ul>
              {park.amenities.showers.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </div>
          <div className="card logistics-card">
            <h4>🧺 Laundry</h4>
            <ul>
              {park.amenities.laundry.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </div>
          <div className="card logistics-card">
            <h4>🛒 Resupply</h4>
            <ul>
              {park.amenities.groceries.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </div>
          <div className="card logistics-card">
            <h4>📶 Connectivity</h4>
            <p>{park.amenities.connectivity}</p>
            {park.amenities.heads_up && (
              <p className="heads-up">⚠️ {park.amenities.heads_up}</p>
            )}
          </div>
        </div>
        <p className="muted small curation-note">
          Guide details are curated and can drift season to season — confirm hours and availability
          with the park before you rely on them.
        </p>
      </section>
    </article>
  );
}
