"""Acceptance tests for specs/001-persistent-prompt-library.md."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from api import main


def run(awaitable):
    return asyncio.run(awaitable)


def prompt_request(**overrides):
    values = {
        "name": "Security review",
        "task": "Review this system prompt",
        "target": "claude_code",
        "context": "A production assistant",
        "constraints": "Do not expose secrets",
        "deliverables": "A prioritized report",
        "tone": "direct",
        "generated_prompt": "Perform a structured security review.",
    }
    values.update(overrides)
    return main.PromptSaveRequest(**values)


class FakePostgresPool:
    """Small PostgreSQL test double whose rows outlive repository instances."""

    def __init__(self):
        self.rows = {}
        self.next_id = 1
        self.calls = []
        self.closed = False

    async def fetchrow(self, query, *args):
        self.calls.append(("fetchrow", query, args))
        normalized = " ".join(query.split()).upper()

        if normalized.startswith("INSERT INTO PROMPTS"):
            prompt_id = self.next_id
            self.next_id += 1
            now = datetime.now(timezone.utc)
            row = {
                "id": prompt_id,
                "name": args[0],
                "task": args[1],
                "target": args[2],
                "tone": args[3],
                "context": args[4],
                "constraints": args[5],
                "deliverables": args[6],
                "generated_prompt": args[7],
                "tags": [args[2]],
                "favorite": False,
                "created_at": now,
            }
            self.rows[prompt_id] = row
            return row

        if normalized.startswith("SELECT") and "WHERE ID = $1" in normalized:
            row = self.rows.get(args[0])
            return dict(row) if row else None

        if normalized.startswith("DELETE FROM PROMPTS"):
            row = self.rows.pop(args[0], None)
            return {"id": args[0]} if row else None

        raise AssertionError(f"Unexpected query: {query}")

    async def fetch(self, query, *args):
        self.calls.append(("fetch", query, args))
        rows = list(self.rows.values())

        if "ILIKE" in query:
            escaped = args[0][1:-1]
            search = (
                escaped.replace(r"\%", "%")
                .replace(r"\_", "_")
                .replace(r"\\", "\\")
                .lower()
            )
            rows = [
                row
                for row in rows
                if search in row["name"].lower() or search in row["task"].lower()
            ]

        if "favorite = TRUE" in query:
            rows = [row for row in rows if row["favorite"]]

        rows.sort(key=lambda row: row["created_at"], reverse=True)
        return [dict(row) for row in rows]

    async def close(self):
        self.closed = True


class FailingPool(FakePostgresPool):
    async def fetch(self, query, *args):
        raise RuntimeError("password=hunter2 SELECT secret_internal_table")

    async def fetchrow(self, query, *args):
        raise RuntimeError("password=hunter2 SELECT secret_internal_table")


class FakeHTTPClient:
    def __init__(self):
        self.closed = False

    async def aclose(self):
        self.closed = True


class TestPersistentPromptLibrary:
    def test_ac1_save_and_retrieve_a_prompt(self):
        pool = FakePostgresPool()
        repository = main.PromptRepository(pool)
        saved = run(main.save_prompt(prompt_request(), repository))
        retrieved = run(main.get_prompt(saved["id"], repository))

        assert saved == {"id": 1, "message": "Saved"}
        assert retrieved["prompt"]["name"] == "Security review"
        assert retrieved["prompt"]["tags"] == ["claude_code"]
        assert retrieved["prompt"]["favorite"] is False
        assert retrieved["prompt"]["created_at"].endswith("+00:00")

    def test_ac2_search_prompts(self):
        pool = FakePostgresPool()
        repository = main.PromptRepository(pool)
        run(main.save_prompt(prompt_request(name="Alpha"), repository))
        run(main.save_prompt(prompt_request(name="Other", task="contains BETA"), repository))
        run(main.save_prompt(prompt_request(name="Unrelated", task="Nothing"), repository))

        result = run(main.list_prompts(search="beta", favorites=False, repository=repository))

        assert [prompt["name"] for prompt in result["prompts"]] == ["Other"]

    def test_ac3_filter_favorites(self):
        pool = FakePostgresPool()
        repository = main.PromptRepository(pool)
        first = run(main.save_prompt(prompt_request(name="Favorite"), repository))
        run(main.save_prompt(prompt_request(name="Ordinary"), repository))
        pool.rows[first["id"]]["favorite"] = True

        result = run(main.list_prompts(search="", favorites=True, repository=repository))

        assert [prompt["name"] for prompt in result["prompts"]] == ["Favorite"]

    def test_ac4_delete_a_prompt(self):
        pool = FakePostgresPool()
        repository = main.PromptRepository(pool)
        saved = run(main.save_prompt(prompt_request(), repository))

        assert run(main.delete_prompt(saved["id"], repository)) == {"message": "Deleted"}
        with pytest.raises(HTTPException) as exc:
            run(main.get_prompt(saved["id"], repository))
        assert exc.value.status_code == 404

    def test_ac5_missing_prompt_handling(self):
        repository = main.PromptRepository(FakePostgresPool())

        for operation in (main.get_prompt, main.delete_prompt):
            with pytest.raises(HTTPException) as exc:
                run(operation(999, repository))
            assert exc.value.status_code == 404
            assert exc.value.detail == "Prompt not found"

    def test_ac6_persistence_across_api_instances(self):
        durable_database = FakePostgresPool()
        first_repository = main.PromptRepository(durable_database)
        saved = run(main.save_prompt(prompt_request(), first_repository))

        second_repository = main.PromptRepository(durable_database)
        retrieved = run(main.get_prompt(saved["id"], second_repository))

        assert retrieved["prompt"]["generated_prompt"] == (
            "Perform a structured security review."
        )

    def test_ac7_database_lifecycle(self, monkeypatch):
        pool = FakePostgresPool()
        client = FakeHTTPClient()
        create_calls = []

        async def create_pool(database_url):
            create_calls.append(database_url)
            return pool

        monkeypatch.setattr(main.asyncpg, "create_pool", create_pool)
        monkeypatch.setattr(main.httpx, "AsyncClient", lambda **kwargs: client)

        async def exercise_lifespan():
            async with main.lifespan(main.app):
                assert isinstance(main.prompt_repository, main.PromptRepository)

        run(exercise_lifespan())

        assert create_calls == [main.config.DATABASE_URL]
        assert pool.closed is True
        assert client.closed is True

    def test_ac8_database_unavailable_at_startup(self, monkeypatch):
        client = FakeHTTPClient()

        async def create_pool(database_url):
            raise OSError("connection refused")

        monkeypatch.setattr(main.asyncpg, "create_pool", create_pool)
        monkeypatch.setattr(main.httpx, "AsyncClient", lambda **kwargs: client)

        async def exercise_lifespan():
            async with main.lifespan(main.app):
                raise AssertionError("lifespan must not start")

        with pytest.raises(OSError, match="connection refused"):
            run(exercise_lifespan())
        assert main.prompt_repository is None
        assert client.closed is True

    def test_ac9_parameterized_input(self):
        pool = FakePostgresPool()
        repository = main.PromptRepository(pool)
        malicious = "50%_'; DROP TABLE prompts; --"

        run(main.save_prompt(prompt_request(name=malicious), repository))
        result = run(
            main.list_prompts(search=malicious, favorites=False, repository=repository)
        )

        insert_query = pool.calls[0][1]
        search_query = pool.calls[1][1]
        assert malicious not in insert_query
        assert malicious not in search_query
        assert "$1" in insert_query and "$1" in search_query
        assert len(result["prompts"]) == 1
        assert len(pool.rows) == 1

    def test_ac10_sanitized_storage_failure(self):
        repository = main.PromptRepository(FailingPool())

        with pytest.raises(HTTPException) as exc:
            run(main.list_prompts(search="", favorites=False, repository=repository))

        assert exc.value.status_code == 503
        assert exc.value.detail == "Prompt storage unavailable"
        assert "hunter2" not in str(exc.value.detail)

    def test_ec1_startup_does_not_fall_back_to_memory(self, monkeypatch):
        self.test_ac8_database_unavailable_at_startup(monkeypatch)
        assert not hasattr(main, "prompt_library")

    def test_ec2_runtime_database_failure_is_sanitized(self):
        self.test_ac10_sanitized_storage_failure()

    def test_ec3_search_wildcards_are_literal(self):
        pool = FakePostgresPool()
        repository = main.PromptRepository(pool)
        run(main.save_prompt(prompt_request(name="100%_literal"), repository))
        run(main.save_prompt(prompt_request(name="100XXliteral"), repository))

        result = run(
            main.list_prompts(
                search="100%_literal", favorites=False, repository=repository
            )
        )

        assert [prompt["name"] for prompt in result["prompts"]] == ["100%_literal"]

    def test_ec4_concurrent_deletes_have_one_winner(self):
        pool = FakePostgresPool()
        repository = main.PromptRepository(pool)
        saved = run(main.save_prompt(prompt_request(), repository))

        async def delete_twice():
            outcomes = await asyncio.gather(
                main.delete_prompt(saved["id"], repository),
                main.delete_prompt(saved["id"], repository),
                return_exceptions=True,
            )
            return outcomes

        outcomes = run(delete_twice())
        assert sum(result == {"message": "Deleted"} for result in outcomes) == 1
        errors = [result for result in outcomes if isinstance(result, HTTPException)]
        assert len(errors) == 1 and errors[0].status_code == 404

    def test_ec5_optional_fields_round_trip_as_null(self):
        pool = FakePostgresPool()
        repository = main.PromptRepository(pool)
        request = prompt_request(
            context=None, constraints=None, deliverables=None, tone=None
        )

        saved = run(main.save_prompt(request, repository))
        prompt = run(main.get_prompt(saved["id"], repository))["prompt"]

        assert prompt["context"] is None
        assert prompt["constraints"] is None
        assert prompt["deliverables"] is None
        assert prompt["tone"] is None

    def test_ec6_postgres_values_are_json_compatible(self):
        pool = FakePostgresPool()
        repository = main.PromptRepository(pool)
        saved = run(main.save_prompt(prompt_request(), repository))

        prompt = run(main.get_prompt(saved["id"], repository))["prompt"]

        assert isinstance(prompt["tags"], list)
        assert isinstance(prompt["created_at"], str)
