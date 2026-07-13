from pathlib import Path

from schemas import PatientTimeline, SessionInsights


def load_patient_timeline(patient_id: str, insights_dir: Path = Path("data/insights")) -> PatientTimeline:
    patient_dir = insights_dir / patient_id
    sessions = [
        SessionInsights.model_validate_json(f.read_text())
        for f in sorted(patient_dir.glob("*.json"))
    ]
    sessions.sort(key=lambda s: s.session_date)
    return PatientTimeline(patient_id=patient_id, sessions=sessions)
