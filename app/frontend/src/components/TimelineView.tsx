import { useState } from "react";
import type { TimelinePlan, TimelineStep } from "../types";
import { downloadIcs } from "../api";

const KIND_ICON: Record<TimelineStep["kind"], string> = {
  prep: "🧭",
  reminder: "⏰",
  critical: "🎯",
  action: "✅",
  info: "ℹ️",
  trip: "🏕️",
};

// Backend step titles carry a leading emoji on the key moments (🎯 book now,
// ⏰ apply now, 🏕️ trip starts…) so the .ics calendar summary reads well. On
// the site the rail dot already shows a per-kind icon, so strip that leading
// emoji here — otherwise those rows show the same icon twice.
function stripLeadingEmoji(title: string): string {
  return title.replace(/^(?:[\p{Extended_Pictographic}\u{1F3FB}-\u{1F3FF}️‍]+)\s*/u, "");
}

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
  const [exportState, setExportState] = useState<"idle" | "busy" | "done" | "error">("idle");
  const exportable = plan.steps.filter((s) => s.when && !s.is_past).length;

  async function exportCalendar() {
    setExportState("busy");
    try {
      await downloadIcs(plan.target.name, plan.steps);
      setExportState("done");
    } catch {
      setExportState("error");
    }
  }

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
        <div className="headline-actions">
          {plan.verify_url && (
            <a className="verify" href={plan.verify_url} target="_blank" rel="noreferrer">
              Confirm current rules →
            </a>
          )}
          {exportable > 0 && (
            <button className="calendar-btn" onClick={exportCalendar} disabled={exportState === "busy"}>
              {exportState === "busy"
                ? "Exporting…"
                : exportState === "done"
                  ? "✅ Added — open the .ics file"
                  : exportState === "error"
                    ? "Export failed — retry"
                    : `🔔 Add ${exportable} reminder${exportable > 1 ? "s" : ""} to my calendar`}
            </button>
          )}
        </div>
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
              <div className="step-title">{stripLeadingEmoji(s.title)}</div>
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
          <strong>Don't let a date slip.</strong>
          <p className="muted">
            The calendar export above puts every deadline on your phone with built-in alarms — a
            day-before nudge plus a 30-minute warning for window-open moments. Live cancellation
            watches with push alerts are the next milestone.
          </p>
        </div>
      </div>
    </section>
  );
}
