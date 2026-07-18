import { useEffect, useMemo, useState } from "react";

interface Props {
  loading: boolean;
  defaultNights?: number;
  /** Restored dates from a persisted session — repopulate instead of the default +30-day window. */
  initialArrival?: string | null;
  initialDeparture?: string | null;
  /** Fired whenever arrival/departure change, so a caller can persist them. */
  onDatesChange?: (arrival: string, departure: string) => void;
  onBuild: (input: {
    arrival: string;
    departure: string;
    force_strategy?: "campground" | "lottery";
  }) => void;
}

function addDays(iso: string, days: number): string {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

const todayISO = () => new Date().toISOString().slice(0, 10);

export default function TripForm({
  loading,
  onBuild,
  defaultNights = 3,
  initialArrival,
  initialDeparture,
  onDatesChange,
}: Props) {
  const defaultArrival = useMemo(() => addDays(todayISO(), 30), []);
  const [arrival, setArrival] = useState(initialArrival || defaultArrival);
  const [departure, setDeparture] = useState(initialDeparture || addDays(arrival, defaultNights));
  const [strategy, setStrategy] = useState<"" | "campground" | "lottery">("");

  useEffect(() => {
    onDatesChange?.(arrival, departure);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [arrival, departure]);

  const invalid = departure <= arrival;
  const nights = Math.max(
    0,
    Math.round((new Date(departure).getTime() - new Date(arrival).getTime()) / 86400000)
  );

  return (
    <form
      className="trip-form card"
      onSubmit={(e) => {
        e.preventDefault();
        if (invalid) return;
        onBuild({
          arrival,
          departure,
          force_strategy: strategy || undefined,
        });
      }}
    >
      <div className="grid2">
        <label>
          Arrival (first night)
          <input type="date" value={arrival} min={todayISO()} onChange={(e) => setArrival(e.target.value)} />
        </label>
        <label>
          Departure (check-out)
          <input type="date" value={departure} min={addDays(arrival, 1)} onChange={(e) => setDeparture(e.target.value)} />
        </label>
      </div>

      <div className="row-between">
        <span className="muted">{nights > 0 ? `${nights} night${nights > 1 ? "s" : ""}` : "Choose valid dates"}</span>
        <label className="inline">
          Strategy
          <select value={strategy} onChange={(e) => setStrategy(e.target.value as typeof strategy)}>
            <option value="">Auto-detect</option>
            <option value="campground">Campground (rolling window)</option>
            <option value="lottery">Lottery / permit</option>
          </select>
        </label>
      </div>

      {invalid && <div className="error">Departure must be after arrival.</div>}

      <button className="primary" type="submit" disabled={invalid || loading}>
        {loading ? "Building…" : `Build my booking timeline`}
      </button>
    </form>
  );
}
