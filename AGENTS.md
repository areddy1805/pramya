# Pramya — Agent Instructions
When the user authorizes implementation of the remaining roadmap, execute
the Master Implementation Plan autonomously from the current phase through
the final planned phase. A completed phase is a transition point, not a stop
condition. Stop only when the roadmap is complete or a genuine blocker
requires user input.
## 1. Project
Pramya is a greenfield, evidence-driven interview preparation platform.
Product identity:
> Pramya — prove you're ready.
The project is intended to become a genuinely usable, production-quality product rather than a demonstration application.
The repository is the long-term source of truth.
The agent's job is to make the repository progressively more correct, reliable, understandable, and production-ready.
The agent is NOT rewarded for:
- maximum code changed
- maximum number of phases completed
- maximum tool calls
- maximum autonomous execution time
- making test output look green
- exhausting available context
- continuing after the useful work is complete
The correct stopping point is part of the engineering task.
---
# 2. Source of Truth
Before making substantial changes:
1. Read this file.
2. Read the relevant sections of `docs/MASTER_IMPLEMENTATION_PLAN.md`.
3. Read `docs/PROJECT_MEMORY.md`.
4. Read relevant entries in `docs/DECISIONS.md`.
5. Inspect the actual implementation.
6. Inspect the relevant tests.
7. Verify the current Git state.
Never assume that:
- an old plan describes the current implementation,
- a previous agent session was correct,
- a previous conversation accurately describes the repository,
- a task is incomplete merely because documentation says so,
- a task is complete merely because an agent previously said so.
When documentation and implementation disagree:
1. inspect both,
2. determine the actual state,
3. preserve the evidence,
4. update the appropriate documentation.
Never silently reconcile conflicting sources by guessing.
---
# 3. Project Memory
`docs/PROJECT_MEMORY.md` is persistent project memory maintained by the agent.
Update it when meaningful long-term knowledge is discovered, including:
- important implementation discoveries
- recurring problems
- infrastructure constraints
- development environment facts
- important integration details
- lessons learned
- non-obvious operational knowledge
- decisions future sessions need to remember
- known limitations
- things that should not be repeated
Do NOT update it for:
- trivial implementation details
- every command executed
- temporary debugging state
- ordinary test results
- session transcripts
Keep it concise, factual, and useful to a future engineering session.
---
# 4. Master Implementation Plan
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
Update the plan when the actual state materially changes.
The implementation plan is NOT permission to execute every future phase automatically.
---
# 5. Autonomous Phase Execution

The master implementation plan is the authoritative execution queue.

When the user instructs the agent to implement the remaining roadmap,
all subsequent planned phases are authorized for autonomous execution.

The currently active phase is the current implementation scope.

The agent MUST:
1. complete the active phase,
2. validate it,
3. update the master plan,
4. commit coherent completed work,
5. determine the next planned phase,
6. automatically begin that phase,
7. continue until the roadmap is complete or a genuine blocker requires
   user input.

Do NOT stop merely because a phase has completed.

Do NOT ask the user:
- "Should I continue?"
- "Ready for the next phase?"
- "Would you like me to proceed?"
- "Phase X is complete; awaiting instruction."

Normal phase completion is an automatic transition point.

The execution loop is:

INSPECT
→ PLAN
→ IMPLEMENT
→ VALIDATE
→ DEBUG
→ REGRESSION VALIDATE
→ AUDIT SCOPE
→ UPDATE PLAN
→ COMMIT
→ VERIFY
→ NEXT PHASE
→ repeat

Future phases remain out of scope only when the current user instruction
explicitly limits execution to a particular phase/task.

Do NOT partially implement future-phase functionality merely because it is
convenient.

If a future-phase dependency is required by the active phase:
implement only the minimum required dependency, record it in the plan,
and continue.

If a future-phase item is discovered but is not required:
record it as deferred and continue the current execution sequence.

A phase boundary is therefore a CONTROLLED TRANSITION, not an AUTOMATIC
STOP CONDITION.
---
# 6. Mandatory Execution Lifecycle
Every implementation task follows:
```text
INSPECT
  ↓
DEFINE ACCEPTANCE CRITERIA
  ↓
PLAN SMALLEST CHANGE
  ↓
IMPLEMENT
  ↓
FOCUSED VALIDATION
  ↓
FIX CONCRETE FAILURES
  ↓
BROADER VALIDATION
  ↓
DIFF / SCOPE REVIEW
  ↓
DOCUMENT ACTUAL STATE
  ↓
COMMIT IF APPROPRIATE
  ↓
STOP

Do not skip stages because the change appears simple.

Do not continue implementation after the acceptance criteria are satisfied merely because additional improvements are visible.

A passing acceptance criterion is a valid stopping condition.

⸻

7. Evidence Before Editing

Every non-trivial code change must have a concrete basis.

A change must be justified by at least one of:

* explicit requirement
* acceptance criterion
* observed test failure
* observed production defect
* documented architectural decision
* required integration contract
* security/privacy requirement

Before editing because of a test failure, be able to state:

Observed:
Expected:
Actual:
Root cause:
Minimal correction:

If this cannot yet be stated with reasonable confidence:

DO NOT EDIT.

Inspect more first.

Do not make speculative changes merely to see whether the test passes.

⸻

8. Smallest Correct Change

Prefer the smallest change that satisfies the requirement.

Avoid:

* speculative abstractions
* broad refactors
* unrelated cleanup
* replacing working implementations without evidence
* changing public contracts unnecessarily
* changing multiple architectural layers when one layer is sufficient

If a larger change is genuinely required:

1. explain why,
2. identify the affected boundaries,
3. implement it deliberately,
4. validate each affected area.

Do not use a large refactor to hide a small bug.

⸻

9. Test Failure Protocol

When a test fails, DO NOT immediately edit code.

Follow this exact sequence:

Step 1 — Reproduce

Run the smallest command that reproduces the failure.

Prefer:

one failing test

over:

entire repository suite

Step 2 — Capture

Capture the complete:

* assertion
* traceback
* relevant logs
* actual value
* expected value

Do not rely on truncated output.

Step 3 — Classify

Classify the failure as exactly one of:

IMPLEMENTATION_DEFECT
TEST_DEFECT
ENVIRONMENT_ISOLATION_DEFECT
TEST_FIXTURE_DEFECT
NONDETERMINISTIC_MODEL_VARIANCE
INFRASTRUCTURE_FAILURE
UNKNOWN

Step 4 — Inspect

Inspect the relevant:

* implementation
* test
* fixture
* configuration
* contract
* dependency

Step 5 — Correct

Make the smallest evidence-backed correction.

Step 6 — Reproduce

Run the failing test again.

Step 7 — Broaden

Only after the focused test passes, run the affected subset.

⸻

10. Never Manufacture Green

Never:

* lower a threshold merely to make a test pass
* weaken an assertion without documented justification
* delete a failing test because it is inconvenient
* convert FAIL into WARNING without evidence
* convert WARNING into PASS
* mark NOT_VERIFIED as PASS
* alter expected values merely to match implementation output
* suppress meaningful errors
* hide failures in command output

If the implementation is correct and the test is wrong, fix the test and document why.

If the test is correct and the implementation is wrong, fix the implementation.

If the situation cannot yet be determined, leave it unresolved and report it honestly.

⸻

11. Two-Failure Rule

If two evidence-based fixes for the same root problem fail:

STOP IMPLEMENTING.

Do not make a third speculative fix.

Produce:

ROOT CAUSE:
OBSERVED EVIDENCE:
ATTEMPT 1:
RESULT 1:
ATTEMPT 2:
RESULT 2:
REMAINING HYPOTHESIS:
RECOMMENDED NEXT INVESTIGATION:

Then stop.

A third attempt is allowed only after new evidence changes the diagnosis.

⸻

12. Hard Debugging Limits

No diagnostic command may run indefinitely.

Every potentially long-running command MUST have a bounded timeout.

This applies to:

* pytest
* Python scripts
* shell scripts
* subprocesses
* HTTP calls
* WebSocket tests
* model calls
* database operations
* browser automation
* Docker operations
* external services
* async diagnostics

A diagnostic that hangs is itself a failure condition.

If a command:

* exceeds its expected duration,
* stops producing useful output,
* becomes obviously stuck,
* repeatedly retries,
* consumes disproportionate resources,

STOP IT.

Do not wait indefinitely.

Do not launch another equivalent diagnostic while the first one is still running.

Do not leave background processes running.

⸻

13. Async / WebSocket / Voice Safety

Pramya contains asynchronous and voice systems.

For any code involving:

* asyncio
* WebSockets
* ASR
* TTS
* audio capture
* audio playback
* background workers
* timers
* task groups
* cancellation
* reconnects

tests and diagnostics must have:

* bounded timeouts
* deterministic teardown
* task cancellation
* awaited task completion where appropriate
* cleanup of sockets
* cleanup of temporary files
* cleanup of subprocesses

Never write a diagnostic loop that waits forever for a state transition.

Never create a background task without a known lifecycle.

A hanging async test is a FAILURE, not a useful diagnostic state.

⸻

14. No Ad-Hoc Debugging Scripts When Tests Can Reproduce It

Prefer the existing test framework.

If an existing pytest test reproduces the issue:

DO NOT create a standalone Python diagnostic unless there is a concrete reason the test framework cannot expose the required evidence.

If a standalone diagnostic is genuinely required:

* give it a hard timeout,
* guarantee cleanup,
* make it minimal,
* do not leave it in the repository,
* stop it immediately when useful evidence is obtained.

Never allow an ad-hoc diagnostic to become an uncontrolled second implementation.

⸻

15. Validation Order

Validation must proceed from cheapest and most deterministic to most expensive and nondeterministic.

Preferred order:

1. syntax
2. imports
3. formatter
4. linter
5. focused unit test
6. affected unit-test subset
7. full deterministic unit/contract suite
8. integration tests
9. E2E
10. model/evaluation tests
11. external APIs/services

Do not spend expensive model/API calls while deterministic local tests are failing.

Do not invoke an LLM to diagnose something that ordinary code/tests can determine.

⸻

16. Local-First Development

When local validation is possible:

USE LOCAL VALIDATION FIRST.

Examples:

* syntax → local
* lint → local
* formatting → local
* unit tests → local
* contract tests → local
* deterministic integration tests → local

External model/API validation should occur only after local deterministic validation is healthy.

If external credentials or services are unavailable:

mark them:

NOT_VERIFIED

Do not substitute “probably works.”

⸻

17. LLM / Model Discipline

LLMs are components of the system, not the system itself.

Do not use an LLM when deterministic code is sufficient.

For agent execution:

Do not call DeepSeek, OpenAI, or another external model to debug:

* syntax
* imports
* ordinary assertions
* deterministic business logic
* filesystem errors
* environment configuration
* test isolation
* straightforward type errors
* ordinary async lifecycle bugs

Model calls are expensive and potentially nondeterministic.

Use them only when their reasoning capability materially contributes to the task.

⸻

18. Model Variance

AI evaluation results must distinguish:

PASS
FAIL
WARNING
NOT_VERIFIED
BLOCKED

Model variance is not equivalent to deterministic correctness.

If repeated evaluation produces different results:

record it as variance.

Do not:

* silently select the favorable result,
* turn variance into PASS,
* lower thresholds,
* modify the golden dataset solely to eliminate the warning,
* claim deterministic correctness.

The primary evaluation result and variance evidence must remain distinguishable.

⸻

19. Cost and Resource Discipline

Agent execution must be resource-aware.

Avoid unnecessary:

* LLM calls
* repeated repository-wide searches
* repeated full test suites
* repeated dependency inspection
* repeated model evaluations
* long-running diagnostics

Before executing an expensive operation, ask internally:

Can this be answered deterministically from the repository?
Can a smaller command provide the evidence?
Has this already been established?

If yes, use the cheaper deterministic path.

Do not continue a task because additional model/context budget is available.

Available budget is not a requirement to spend it.

⸻

20. Context Discipline

Do not repeatedly reread the entire repository when the relevant scope is known.

Use targeted inspection.

Prefer:

specific file
specific function
specific test
specific configuration
specific documentation section

over:

entire repository

Re-read broader context only when the evidence indicates that local context is insufficient.

Maintain a compact mental working set:

current requirement
relevant architecture
affected files
failing tests
acceptance criteria

Do not accumulate unnecessary historical context.

⸻

21. AI Engineering

AI/model/provider-specific implementation must remain behind appropriate interfaces.

Do not scatter provider-specific calls throughout business logic.

Treat model output as untrusted data.

Validate structured outputs before they affect application state.

Preserve:

* provenance
* confidence
* source evidence
* model/provider metadata where appropriate
* failure state

Never allow AI to invent:

* candidate experience
* candidate achievements
* skills
* interview history
* evidence
* employment history

⸻

22. Evidence Model

Pramya is evidence-driven.

Candidate information must distinguish between concepts such as:

* claimed
* observed
* demonstrated
* inferred
* unknown

Never present an inference as candidate-provided fact.

Never fabricate experience, achievements, skills, or interview history.

When evidence is missing:

represent the absence explicitly.

⸻

23. Voice Architecture

Voice is a first-class product capability.

The system must explicitly model states such as:

* idle
* starting
* listening
* processing
* speaking
* paused
* interrupted
* cancelled
* completed
* error

Interruption and cancellation are correctness requirements.

Never allow:

* stale TTS after interruption
* stale TTS after cancellation
* duplicate answer submission
* stale turn state after reconnect
* uncontrolled background audio tasks
* silent task failures

Reconnect behavior must be based on authoritative persisted state rather than client assumptions.

Voice persistence must respect security, retention, and privacy requirements.

⸻

24. Audio Persistence and Privacy

Audio is sensitive candidate data.

Any audio persistence implementation must explicitly define:

* whether persistence is enabled
* storage location
* retention period
* ownership/access control
* deletion behavior
* missing-file behavior
* failure behavior
* whether persistence is required or optional

Do not silently introduce permanent/default-on recording behavior without an explicit product/security decision.

A field such as retention_days does not by itself constitute a retention system.

⸻

25. Frameworks

Use frameworks because they provide a real architectural responsibility.

Do not add:

* LangChain
* LangGraph
* LlamaIndex
* additional AI frameworks
* infrastructure
* packages

merely to increase the technology list.

Every major framework must have a documented responsibility.

Avoid dependency sprawl.

⸻

26. Local AI

Local models are first-class components.

Respect target development hardware and memory constraints.

Prefer:

* lazy loading
* resource-aware model lifecycle
* caching
* deterministic preprocessing
* appropriate model routing
* bounded concurrency
* graceful degradation

Do not assume all local models can remain loaded simultaneously.

Do not introduce concurrent model workloads without understanding their resource impact.

⸻

27. Security and Privacy

Treat all candidate-provided data as sensitive application data.

This includes:

* resumes
* job descriptions
* interview transcripts
* audio
* personal information
* API credentials

Never:

* commit secrets
* log secrets
* expose credentials
* unnecessarily log candidate content
* assume uploaded documents are trusted
* expose another user’s interview/audio data

Uploaded documents are untrusted input.

Authorization must be enforced server-side.

Resource ownership must be checked before returning:

* interviews
* transcripts
* audio
* candidate evidence
* reports
* analytics

Do not rely solely on frontend restrictions.

⸻

28. Database and Persistence

Persistent state is authoritative state.

Do not introduce in-memory state as the sole source of truth for information that must survive:

* reconnect
* restart
* process failure
* browser refresh
* session migration

When persistence is introduced:

consider:

* idempotency
* transaction boundaries
* partial failure
* duplicate writes
* retention
* cleanup
* migrations
* recovery

Do not claim persistence merely because a row is written in the happy path.

⸻

29. Error Handling

Errors must be explicit.

Prefer:

* typed/domain errors
* meaningful error codes
* structured logs
* graceful degradation where appropriate
* clear client-visible failure states

Do not broadly swallow exceptions merely to keep a test green.

If an operation is intentionally best-effort:

document that behavior explicitly.

Best-effort behavior must not hide security, data-integrity, or correctness failures.

⸻

30. Observability

Observability must support understanding system behavior without leaking sensitive data.

Record useful metadata such as:

* operation
* session ID
* request ID
* latency
* provider
* model
* status
* error classification

Avoid raw candidate content unless explicitly required and appropriately protected.

Observability failures must not normally take down the core application path.

⸻

31. Git Discipline

Git history should look like normal professional engineering work.

Do NOT:

* commit every minor task
* create a commit for every file
* manufacture commit history
* create artificial commits merely to mark phase numbers
* commit temporary diagnostics
* commit local runtime state
* commit credentials

Commit coherent feature-level or implementation-level changes.

Commit messages should be:

* short
* natural
* human-written
* descriptive of the meaningful change

Avoid generic AI-generated messages such as:

feat: implement feature
chore: update files
implement phase 3
complete task 4.2
refactor code
add comprehensive functionality

Do not mechanically map plan tasks to commits.

⸻

32. Pre-Commit Gate

Before committing:

1. inspect git status
2. inspect git diff --stat
3. inspect relevant diff
4. ensure unrelated changes are excluded
5. run required tests
6. inspect staged changes
7. verify no secrets/runtime artifacts are staged
8. write a concise commit message
9. commit
10. run git status --short again

A clean worktree is preferred after a completed task.

If unrelated pre-existing modifications exist:

do not overwrite, revert, or include them without explicit reason.

⸻

33. Diff Discipline

After meaningful implementation:

git status --short
git diff --stat
git diff -- <affected files>

Check:

* scope
* accidental edits
* generated files
* credentials
* temporary diagnostics
* unrelated refactors
* unexpected dependency changes

If the diff is materially larger than the requirement:

STOP.

Investigate scope creep before continuing.

⸻

34. Documentation

Documentation must describe reality.

Do not update documentation merely to make progress appear complete.

Important architectural decisions belong in:

docs/DECISIONS.md

Long-term project knowledge belongs in:

docs/PROJECT_MEMORY.md

Execution state belongs in:

docs/MASTER_IMPLEMENTATION_PLAN.md

Tests/evaluation methodology belongs with the relevant evaluation documentation.

Never document an unverified claim as fact.

⸻

35. Honest Status

Use explicit status terminology.

Allowed:

PASS
FAIL
WARNING
NOT_VERIFIED
BLOCKED
IN_PROGRESS
COMPLETE WITH KNOWN WARNINGS

Do not call a phase:

green
fully complete
production-ready
done

when required validation is failing or missing.

Examples:

157 unit+contract tests PASS.
External model validation NOT_VERIFIED.
Phase H IN_PROGRESS.
18 tests PASS.
3 tests FAIL.
Phase F COMPLETE WITH KNOWN WARNINGS.
95 checks: 0 FAIL, 3 WARNING.

The report must reflect the actual evidence.

⸻
# 36. Stop Conditions

STOP autonomous execution only when one of the following is true:

1. ALL planned V1 phases are complete.

2. A genuine BLOCKED condition exists that cannot reasonably be resolved
   autonomously.

3. A required architectural/product/security decision is not established
   anywhere in the repository, accepted ADRs, master plan, or explicit
   user instructions.

4. Required external infrastructure is unavailable and the blocked
   capability is mandatory for the current acceptance criteria.

5. Continuing would require an irreversible or materially destructive
   action not already authorized by the project specification.

6. Resource constraints make continued execution unsafe.

7. The same root problem has failed two evidence-based correction attempts
   without new evidence.

8. A diagnostic or implementation process becomes uncontrolled despite
   bounded execution safeguards.

DO NOT stop merely because:

- the current phase is complete,
- the current acceptance criteria pass,
- a commit was created,
- the next phase is obvious,
- a completion report was generated.

When a phase is complete and the next phase is defined by the master plan:

CONTINUE.

"Acceptance criteria satisfied" means:

CURRENT PHASE COMPLETE → VALIDATE → COMMIT → ADVANCE.

It does NOT mean:

CURRENT PHASE COMPLETE → STOP ENTIRE EXECUTION..

⸻

37. Never Fix Forward From a Broken State

If a change causes an unrelated test to fail:

STOP.

Determine whether:

1. the new change is wrong,
2. the test depends on ambient environment,
3. the test fixture is wrong,
4. the contract genuinely changed.

Do not immediately add another change to restore green.

Do not create a chain:

failure
→ patch
→ new failure
→ patch
→ new failure
→ patch
→ unrelated refactor

Break the chain.

Return to evidence.

⸻

38. Phase Completion

A phase is complete only when:

1. implementation satisfies its acceptance criteria,
2. required deterministic tests pass,
3. known warnings are documented,
4. unresolved failures are explicitly classified,
5. scope is reviewed,
6. documentation reflects reality,
7. the relevant commit is created if appropriate.

A phase may legitimately end as:

COMPLETE WITH KNOWN WARNINGS

It must not be falsely represented as fully green.

⸻

39. Phase Completion Report

At the end of every substantial phase/task, report:

PHASE:
STATUS:
IMPLEMENTED:
- ...
VALIDATION:
- ...
WARNINGS:
- ...
FAILURES:
- ...
NOT_VERIFIED:
- ...
DEFERRED:
- ...
COMMIT:
- hash + message
WORKTREE:
- clean / dirty
NEXT PHASE:
- phase/task identified from MASTER_IMPLEMENTATION_PLAN.md

If autonomous roadmap execution is active:
- automatically begin the next phase after the completion report.

A completion report is a checkpoint artifact, not a permission gate.

⸻


40. Session Completion

At the end of a substantial implementation session:

1. verify actual project state
2. run relevant deterministic tests
3. classify remaining failures
4. update project memory if meaningful knowledge was discovered
5. update the master implementation plan
6. record important architectural decisions
7. inspect Git diff
8. commit only coherent completed work
9. verify final Git status
10. stop

Do not leave the repository in a state that the next session cannot understand.
⸻

41. Greenfield Rule

Pramya started from scratch.

Do not assume an existing:

* backend
* frontend
* database
* architecture
* deployment environment
* application structure

unless it actually exists in the repository.

Build incrementally.

Do not introduce compatibility layers for imaginary legacy systems.

⸻

42. Agent Autonomy Boundary

The agent may autonomously:

* inspect files
* implement the assigned task
* run deterministic tests
* fix concrete regressions
* update relevant documentation
* perform focused refactors required by the task
* commit coherent completed work when instructed by the workflow

The agent must NOT autonomously:

* begin future phases
* redesign the entire system
* change major architectural direction
* add unrelated frameworks
* change security/privacy policy
* change data-retention policy
* introduce expensive external services
* make irreversible infrastructure changes
* manufacture test success
* continue indefinitely after reaching a stop condition

When an architectural/product/security decision is required:

STOP and report the decision required.

⸻

43. Core Engineering Principles

Pramya must be engineered as a real product.

Prefer:

* simple architecture
* modular design
* explicit boundaries
* deterministic logic where possible
* typed interfaces
* testable components
* observable AI operations
* graceful failure
* explicit state
* evidence provenance
* reproducibility
* maintainability
* security
* privacy
* bounded resource usage

Avoid:

* unnecessary abstractions
* premature microservices
* framework-for-framework’s-sake
* model sprawl
* unnecessary dependencies
* giant unstructured modules
* hidden state
* duplicated business logic
* speculative engineering

A modular monolith is preferred unless a concrete requirement proves otherwise.

⸻

44. Final Principle

The goal is not to make the project look impressive.

The goal is to build something that is actually excellent.

Optimize for:

correctness → evidence → reliability → security → usability → architecture → maintainability → polish

The agent must prefer:

small correct progress over large uncertain progress.

And above all:

When uncertain, stop and preserve the evidence rather than guessing.

### One important architectural change from your current file
I deliberately changed the priority from:
```text
correctness → usability → architecture → reliability → maintainability → polish

to:

correctness → evidence → reliability → security → usability → architecture → maintainability → polish

That is more appropriate for the way you’re building Pramya. The failure mode you just encountered was fundamentally an evidence/control problem, not a coding-capability problem.

The new AGENTS.md establishes three hard brakes that your current file lacks:

TWO FAILED FIXES → STOP
HANGING DIAGNOSTIC → KILL/STOP
ACCEPTANCE CRITERIA MET → STOP

⸻

# 45. Autonomous Roadmap Mode

When the user gives an instruction equivalent to:

- implement the remaining phases,
- finish the implementation,
- continue through the roadmap,
- complete the V1,
- implement everything remaining,
- proceed autonomously,
- finish the master plan,

interpret that instruction as:

AUTONOMOUS ROADMAP MODE = ENABLED.

When the user authorizes completion of the remaining roadmap, Autonomous
Roadmap Mode is enabled.

Execute the Master Implementation Plan from the current phase through the
final planned phase without requesting confirmation between phases.

For each phase:

INSPECT
→ DEFINE ACCEPTANCE
→ IMPLEMENT
→ FOCUSED VALIDATION
→ FIX CONCRETE FAILURES
→ BROADER VALIDATION
→ DIFF/SCOPE REVIEW
→ UPDATE PLAN/MEMORY
→ COMMIT
→ VERIFY GIT STATE
→ ADVANCE TO NEXT PHASE

A completed phase is a transition point, not a stop condition.

Continue automatically into the next planned phase unless:
- a genuine blocker requires user input;
- an architectural/product/security decision is undefined;
- the two-failure rule is triggered;
- resource usage becomes unsafe;
- required external infrastructure is unavailable;
- destructive/irreversible action requires authorization;
- or the entire authorized roadmap is complete.

Never ask for confirmation merely because a phase finished.

Autonomy controls sequencing, not engineering standards.

All existing evidence, validation, security, scope, resource, debugging,
and honesty rules remain mandatory.

AUTONOMOUS ROADMAP MODE does NOT authorize:

- arbitrary scope expansion,
- unrelated refactors,
- unapproved architecture changes,
- security/privacy policy changes,
- destructive infrastructure operations,
- fabrication of validation,
- ignoring acceptance criteria,
- bypassing the two-failure rule.

Autonomy governs SEQUENCING.
It does not remove ENGINEERING CONTROLS.
