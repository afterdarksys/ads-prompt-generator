"""Pytest configuration and fixtures."""
from __future__ import annotations

import pytest

from app import create_app
from config import Config


@pytest.fixture
def app():
    """Create application for testing."""
    # Override config for testing
    import os

    os.environ["FLASK_ENV"] = "testing"
    os.environ["FLASK_DEBUG"] = "false"
    os.environ["CACHE_ENABLED"] = "false"
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    os.environ["METRICS_ENABLED"] = "false"
    os.environ["SECRET_KEY"] = "test-secret-key"

    app = create_app()
    app.config["TESTING"] = True

    yield app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create CLI test runner."""
    return app.test_cli_runner()
