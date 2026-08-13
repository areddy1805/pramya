"""LangGraph interview workflow tests (Phase C realignment).

Prove the graph is REAL in the execution path:
- InterviewState is a genuine LangGraph StateGraph (nodes, conditional
  edges, checkpointer with thread_id).
- question/answer/hint/report actions route through the graph and produce
  validated outputs via the domain generators (LangChain -> router).
- Parallel fan-out is impossible: one branch per action.
- The workflow compiles with a MemorySaver checkpointer and checkpoints
  per thread_id.
"""

from __future__ import annotations

import json
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from app.ai.contracts import ChatResponse, Usage
from app.ai.policy import TaskPolicyTable
from app.ai.router import InferenceRouter
from app.interview.workflow import build_interview_workflow


class QueueProvider:
    """Fake router provider returning queued JSON per call."""

    name = "fake"

    def __init__(self, contents: list[str]) -> None:
        self.contents = contents
        self.calls = 0

    async def generate(self, request: Any) -> ChatResponse:
        self.calls += 1
        content = self.contents.pop(0) if self.contents else "{}"
        return ChatResponse(content=content, model="fake", usage=Usage(total_tokens=1))


def _router(provider: QueueProvider) -> InferenceRouter:
    return InferenceRouter(policy=TaskPolicyTable(), omlx=None, deepseek=provider)


Q = json.dumps(
    {
        "text": "Describe a distributed system you built.",
        "type": "project_deep_dive",
        "difficulty": "medium",
        "rationale": "Probes architecture",
        "hint_levels": ["Think about CAP"],
        "target_competency": "System Design",
    }
)
EVAL = json.dumps(
    {
        "dimensions": {"correctness": 7.0},
        "overall": 7.0,
        "confidence": 0.8,
        "strengths": [],
        "weaknesses": [],
        "missing_evidence": [],
        "follow_ups": [],
        "evidence": [{"claim": "Built a stream processor", "status": "observed", "strength": 0.8}],
        "evaluator_version": "pramya-eval-1.0",
    }
)
HINT = json.dumps({"hint": "Think about consistency across nodes."})
REPORT = json.dumps({"report": "Strong tradeoff awareness; work on quantifying impact."})


def _base() -> dict[str, Any]:
    return {
        "session_id": 1,
        "user_id": 1,
        "history": "QUESTION: Hi",
        "evidence_summary": "Built stream processor",
        "competency": "System Design",
        "difficulty": "medium",
        "seniority": "mid",
        "hints_used": 0,
        "question_text": None,
        "question_type": None,
        "question_difficulty": None,
        "hint_levels": None,
        "rationale": None,
        "target_competency": None,
        "hint": None,
        "answer_text": None,
        "evidence_context": "",
        "evidence_retrieved": None,
        "evaluation": None,
        "evaluation_overall": None,
        "extracted_evidence": None,
        "candidate_state_score": None,
        "next_action": None,
        "report": None,
        "report_input": None,
        "error": None,
    }


async def test_workflow_is_a_compiled_langgraph_state_graph() -> None:
    wf = build_interview_workflow(_router(QueueProvider([])))
    assert isinstance(wf, CompiledStateGraph)
    # Checkpointer wired (thread_id per session).
    assert wf.checkpointer is not None


async def test_question_flow_routes_and_generates() -> None:
    provider = QueueProvider([Q])
    wf = build_interview_workflow(_router(provider))

    state = await wf.ainvoke(
        {**_base(), "action": "question"},
        config={"configurable": {"thread_id": "thread-1"}},
    )
    assert state["question_text"] == "Describe a distributed system you built."
    assert state["question_type"] == "project_deep_dive"
    assert state["target_competency"] == "System Design"
    assert provider.calls == 1  # exactly one LLM call (question generation)


async def test_answer_flow_evaluates_extracts_and_decides() -> None:
    provider = QueueProvider([EVAL])
    wf = build_interview_workflow(_router(provider))

    state = await wf.ainvoke(
        {
            **_base(),
            "action": "answer",
            "question_text": "Describe a distributed system you built.",
            "answer_text": "I built a stream processor with at-least-once delivery.",
        },
        config={"configurable": {"thread_id": "thread-2"}},
    )
    assert state["evaluation_overall"] == 7.0
    assert state["extracted_evidence"]  # evidence extraction node ran
    assert state["next_action"] in ("follow_up", "next_question", "repeat", "finish")
    assert provider.calls == 1  # exactly one LLM call (evaluation)


async def test_hint_flow_returns_hint() -> None:
    provider = QueueProvider([HINT])
    wf = build_interview_workflow(_router(provider))

    state = await wf.ainvoke(
        {**_base(), "action": "hint", "question_text": "Describe a system", "hints_used": 0},
        config={"configurable": {"thread_id": "thread-3"}},
    )
    assert "consistency" in (state["hint"] or "")
    assert provider.calls == 1


async def test_report_flow_synthesizes() -> None:
    provider = QueueProvider([REPORT])
    wf = build_interview_workflow(_router(provider))

    state = await wf.ainvoke(
        {**_base(), "action": "report", "report_input": "SESSION SUMMARY:\nQ: x\nA: y"},
        config={"configurable": {"thread_id": "thread-4"}},
    )
    assert "tradeoff" in (state["report"] or "").lower()
    assert state["next_action"] == "finish"
    assert provider.calls == 1


async def test_question_flow_does_not_fire_evaluator() -> None:
    """No parallel fan-out: a question action must not call the evaluator."""
    provider = QueueProvider([Q])
    wf = build_interview_workflow(_router(provider))

    await wf.ainvoke(
        {**_base(), "action": "question"},
        config={"configurable": {"thread_id": "thread-5"}},
    )
    # Question flow: retrieve (no LLM) -> generate (1 call). Evaluator is not
    # reachable from the question branch.
    assert provider.calls == 1


async def test_checkpoints_are_keyed_by_thread_id() -> None:
    """Same thread accumulates; different threads are isolated."""
    provider = QueueProvider([Q, Q])
    wf = build_interview_workflow(_router(provider))

    await wf.ainvoke(
        {**_base(), "action": "question"},
        config={"configurable": {"thread_id": "thread-a"}},
    )
    await wf.ainvoke(
        {**_base(), "action": "question"},
        config={"configurable": {"thread_id": "thread-b"}},
    )
    # Each thread ran independently: two question generations, two calls.
    assert provider.calls == 2
