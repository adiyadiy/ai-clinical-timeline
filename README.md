# AI Clinical Timeline (MVP)

## Goal & clinical use case

An assistant that reads a single therapy session transcript and produces
structured, evidence-grounded clinical insights — mood observations, symptom
status, medication changes, and risk flags — each tied to a verbatim quote
from the transcript. Insights from multiple sessions are aggregated into a
per-patient timeline, which is rendered as a clinician-facing visualization
showing longitudinal progress at a glance.

The intent is to help a clinician quickly answer "how has this patient been
doing across sessions?" without re-reading every session note — while never
inventing a clinical claim the source text doesn't support. Every structured
field that carries clinical weight (symptoms, moods, risk flags, medication
changes) is required to cite an `evidence_quote` from the transcript it came
from.

This is a learning/demo project, not a production clinical tool. It is built
deliberately as a sequence of small, independently runnable vertical slices
rather than a single large system.

## Architecture & data flow

```
Stage 1 — single-session extraction
transcript.txt
      │
      ▼
run_session.py ──► extractor.py ──► Claude API (structured output)
      │                                     │
      │                                     ▼
      │                          ExtractedInsights (LLM output only)
      │                                     │
      └──────────────► SessionInsights (+ session_id/patient_id/date)
                                             │
                                             ▼
                          data/insights/{patient_id}/{session_id}.json


Stage 2 — aggregation (no LLM call)
data/insights/{patient_id}/*.json
      │
      ▼
timeline.py ──► PatientTimeline


Stage 3a — visualization                 Stage 3b — cross-session synthesis
PatientTimeline                           PatientTimeline
      │                                         │
      ▼                                         ▼
render_timeline.py                    synthesize_patient.py ──► synthesizer.py ──► Claude API
      │                                         │                                        │
      ▼                                         │                                        ▼
output/{patient_id}_timeline.html               │                          ExtractedSynthesis (LLM output only)
                                                 │                                        │
                                                 └──────────────► TimelineSynthesis (+ patient_id/session_count/date_range)
                                                                              │
                                                                              ▼
                                                               data/synthesis/{patient_id}.json
```

Two families of Pydantic schemas do the heavy lifting (`schemas.py`), both
following the same split:

- **`ExtractedInsights`** — exactly what the LLM is asked to produce for one
  session. Does not include `session_id`/`patient_id`/`session_date`, because
  the LLM shouldn't be trusted to reproduce identifiers the pipeline already
  knows correctly.
- **`SessionInsights`** — `ExtractedInsights` plus those identifiers, added by
  the pipeline after parsing. This is the artifact actually persisted to disk.
- **`PatientTimeline`** — a pure container (`patient_id` + an ordered list of
  `SessionInsights`), with `session_count` / `date_range` as computed
  properties, not stored fields. No cross-session synthesis happens here —
  see "Structured timeline instead of charts" below.
- **`ExtractedSynthesis`** — the LLM-facing synthesis output: a
  `trajectory_summary`, a list of `NotableChange`s, and a `risk_summary`.
  Same split principle as `ExtractedInsights`.
- **`TimelineSynthesis`** — `ExtractedSynthesis` plus `patient_id` /
  `session_count` / `date_range_start` / `date_range_end`, attached after
  parsing, same as `SessionInsights`.
- **`NotableChange` / `SupportingEvidence`** — every notable change must cite
  one or more `SupportingEvidence` entries (a session date + a quote from
  that session). Unlike most of the schema, this isn't just a prompted
  convention — it's checked in code. See "Grounding: what's verified vs.
  what's prompted" below.

## Running the extraction pipeline

Requires Python 3.10+ (the schemas use `X | None` syntax) and an Anthropic API
key.

```bash
python3.10 -m venv .venv   # or any 3.10+ interpreter
.venv/bin/pip install -r requirements.txt

echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
set -a; source .env; set +a

.venv/bin/python run_session.py data/sample_transcript.txt
# → writes data/insights/patient_stub/sample_transcript.json
```

`run_session.py <transcript_file> [session_id] [patient_id]` — `session_id`
defaults to the transcript filename, `patient_id` defaults to `patient_stub`.

## Generating the timeline visualization

Once at least one session exists for a patient under `data/insights/`:

```bash
.venv/bin/python render_timeline.py patient_stub
# → writes output/patient_stub_timeline.html
```

Open the file directly in a browser, or publish it wherever you're viewing
this project. `render_timeline.py` only reads already-validated
`SessionInsights` JSON via `timeline.py` — it makes no API calls and adds no
new clinical claims; it's a rendering layer over data that was already
computed and stored.

## Running cross-session synthesis

Once at least one session exists for a patient under `data/insights/`:

```bash
.venv/bin/python synthesize_patient.py patient_stub
# → writes data/synthesis/patient_stub.json
```

This is a second, distinct Claude API call — it reads every session's
already-extracted `SessionInsights` (not the raw transcripts) and produces a
`TimelineSynthesis`: a trajectory summary, a list of notable changes each
citing specific session dates and quotes, and a risk summary that explicitly
avoids inferring a trend from limited data. It does not touch
`extractor.py`, `timeline.py`, or `render_timeline.py` — purely additive on
top of `PatientTimeline`.

**Generated outputs are intentionally not committed.** `data/insights/`,
`data/synthesis/`, and `output/` are all gitignored — everything in them is
fully reproducible from `data/sample_transcript.txt` (or your own
transcripts) plus the commands above. The repo's source of truth is the code
and the input fixtures, not generated artifacts.

## Key design decisions & tradeoffs

**No RAG.** Every extraction call operates on exactly one transcript that
fits comfortably in context — there's nothing to retrieve. RAG would add
chunking, embeddings, and a vector store to solve a problem this project
doesn't have yet. Revisit if/when transcripts routinely exceed context or
insights need to be retrieved across a large corpus of unrelated patients.

**No database.** Insights are flat JSON files, one per session, organized as
`data/insights/{patient_id}/{session_id}.json`. This is enough to prove the
full pipeline end-to-end and to aggregate a single patient's sessions cheaply
(directory scan + Pydantic validation). It stops being enough once you need
to query across patients, handle concurrent writes, or scale past a few
thousand files — at that point the natural move is a real datastore, not a
bigger file convention.

**Structured timeline instead of charts.** The patient timeline is rendered
as a chronological log (session cards with dates, mood/symptom/medication
chips, risk flags), not a line or bar chart. The data isn't numeric magnitude
data — a "mood over time" line chart would require inventing a mood *score*
that doesn't exist in the schema. Rendering the aggregation as-is (not a
derived metric) keeps the visualization honest to what was actually
extracted.

**Evidence grounding, but not everywhere.** `evidence_quote` is required on
symptoms, moods, risk flags, and medication changes — the fields most likely
to be scrutinized. It's deliberately *not* required on `interventions`,
`action_items`, or `notable_quotes`, which are lower-stakes and would add
schema weight without much payoff.

**Patient-scoped file layout, not filtering.** Insight files live under
`data/insights/{patient_id}/`, so `timeline.py` can trust the directory
structure to scope a patient's sessions rather than filtering every file's
`patient_id` field at load time.

**Two-schema split for extraction (`ExtractedInsights` vs.
`SessionInsights`).** The LLM never sees or has to reproduce `session_id`,
`patient_id`, or `session_date` — the pipeline attaches those after parsing.
This removes an entire class of failure (mismatched or hallucinated
identifiers) for free.

**Grounding: what's verified vs. what's prompted.** The synthesis step
(`synthesizer.py`) goes a step further than prompting for grounding — it
programmatically validates it. Every `NotableChange` must cite
`supporting_evidence`, and `_validate_grounding` checks each entry's
`evidence_quote` against the actual session it's attributed to (summary,
interventions, action items, notable quotes, and every field-level
`evidence_quote`) as an exact, verbatim substring. If a cited quote doesn't
literally appear in that session's extracted data, synthesis fails loudly
instead of silently shipping an ungrounded claim.

This is a deliberate, explicit MVP boundary, not a bug, in two directions:

- **Guarantees traceability, not semantic relevance.** The check proves a
  quote is real and belongs to the session it's cited against — it does not
  prove that quote is the *right* or most relevant evidence for the specific
  claim it's attached to. A technically verbatim quote can still be a weak or
  mismatched citation; this was observed once during manual review (a quote
  about one intervention was cited to support a claim about a different one)
  and passed validation because the substring check has no notion of
  relevance, only existence.
- **Two fields are not code-verified at all.** `trajectory_summary` and
  `risk_summary` are free-text prose, grounded only by system-prompt
  instructions (cite dates, don't infer trends, no invented scores) — not by
  any post-hoc check against the source sessions, unlike `notable_changes`.
  Extending a substring-style check to prose is a materially harder problem,
  since correct summaries paraphrase by nature; a strict verbatim check would
  reject good output as often as bad. Left as future work rather than solved
  with a check that would create false failures.

## Future improvements

Roughly in the order they'd become necessary, not necessarily the order
they'd be built:

- **Semantic relevance validation for synthesis evidence** — the current
  grounding check only verifies a cited quote exists verbatim in the session
  it's attributed to; it doesn't verify that quote is actually the best (or
  even a relevant) piece of evidence for the specific claim it's attached to.
  See "Grounding: what's verified vs. what's prompted" above.
- **Extend grounding validation to prose fields** — `trajectory_summary` and
  `risk_summary` currently rely on prompt-level instructions only, with no
  code-level check like the one applied to `notable_changes`.
- **Extraction verification pass** — a second, cheaper pass that checks the
  first (single-session) extraction's claims against the source transcript,
  as a hallucination check beyond schema validation.
- **Real datastore** once file-per-session stops scaling (see "No database"
  above).
- **Batch API** for bulk/offline extraction runs — 50% cost reduction, built
  for exactly this shape of independent, non-interactive requests.
- **Prompt caching** on the (currently static) system prompt once call volume
  makes the cache-write cost worth it.
- **Controlled vocabulary for `topics`** once there's enough real data to know
  what the right categories are.
- **Auth, multi-user support, production deployment** — all explicitly out of
  scope for this MVP.
