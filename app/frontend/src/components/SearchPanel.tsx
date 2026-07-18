import { useEffect, useRef, useState } from "react";
import type { SearchResult } from "../types";
import { search } from "../api";

export interface ManualPrefill {
  name: string;
  park: string;
  type: string;
}

export default function SearchPanel({
  onSelect,
  prefill = null,
}: {
  onSelect: (r: SearchResult) => void;
  prefill?: ManualPrefill | null;
}) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [showManual, setShowManual] = useState(prefill != null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) {
      setResults([]);
      setNote(null);
      return;
    }
    const t = setTimeout(async () => {
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      setLoading(true);
      try {
        const res = await search(term, ctrl.signal);
        setResults(res.results);
        setNote(res.online ? null : res.note ?? "recreation.gov is unreachable — enter details manually.");
        if (!res.online) setShowManual(true);
      } catch (e) {
        if ((e as Error).name !== "AbortError") {
          setNote("Search failed. You can still enter a facility manually below.");
          setShowManual(true);
        }
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <section className="search-panel">
      <label className="search-box">
        <span className="search-icon">🔍</span>
        <input
          autoFocus
          placeholder="Search a campground or permit (e.g. Upper Pines, Half Dome, The Wave)…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        {loading && <span className="spinner" aria-label="loading" />}
      </label>

      {note && <div className="notice">{note}</div>}

      {results.length > 0 && (
        <ul className="results">
          {results.map((r) => (
            <li key={`${r.entity_type}-${r.id}`}>
              <button onClick={() => onSelect(r)}>
                <span className={`badge ${r.entity_type}`}>{r.entity_type}</span>
                <span className="result-name">{r.name}</span>
                <span className="muted">
                  {[r.parent_name, [r.city, r.state].filter(Boolean).join(", ")]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="manual-toggle">
        <button className="link" onClick={() => setShowManual((s) => !s)}>
          {showManual ? "Hide manual entry" : "Can't find it? Enter a facility manually"}
        </button>
      </div>

      {showManual && <ManualEntry onSelect={onSelect} prefill={prefill} />}
    </section>
  );
}

function ManualEntry({
  onSelect,
  prefill,
}: {
  onSelect: (r: SearchResult) => void;
  prefill?: ManualPrefill | null;
}) {
  const [name, setName] = useState(prefill?.name ?? "");
  const [id, setId] = useState("");
  const [type, setType] = useState(prefill?.type ?? "campground");
  const [park, setPark] = useState(prefill?.park ?? "");

  return (
    <div className="manual card">
      <p className="muted">
        Find the ID in a recreation.gov URL, e.g. <code>/camping/campgrounds/<b>232447</b></code> or{" "}
        <code>/permits/<b>234652</b></code>.
      </p>
      <div className="grid2">
        <label>
          Facility name
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Upper Pines" />
        </label>
        <label>
          Recreation.gov ID
          <input value={id} onChange={(e) => setId(e.target.value)} placeholder="232447" />
        </label>
        <label>
          Type
          <select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="campground">Campground</option>
            <option value="permit">Permit / backcountry</option>
          </select>
        </label>
        <label>
          Park (optional, improves rules)
          <input value={park} onChange={(e) => setPark(e.target.value)} placeholder="Yosemite National Park" />
        </label>
      </div>
      <button
        className="primary"
        disabled={!name.trim() || !id.trim()}
        onClick={() =>
          onSelect({
            id: id.trim(),
            name: name.trim(),
            entity_type: type,
            parent_name: park.trim() || null,
          })
        }
      >
        Use this facility
      </button>
    </div>
  );
}
