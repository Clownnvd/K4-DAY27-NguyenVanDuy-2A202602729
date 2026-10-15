```yaml
goal: Complete and prove the Day 27 HITL PR Review Agent across routing, interrupts, audit, replay, and Streamlit UI.
scope:
  include: [exercises 1-4, app.py, deterministic tests, audit evidence, README handoff]
  exclude: [posting unsolicited comments to the course PR repository, production PostgreSQL deployment]
inputs: [PR-Demo public fixtures, ReviewState and PRAnalysis schemas, SQLite audit schema]
outputs: [working LangGraph exercises, Streamlit UI, tests, screenshots, verification receipt]
invariants:
  - low-confidence actions never auto-approve
  - a human decision is required for medium confidence
  - escalation asks specific questions and resumes with answers
  - every meaningful node emits structured audit data
  - tests never post a GitHub comment
acceptance:
  - id: AC1
    check: uv run pytest -q
    required: true
  - id: AC2
    check: uv run python scripts/run_acceptance.py
    required: true
  - id: AC3
    check: uv run streamlit run app.py --server.headless true and HTTP health check
    required: true
  - id: AC4
    check: secret scan plus git diff --check
    required: true
risk: medium
rollback: Revert the final student commit; the upstream fork baseline remains in Git history.
```
