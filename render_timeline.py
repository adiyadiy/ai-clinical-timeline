import html
import sys
from pathlib import Path

from schemas import PatientTimeline, SessionInsights
from timeline import load_patient_timeline

SYMPTOM_ICON = {"new": "●", "worsening": "↘", "improving": "↗", "stable": "→", "resolved": "✓"}
MEDICATION_ICON = {
    "started": "+", "stopped": "–", "dose_changed": "↕",
    "continued": "=", "side_effect_reported": "!", "adherence_issue": "?", "other": "•",
}
MOOD_ICON = {"positive": "↑", "negative": "↓", "neutral": "–", "mixed": "↕"}
RISK_LABEL = {"low": "low severity", "moderate": "moderate severity", "high": "high severity"}

CSS = """
:root {
  --ground: #f9f9f7; --surface: #fcfcfb; --border: rgba(11, 11, 11, 0.10);
  --ink: #0b0b0b; --ink-secondary: #52514e; --ink-muted: #898781;
  --accent: #4a3aa7; --accent-ink: #ffffff;
  --status-warning: #fab219; --status-serious: #ec835a; --status-critical: #d03b3b;
  --font-sans: system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --ground: #0d0d0d; --surface: #1a1a19; --border: rgba(255, 255, 255, 0.10);
    --ink: #ffffff; --ink-secondary: #c3c2b7; --ink-muted: #898781;
    --accent: #9085e9; --accent-ink: #0d0d0d;
  }
}
:root[data-theme="dark"] {
  --ground: #0d0d0d; --surface: #1a1a19; --border: rgba(255, 255, 255, 0.10);
  --ink: #ffffff; --ink-secondary: #c3c2b7; --ink-muted: #898781;
  --accent: #9085e9; --accent-ink: #0d0d0d;
}
:root[data-theme="light"] {
  --ground: #f9f9f7; --surface: #fcfcfb; --border: rgba(11, 11, 11, 0.10);
  --ink: #0b0b0b; --ink-secondary: #52514e; --ink-muted: #898781;
  --accent: #4a3aa7; --accent-ink: #ffffff;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--ground); color: var(--ink);
  font-family: var(--font-sans); line-height: 1.5;
}
.page { max-width: 720px; margin: 0 auto; padding: 40px 20px 80px; display: flex; flex-direction: column; gap: 28px; }
h1 { font-size: 1.4rem; font-weight: 650; margin: 0 0 16px; text-wrap: balance; }
h2 { font-size: 0.95rem; font-weight: 650; margin: 0 0 12px; }

.stat-row { display: flex; gap: 24px; flex-wrap: wrap; }
.stat-tile__label { font-size: 0.7rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-muted); margin-bottom: 4px; }
.stat-tile__value { font-size: 1.1rem; font-weight: 600; color: var(--ink); }
.stat-tile__value.mono { font-family: var(--font-mono); font-weight: 500; }

.risk-rollup { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 18px 20px; }
.risk-rollup__empty { margin: 0; color: var(--ink-secondary); font-size: 0.9rem; }
.risk-rollup .risk-flag { margin-top: 10px; }
.risk-rollup .risk-flag:first-of-type { margin-top: 0; }

.session-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 22px 24px; display: flex; flex-direction: column; gap: 16px; }
.session-card__header { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.session-date { font-family: var(--font-mono); font-weight: 600; font-size: 1rem; color: var(--accent); }
.gap-badge { font-family: var(--font-mono); font-size: 0.78rem; color: var(--ink-muted); }
.summary { margin: 0; color: var(--ink-secondary); max-width: 65ch; }

.section-label { font-size: 0.7rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-muted); margin-bottom: 8px; }
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; }

.chip { border: 1px solid var(--border); border-radius: 999px; background: var(--ground); }
.chip[open] { border-radius: 14px; }
.chip > summary { list-style: none; cursor: pointer; display: inline-flex; align-items: center; gap: 7px; padding: 5px 12px; font-size: 0.85rem; color: var(--ink-secondary); }
.chip > summary::-webkit-details-marker { display: none; }
.chip > summary::after { content: "+"; color: var(--ink-muted); font-size: 0.75rem; }
.chip[open] > summary::after { content: "–"; }
.chip > summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 999px; }
.chip__quote { margin: 0; padding: 0 14px 12px 14px; font-family: var(--font-mono); font-size: 0.8rem; color: var(--ink-muted); line-height: 1.5; }

.risk-flag { display: flex; gap: 12px; padding: 14px 16px; border-radius: 10px; border: 1px solid var(--border); border-left: 4px solid var(--risk-color); background: color-mix(in srgb, var(--risk-color) 10%, var(--surface)); }
.risk-flag--low { --risk-color: var(--status-warning); }
.risk-flag--moderate { --risk-color: var(--status-serious); }
.risk-flag--high { --risk-color: var(--status-critical); }
.risk-flag__icon { flex-shrink: 0; width: 22px; height: 22px; border-radius: 50%; background: var(--risk-color); color: #ffffff; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.8rem; }
.risk-flag__label { font-weight: 600; font-size: 0.88rem; margin-bottom: 4px; }
.risk-flag__quote { margin: 0; font-family: var(--font-mono); font-size: 0.82rem; color: var(--ink-secondary); line-height: 1.5; }

@media (prefers-reduced-motion: no-preference) {
  .chip > summary::after { transition: transform 120ms ease; }
}
"""


def _esc(s: str) -> str:
    return html.escape(s)


def _cap(s: str) -> str:
    s = s.replace("_", " ")
    return s[0].upper() + s[1:] if s else s


def _render_risk_flag(flag, date_prefix: str = "") -> str:
    label = f"{date_prefix}{_cap(flag.risk_type)} · {RISK_LABEL.get(flag.severity, flag.severity)}"
    quote = f'&ldquo;{_esc(flag.evidence_quote)}&rdquo;' if flag.evidence_quote else ""
    return f"""<div class="risk-flag risk-flag--{flag.severity}">
  <span class="risk-flag__icon">!</span>
  <div class="risk-flag__body">
    <div class="risk-flag__label">{_esc(label)}</div>
    <p class="risk-flag__quote">{quote}</p>
  </div>
</div>"""


def _render_chip(icon: str, label: str, quote: str | None) -> str:
    quote_html = f'<p class="chip__quote">&ldquo;{_esc(quote)}&rdquo;</p>' if quote else ""
    return f"""<details class="chip">
  <summary>{_esc(icon)} {_esc(label)}</summary>
  {quote_html}
</details>"""


def _render_session_card(session: SessionInsights, gap_days: int | None) -> str:
    parts = []
    header = f'<div class="session-card__header"><time class="session-date">{session.session_date.isoformat()}</time>'
    if gap_days is not None:
        header += f'<span class="gap-badge">{gap_days} days since previous session</span>'
    header += "</div>"
    parts.append(header)
    parts.append(f'<p class="summary">{_esc(session.summary)}</p>')

    if session.risk_flags:
        flags_html = "\n".join(_render_risk_flag(f) for f in session.risk_flags)
        parts.append(f'<div class="risk-flags">{flags_html}</div>')

    if session.symptoms:
        chips = "\n".join(
            _render_chip(SYMPTOM_ICON.get(s.status, "•"), f"{_cap(s.symptom)} · {s.status}", s.evidence_quote)
            for s in session.symptoms
        )
        parts.append(f'<div class="section"><div class="section-label">Symptoms</div><div class="chip-row">{chips}</div></div>')

    if session.moods:
        chips = "\n".join(
            _render_chip(MOOD_ICON.get(m.valence, "•"), _cap(m.primary_affect), m.evidence_quote or m.context)
            for m in session.moods
        )
        parts.append(f'<div class="section"><div class="section-label">Observations noted this session</div><div class="chip-row">{chips}</div></div>')

    if session.medications:
        chips = "\n".join(
            _render_chip(MEDICATION_ICON.get(m.status, "•"), f"{_cap(m.medication_name)} · {_cap(m.status)}", m.evidence_quote)
            for m in session.medications
        )
        parts.append(f'<div class="section"><div class="section-label">Medications</div><div class="chip-row">{chips}</div></div>')

    return f'<article class="session-card">{"".join(parts)}</article>'


def _render_risk_rollup(timeline: PatientTimeline) -> str:
    all_flags = [(s.session_date, f) for s in timeline.sessions for f in s.risk_flags]
    if not all_flags:
        body = f'<p class="risk-rollup__empty">✓ No risk flags recorded across {timeline.session_count} sessions.</p>'
    else:
        body = "\n".join(_render_risk_flag(f, date_prefix=f"{d.isoformat()} · ") for d, f in all_flags)
    return f'<section class="risk-rollup"><h2>Risk flags across all sessions</h2>{body}</section>'


def render_patient_timeline_html(timeline: PatientTimeline) -> str:
    date_range = timeline.date_range
    range_text = f"{date_range[0].isoformat()} – {date_range[1].isoformat()}" if date_range else "–"

    sessions_desc = list(reversed(timeline.sessions))
    cards = []
    for i, session in enumerate(sessions_desc):
        prior = sessions_desc[i + 1] if i + 1 < len(sessions_desc) else None
        gap_days = (session.session_date - prior.session_date).days if prior else None
        cards.append(_render_session_card(session, gap_days))

    return f"""<title>Patient Timeline – {_esc(timeline.patient_id)}</title>
<style>{CSS}</style>
<div class="page">
  <header>
    <h1>Patient timeline</h1>
    <div class="stat-row">
      <div class="stat-tile"><div class="stat-tile__label">Patient</div><div class="stat-tile__value mono">{_esc(timeline.patient_id)}</div></div>
      <div class="stat-tile"><div class="stat-tile__label">Sessions</div><div class="stat-tile__value">{timeline.session_count}</div></div>
      <div class="stat-tile"><div class="stat-tile__label">Range</div><div class="stat-tile__value mono">{range_text}</div></div>
    </div>
  </header>
  {_render_risk_rollup(timeline)}
  <div class="timeline">
    {"".join(cards)}
  </div>
</div>"""


def main():
    patient_id = sys.argv[1] if len(sys.argv) > 1 else "patient_stub"
    timeline = load_patient_timeline(patient_id)

    out_dir = Path("output")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{patient_id}_timeline.html"
    out_path.write_text(render_patient_timeline_html(timeline))

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
