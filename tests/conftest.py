from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from nettodeals.app import create_app
from nettodeals.config import Settings


@pytest.fixture
def settings(tmp_path):
    return replace(
        Settings(),
        db_path=str(tmp_path / "nettodeals.db"),
        admin_token="test-admin-token-with-enough-entropy",
        cookie_secure=False,
        auto_sync_enabled=False,
        auto_sync_on_start=False,
        google_trends_enabled=False,
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client
