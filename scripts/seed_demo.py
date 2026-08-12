#!/usr/bin/env python3
"""Seed demo data through the real API (Phase J demo mode).

POST /api/v1/demo/setup drives the full service pipeline (profile ->
resume upload/index/extract -> role analysis -> readiness -> preparation)
for the 4 bundled demo roles. Idempotent: re-running reuses existing
documents (content-hash dedup) and roles.

Usage:
    cd backend && uv run python ../scripts/seed_demo.py
    uv run python ../scripts/seed_demo.py --roles senior-fullstack,frontend
    uv run python ../scripts/seed_demo.py --user 1
"""

from __future__ import annotations

import argparse
import asyncio

import httpx

BASE = "http://127.0.0.1:8001/api/v1"


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Pramya demo data")
    parser.add_argument("--base", default=BASE, help="backend base URL")
    parser.add_argument("--user", type=int, default=1, help="user id to seed")
    parser.add_argument(
        "--roles", default=None, help="comma-separated role keys (default: all 4)"
    )
    args = parser.parse_args()

    params = {"user_id": args.user}
    if args.roles:
        params["roles"] = args.roles

    async with httpx.AsyncClient(timeout=600.0) as client:
        r = await client.post(f"{args.base}/demo/setup", params=params)
        if r.status_code >= 400:
            print(f"demo setup failed: {r.status_code} {r.text[:400]}")
            raise SystemExit(1)
        data = r.json()
        print(f"profile: {data['profile']}")
        for role in data["roles"]:
            print(
                f"  role {role['key']:<18} doc={role['document_id']} "
                f"chunks={role['chunks']} evidence={role['evidence_count']} "
                f"competencies={role['competencies']} role_id={role['role_id']}"
            )
        print(
            f"readiness={data['readiness']} critical_gaps={data['critical_gaps']} "
            f"preparation_items={data['preparation_items']}"
        )
        print("demo seed complete")


if __name__ == "__main__":
    asyncio.run(main())
