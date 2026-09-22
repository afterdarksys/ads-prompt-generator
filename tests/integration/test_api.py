"""Integration tests for API endpoints."""
from __future__ import annotations

import pytest


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_endpoint(self, client):
        """Test /health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.get_json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_ready_endpoint(self, client):
        """Test /ready endpoint."""
        response = client.get("/ready")
        assert response.status_code == 200

        data = response.get_json()
        assert data["status"] in ["ready", "not_ready"]
        assert "checks" in data


class TestGenerateEndpoint:
    """Test /api/v1/generate endpoint."""

    def test_generate_success_minimal(self, client):
        """Test successful prompt generation with minimal input."""
        response = client.post(
            "/api/v1/generate",
            json={
                "target": "chatgpt",
                "task": "Test task",
            },
        )
        assert response.status_code == 200

        data = response.get_json()
        assert "prompt" in data
        assert "Test task" in data["prompt"]
        assert data["cached"] is False

    def test_generate_success_full(self, client):
        """Test successful prompt generation with all fields."""
        response = client.post(
            "/api/v1/generate",
            json={
                "target": "claude_code",
                "task": "Test task",
                "context": "Test context",
                "constraints": "Test constraints",
                "deliverables": "Test deliverables",
                "tone": "concise",
            },
        )
        assert response.status_code == 200

        data = response.get_json()
        assert "prompt" in data
        assert "Test task" in data["prompt"]
        assert "Test context" in data["prompt"]

    def test_generate_missing_task(self, client):
        """Test error when task is missing."""
        response = client.post(
            "/api/v1/generate",
            json={"target": "chatgpt"},
        )
        assert response.status_code == 400

        data = response.get_json()
        assert "error" in data

    def test_generate_empty_task(self, client):
        """Test error when task is empty."""
        response = client.post(
            "/api/v1/generate",
            json={
                "target": "chatgpt",
                "task": "   ",
            },
        )
        assert response.status_code == 400

        data = response.get_json()
        assert "error" in data

    def test_generate_alias_uses_that_models_shape(self, client):
        """An alias selects that model's optimizations."""
        response = client.post(
            "/api/v1/generate",
            json={"target": "o3", "task": "Add 2 and 2"},
        )
        assert response.status_code == 200
        prompt = response.get_json()["prompt"].lower()
        assert "think step by step" not in prompt
        assert "you are" not in prompt

    def test_list_targets(self, client):
        """The catalog exposes one entry per profile."""
        response = client.get("/api/v1/targets")
        assert response.status_code == 200
        ids = {item["id"] for item in response.get_json()["targets"]}
        assert "chatgpt" in ids
        assert "grok" in ids
        assert "deepseek_r1" in ids

    def test_generate_invalid_target(self, client):
        """Test error with invalid target."""
        response = client.post(
            "/api/v1/generate",
            json={
                "target": "invalid",
                "task": "Test task",
            },
        )
        assert response.status_code == 400

        data = response.get_json()
        assert "error" in data

    def test_generate_invalid_json(self, client):
        """Test error with invalid JSON."""
        response = client.post(
            "/api/v1/generate",
            data="not json",
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_generate_task_too_long(self, client):
        """Test error when task exceeds max length."""
        response = client.post(
            "/api/v1/generate",
            json={
                "target": "chatgpt",
                "task": "A" * 20000,  # Exceeds MAX_TASK_LENGTH (10KB)
            },
        )
        assert response.status_code == 400

        data = response.get_json()
        assert "error" in data

    def test_response_has_request_id(self, client):
        """Test that responses include request ID."""
        response = client.post(
            "/api/v1/generate",
            json={
                "target": "chatgpt",
                "task": "Test task",
            },
        )

        assert "X-Request-ID" in response.headers


class TestIndexPage:
    """Test main index page."""

    def test_index_page(self, client):
        """Test that index page loads."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"Prompt Generator" in response.data
