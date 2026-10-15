from __future__ import annotations

import asyncio
from types import SimpleNamespace

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from common.db import checkpoint_saver, replay_events
from common.schemas import PRAnalysis, ReviewComment
from exercises import exercise_1_confidence as ex1
from exercises import exercise_2_hitl as ex2
from exercises import exercise_3_escalation as ex3
from exercises import exercise_4_audit as ex4


def analysis(confidence: float) -> PRAnalysis:
    return PRAnalysis(
        summary="Bounded review fixture", risk_factors=["fixture risk"],
        comments=[ReviewComment(file="app.py", line=10, severity="issue", body="Review this change")],
        confidence=confidence, confidence_reasoning="Deterministic fixture",
        escalation_questions=["Why is app.py line 10 safe?"],
    )


def test_confidence_boundaries_route_safely():
    assert ex1.node_route({"analysis": analysis(.73)})["decision"] == "auto_approve"
    assert ex1.node_route({"analysis": analysis(.58)})["decision"] == "human_approval"
    assert ex1.node_route({"analysis": analysis(.57)})["decision"] == "escalate"


def test_medium_confidence_interrupts_and_reject_does_not_post(monkeypatch):
    monkeypatch.setattr(ex2, "node_fetch_pr", lambda state: {
        "pr_title": "Fixture", "pr_diff": "+ safe", "pr_files": ["app.py"], "pr_head_sha": "abc1234"})
    monkeypatch.setattr(ex2, "node_analyze", lambda state: {"analysis": analysis(.65)})
    monkeypatch.setattr(ex2, "post_review_comment", lambda *args: (_ for _ in ()).throw(
        AssertionError("reject path must not post")))
    graph = ex2.build_graph()
    cfg = {"configurable": {"thread_id": "medium"}}
    first = graph.invoke({"pr_url": "https://github.com/acme/repo/pull/1", "thread_id": "medium"}, cfg)
    assert first["__interrupt__"][0].value["kind"] == "approval_request"
    final = graph.invoke(Command(resume={"choice": "reject", "feedback": "Needs tests"}), cfg)
    assert final["final_action"] == "rejected"


def test_low_confidence_escalates_then_synthesizes(monkeypatch):
    monkeypatch.setattr(ex3, "node_fetch_pr", lambda state: {
        "pr_title": "Risky", "pr_diff": "+ md5(password)", "pr_files": ["auth.py"], "pr_head_sha": "def5678"})
    monkeypatch.setattr(ex3, "node_analyze", lambda state: {"analysis": analysis(.40)})
    monkeypatch.setattr(ex3, "node_synthesize", lambda state: {"analysis": analysis(.80)})
    monkeypatch.setattr(ex3, "node_commit", lambda state: {"final_action": "committed_after_escalation"})
    graph = ex3.build_graph()
    cfg = {"configurable": {"thread_id": "low"}}
    first = graph.invoke({"pr_url": "https://github.com/acme/repo/pull/2", "thread_id": "low"}, cfg)
    payload = first["__interrupt__"][0].value
    assert payload["kind"] == "escalation" and payload["questions"]
    refined = graph.invoke(Command(resume={payload["questions"][0]: "Use Argon2 instead"}), cfg)
    assert refined["__interrupt__"][0].value["kind"] == "approval_request"
    final = graph.invoke(Command(resume={"choice": "approve", "feedback": "Refined review checked"}), cfg)
    assert final["final_action"] == "committed_after_escalation"


class FakeStructuredLLM:
    async def ainvoke(self, _messages):
        return analysis(.65)


class FakeLLM:
    def with_structured_output(self, _schema):
        return FakeStructuredLLM()


def test_audit_graph_persists_human_decision(tmp_path, monkeypatch):
    async def scenario():
        db_file = tmp_path / "audit.db"
        monkeypatch.setenv("HITL_DB_PATH", str(db_file))
        monkeypatch.setenv("GITHUB_USER", "fixture-reviewer")
        monkeypatch.setattr(ex4, "fetch_pr", lambda _url: SimpleNamespace(
            title="Fixture", diff="+ safe change", files_changed=["app.py"], head_sha="abc1234"))
        monkeypatch.setattr(ex4, "get_llm", lambda: FakeLLM())
        monkeypatch.setattr(ex4, "post_review_comment", lambda *_args: None)
        async with checkpoint_saver(str(db_file)) as saver:
            await saver.setup()
            graph = ex4.build_graph(saver)
            cfg = {"configurable": {"thread_id": "audit-thread"}}
            first = await graph.ainvoke({
                "pr_url": "https://github.com/acme/repo/pull/3", "thread_id": "audit-thread"}, cfg)
            assert first["__interrupt__"][0].value["kind"] == "approval_request"
            final = await graph.ainvoke(Command(resume={"choice": "approve", "feedback": "Checked"}), cfg)
            assert final["final_action"] == "committed"
        events = await replay_events("audit-thread")
        actions = [event["action"] for event in events]
        assert {"fetch_pr", "analyze", "route", "human_approval", "commit"}.issubset(actions)
        assert any(event["reviewer_id"] == "fixture-reviewer" and event["decision"] == "approve"
                   for event in events)

    asyncio.run(scenario())
