import { useEffect, useState } from "react";
import type { ParkSummary } from "../types";
import { getParks } from "../api";
import ParkArt from "./ParkArt";

export default function ParkExplorer({ onOpen }: { onOpen: (slug: string) => void }) {
  const [parks, setParks] = useState<ParkSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getParks()
      .then((r) => alive && setParks(r.parks))
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <section className="explore">
      <div className="hero">
        <p className="eyebrow">Field guide · Eight flagship parks</p>
        <h2>
          Where to go, when to book,
          <br />
          and where the hot showers are.
        </h2>
        <p className="lede">
          Curated trips wired straight into the booking-timeline planner — plus the trail food,
          the town dinners, and the campground logistics guidebooks skip.
        </p>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="park-grid">
        {parks.map((p) => (
          <button key={p.slug} className="park-card" onClick={() => onOpen(p.slug)}>
            <div className="park-card-art">
              <ParkArt slug={p.slug} />
            </div>
            <div className="park-card-label">
              <p className="eyebrow">
                {p.state} · est. {p.established}
              </p>
              <h3>{p.name}</h3>
              <p className="tagline">{p.tagline}</p>
              <span className="park-card-cta">
                {p.trip_count} suggested trip{p.trip_count === 1 ? "" : "s"} →
              </span>
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
