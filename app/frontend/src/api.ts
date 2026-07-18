import type {
  ConciergeResponse,
  LotteryResponse,
  ParkGuide,
  ParkSummary,
  SearchResponse,
  TimelinePlan,
  TimelineStep,
  Watch,
  WatchesResponse,
} from "./types";

// Empty base -> same origin (prod, or dev via Vite's /api proxy).
const BASE = import.meta.env.VITE_API_BASE ?? "";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export async function search(query: string, signal?: AbortSignal): Promise<SearchResponse> {
  const res = await fetch(`${BASE}/api/search?q=${encodeURIComponent(query)}`, { signal });
  return json<SearchResponse>(res);
}

export async function getTimeline(body: {
  id: string;
  name: string;
  entity_type: string;
  parent_name?: string | null;
  arrival: string;
  departure: string;
  force_strategy?: "campground" | "lottery";
}): Promise<TimelinePlan> {
  const res = await fetch(`${BASE}/api/timeline`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return json<TimelinePlan>(res);
}

export async function getLotteries(year: number): Promise<LotteryResponse> {
  const res = await fetch(`${BASE}/api/lotteries?year=${year}`);
  return json<LotteryResponse>(res);
}

export async function getParks(): Promise<{ parks: ParkSummary[] }> {
  const res = await fetch(`${BASE}/api/parks`);
  return json<{ parks: ParkSummary[] }>(res);
}

export async function getPark(slug: string): Promise<ParkGuide> {
  const res = await fetch(`${BASE}/api/parks/${slug}`);
  return json<ParkGuide>(res);
}

export async function askConcierge(body: {
  query: string;
  month?: number | null;
  year?: number | null;
}): Promise<ConciergeResponse> {
  const res = await fetch(`${BASE}/api/concierge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return json<ConciergeResponse>(res);
}

export async function preparePlan(body: {
  park_slug: string;
  trip_title: string;
  month?: number | null;
  year?: number | null;
}): Promise<TimelinePlan> {
  const res = await fetch(`${BASE}/api/prepare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return json<TimelinePlan>(res);
}

/* ---- Watches ---- */

export async function getWatches(): Promise<WatchesResponse> {
  return json<WatchesResponse>(await fetch(`${BASE}/api/watches`));
}

export async function createWatch(body: {
  campground_id: string;
  name: string;
  arrival: string;
  departure: string;
}): Promise<Watch> {
  const res = await fetch(`${BASE}/api/watches`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return json<Watch>(res);
}

export async function checkWatch(id: string): Promise<Watch> {
  return json<Watch>(await fetch(`${BASE}/api/watches/${id}/check`, { method: "POST" }));
}

export async function dismissWatchAlert(id: string): Promise<Watch> {
  return json<Watch>(await fetch(`${BASE}/api/watches/${id}/dismiss`, { method: "POST" }));
}

export async function deleteWatch(id: string): Promise<void> {
  await json(await fetch(`${BASE}/api/watches/${id}`, { method: "DELETE" }));
}

export async function getPushConfig(): Promise<{ enabled: boolean; public_key: string | null }> {
  return json(await fetch(`${BASE}/api/push/config`));
}

export async function subscribePush(sub: PushSubscription): Promise<void> {
  await json(
    await fetch(`${BASE}/api/push/subscribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(sub.toJSON()),
    })
  );
}

/** Download the plan's key dates as a calendar file with reminder alarms. */
export async function downloadIcs(title: string, steps: TimelineStep[]): Promise<void> {
  const res = await fetch(`${BASE}/api/ics`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, steps }),
  });
  if (!res.ok) throw new Error(`Calendar export failed (${res.status})`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "trailhead-plan.ics";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
