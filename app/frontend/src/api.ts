import type { LotteryResponse, ParkGuide, ParkSummary, SearchResponse, TimelinePlan } from "./types";

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
