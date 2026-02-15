from __future__ import annotations

import pytest


@pytest.fixture(params=["cpu", "gpu"])
def device(request: pytest.FixtureRequest) -> str:
    """Device parameter for example benchmark tests."""
    return str(request.param)
