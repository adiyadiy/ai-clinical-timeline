from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel


class MoodAssessment(BaseModel):
    primary_affect: str
    valence: Literal["positive", "neutral", "negative", "mixed"]
    context: str | None = None  # what was being discussed
    evidence_quote: str | None = None


class SymptomMention(BaseModel):
    symptom: str
    status: Literal["new", "worsening", "improving", "stable", "resolved"]
    evidence_quote: str | None = None


class RiskFlag(BaseModel):
    risk_type: Literal["suicidal_ideation", "self_harm", "harm_to_others", "substance_use", "other"]
    severity: Literal["low", "moderate", "high"]
    evidence_quote: str | None = None


class MedicationMention(BaseModel):
    medication_name: str
    status: Literal["started", "stopped", "dose_changed", "continued", "side_effect_reported", "adherence_issue", "other"]
    evidence_quote: str | None = None


class SessionInput(BaseModel):
    session_id: str
    patient_id: str
    session_date: date
    clinician_id: str | None = None
    session_type: str | None = None
    transcript: str


class ExtractedInsights(BaseModel):
    """What the LLM produces."""
    summary: str
    topics: list[str] = []
    moods: list[MoodAssessment] = []
    symptoms: list[SymptomMention] = []
    risk_flags: list[RiskFlag] = []
    medications: list[MedicationMention] = []
    interventions: list[str] = []
    action_items: list[str] = []
    notable_quotes: list[str] = []


class SessionInsights(ExtractedInsights):
    """Final artifact: LLM output + identifiers the pipeline already knows."""
    session_id: str
    patient_id: str
    session_date: date
    model_version: str
    generated_at: datetime


class PatientTimeline(BaseModel):
    """Pure aggregation of a patient's sessions — no cross-session synthesis."""
    patient_id: str
    sessions: list[SessionInsights]

    @property
    def session_count(self) -> int:
        return len(self.sessions)

    @property
    def date_range(self) -> tuple[date, date] | None:
        if not self.sessions:
            return None
        dates = [s.session_date for s in self.sessions]
        return min(dates), max(dates)


class SupportingEvidence(BaseModel):
    session_date: date  # must be a real session date from this timeline
    evidence_quote: str  # must be a verbatim substring of that session's extracted data


class NotableChange(BaseModel):
    description: str
    supporting_evidence: list[SupportingEvidence]


class ExtractedSynthesis(BaseModel):
    """What the LLM produces."""
    trajectory_summary: str
    notable_changes: list[NotableChange] = []
    risk_summary: str


class TimelineSynthesis(ExtractedSynthesis):
    """Final artifact: LLM output + identifiers the pipeline already knows."""
    patient_id: str
    session_count: int
    date_range_start: date
    date_range_end: date
    model_version: str
    generated_at: datetime
