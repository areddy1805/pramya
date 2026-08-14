"""Root test configuration.

Unit/contract/integration tests MUST NOT depend on a live Langfuse instance:
a broken/slow self-hosted Langfuse (or OTel ingestion) must never hang the
application tests. The observability singleton is forced to NullObservability
here; Langfuse delivery is verified only by dedicated integration tests that
explicitly opt in (marker ``langfuse_live``).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.observability as observability


def _null_settings() -> object:
    """Settings stub with Langfuse unconfigured -> NullObservability."""
    return SimpleNamespace(
        langfuse_public_key=None,
        langfuse_secret_key=None,
        langfuse_host="http://localhost:3030",
    )


@pytest.fixture(autouse=True)
def _isolate_observability(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force NullObservability for every test unless it opts into Langfuse.

    A broken/slow Langfuse backend must never be able to hang the
    application tests: telemetry enqueue goes through NullObservability
    (structured logs only). Langfuse-specific integration tests re-enable
    a real client explicitly and use the ``langfuse_live`` marker.
    """
    observability.reset_observability()
    monkeypatch.setattr(observability, "get_settings", _null_settings)
    yield
    observability.reset_observability()
