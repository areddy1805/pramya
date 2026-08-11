# Pramya

> **Pramya — prove you're ready.**

Evidence-driven interview preparation.

Pramya is a new open-source project for serious interview preparation across technical and professional roles.

It is being designed around a simple idea:

> Don't just practice answers. Build evidence that you're ready.

## Status

**Early development — architecture and implementation planning.**

The product is not yet ready for general use.

## Vision

Pramya will combine:

- resume and profile understanding
- job-description analysis
- candidate evidence
- adaptive mock interviews
- technical and behavioral preparation
- evidence-backed evaluation
- targeted practice
- longitudinal progress
- retrieval
- modern AI orchestration
- local AI inference
- voice interviewing
- streaming speech
- interruption and resume support

The goal is to build a genuinely useful interview-preparation product rather than a generic LLM chat interface.

## AI Architecture

The planned V1 AI stack includes:

- DeepSeek V4 Flash (escalation/cloud reasoning only)
- Qwen3.5-4B (primary local workhorse, alias `pramya-4b`)
- BGE-M3
- Qwen3-Reranker-0.6B
- Parakeet TDT 0.6B v3
- Qwen3-ASR 1.7B
- Qwen3-TTS 0.6B

The architecture uses model routing so that each task is handled by an appropriate capability rather than sending every operation to a single model. Local 4B handles the majority of workload; cloud escalation is reserved for workloads where additional capability is justified. (Qwen3.5-9B is deferred from the V1 stack — see docs/MODEL_CATALOG.md.)

## Technology

The planned architecture includes:

- React
- TypeScript
- Python
- FastAPI
- LangGraph
- LangChain
- LlamaIndex
- MLX/oMLX
- retrieval and reranking
- structured AI evaluation
- streaming voice
- Docker
- GitHub Actions

The final responsibilities of each technology will be documented during the architecture phase.

## Development

See:

- `AGENTS.md`
- `docs/PROJECT_MEMORY.md`
- `docs/MASTER_IMPLEMENTATION_PLAN.md`
- `docs/DECISIONS.md`

## License

See `LICENSE`.