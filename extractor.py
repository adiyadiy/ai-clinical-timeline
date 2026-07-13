from datetime import datetime, timezone
import anthropic
from schemas import SessionInput, SessionInsights, ExtractedInsights

MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = """You are a clinical documentation assistant analyzing a single \
therapy session transcript. Extract structured insights strictly grounded in the \
transcript. For every symptom, mood, risk flag, and medication mention, include a \
short verbatim evidence_quote from the transcript. Do not infer clinical claims \
not supported by the text. Flag risk indicators (suicidal ideation, self-harm, \
harm to others, substance use) even if mentioned only briefly."""


def extract_insights(session: SessionInput) -> SessionInsights:
    client = anthropic.Anthropic()

    response = client.messages.parse(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Session transcript:\n\n{session.transcript}"}],
        output_format=ExtractedInsights,
    )

    if response.parsed_output is None:
        raise RuntimeError(f"extraction failed, stop_reason={response.stop_reason}")

    return SessionInsights(
        **response.parsed_output.model_dump(),
        session_id=session.session_id,
        patient_id=session.patient_id,
        session_date=session.session_date,
        model_version=response.model,
        generated_at=datetime.now(timezone.utc),
    )
