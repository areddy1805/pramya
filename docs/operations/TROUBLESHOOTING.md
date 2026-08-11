# Pramya — Troubleshooting

> Living runbook. Add entries as real issues are hit; keep them actionable.

---

## 1. Common Failure Modes → Recovery

| Symptom | Cause | Fix |
|---|---|---|
| Interview stuck at processing | DeepSeek timeout / LLM failure | Check logs for provider error; session should transition to error_recovery and offer retry. Verify DEEPSEEK_API_KEY. |
| Voice: no transcript appears | oMLX/parakeet-mlx down or OMLX_BASE_URL wrong | `curl $OMLX_BASE_URL/models`; restart oMLX; app falls back to manual transcript mode — UI must show that. |
| Voice: no interviewer audio | TTS failure (mlx-audio / oMLX audio endpoint) | Check model loaded; fallback = text response; verify audio endpoint support (Phase 7 note). |
| Stale TTS after interrupt | Client buffer not cleared or server queue not cancelled | Bug in interrupt path — see voice test matrix; both server `tts_stop` + client AudioWorklet clear must run. |
| Browser refresh loses state | LangGraph checkpoint missing | Verify thread_id = session id; PostgresSaver configured; durability not "exit". |
| Duplicated questions after resume | Idempotency key missing on answer | Turn idempotency keys must be honored; test in Phase 3. |
| Retrieval returns garbage | Embedding dimension mismatch / index wrong | BGE-M3 = 1024; verify `document_chunk.embedding` column and HNSW ops; re-ingest after model change. |
| Re-ingestion duplicates chunks | LlamaIndex no vector-store dedup | Use explicit docstore (content hash); delete-by-document on replace. |
| Memory pressure on M4 | Too many models loaded | oMLX pinning/TTL; 4-bit; don't load Qwen3-ASR during live sessions (recorded only). |
| DeepSeek errors on penalties | frequency/presence penalty used | Removed/unsupported — do not send. |
| Legacy model ID error | deepseek-chat / deepseek-reasoner used | Use `deepseek-v4-flash`. |
| Structured output invalid repeatedly | Schema drift / prompt mismatch | Bump evaluation_version; check golden eval; retry-feedback loop should have caught it. |
| Langfuse data delayed | SDK <4.7 with v4 server | Upgrade SDK; real-time ingestion needs ≥4.7. |
| MCP client cannot connect | SDK version mismatch (v1 vs v2 protocol) | Re-verify at Phase 11; pin SDK; streamable-http transport. |

## 2. Environment Checks

```bash
docker compose ps                # db up?
curl http://localhost:8000/api/v1/health
curl $OMLX_BASE_URL/models       # local models?
make test                        # unit+integration
make evals                       # AI eval suite
```

## 3. Where to Look First

- Logs: `backend` stdout (structured JSON; request_id/session_id correlation).
- Langfuse (if enabled): trace per interview/session.
- `docs/MODEL_CATALOG.md`: model pins + licenses.
- `docs/MASTER_IMPLEMENTATION_PLAN.md` §35: phase/status; §29 risk register.

## 4. Known Platform Quirks (verified)

- Parakeet v3 = chunked pseudo-streaming (no cache-aware streaming) — expected; latency handled by commit policy.
- DeepSeek thinking mode: temperature/top_p inert; cache-hit tokens reported via usage fields.
- LlamaIndex: `IngestionPipeline` doesn't dedupe against vector store; node hash excludes metadata.
- MCP Python SDK v2 renamed `FastMCP` → `MCPServer` (2026-07-28 protocol revision) — import from `mcp.server`.
- oMLX: audio endpoint support for Parakeet/Qwen3-ASR/Qwen3-TTS must be verified at Phase 7; direct mlx paths are the fallback.
- Qwen3.5 checkpoints are VLM — use text-only inference path with correct chat template.

## 5. Performance Reference Points (fill after measurement)

- TTF-transcript (live): target < ___ ms (Phase 8)
- TTFA: target < ___ ms
- Question gen latency (deepseek): ___ ms p50/p95
- Retrieval p50: ___ ms; rerank added: ___ ms
- Memory peak (all services + oMLX loaded models): ___ GB
- Cost per 15-min interview (cloud share): $___
