import sys
from datetime import date
from pathlib import Path

from schemas import SessionInput
from extractor import extract_insights


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_session.py <transcript_file> [session_id] [patient_id]")
        sys.exit(1)

    transcript_path = Path(sys.argv[1])
    session = SessionInput(
        session_id=sys.argv[2] if len(sys.argv) > 2 else transcript_path.stem,
        patient_id=sys.argv[3] if len(sys.argv) > 3 else "patient_stub",
        session_date=date.today(),
        transcript=transcript_path.read_text(),
    )

    insights = extract_insights(session)

    out_dir = Path("data/insights") / session.patient_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{session.session_id}.json"
    out_path.write_text(insights.model_dump_json(indent=2))

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
