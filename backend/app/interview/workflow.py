# pyright: basic
"""LangGraph interview workflow (Phase C realignment, ADR-002).

The interview lifecycle is a real LangGraph StateGraph that executes in the
production path. Typed state + conditional routing decide the next action
(hint / follow_up / repeat / next_question / finish); nodes call the domain
services (retrieval, question generation, evaluation, evidence extraction).

Architecture (per the realignment directive):
    LangGraph -> application workflow -> domain/state invariants
              -> repositories -> PostgreSQL

InterviewService remains the domain/invariant layer (state transitions,
persistence, idempotency, SSE events); the graph is the workflow engine.
Each HTTP/voice action runs the graph with the session's ``thread_id``
(checkpointer), so LangGraph state is checkpointed per interview.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from langgraph.checkpoint.memory import MemorySaver  # pyright: ignore[reportMissingTypeStubs]
from langgraph.graph import END, START, StateGraph  # pyright: ignore[reportMissingTypeStubs]
from langgraph.graph.state import (  # pyright: ignore[reportMissingTypeStubs]
    CompiledStateGraph,
)

from app.ai.router import InferenceRouter
from app.interview.generation import (
    Evaluator,
    Hints,
    QuestionGenerator,
    parse_question_output,
)
from app.knowledge.retrieval import RetrievalService


class InterviewState(TypedDict):
    """Typed LangGraph state for one interview action run.

    Minimal payload: the deterministic service loads domain state from
    PostgreSQL and hands the graph the context it needs; nodes return the
    AI outputs + routing decision. Persistent domain state never lives
    inside the graph (ADR-022: service is authoritative).
    """

    # Context (input)
    session_id: int
    user_id: int
    action: Literal["question", "answer", "hint", "report"]
    history: str
    evidence_summary: str
    competency: str
    difficulty: str
    seniority: str

    # Question generation (input/output)
    hints_used: int
    question_text: str | None
    question_type: str | None
    question_difficulty: str | None
    hint_levels: list[str] | None
    rationale: str | None
    target_competency: str | None
    hint: str | None

    # Answer evaluation (input/output)
    answer_text: str | None
    evidence_context: str
    evidence_retrieved: bool | None
    evaluation: dict[str, Any] | None
    evaluation_overall: float | None

    # Evidence extraction + candidate-state update
    extracted_evidence: list[dict[str, Any]] | None
    candidate_state_score: float | None

    # Routing decision
    next_action: str | None  # hint | follow_up | repeat | next_question | finish

    # Report
    report: str | None
    report_input: str | None

    # Errors (never swallow in the graph: surfaced to the service)
    error: str | None


def build_interview_workflow(
    router: InferenceRouter,
    *,
    retrieval: RetrievalService | None = None,
) -> CompiledStateGraph[InterviewState, None, InterviewState, InterviewState]:
    """Compile the interview StateGraph with a MemorySaver checkpointer.

    thread_id = interview session's ``graph_thread_id`` (set by
    InterviewService.create_session). MemorySaver is the single-process
    dev-runtime checkpointer; durable domain state lives in PostgreSQL.
    """
    qgen = QuestionGenerator(router)
    evaluator = Evaluator(router)
    hints = Hints(router)

    async def load_session(state: InterviewState) -> dict[str, Any]:
        """Verify session ownership + context was provided by the service."""
        if state["session_id"] <= 0 or state["user_id"] <= 0:
            return {"error": "session context missing"}
        return {}

    async def retrieve_context(state: InterviewState) -> dict[str, Any]:
        """Retrieve evidence context for the current query (RAG node)."""
        if retrieval is None:
            return {"evidence_context": ""}
        query = state.get("answer_text") or state.get("question_text") or ""
        if not query.strip():
            return {"evidence_context": ""}
        result = await retrieval.search(state["user_id"], query)
        context = "\n\n".join(c.content for c in result.chunks[:5])
        return {
            "evidence_context": context,
            "evidence_retrieved": len(result.chunks) > 0,
        }

    async def generate_question(state: InterviewState) -> dict[str, Any]:
        """generate_question node (LangChain streaming pipeline -> DeepSeek).

        Streams tokens through the model (LangGraph ``stream_mode="messages"``
        surfaces them to the realtime voice engine); accumulates and parses
        into the InterviewQuestion schema for persistence.
        """
        text = ""
        async for token in qgen.stream_question(
            competency=state["competency"],
            difficulty=state["difficulty"],
            seniority=state["seniority"],
            evidence_summary=state["evidence_summary"],
            history=state["history"],
            hints_used=state.get("hints_used", 0),
        ):
            text += token
        question = parse_question_output(text, default_competency=state["competency"])
        return {
            "question_text": question.text,
            "question_type": question.type,
            "question_difficulty": question.difficulty,
            "hint_levels": question.hint_levels,
            "rationale": question.rationale,
            "target_competency": question.target_competency or state["competency"],
        }

    async def evaluate_answer(state: InterviewState) -> dict[str, Any]:
        """evaluate_answer node (LangChain pipeline -> DeepSeek)."""
        evaluation = await evaluator.evaluate(
            question_text=state.get("question_text") or "",
            answer_text=state.get("answer_text") or "",
            evidence_context=state.get("evidence_context", ""),
            hints_used=state.get("hints_used", 0),
        )
        return {
            "evaluation": evaluation.model_dump(mode="json"),
            "evaluation_overall": evaluation.overall,
        }

    async def extract_evidence(state: InterviewState) -> dict[str, Any]:
        """extract_evidence node: derive claimed evidence from the evaluation.

        Deterministic (no extra LLM call): the evaluation payload already
        carries evidence claims; the service persists them as CLAIMED rows.
        """
        evaluation = state.get("evaluation") or {}
        claims = evaluation.get("evidence") or []
        rows = []
        for claim in claims:
            if isinstance(claim, dict) and claim.get("claim"):
                rows.append(
                    {
                        "claim": claim["claim"],
                        "status": claim.get("status", "claimed"),
                        "strength": claim.get("strength"),
                        "competency_hint": claim.get("competency_hint"),
                    }
                )
        return {"extracted_evidence": rows}

    async def update_candidate_state(state: InterviewState) -> dict[str, Any]:
        """update_candidate_state node: normalize candidate-state signals.

        Deterministic aggregation over the evaluation (no LLM). Persisted
        evidence + readiness updates remain the service's job.
        """
        overall = state.get("evaluation_overall")
        return {"candidate_state_score": overall}

    async def determine_next_action(state: InterviewState) -> dict[str, Any]:
        """Routing decision: hint / follow_up / repeat / next_question / finish.

        Deterministic policy over evaluation quality + turn signals.
        """
        overall = state.get("evaluation_overall")
        if overall is None:
            return {"next_action": "next_question"}
        if overall < 2.0:
            return {"next_action": "repeat"}
        follow_ups = (state.get("evaluation") or {}).get("follow_ups") or []
        if follow_ups:
            return {"next_action": "follow_up"}
        return {"next_action": "next_question"}

    async def generate_hint(state: InterviewState) -> dict[str, Any]:
        """hint node: progressive hint via LangChain pipeline."""
        hint = await hints.hint_for(
            question_text=state.get("question_text") or "",
            hint_level=min((state.get("hints_used", 0) or 0) + 1, 4),
        )
        return {"hint": hint, "next_action": "hint"}

    async def generate_report(state: InterviewState) -> dict[str, Any]:
        """report/finalize node: final synthesis (LangChain text chain)."""
        report = await _report_via_service_chain(router, state)
        return {"report": report, "next_action": "finish"}

    # -- graph assembly ------------------------------------------------------

    graph = StateGraph(InterviewState)
    graph.add_node("load_session", load_session)
    graph.add_node("retrieve_context", retrieve_context)
    graph.add_node("generate_question", generate_question)
    graph.add_node("evaluate_answer", evaluate_answer)
    graph.add_node("extract_evidence", extract_evidence)
    graph.add_node("update_candidate_state", update_candidate_state)
    graph.add_node("determine_next_action", determine_next_action)
    graph.add_node("generate_hint", generate_hint)
    graph.add_node("generate_report", generate_report)

    graph.add_edge(START, "load_session")

    def _route_action(state: InterviewState) -> str:
        """select_mode: route by action; both question and answer flows run
        retrieval first (RAG context feeds generation or evaluation)."""
        if state.get("error"):
            return END
        return {
            "question": "retrieve_context",
            "answer": "retrieve_context",
            "hint": "generate_hint",
            "report": "generate_report",
        }.get(state["action"], "generate_question")

    graph.add_conditional_edges(
        "load_session",
        _route_action,
        {
            "retrieve_context": "retrieve_context",
            "generate_hint": "generate_hint",
            "generate_report": "generate_report",
            END: END,
        },
    )

    # question/answer flow: retrieve -> route by action (parallel fan-out is
    # forbidden here — one branch per action)
    def _route_after_retrieval(state: InterviewState) -> str:
        return "evaluate_answer" if state["action"] == "answer" else "generate_question"

    graph.add_conditional_edges(
        "retrieve_context",
        _route_after_retrieval,
        {"generate_question": "generate_question", "evaluate_answer": "evaluate_answer"},
    )
    graph.add_edge("generate_question", END)

    # answer flow: evaluate -> extract -> update -> decide
    graph.add_edge("evaluate_answer", "extract_evidence")
    graph.add_edge("extract_evidence", "update_candidate_state")
    graph.add_edge("update_candidate_state", "determine_next_action")

    def _route_after_decision(state: InterviewState) -> str:
        # finish/follow_up/repeat/next_question return to the service for
        # persistence; only 'finish' finalizes a report when requested.
        return "finalize_report" if state.get("next_action") == "finish" else END

    graph.add_conditional_edges(
        "determine_next_action",
        _route_after_decision,
        {"finalize_report": "generate_report", END: END},
    )
    graph.add_edge("generate_hint", END)
    graph.add_edge("generate_report", END)

    return graph.compile(checkpointer=MemorySaver())


async def _report_via_service_chain(router: InferenceRouter, state: InterviewState) -> str:
    """Final report through the LangChain text chain (shared with service)."""
    from app.ai.langchain.pipelines import text_chain
    from app.ai.policy import TaskClass
    from app.services.prompts import load_prompt

    chain = text_chain(
        router,
        TaskClass.FINAL_SYNTHESIS,
        load_prompt(
            "report_generation/final_report.txt",
            fallback=(
                "Write an evidence-backed interview report: strengths, "
                "weaknesses, readiness signals, and recommended practice."
            ),
        ),
    )
    return str(await chain.ainvoke({"user": state.get("report_input") or ""}))


__all__ = ["InterviewState", "build_interview_workflow", "MemorySaver"]
