import type { TimelinePlan, TimelineStep } from "../types";

const KIND_ICON: Record<TimelineStep["kind"], string> = {
  prep: "🧭",
  reminder: "⏰",
  critical: "🎯",
  action: "✅",
  info: "ℹ️",
  trip: "🏕️",
};

function fmt(when: string | null): string {
  if (!when) return "Do now";
  const hasTime = when.includes("T");
  const d = new Date(hasTime ? when : when + "T00:00:00");
  const opts: Intl.DateTimeFormatOptions = hasTime
    ? { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }
    : { weekday: "short", month: "short", day: "numeric", year: "numeric" };
  return d.toLocaleString(undefined, opts);
}

export default function TimelineView({ plan }: { plan: TimelinePlan }) {
  return (
    <section className="timeline">
      <div className={`headline ${plan.strategy}`}>
        <div className="headline-tags">
          <span className={`badge ${plan.strategy}`}>{plan.strategy}</span>
          {plan.competitiveness && (
            <span className={`chip chip-${plan.competitiveness}`}>{plan.competitiveness} demand</span>
          )}
          {plan.rule_name && <span className="chip">{plan.rule_name}</span>}
        </div>
        <h3>{plan.headline}</h3>
        {plan.verify_url && (
          <a className="verify" href={plan.verify_url} target="_blank" rel="noreferrer">
            Confirm current rules on recreation.gov →
          </a>
        )}
      </div>

      <ol className="steps">
        {plan.steps.map((s, i) => (
          <li key={i} className={`step ${s.kind} urgency-${s.urgency} ${s.is_past ? "past" : ""}`}>
            <div className="step-rail">
              <span className="dot">{KIND_ICON[s.kind]}</span>
            </div>
            <div className="step-body">
              <div className="step-head">
                <span className="step-when">{fmt(s.when)}</span>
                {s.is_past && <span className="chip chip-past">past</span>}
                {s.urgency === "high" && !s.is_past && <span className="chip chip-high">act</span>}
              </div>
              <div className="step-title">{s.title}</div>
              <div className="step-detail">{s.detail}</div>
              {s.verify_url && (
                <a href={s.verify_url} target="_blank" rel="noreferrer" className="step-link">
                  Open on recreation.gov →
                </a>
              )}
            </div>
          </li>
        ))}
      </ol>

      <div className="watch-cta card">
        <div>
          <strong>Missed the window or it's sold out?</strong>
          <p className="muted">
            Last-minute cancellations open up constantly. Availability watches with web-push alerts
            are coming in Milestone 2 — this app is already installable so notifications will work.
          </p>
        </div>
      </div>
    </section>
  );
}
