# Spec: Persistent Prompt Library

**Author:** Codex with product direction from Ryan  
**Date:** 2026-07-29  
**Status:** Approved  
**Reviewer:** Ryan  
**Approval basis:** Ryan authorized the proposed rebuild and first implementation milestone with “go for it” on 2026-07-29.  
**Related specs:** N/A — first product specification in this repository.

## Context

Prompt Generator Pro currently exposes API operations for saving, listing, reading,
searching, and deleting generated prompts. Those operations store data in a Python
dictionary. Every API restart therefore erases the user's library even though the
Docker stack provisions PostgreSQL and initializes a `prompts` table.

A real product cannot present saved work as a library while silently discarding it
on restart. This milestone connects the existing prompt-library contract to the
existing PostgreSQL schema. It intentionally preserves the browser-facing API so
later product work can build on a durable foundation without requiring a frontend
rewrite.

## Functional Requirements

- FR-1: The API MUST store every prompt accepted by `POST /api/v1/library/prompts`
  in PostgreSQL and MUST return the generated integer identifier.
- FR-2: The API MUST return stored prompts from `GET /api/v1/library/prompts`.
- FR-3: The list endpoint MUST apply a case-insensitive name-or-task search when
  the `search` query parameter is non-empty.
- FR-4: The list endpoint MUST return only favorite prompts when the `favorites`
  query parameter is `true`.
- FR-5: The API MUST return a stored prompt by identifier from
  `GET /api/v1/library/prompts/{prompt_id}`.
- FR-6: The API MUST return HTTP 404 with `{"detail": "Prompt not found"}` when a
  requested prompt identifier does not exist.
- FR-7: The API MUST hard-delete an existing prompt through
  `DELETE /api/v1/library/prompts/{prompt_id}`.
- FR-8: The delete endpoint MUST return HTTP 404 with
  `{"detail": "Prompt not found"}` when the prompt does not exist.
- FR-9: Stored prompts MUST remain available after the API process is stopped and
  started while PostgreSQL retains its data volume.
- FR-10: The API MUST establish its PostgreSQL connection pool during application
  startup and close it during application shutdown.
- FR-11: Application startup MUST fail when PostgreSQL is unavailable; the API
  MUST NOT silently fall back to volatile storage.
- FR-12: Existing prompt-library request and success-response shapes MUST remain
  backward compatible.

## Non-Functional Requirements

- NFR-S1: All SQL statements containing user-provided values MUST use PostgreSQL
  parameters; user input MUST NOT be interpolated into SQL text.
- NFR-S2: Database errors returned to HTTP clients MUST use the generic message
  `Prompt storage unavailable` and MUST NOT expose connection strings, SQL text,
  credentials, or driver exception details.
- NFR-R1: A successfully committed prompt MUST survive API process restart as
  verified against the same PostgreSQL database.
- NFR-R2: Database resources MUST be released when the FastAPI lifespan exits.
- NFR-C1: The implementation MUST support Python 3.11 and PostgreSQL 15, matching
  the existing Docker images.
- NFR-A1: N/A — this milestone does not change rendered UI or interaction
  semantics.

## Acceptance Criteria

### AC-1: Save and retrieve a prompt (FR-1, FR-2, FR-5, FR-12)

Given an empty prompt library and an available PostgreSQL database  
When a client saves a valid prompt and retrieves the returned identifier  
Then both endpoints respond successfully  
And the retrieved prompt contains the submitted fields and server-generated fields

### AC-2: Search prompts (FR-2, FR-3)

Given prompts whose names and tasks contain different text and letter casing  
When a client lists prompts with a non-empty search query  
Then only prompts with a case-insensitive match in name or task are returned

### AC-3: Filter favorites (FR-2, FR-4)

Given one favorite prompt and one non-favorite prompt in PostgreSQL  
When a client lists prompts with `favorites=true`  
Then only the favorite prompt is returned

### AC-4: Delete a prompt (FR-7)

Given a stored prompt  
When a client deletes its identifier  
Then the delete endpoint returns `{"message": "Deleted"}`  
And a later retrieval of that identifier returns HTTP 404

### AC-5: Missing prompt handling (FR-6, FR-8)

Given an identifier that is not present in PostgreSQL  
When a client retrieves or deletes that identifier  
Then each operation returns HTTP 404 with `{"detail": "Prompt not found"}`

### AC-6: Persistence across API instances (FR-9, NFR-R1)

Given a prompt committed through one API application instance  
When that instance shuts down and a second instance connects to the same database  
Then the second instance can retrieve the prompt using the original identifier

### AC-7: Database lifecycle (FR-10, NFR-R2)

Given an available PostgreSQL database  
When the FastAPI lifespan starts and then exits  
Then exactly one application pool is initialized  
And that pool is closed during shutdown

### AC-8: Database unavailable at startup (FR-11)

Given a PostgreSQL endpoint that cannot be reached  
When the FastAPI lifespan starts  
Then startup fails  
And no volatile prompt store is substituted

### AC-9: Parameterized input (NFR-S1)

Given prompt fields and search text containing quotes and SQL metacharacters  
When a client saves and searches for the prompt  
Then the values are treated as data  
And the prompt table remains intact

### AC-10: Sanitized storage failure (NFR-S2)

Given PostgreSQL raises an unexpected driver error during a library operation  
When the endpoint handles the failure  
Then it returns HTTP 503 with `{"detail": "Prompt storage unavailable"}`  
And the response contains no driver exception details

## Edge Cases and Error Scenarios

- EC-1: PostgreSQL is unavailable during startup → fail application startup without
  starting an in-memory fallback (FR-11).
- EC-2: PostgreSQL fails after startup during a library operation → log the
  exception server-side and return the sanitized HTTP 503 response (NFR-S2).
- EC-3: Search text contains `%`, `_`, quotes, or SQL syntax → treat the entire
  value as search data, not executable SQL (NFR-S1).
- EC-4: A delete races with another delete → exactly one delete succeeds; later
  attempts receive the specified 404 response (FR-7, FR-8).
- EC-5: Optional prompt fields are omitted → persist and return them as `null`
  without rejecting the request (FR-1, FR-12).
- EC-6: PostgreSQL returns an array for `tags` and a timezone-aware timestamp for
  `created_at` → serialize both values to the existing JSON-compatible response
  shape (FR-12).

## API Contracts

### `POST /api/v1/library/prompts`

```typescript
interface PromptSaveRequest {
  name: string;
  task: string;
  target: string;
  context?: string | null;
  constraints?: string | null;
  deliverables?: string | null;
  tone?: string | null;
  generated_prompt: string;
}

interface PromptSaveResponse {
  id: number;
  message: "Saved";
}
```

- Success: HTTP 200 with `PromptSaveResponse`.
- Storage failure: HTTP 503 with `{"detail": "Prompt storage unavailable"}`.
- Validation failure: existing FastAPI HTTP 422 response.

### `GET /api/v1/library/prompts?search={text}&favorites={boolean}`

```typescript
interface StoredPrompt extends PromptSaveRequest {
  id: number;
  tags: string[];
  favorite: boolean;
  created_at: string; // ISO 8601
}

interface PromptListResponse {
  prompts: StoredPrompt[];
}
```

- Success: HTTP 200 with `PromptListResponse`, ordered newest first.
- Storage failure: HTTP 503 with `{"detail": "Prompt storage unavailable"}`.

### `GET /api/v1/library/prompts/{prompt_id}`

- Success: HTTP 200 with `{"prompt": StoredPrompt}`.
- Missing identifier: HTTP 404 with `{"detail": "Prompt not found"}`.
- Storage failure: HTTP 503 with `{"detail": "Prompt storage unavailable"}`.

### `DELETE /api/v1/library/prompts/{prompt_id}`

- Success: HTTP 200 with `{"message": "Deleted"}`.
- Missing identifier: HTTP 404 with `{"detail": "Prompt not found"}`.
- Storage failure: HTTP 503 with `{"detail": "Prompt storage unavailable"}`.

## Data Models

### `prompts`

| Field | Type | Constraints |
|---|---|---|
| `id` | serial | Primary key, generated by PostgreSQL |
| `name` | varchar(255) | Not null |
| `task` | text | Not null |
| `target` | varchar(50) | Not null |
| `tone` | varchar(255) | Nullable |
| `context` | text | Nullable |
| `constraints` | text | Nullable |
| `deliverables` | text | Nullable |
| `generated_prompt` | text | Nullable for compatibility with existing schema |
| `tags` | text[] | Not null, default empty array |
| `favorite` | boolean | Not null, default false |
| `created_at` | timestamptz | Not null, generated by PostgreSQL |
| `updated_at` | timestamptz | Not null, generated by PostgreSQL |

Existing indexes on `target` and `favorite` remain unchanged. Search is expected to
operate on a small first-release dataset; dedicated text-search indexing is deferred.
Deletion is hard deletion to preserve the existing endpoint semantics.

## Out of Scope

- OS-1: Authentication and multi-user ownership — requires a separate security
  review and data-isolation specification.
- OS-2: API-key persistence or encryption — security-sensitive work requiring a
  dedicated specification.
- OS-3: Prompt updates, favorite toggling, tags editing, pagination, or versioning —
  no existing API contract supports these operations.
- OS-4: Persisting security scans, red-team sessions, or ART attacks — each job type
  needs lifecycle and retention requirements beyond this milestone.
- OS-5: Celery worker integration — deferred until durable job records are
  specified.
- OS-6: UI redesign — the existing frontend contract remains functional.
- OS-7: Billing, teams, exports, and production deployment — later product
  milestones.
