# Verification receipt — Day 27 HITL PR Review Agent

## Outcome

Completed the confidence router, LangGraph interrupts, reviewer escalation,
refined-review confirmation, structured SQLite audit trail, durable checkpoint,
session replay, and Streamlit UI. GitHub writes fail closed unless
`ALLOW_GITHUB_WRITE=1` is explicitly configured.

## Changed scope

- `exercises/exercise_1_confidence.py`: structured PR analysis and three-way routing.
- `exercises/exercise_2_hitl.py`: approval interrupt, checkpointer, and resume loop.
- `exercises/exercise_3_escalation.py`: targeted Q&A, synthesis, and final approval.
- `exercises/exercise_4_audit.py`: durable workflow plus audit events for every decision.
- `app.py`: browser UI for start, approve/reject/edit, escalation, and recent sessions.
- `common/db.py`: explicit checkpoint serializer allowlist for `PRAnalysis`.
- `common/github.py`: opt-in external write gate.
- `tests/` and `scripts/`: deterministic regression and evidence runners.

## Checks

| Check | Fresh result | Evidence |
|---|---|---|
| `uv run pytest -q` | PASS — 4 tests | routing boundaries, reject-no-write, two-stage escalation, persisted audit |
| `uv run python -X utf8 scripts/run_acceptance.py` | PASS | all five exercises, schema, boundaries, and write gate |
| `uv run python -X utf8 scripts/run_offline_demo.py` | PASS | 2 sessions, 15 structured audit events with no duplicated pre-interrupt event |
| Streamlit health | PASS — HTTP `200 ok` | `http://127.0.0.1:8501/_stcore/health` |
| Browser inspection | PASS | recent medium and escalation sessions visible in the sidebar |
| Live LLM routing | PASS | PR fixture 1 routed to human approval at 60%; fixture 2 escalated at 50% |
| External write cleanup | PASS | temporary course-PR comment `6192634222` was deleted; follow-up GET returned 404 |

## Regression proof

The tests pin the exact threshold contract: `0.73 → auto_approve`,
`0.58 → human_approval`, and `0.57 → escalate`. The low-confidence test must
cross two interrupts: first the contextual questions, then final human approval
of the refined review. The reject test raises immediately if any GitHub write is
attempted.

## Evidence artifacts

- `artifacts/day27_audit_receipt.json`: UTF-8 export of every structured event.
- `evidence/streamlit-sessions.png`: browser proof of the Streamlit UI and replayable sessions.
- `TASK_CONTRACT.md`: acceptance contract used before implementation.

## Remaining gaps

- The live model's self-reported confidence varies by model and run; deterministic
  tests are the authority for routing boundaries.
- The final GitHub write path remains deliberately unexecuted after adding the
  opt-in gate, so the lab cannot create another unsolicited external comment.
