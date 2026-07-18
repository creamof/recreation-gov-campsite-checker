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
