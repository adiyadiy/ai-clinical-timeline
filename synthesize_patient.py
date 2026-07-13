import sys
from pathlib import Path

from timeline import load_patient_timeline
from synthesizer import synthesize_timeline


def main():
    patient_id = sys.argv[1] if len(sys.argv) > 1 else "patient_stub"
    timeline = load_patient_timeline(patient_id)

    synthesis = synthesize_timeline(timeline)

    out_dir = Path("data/synthesis")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{patient_id}.json"
    out_path.write_text(synthesis.model_dump_json(indent=2))

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
