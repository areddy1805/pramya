#!/usr/bin/env python3
"""Seed demo data through the real API (real oMLX inference).

Exercises: candidate create -> resume upload -> index -> extract ->
JD analyze -> readiness -> prep queue -> interview begin -> question ->
answer -> evaluation -> report. All via HTTP against the running backend.
"""

import asyncio
import sys

import httpx

BASE = "http://127.0.0.1:8001/api/v1"
UID = 1

RESUME = """Alex Rivera — Senior Backend Engineer

Senior backend engineer with 7 years of experience building distributed
systems. Led a team of 5 engineers at Acme Corp.

Experience
- Acme Corp, Staff Engineer (2021-present): designed event-driven payment
  platform processing 2M transactions/day on Python, FastAPI, PostgreSQL,
  Kafka. Reduced p95 latency by 40%. Led 5 engineers.
- Beta Labs, Senior Engineer (2018-2021): built real-time analytics
  pipeline with Go and ClickHouse; deployed to Kubernetes.
- Gamma Inc, Engineer (2017-2018): microservices migration, Node.js.

Projects
- Checkout Platform: distributed transaction processing, exactly-once
  semantics, circuit breakers. Technologies: Python, Kafka, PostgreSQL.
- Realtime Analytics: streaming aggregation, 100k events/sec.

Achievements
- Reduced p95 latency by 40% through caching and query optimization.
- Cut infrastructure cost 30% by right-sizing Kubernetes clusters.

Certifications
- AWS Solutions Architect Professional

Technologies: Python, FastAPI, PostgreSQL, Kafka, Redis, Docker,
Kubernetes, AWS, Go, ClickHouse, Node.js, TypeScript, React.

Strengths: distributed systems, reliability, mentoring.
Weaknesses: no mobile experience, limited frontend depth.
"""

JD = """Senior Full Stack Engineer — Platform Team

We are looking for a senior full stack engineer to own features end to
end on our developer platform. You will build and operate services
serving millions of requests per day.

Requirements
- 5+ years of software engineering experience
- Strong TypeScript and React experience building production web apps
- Backend experience with Python or Node.js, REST APIs, PostgreSQL
- Experience designing and operating distributed systems at scale
- Deep understanding of system design: caching, queues, data consistency
- Experience with AWS or GCP in production
- Led or mentored other engineers

Preferred
- Experience with real-time systems (WebSockets, streaming)
- Kubernetes and CI/CD ownership
- Monitoring/observability tooling (OpenTelemetry, Grafana)

Responsibilities
- Own features from design to production
- Review code, mentor junior engineers
- Improve reliability and performance of critical services
- Work with product on technical tradeoffs
"""


async def main() -> None:
    client = httpx.AsyncClient(timeout=180.0)

    async def req(method: str, path: str, **kw: object) -> dict:
        r = await client.request(method, f"{BASE}{path}", **kw)
        if r.status_code >= 400:
            print(f"  !! {method} {path} -> {r.status_code} {r.text[:200]}")
            return {}
        return r.json()

    print("creating candidate profile...")
    await req("POST", "/candidates", json={"user_id": UID, "headline": "Senior Backend Engineer", "seniority_target": "senior"})

    print("uploading resume...")
    doc = await req("POST", "/documents", data={"user_id": UID, "kind": "resume"}, files={"file": ("resume.txt", RESUME.encode(), "text/plain")})
    if doc:
        print(f"  doc {doc['id']} status {doc['status']}")
        idx = await req("POST", f"/documents/{doc['id']}/index?user_id={UID}")
        print(f"  indexed {idx.get('chunk_count')} chunks dim {idx.get('dimension')}")
        ext = await req("POST", f"/candidates/{UID}/extract?document_id={doc['id']}")
        print(f"  extraction evidence_count={ext.get('evidence_count')}")

    print("analyzing JD...")
    role = await req("POST", "/roles/analyze", json={"user_id": UID, "jd_text": JD})
    if role:
        print(f"  role {role['title']} competencies={len(role.get('competencies', []))}")

    print("computing readiness...")
    rd = await req("POST", f"/readiness?user_id={UID}&role_id={role.get('id') if role else ''}")
    print(f"  overall={rd.get('overall')} gaps={len(rd.get('critical_gaps', []))}")

    print("regenerating prep queue...")
    prep = await req("POST", f"/preparation/regenerate?user_id={UID}")
    print(f"  {len(prep)} items")

    print("starting interview...")
    s = await req("POST", "/interviews", json={"user_id": UID, "kind": "technical", "role_id": role.get("id") if role else None, "duration_minutes": 20, "focus_competency_ids": [], "mode": "text"})
    if s:
        sid = s["id"]
        await req("POST", f"/interviews/{sid}/begin?user_id={UID}")
        q = await req("POST", f"/interviews/{sid}/questions?user_id={UID}")
        if q:
            print(f"  Q: {q['text'][:60]}...")
            ans = await req("POST", f"/interviews/{sid}/answers?user_id={UID}", json={"question_id": q["id"], "answer_text": "I built an event-driven payment platform processing 2M transactions per day. We chose Kafka for durability and designed exactly-once semantics via idempotent consumers and a transactional outbox. The hardest tradeoff was consistency vs latency: we used optimistic concurrency with retries to keep p95 under 200ms. I led the reliability work that cut p95 latency by 40%.", "idempotency_key": "demo-ans-1", "mode": "text"})
            print(f"  answer {ans.get('id')} evaluated")
        print("stopping session...")
        await req("POST", f"/interviews/{sid}/stop?user_id={UID}")

    await client.aclose()
    print("seed complete")


if __name__ == "__main__":
    asyncio.run(main())
