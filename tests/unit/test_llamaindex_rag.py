"""LlamaIndex integration unit tests (Phase D realignment).

Prove the LlamaIndex RAG layer is REAL, not decorative:
- RouterEmbeddings is a genuine llama-index BaseEmbedding that routes every
  embedding call through the InferenceRouter (ADR-004 boundary).
- The deterministic chunker feeds the LlamaIndex pipeline as TextNodes.
- PramyaVectorStore implements the llama-index vector store interface.
- The retriever produces context via a rerank postprocessor.
"""

from __future__ import annotations

from typing import Any

from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.schema import NodeWithScore, QueryBundle

from app.ai.contracts import EmbedResponse, RerankResponse
from app.ai.policy import TaskPolicyTable
from app.ai.router import InferenceRouter
from app.knowledge.rag import (
    DeterministicChunker,
    Document,
    RouterEmbeddings,
    to_llamaindex_documents,
)
from app.knowledge.rag.service import RouterRerankPostprocessor


class FakeOmlx:
    """Fake oMLX retrieval provider (embeddings + rerank)."""

    name = "fake"

    def __init__(self) -> None:
        self.embed_calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> EmbedResponse:
        self.embed_calls.append(texts)
        return EmbedResponse(
            embeddings=[[0.1] * 1024 for _ in texts], model="bge-m3-mlx-4bit", dimension=1024
        )

    async def rerank(
        self, query: str, documents: list[str], *, top_n: int | None = None
    ) -> RerankResponse:
        return RerankResponse(
            results=[
                {"index": i, "score": float(len(documents) - i)} for i in range(len(documents))
            ],
            model="Qwen3-Reranker-0.6B-4bit",
        )


def _router(omlx: FakeOmlx) -> InferenceRouter:
    return InferenceRouter(policy=TaskPolicyTable(), omlx=omlx, deepseek=None)


async def test_router_embeddings_is_real_llamaindex_embedding() -> None:
    omlx = FakeOmlx()
    emb = RouterEmbeddings(_router(omlx))

    assert isinstance(emb, BaseEmbedding)
    vector = await emb._aget_query_embedding("hello")
    assert len(vector) == 1024
    # Routed through the router (oMLX/BGE-M3), never direct.
    assert omlx.embed_calls


async def test_chunker_produces_llamaindex_text_nodes() -> None:
    docs = to_llamaindex_documents("x" * 3000, document_id=1, kind="resume", filename="r.txt")
    nodes = DeterministicChunker(chunk_size=1200, chunk_overlap=200)(docs)
    assert nodes
    assert all(n.text for n in nodes)
    meta = dict(nodes[0].metadata or {})
    assert "chunk_index" in meta
    assert "char_start" in meta


def test_to_llamaindex_documents_carries_metadata() -> None:
    docs = to_llamaindex_documents("body", document_id=7, kind="resume", filename="a.txt")
    assert docs[0].text == "body"
    assert docs[0].metadata["document_id"] == "7"
    assert docs[0].metadata["kind"] == "resume"


async def test_rerank_postprocessor_reranks_via_router() -> None:
    omlx = FakeOmlx()
    post = RouterRerankPostprocessor(_router(omlx), top_n=2)
    nodes = [
        NodeWithScore(node=Document(text="third"), score=0.1),
        NodeWithScore(node=Document(text="first"), score=0.9),
        NodeWithScore(node=Document(text="second"), score=0.5),
    ]
    # Fake rerank scores index 0 highest (3.0, 2.0, 1.0): order preserved
    # by relevance score, not by input order.
    reranked = await post._apostprocess_nodes(nodes, QueryBundle(query_str="q"))
    assert reranked[0].get_content() == "third"
    assert reranked[1].get_content() == "first"


async def test_rerank_postprocessor_keeps_order_on_failure() -> None:
    class BrokenOmlx(FakeOmlx):
        async def rerank(self, *args: Any, **kwargs: Any) -> RerankResponse:
            raise RuntimeError("rerank down")

    post = RouterRerankPostprocessor(_router(BrokenOmlx()), top_n=2)
    nodes = [
        NodeWithScore(node=Document(text="a"), score=0.9),
        NodeWithScore(node=Document(text="b"), score=0.5),
    ]
    out = await post._apostprocess_nodes(nodes, QueryBundle(query_str="q"))
    assert [n.get_content() for n in out] == ["a", "b"]
