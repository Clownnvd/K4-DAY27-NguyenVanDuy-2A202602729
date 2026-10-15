"""Deterministic release gate for the Day 27 student implementation."""
from __future__ import annotations

import ast
import asyncio
import os
import sys
import tempfile
from pathlib import Path

from common.db import db_conn, write_audit_event
from common.github import post_review_comment
from common.schemas import AuditEntry, PRAnalysis
from exercises.exercise_1_confidence import node_route

ROOT = Path(__file__).resolve().parents[1]


async def verify_audit() -> None:
    with tempfile.TemporaryDirectory(prefix="day27-acceptance-") as folder:
        os.environ["HITL_DB_PATH"] = str(Path(folder) / "audit.db")
        await write_audit_event(
            thread_id="acceptance", pr_url="https://github.com/acme/repo/pull/1",
            entry=AuditEntry(agent_id="acceptance", action="route", confidence=.58,
                             risk_level="med", decision="pending", reason="boundary",
                             execution_time_ms=1))
        async with db_conn() as conn:
            row = await (await conn.execute(
                "SELECT confidence, risk_level FROM audit_events WHERE thread_id='acceptance'"
            )).fetchone()
            assert row["confidence"] == .58 and row["risk_level"] == "med"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    def analysis(confidence: float) -> PRAnalysis:
        return PRAnalysis(summary="fixture", confidence=confidence,
                          confidence_reasoning="boundary", comments=[], risk_factors=[])

    assert node_route({"analysis": analysis(.73)})["decision"] == "auto_approve"
    assert node_route({"analysis": analysis(.58)})["decision"] == "human_approval"
    assert node_route({"analysis": analysis(.57)})["decision"] == "escalate"
    asyncio.run(verify_audit())

    os.environ.pop("ALLOW_GITHUB_WRITE", None)
    try:
        post_review_comment("https://github.com/acme/repo/pull/1", "must not send")
    except RuntimeError as error:
        assert "disabled" in str(error)
    else:
        raise AssertionError("GitHub writes must fail closed")

    for relative in ["exercises/exercise_1_confidence.py", "exercises/exercise_2_hitl.py",
                     "exercises/exercise_3_escalation.py", "exercises/exercise_4_audit.py", "app.py"]:
        source = (ROOT / relative).read_text(encoding="utf-8")
        ast.parse(source)
        assert "NotImplementedError" not in source, relative
    print("PASS: routing boundaries, audit schema, write gate, and all five exercises")


if __name__ == "__main__":
    main()
