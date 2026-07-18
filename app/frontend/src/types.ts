export interface SearchResult {
  id: string;
  name: string;
  entity_type: string;
  parent_name?: string | null;
  city?: string | null;
  state?: string | null;
  reservable?: boolean | null;
}

export interface SearchResponse {
  query: string;
  online: boolean;
  results: SearchResult[];
  note?: string | null;
}

export type StepKind = "prep" | "reminder" | "critical" | "action" | "info" | "trip";

export interface TimelineStep {
  when: string | null;
  title: string;
  detail: string;
  kind: StepKind;
  urgency: "low" | "medium" | "high";
  verify_url?: string | null;
  is_past: boolean;
}

export interface TimelinePlan {
  target: SearchResult;
  arrival: string;
  departure: string;
  strategy: "campground" | "lottery" | "unknown";
  headline: string;
  rule_name?: string | null;
  competitiveness?: string | null;
  steps: TimelineStep[];
  verify_url?: string | null;
}

export interface LotteryPhase {
  name: string;
  kind: string;
  opens: string;
  closes: string;
  results: string | null;
  notes: string;
}

export interface Lottery {
  slug: string;
  name: string;
  park: string;
  verify_url: string;
  summary: string;
  phases: LotteryPhase[];
}

export interface LotteryResponse {
  year: number;
  lotteries: Lottery[];
}

/* ---- Watches ---- */

export interface Watch {
  id: string;
  campground_id: string;
  name: string;
  arrival: string;
  departure: string;
  active: boolean;
  created_at: string;
  last_checked: string | null;
  status: "unknown" | "available" | "unavailable" | "error" | "expired";
  available: number | null;
  total: number | null;
  alert: { at: string; available: number } | null;
  error: string | null;
}

export interface WatchesResponse {
  watches: Watch[];
  push_enabled: boolean;
}

/* ---- Parks guide ---- */

export interface ParkSummary {
  slug: string;
  name: string;
  state: string;
  established: string;
  tagline: string;
  trip_count: number;
}

export interface PlanTarget {
  name: string;
  entity_type: string;
  rec_gov_id: string | null;
  note: string;
}

export interface Trip {
  title: string;
  style: string;
  nights: number;
  best_months: string;
  summary: string;
  itinerary: string[];
  targets: PlanTarget[];
}

export interface ParkActivity {
  name: string;
  kind: string;
  detail: string;
}

export interface Eat {
  name: string;
  where: string;
  detail: string;
}

export interface ParkAmenities {
  showers: string[];
  laundry: string[];
  groceries: string[];
  connectivity: string;
  heads_up: string;
}

/* ---- Concierge ---- */

export interface Intent {
  months: number[];
  interests: string[];
  party: string | null;
  places: string[];
  summary: string;
}

export interface TimingItem {
  label: string;
  when: string | null;
  status: "upcoming" | "act-now" | "passed" | "info";
  detail: string;
}

export interface TripOption {
  park_slug: string;
  park_name: string;
  state: string;
  trip_title: string;
  style: string;
  nights: number;
  best_months: string;
  summary: string;
  score: number;
  why: string[];
  timing: TimingItem[];
}

export interface ConciergeResponse {
  intent: Intent;
  engine: "claude" | "local";
  target_month: string;
  arrival: string;
  options: TripOption[];
}

export interface ParkGuide extends Omit<ParkSummary, "trip_count"> {
  description: string;
  best_seasons: string;
  crowd_tip: string;
  official_url: string;
  trips: Trip[];
  activities: ParkActivity[];
  eats: Eat[];
  amenities: ParkAmenities;
}
