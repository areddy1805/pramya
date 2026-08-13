"""Demo fixtures integrity (Phase J).

The 4 bundled demo roles must ship with non-empty resume + JD fixtures so
`make demo-setup` and the demo API work on a fresh clone.
"""

from __future__ import annotations

from app.services.demo import DEMO_ROLE_KEYS, load_demo_fixture


def test_all_demo_roles_have_fixtures() -> None:
    assert DEMO_ROLE_KEYS == [
        "senior-fullstack",
        "backend",
        "frontend",
        "product-manager",
    ]
    for key in DEMO_ROLE_KEYS:
        resume = load_demo_fixture(key, "resume.md")
        jd = load_demo_fixture(key, "jd.md")
        assert len(resume) > 400, f"{key} resume too short"
        assert len(jd) > 300, f"{key} JD too short"
        # JD must satisfy the role-analysis minimum length (20 chars).
        assert len(jd) >= 20
