# Pramya — Agent Instructions

## Project

Pramya is a greenfield, evidence-driven interview preparation platform.

Product identity:

> Pramya — prove you're ready.

The project is intended to become a genuinely usable, production-quality product rather than a demonstration application.

---

## Source of Truth

The repository is the long-term source of truth.

Before making substantial changes:

1. Read this file.
2. Read the relevant sections of `docs/MASTER_IMPLEMENTATION_PLAN.md`.
3. Read `docs/PROJECT_MEMORY.md`.
4. Read relevant entries in `docs/DECISIONS.md`.
5. Inspect the actual implementation and tests.
6. Never assume that an old plan or previous conversation accurately describes the current implementation.

When documentation and implementation disagree, investigate the discrepancy and update the appropriate documentation rather than blindly following stale information.

---

## Project Memory

`docs/PROJECT_MEMORY.md` is persistent project memory maintained by the agent.

Update it when meaningful long-term knowledge is discovered, including:

- important implementation discoveries
- recurring problems
- infrastructure constraints
- development environment facts
- important integration details
- lessons learned
- non-obvious operational knowledge
- decisions that future sessions need to remember
- known limitations
- things that should not be repeated

Do NOT update it for every trivial implementation detail.

Do NOT turn it into a session transcript.

Keep it concise, factual, and useful to a future engineering session.

---

## Master Implementation Plan

`docs/MASTER_IMPLEMENTATION_PLAN.md` is the authoritative execution plan.

The agent must maintain it as implementation progresses.

It should reflect:

- current phase
- current work
- completed work
- upcoming work
- dependencies
- blockers
- acceptance criteria
- known issues
- deferred scope
- architectural status

Do not mechanically mirror every tiny coding task into the plan.

Update the plan when the actual state of the project materially changes.

---

## Architectural Principles

Pramya must be engineered as a real product.

Prefer:

- simple architecture
- modular design
- explicit boundaries
- deterministic logic where possible
- typed interfaces
- testable components
- observable AI operations
- graceful failure
- explicit state
- evidence provenance
- reproducibility
- maintainability

Avoid:

- unnecessary abstractions
- premature microservices
- framework-for-framework's-sake
- model sprawl
- unnecessary dependencies
- giant unstructured modules
- hidden state
- duplicated business logic

A modular monolith is preferred unless a concrete requirement proves otherwise.

---

## AI Engineering

LLMs are components of the system, not the system itself.

Do not use an LLM when deterministic code is sufficient.

AI/model/provider-specific implementation must remain behind appropriate interfaces.

Do not scatter provider-specific calls throughout business logic.

Treat model output as untrusted data.

Validate structured outputs before they affect application state.

Never allow the AI to invent candidate experience or evidence.

Preserve evidence provenance.

---

## Evidence

Pramya is evidence-driven.

Candidate information must distinguish between concepts such as:

- claimed
- observed
- demonstrated
- inferred
- unknown

Never present an inference as candidate-provided fact.

Never fabricate experience, achievements, skills, or interview history.

---

## Voice

Voice is a first-class product capability.

The system must explicitly model states such as:

- listening
- processing
- speaking
- paused
- interrupted
- cancelled
- completed
- error

Interruption and cancellation are correctness requirements.

Never allow stale TTS to continue after an interview turn has been interrupted or cancelled.

---

## Frameworks

Use frameworks because they provide a real architectural responsibility.

Do not add:

- LangChain
- LangGraph
- LlamaIndex
- additional AI frameworks
- infrastructure
- packages

merely to increase the technology list.

Every major framework should have a documented responsibility.

---

## Local AI

Local models are first-class components.

Respect the target development hardware and memory constraints.

Prefer:

- lazy loading
- resource-aware model lifecycle
- caching
- deterministic preprocessing
- appropriate model routing
- bounded concurrency

Do not assume all local models can remain loaded simultaneously.

---

## Testing

Never claim that something works without verification.

For meaningful implementation work:

1. run relevant tests
2. inspect failures
3. fix regressions
4. inspect the diff
5. verify the affected user flow

AI functionality must eventually have regression/evaluation coverage rather than relying only on subjective inspection.

---

## Security and Privacy

Treat all candidate-provided data as sensitive application data.

This includes:

- resumes
- job descriptions
- interview transcripts
- audio
- personal information
- API credentials

Never commit secrets.

Never log secrets.

Avoid unnecessarily logging candidate content.

Treat uploaded documents as untrusted input.

---

## Git

Git history should look like normal professional engineering work.

Do NOT commit every minor task.

Do NOT create a commit for every file or function.

Commit coherent feature-level or implementation-level changes.

Commit messages should be:

- short
- natural
- human-written
- descriptive of the meaningful change

Avoid generic AI-generated messages such as:

- `feat: implement feature`
- `chore: update files`
- `implement phase 3`
- `complete task 4.2`
- `refactor code`
- `add comprehensive functionality`

Do not mechanically map plan tasks to commits.

Do not manufacture commit history.

Before committing:

1. inspect the diff
2. verify unrelated changes are excluded
3. run relevant tests
4. inspect staged changes
5. write a concise commit message
6. commit

---

## Documentation

Documentation must describe reality.

Do not update documentation merely to make progress appear complete.

Important architectural decisions belong in `docs/DECISIONS.md`.

Long-term project knowledge belongs in `docs/PROJECT_MEMORY.md`.

Execution state belongs in `docs/MASTER_IMPLEMENTATION_PLAN.md`.

---

## Session Completion

At the end of a substantial implementation session:

1. verify the actual project state
2. run relevant tests
3. update project memory if meaningful knowledge was discovered
4. update the master implementation plan
5. record important decisions
6. inspect the Git diff
7. commit only coherent completed work

Do not leave the repository in a state that the next session cannot understand.

---

## Greenfield Rule

Pramya started from scratch.

Do not assume an existing backend, frontend, database, architecture, deployment environment, or application structure unless it has actually been created in the repository.

Build the system incrementally.

---

## Core Principle

The goal is not to make the project look impressive.

The goal is to build something that is actually excellent.

Optimize for:

**correctness → usability → architecture → reliability → maintainability → polish**

in that order.