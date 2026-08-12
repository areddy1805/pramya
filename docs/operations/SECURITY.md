# Pramya — Security

> ADR-010 (docs/architecture/ADR-010-security-and-pii.md). Threat model + controls. Published posture for users.

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
- **API hardening**: CORSMiddleware applied (config `CORS_ORIGINS`);
  optional bearer-token auth (`API_TOKENS`, HTTP + voice WS `?token=`);
  per-IP rate limit (`RATE_LIMIT_RPM`, in-memory fixed window); security
  headers on every response (nosniff / frame-deny / referrer / permissions);
  request validation; upload storage keys derive from content digest +
  whitelisted extension (never client filenames). All Phase I (2026-08).
- **Local-only mode**: no candidate data leaves the machine when local
  routing suffices; DeepSeek calls only when configured/needed.

## Reporting

Security issues: see SECURITY.md (root) responsible-disclosure instructions.

## Verification

- Tests: injection fixtures, oversized uploads, structured-output
  validation, redaction assertions, authz checks.
- CI: secret scanning, dependency advisories, lint.
- Review: security review before v1 release (Release Standard).
