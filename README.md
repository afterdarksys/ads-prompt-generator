# ads-prompt-generator

Prompt Generator Pro — a security-enhanced prompt engineering platform. Generates optimized prompts for ChatGPT and Claude Code, stores them in a persistent library, and runs the results through LLM security scanning and red team tooling.

## Features

- **Prompt generation** — one request, shaped per target model (ChatGPT, OpenAI o-series, Claude, Claude Code, Gemini, Grok, Llama, DeepSeek, DeepSeek R1, Mistral)
- **Prompt library** — PostgreSQL-backed persistence with search and favorites
- **Playground** — execute prompts against Anthropic, OpenAI, or OpenRouter (plus a detached no-call mode)
- **Security scanning** — prompt injection, jailbreak, data-leak, and toxicity checks with a composite risk score
- **Red team sessions** — orchestration hooks for Garak, Promptmap2, PyRIT, and Promptfoo
- **ART attacks** — adversarial evasion, poisoning, extraction, and inference testing against served models

`claude` is still Claude Code. Claude chat is `claude_chat` (aliases: `sonnet`, `opus`, `haiku`). Other aliases include `gpt-4o`, `o3`, `grok-4`, and `deepseek-r1`. `GET /api/v1/targets` lists every id and the optimization applied to it.

| Target | What changes in the prompt |
|---|---|
| `chatgpt` | Labeled sections, a fixed answer format, questions only when required |
| `gpt_reasoning` | A short user message. No persona and no request to show reasoning |
| `claude_chat` | XML tags, and instructions that refer to those tags by name |
| `claude_code` | Smallest correct change, read files first, no invented APIs |
| `gemini` | Task stays narrow, constraints are requirements, format is exact |
| `grok` | Direct tone, one persona, stop when the format is done |
| `llama` | Short headings, output contract repeated at the end |
| `deepseek` | The deliverable itself, and no libraries the constraints did not name |
| `deepseek_r1` | One user message, no examples. Math results go in `\boxed{}` |
| `mistral` | Imperative instructions, constraints in order, no trailing alternatives |

## Platform integrations

| Platform | Purpose |
|---|---|
| [darkapi.io](https://darkapi.io) | Threat intelligence enrichment |
| [llmsecurity.dev](https://llmsecurity.dev) | AI model security scanning |
| [models2go.com](https://models2go.com) | ML model serving |
| [apiproxy.app](https://apiproxy.app) | Unified API gateway |

## Quick start

```bash
docker compose up -d
```

The API and UI are served at `http://localhost:8000`; interactive docs at `http://localhost:8000/docs`.

### Running locally without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload
```

## Configuration

All credentials are supplied via environment variables — none are committed. Create a `.env` file:

```bash
# Platform keys
DARKAPI_KEY=
LLMSECURITY_KEY=
MODELS2GO_KEY=
APIPROXY_KEY=

# LLM provider keys
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
OPENROUTER_API_KEY=

# Infrastructure
DATABASE_URL=postgresql://promptgen:promptgen@postgres:5432/prompt_generator
REDIS_URL=redis://redis:6379/0
```

> The database credentials in `docker-compose.yml` are local development defaults. Replace them before deploying anywhere reachable.

## API

Prompt generation and library:

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/generate` | Generate an optimized prompt |
| `POST` | `/api/v1/playground/execute` | Run a prompt against a provider |
| `GET` | `/api/v1/library/prompts` | List saved prompts (`search`, `favorites`) |
| `POST` | `/api/v1/library/prompts` | Save a prompt |
| `GET` | `/api/v1/library/prompts/{id}` | Fetch a prompt |
| `DELETE` | `/api/v1/library/prompts/{id}` | Delete a prompt |

Security and red team:

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/security/scan` | Queue a security scan |
| `GET` | `/api/v1/security/scan/{id}` | Scan status and results |
| `POST` | `/api/v1/redteam/session` | Start a red team session |
| `GET` | `/api/v1/redteam/session/{id}` | Session status and results |
| `POST` | `/api/v1/art/attack` | Queue an ART attack |
| `GET` | `/api/v1/platforms/status` | Connectivity check for integrations |

## Security tooling

The red team and ART endpoints orchestrate external tools. Install them as needed:

```bash
pip install adversarial-robustness-toolbox garak pyrit promptmap
npm install -g promptfoo
```

These are offensive-security tools intended for testing systems you own or are authorized to test.

## Tests

```bash
pytest
```

## License

Proprietary — After Dark Systems.
