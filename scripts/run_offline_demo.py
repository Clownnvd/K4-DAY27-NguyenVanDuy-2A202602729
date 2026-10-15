"""Generate reproducible HITL + escalation audit evidence without external writes."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace

from langgraph.types import Command

from common.db import checkpoint_saver
from common.schemas import PRAnalysis, ReviewComment
from exercises import exercise_4_audit as workflow

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "artifacts" / "day27_audit_evidence.db"
RECEIPT = ROOT / "artifacts" / "day27_audit_receipt.json"


def result(confidence: float, question: str | None = None) -> PRAnalysis:
    return PRAnalysis(
        summary=f"Offline verified review at confidence {confidence:.0%}",
        risk_factors=["Authentication and migration context require review"],
        comments=[ReviewComment(file="app.py", line=10, severity="issue",
                                body="Verify behavior before merge")],
        confidence=confidence, confidence_reasoning="Deterministic lab evidence",
        escalation_questions=[question] if question else [],
    )


class QueueStructured:
    def __init__(self, queue):
        self.queue = queue

    async def ainvoke(self, _messages):
        return self.queue.pop(0)


class QueueLLM:
    def __init__(self, queue):
        self.queue = queue

    def with_structured_output(self, _schema):
        return QueueStructured(self.queue)


async def run_case(
    thread: str,
    analyses: list[PRAnalysis],
    resume: dict,
    final_approval: dict | None = None,
) -> None:
    workflow.get_llm = lambda: QueueLLM(analyses)
    workflow.fetch_pr = lambda url: SimpleNamespace(
        title="Offline fixture", diff="+ security-sensitive change",
        files_changed=["app.py"], head_sha="abc1234")
    workflow.post_review_comment = lambda *_args: None
    async with checkpoint_saver(str(DB)) as saver:
        await saver.setup()
        graph = workflow.build_graph(saver)
        cfg = {"configurable": {"thread_id": thread}}
        state = await graph.ainvoke({
            "pr_url": f"https://github.com/offline/fixture/pull/{thread[-1]}", "thread_id": thread}, cfg)
        payload = state["__interrupt__"][0].value
        print(thread, "interrupt=", payload["kind"])
        state = await graph.ainvoke(Command(resume=resume), cfg)
        if "__interrupt__" in state:
            refined = state["__interrupt__"][0].value
            print(thread, "interrupt=", refined["kind"])
            if final_approval is None:
                raise AssertionError("A final approval response is required")
            state = await graph.ainvoke(Command(resume=final_approval), cfg)
        print(thread, "final_action=", state["final_action"])


async def main() -> None:
    DB.parent.mkdir(exist_ok=True)
    DB.unlink(missing_ok=True)
    os.environ["HITL_DB_PATH"] = str(DB)
    os.environ["GITHUB_USER"] = "NguyenVanDuy"
    await run_case("offline-medium-1", [result(.65)],
                   {"choice": "approve", "feedback": "Đã kiểm tra migration"})
    question = "Vì sao thay đổi xác thực tại app.py:10 là an toàn?"
    await run_case("offline-escalate-2", [result(.40, question), result(.82)],
                   {question: "Đã bổ sung Argon2, parameterized query và test."},
                   {"choice": "approve", "feedback": "Đã kiểm tra bản review tinh chỉnh"})
    import sqlite3
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in conn.execute(
            "SELECT thread_id, pr_url, action, confidence, risk_level, reviewer_id, "
            "decision, reason, execution_time_ms FROM audit_events ORDER BY id"
        )]
    RECEIPT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("audit_db=", DB)
    print("audit_receipt=", RECEIPT)


if __name__ == "__main__":
    asyncio.run(main())
