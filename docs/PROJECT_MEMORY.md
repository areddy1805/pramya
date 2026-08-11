# Pramya — Project Memory

> Persistent engineering memory for Pramya.
>
> This file is maintained by the engineering agent across development sessions.
> It is not a session transcript and should contain only durable, useful knowledge.

---

## Current State

Project status: Greenfield — planning

Current phase: Not started

Current implementation milestone: Not started

---

## Product

Pramya is an evidence-driven interview preparation platform.

Primary positioning:

> Pramya — prove you're ready.

The product must be genuinely useful to people preparing for interviews across different technical and professional roles.

It must not be a generic AI chat application.

---

## Development Goal

The project is intentionally designed to provide substantial real-world experience with modern AI application engineering, including:

- LangGraph
- LangChain
- LlamaIndex
- RAG
- hybrid retrieval
- reranking
- structured AI outputs
- model routing
- local inference
- MLX
- speech-to-text
- text-to-speech
- streaming AI
- interruption/cancellation
- React AI UX
- evaluation
- observability
- production engineering

The product itself remains the primary concern.

---

## Target Local Hardware

Primary development machine:

- Apple Silicon M4
- 16 GB unified memory
- 512 GB storage

Local AI architecture must respect these constraints.

---

## Definitive AI Stack

The currently selected V1 model architecture is:

### Cloud reasoning

DeepSeek V4 Flash

### Local LLM

Qwen3.5-4B 4-bit

Qwen3.5-9B 4-bit

### Embeddings

BGE-M3

### Reranking

Qwen3-Reranker-0.6B 4-bit

### Live ASR

Parakeet TDT 0.6B v3

### Recorded / multilingual ASR

Qwen3-ASR 1.7B

### TTS

Qwen3-TTS 0.6B

These decisions are documented in the master planning material and should not be casually reopened.

---

## Local Runtime

The intended local AI architecture uses Apple-Silicon-native MLX/oMLX infrastructure where appropriate.

Do not introduce Ollama merely for convenience.

Speech workloads should use the appropriate MLX audio tooling rather than forcing speech models through an LLM serving layer.

---

## Voice

Voice is a first-class feature.

The intended experience includes:

- live transcription
- spoken interviewer
- streaming audio
- interruption
- pause
- resume
- stop
- cancellation
- transcript synchronization
- graceful recovery

The voice system must behave like an actual interactive interview rather than a batch transcription demo.

---

## Product Differentiator

Pramya is evidence-driven.

The system should understand:

- what the candidate claims
- what the candidate has demonstrated
- what evidence supports a claim
- what the target role requires
- where the candidate is weak
- what should be practiced next
- how the candidate changes over multiple sessions

---

## Long-Term Memory Rules

Only record information here that will materially help future engineering sessions.

Good entries:

- important architectural discoveries
- persistent integration problems
- environment constraints
- non-obvious fixes
- operational knowledge
- important lessons
- known limitations

Bad entries:

- every completed task
- every command executed
- temporary debugging output
- conversation transcripts
- trivial implementation details

---

## Known Problems

None yet.

---

## Important Lessons

None yet.

---

## Deferred Decisions

None yet.

---

## Operational Notes

None yet.