import { useEffect, useMemo, useState } from "react";
import type { Lottery } from "../types";
import { getLotteries } from "../api";

function fmtDay(iso: string): string {
  return new Date(iso + "T00:00:00").toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

export default function LotteryExplorer() {
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(currentYear);
  const [lotteries, setLotteries] = useState<Lottery[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getLotteries(year)
      .then((r) => alive && setLotteries(r.lotteries))
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [year]);

  const years = useMemo(() => [currentYear, currentYear + 1, currentYear + 2], [currentYear]);

  return (
    <section className="lotteries">
      <div className="section-head">
        <div>
          <h2>Backcountry permit lotteries</h2>
          <p className="muted">
            High-demand permits use application windows, not first-come booking. These are the key
            dates — confirm the exact current-year windows on recreation.gov.
          </p>
        </div>
        <label className="inline">
          Year
          <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="lottery-grid">
        {lotteries.map((lot) => (
          <article key={lot.slug} className="card lottery-card">
            <header>
              <h3>{lot.name}</h3>
              <span className="muted">{lot.park}</span>
            </header>
            <p>{lot.summary}</p>
            <ul className="phases">
              {lot.phases.map((ph, i) => (
                <li key={i}>
                  <div className="phase-head">
                    <span className="phase-name">{ph.name}</span>
                    <span className={`chip chip-${ph.kind === "lottery" ? "high" : ""}`}>{ph.kind}</span>
                  </div>
                  <div className="phase-dates">
                    Apply <b>{fmtDay(ph.opens)} – {fmtDay(ph.closes)}</b>
                    {ph.results && (
                      <>
                        {" "}
                        · results <b>{fmtDay(ph.results)}</b>
                      </>
                    )}
                  </div>
                  <div className="muted small">{ph.notes}</div>
                </li>
              ))}
            </ul>
            <a className="verify" href={lot.verify_url} target="_blank" rel="noreferrer">
              View on recreation.gov →
            </a>
          </article>
        ))}
      </div>
    </section>
  );
}
