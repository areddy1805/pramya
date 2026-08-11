# Pramya — Security

> ADR-013 (docs/architecture/0013-security-and-pii.md). Threat model + controls. Published posture for users.

## Data We Process

Resumes, job descriptions, interview answers, transcripts, voice recordings,
personal information. All treated as sensitive application data.

## Controls

- **Upload validation**: size limit, type allowlist (PDF/DOCX/TXT/MD), page
  limits, content scanning, safe parsers (pypdf/python-docx), no arbitrary
  URL fetch (SSRF care).
- **Prompt injection**: strict separation SYSTEM / USER DATA / DOCUMENT
  DATA / RETRIEVED EVIDENCE / MODEL OUTPUT; documents never become
  instructions; delimiters + validation; adversarial-document fixtures in
  tests.
- **LLM output gate**: LLM → structured proposal → Pydantic validation →
  application logic → persistence. Model cannot write privileged state.
- **Evidence provenance**: no fabricated experience; provenance classes
  (claimed/observed/demonstrated/inferred/unknown); immutable ledger.
- **Secrets**: env-only, never committed; `.env.example` only; no logging of
  keys; rotation documented.
- **PII / logging**: redaction layer; no raw candidate content in logs or
  traces; IDs + metadata only.
- **Retention & deletion**: configurable audio retention (off by default);
  deletion endpoints for profile, sessions, audio, transcripts; cascades.
- **API hardening**: CORS policy, rate limiting, request validation, secure
  headers; auth only if deployment requires (not a V1 blocker).
- **Local-only mode**: no candidate data leaves the machine when local
  routing suffices; DeepSeek calls only when configured/needed.

## Reporting

Security issues: see SECURITY.md (root) responsible-disclosure instructions.

## Verification

- Tests: injection fixtures, oversized uploads, structured-output
  validation, redaction assertions, authz checks.
- CI: secret scanning, dependency advisories, lint.
- Review: security review before v1 release (Release Standard).
