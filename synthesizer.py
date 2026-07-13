from datetime import datetime, timezone
import anthropic
from schemas import PatientTimeline, TimelineSynthesis, ExtractedSynthesis

MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = """You are a clinical documentation assistant synthesizing a \
patient's therapy sessions into a longitudinal progress summary. You are given \
structured, already-extracted insights from each session — not raw transcripts. \
Treat each session's extracted data as ground truth.

Grounding rules, strictly enforced:
- Every claim in trajectory_summary, and every notable_change, must be \
traceable to specific session dates. Do not write a general statement (e.g. \
"mood has improved") without it being backed by concrete examples from named \
sessions.
- Every notable_change must list its supporting_evidence: one entry per \
session date it draws on, each with that session's date and a quote. Only use \
dates that literally appear in the sessions you were given — never invent, \
guess, or approximate a date.
- Each evidence_quote must be an EXACT, VERBATIM substring copied directly \
from that session's data as given to you — from its summary, interventions, \
action_items, notable_quotes, or any evidence_quote field already present on a \
symptom, mood, risk_flag, or medication. Do not paraphrase, shorten with an \
ellipsis, fix casing/punctuation, or combine text from two places into one \
quote. If you cannot find a suitable exact quote in the session data to \
support a claim for a given date, do not cite that date for that claim.
- Do not infer a trend from limited data, especially around risk. If a risk \
flag appears in only one session and not in later sessions, state that fact \
plainly: it was recorded once, on that date, and not recorded again. Do not \
conclude the underlying risk has decreased, resolved, or gone away — absence \
of a flag in later sessions is not a clinical risk assessment. If no risk \
flags were recorded in any session, say so plainly and do not add any \
interpretation beyond that fact.
- Never invent a numeric score, percentage, or rating for mood, risk, or \
progress. These do not exist in the source data.
- Actively look for meaningful behavioral or skill patterns across sessions \
(e.g. a coping strategy that was introduced, then practiced, then used \
independently) — not only whether symptoms got better or worse. A pattern \
that recurs or visibly evolves across sessions is more clinically significant \
than a single session's detail and should be surfaced as its own \
notable_change.
- If the data does not clearly support a pattern for some aspect, say so \
rather than inventing one."""


def _format_sessions(timeline: PatientTimeline) -> str:
    blocks = [
        f"Session — {s.session_date.isoformat()} (session_id: {s.session_id}):\n{s.model_dump_json(indent=2)}"
        for s in timeline.sessions
    ]
    return "\n\n".join(blocks)


def _session_text_pool(session) -> str:
    """Every piece of quotable text extracted from one session, for substring grounding checks."""
    parts = [session.summary, *session.interventions, *session.action_items, *session.notable_quotes]
    for group in (session.symptoms, session.moods, session.risk_flags, session.medications):
        for item in group:
            if item.evidence_quote:
                parts.append(item.evidence_quote)
    return " ".join(parts).lower()


def _validate_grounding(extracted: ExtractedSynthesis, timeline: PatientTimeline) -> None:
    sessions_by_date = {s.session_date: s for s in timeline.sessions}
    text_pool_by_date = {d: _session_text_pool(s) for d, s in sessions_by_date.items()}

    for change in extracted.notable_changes:
        if not change.supporting_evidence:
            raise ValueError(f"Ungrounded claim: notable_change {change.description!r} has no supporting evidence.")
        for evidence in change.supporting_evidence:
            if evidence.session_date not in sessions_by_date:
                raise ValueError(
                    f"Ungrounded claim: notable_change {change.description!r} cites "
                    f"{evidence.session_date.isoformat()}, which is not a session date in this timeline."
                )
            if evidence.evidence_quote.strip().lower() not in text_pool_by_date[evidence.session_date]:
                raise ValueError(
                    f"Unverifiable quote: notable_change {change.description!r} cites a quote "
                    f"for {evidence.session_date.isoformat()} that doesn't appear verbatim in that "
                    f"session's extracted data: {evidence.evidence_quote!r}"
                )


def synthesize_timeline(timeline: PatientTimeline) -> TimelineSynthesis:
    client = anthropic.Anthropic()

    response = client.messages.parse(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"Patient {timeline.patient_id} — {timeline.session_count} sessions:\n\n"
                f"{_format_sessions(timeline)}"
            ),
        }],
        output_format=ExtractedSynthesis,
    )

    if response.parsed_output is None:
        raise RuntimeError(f"synthesis failed, stop_reason={response.stop_reason}")

    extracted = response.parsed_output
    _validate_grounding(extracted, timeline)

    date_range = timeline.date_range
    return TimelineSynthesis(
        **extracted.model_dump(),
        patient_id=timeline.patient_id,
        session_count=timeline.session_count,
        date_range_start=date_range[0],
        date_range_end=date_range[1],
        model_version=response.model,
        generated_at=datetime.now(timezone.utc),
    )
