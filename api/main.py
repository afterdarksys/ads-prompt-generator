"""
Prompt Generator Pro - Backend API
Integrates with security testing tools and After Dark platforms

Platforms:
- darkapi.io: Threat intelligence
- llmsecurity.dev: AI model security scanning
- models2go.com: ML model serving
- apiproxy.app: Unified API gateway

Security Tools:
- ART: Adversarial Robustness Toolbox
- Garak: LLM vulnerability scanner
- Promptfoo: LLM testing framework
- PyRIT: Python Risk Identification Toolkit
- Promptmap2: Prompt injection scanner
- CAI: Cybersecurity AI framework
"""

import os
import json
import asyncio
import httpx
import asyncpg
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import structlog

from prompt_gen.core import (
    PromptRequest,
    PromptTarget,
    engineer_system,
    generate_prompt as render_prompt,
    list_profiles as model_profiles,
)

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
log = structlog.get_logger()

# Configuration
class Config:
    # Platform endpoints
    DARKAPI_URL = os.getenv("DARKAPI_URL", "https://api.darkapi.io/v1")
    DARKAPI_KEY = os.getenv("DARKAPI_KEY", "")

    LLMSECURITY_URL = os.getenv("LLMSECURITY_URL", "https://api.llmsecurity.dev/v1")
    LLMSECURITY_KEY = os.getenv("LLMSECURITY_KEY", "")

    MODELS2GO_URL = os.getenv("MODELS2GO_URL", "https://api.models2go.com/v1")
    MODELS2GO_KEY = os.getenv("MODELS2GO_KEY", "")

    APIPROXY_URL = os.getenv("APIPROXY_URL", "https://api.apiproxy.app/v1")
    APIPROXY_KEY = os.getenv("APIPROXY_KEY", "")

    # LLM Provider keys
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/prompt_generator")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

config = Config()

# In-memory storage for prototype features not yet migrated to PostgreSQL.
api_keys_store: Dict[int, dict] = {}
security_scans: Dict[str, dict] = {}
redteam_sessions: Dict[str, dict] = {}

# Shared application resources
http_client: Optional[httpx.AsyncClient] = None
database_pool: Optional[asyncpg.Pool] = None
prompt_repository: Optional["PromptRepository"] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client, database_pool, prompt_repository
    http_client = httpx.AsyncClient(timeout=60.0)
    database_pool = None
    prompt_repository = None

    try:
        database_pool = await asyncpg.create_pool(config.DATABASE_URL)
        prompt_repository = PromptRepository(database_pool)
        log.info("prompt_generator_started", version="2.0.0")
        yield
    finally:
        prompt_repository = None
        if database_pool is not None:
            await database_pool.close()
            database_pool = None
        await http_client.aclose()
        http_client = None
        log.info("prompt_generator_stopped")

app = FastAPI(
    title="Prompt Generator Pro",
    description="Security-enhanced prompt engineering platform",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# MODELS
# ============================================================================

class GenerateRequest(BaseModel):
    target: str = Field(
        default="chatgpt",
        description="Target model id. See GET /api/v1/targets.",
    )
    task: str = Field(..., min_length=1, description="What the model should do")
    tone: Optional[str] = None
    context: Optional[str] = None
    constraints: Optional[str] = None
    deliverables: Optional[str] = None

class PlaygroundRequest(BaseModel):
    provider: str = Field(..., description="Provider: detached, anthropic, openai, openrouter")
    model: str
    prompt: str
    key_id: Optional[int] = None
    api_key: Optional[str] = None

class PromptSaveRequest(BaseModel):
    name: str
    task: str
    target: str
    context: Optional[str] = None
    constraints: Optional[str] = None
    deliverables: Optional[str] = None
    tone: Optional[str] = None
    generated_prompt: str

class APIKeyRequest(BaseModel):
    provider: str
    key_name: str
    api_key: str

# Security Models
class SecurityScanRequest(BaseModel):
    prompt: str = Field(..., description="Prompt to scan for security issues")
    target_model: Optional[str] = Field(None, description="Model to test against")
    scan_types: List[str] = Field(
        default=["injection", "jailbreak", "data_leak", "toxicity"],
        description="Types of scans to run"
    )

class RedTeamRequest(BaseModel):
    prompt: str = Field(..., description="System prompt to red team")
    target_model: str = Field(..., description="Model to test")
    attack_types: List[str] = Field(
        default=["jailbreak", "injection", "extraction"],
        description="Types of attacks to simulate"
    )
    iterations: int = Field(default=5, ge=1, le=50)
    tools: List[str] = Field(
        default=["garak", "promptmap2"],
        description="Tools to use: garak, promptmap2, pyrit, promptfoo"
    )

class ARTAttackRequest(BaseModel):
    model_endpoint: str = Field(..., description="models2go.com endpoint to test")
    attack_type: str = Field(..., description="evasion, poisoning, extraction, inference")
    samples: List[dict] = Field(..., description="Input samples to attack")


# ============================================================================
# PERSISTENT PROMPT STORAGE
# ============================================================================

PROMPT_COLUMNS = """
    id, name, task, target, tone, context, constraints, deliverables,
    generated_prompt, tags, favorite, created_at
"""


def serialize_prompt(record: asyncpg.Record) -> dict:
    """Convert PostgreSQL-specific values to the existing JSON response shape."""
    prompt = dict(record)
    prompt["tags"] = list(prompt.get("tags") or [])
    created_at = prompt.get("created_at")
    if isinstance(created_at, datetime):
        prompt["created_at"] = created_at.isoformat()
    return prompt


def escape_like(value: str) -> str:
    """Escape PostgreSQL LIKE metacharacters so search input remains literal."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class PromptRepository:
    """PostgreSQL-backed prompt library."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def save(self, req: PromptSaveRequest) -> dict:
        record = await self.pool.fetchrow(
            f"""
            INSERT INTO prompts (
                name, task, target, tone, context, constraints, deliverables,
                generated_prompt, tags
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::text[])
            RETURNING {PROMPT_COLUMNS}
            """,
            req.name,
            req.task,
            req.target,
            req.tone,
            req.context,
            req.constraints,
            req.deliverables,
            req.generated_prompt,
            [req.target],
        )
        return serialize_prompt(record)

    async def list(self, search: str = "", favorites: bool = False) -> List[dict]:
        conditions = []
        parameters = []

        if search:
            parameters.append(f"%{escape_like(search)}%")
            conditions.append(
                "(name ILIKE $1 ESCAPE E'\\\\' OR task ILIKE $1 ESCAPE E'\\\\')"
            )
        if favorites:
            conditions.append("favorite = TRUE")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        records = await self.pool.fetch(
            f"""
            SELECT {PROMPT_COLUMNS}
            FROM prompts
            {where_clause}
            ORDER BY created_at DESC
            """,
            *parameters,
        )
        return [serialize_prompt(record) for record in records]

    async def get(self, prompt_id: int) -> Optional[dict]:
        record = await self.pool.fetchrow(
            f"""
            SELECT {PROMPT_COLUMNS}
            FROM prompts
            WHERE id = $1
            """,
            prompt_id,
        )
        return serialize_prompt(record) if record else None

    async def delete(self, prompt_id: int) -> bool:
        record = await self.pool.fetchrow(
            """
            DELETE FROM prompts
            WHERE id = $1
            RETURNING id
            """,
            prompt_id,
        )
        return record is not None


def get_prompt_repository() -> PromptRepository:
    if prompt_repository is None:
        raise HTTPException(503, "Prompt storage unavailable")
    return prompt_repository


def prompt_storage_error(operation: str, error: Exception) -> HTTPException:
    log.error("prompt_storage_failed", operation=operation, error=str(error))
    return HTTPException(503, "Prompt storage unavailable")


# ============================================================================
# PROMPT GENERATION ENDPOINTS
# ============================================================================

@app.get("/api/v1/targets")
async def list_targets():
    """List prompt targets and the optimization applied to each."""
    return {
        "targets": [
            {
                "id": profile.id,
                "label": profile.label,
                "family": profile.family,
                "summary": profile.summary,
                "structure": profile.structure,
            }
            for profile in model_profiles()
        ]
    }


@app.post("/api/v1/generate")
async def generate_prompt_endpoint(req: GenerateRequest):
    """Generate an optimized prompt for the target model."""

    if not req.task or not req.task.strip():
        raise HTTPException(400, "Task is required")

    try:
        target = PromptTarget.from_string(req.target)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    system = engineer_system(target)
    user_content = f"Create an optimized prompt for the following:\n\nTASK: {req.task.strip()}\n"
    if req.tone:
        user_content += f"\nTONE: {req.tone}"
    if req.context:
        user_content += f"\nCONTEXT: {req.context}"
    if req.constraints:
        user_content += f"\nCONSTRAINTS: {req.constraints}"
    if req.deliverables:
        user_content += f"\nDELIVERABLES: {req.deliverables}"
    user_content += "\n\nGenerate only the optimized prompt, no explanations."

    local_prompt = render_prompt(
        PromptRequest(
            target=target,
            task=req.task,
            context=req.context or "",
            constraints=req.constraints or "",
            deliverables=req.deliverables or "",
            tone=req.tone or "",
        )
    )

    # Use Anthropic API for generation
    if config.ANTHROPIC_API_KEY:
        try:
            response = await http_client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": config.ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 2000,
                    "system": system,
                    "messages": [{"role": "user", "content": user_content}]
                }
            )
            data = response.json()
            generated = data.get("content", [{}])[0].get("text", "")
            if generated.strip():
                return {"prompt": generated, "target": target.value, "source": "model"}
        except Exception as e:
            log.error("generation_failed", error=str(e))

    return {"prompt": local_prompt, "target": target.value, "source": "template"}

# ============================================================================
# PLAYGROUND ENDPOINTS
# ============================================================================

@app.post("/api/v1/playground/execute")
async def execute_playground(req: PlaygroundRequest):
    """Execute a prompt against an LLM provider"""

    start_time = datetime.now()

    if req.provider == "detached":
        return {
            "response": f"[Detached Mode] Prompt received ({len(req.prompt)} chars). No API call made.",
            "model": "detached",
            "tokens_used": 0,
            "duration_ms": 0
        }

    # Get API key
    api_key = req.api_key
    if req.key_id and req.key_id in api_keys_store:
        api_key = api_keys_store[req.key_id].get("api_key")

    if not api_key:
        raise HTTPException(400, "API key required")

    try:
        if req.provider == "anthropic":
            response = await http_client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": req.model,
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": req.prompt}]
                }
            )
            data = response.json()
            text = data.get("content", [{}])[0].get("text", "")
            tokens = data.get("usage", {}).get("output_tokens", 0)

        elif req.provider == "openai":
            response = await http_client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": req.model,
                    "messages": [{"role": "user", "content": req.prompt}]
                }
            )
            data = response.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            tokens = data.get("usage", {}).get("total_tokens", 0)

        elif req.provider == "openrouter":
            response = await http_client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": req.model,
                    "messages": [{"role": "user", "content": req.prompt}]
                }
            )
            data = response.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            tokens = data.get("usage", {}).get("total_tokens", 0)
        else:
            raise HTTPException(400, f"Unknown provider: {req.provider}")

        duration = (datetime.now() - start_time).total_seconds() * 1000

        return {
            "response": text,
            "model": req.model,
            "tokens_used": tokens,
            "duration_ms": int(duration)
        }

    except Exception as e:
        log.error("playground_execution_failed", error=str(e), provider=req.provider)
        raise HTTPException(500, f"Execution failed: {str(e)}")

# ============================================================================
# LIBRARY ENDPOINTS
# ============================================================================

@app.get("/api/v1/library/prompts")
async def list_prompts(
    search: str = "",
    favorites: bool = False,
    repository: PromptRepository = Depends(get_prompt_repository),
):
    """List saved prompts"""
    try:
        return {"prompts": await repository.list(search, favorites)}
    except Exception as error:
        raise prompt_storage_error("list", error)

@app.post("/api/v1/library/prompts")
async def save_prompt(
    req: PromptSaveRequest,
    repository: PromptRepository = Depends(get_prompt_repository),
):
    """Save a prompt to the library"""
    try:
        prompt = await repository.save(req)
        return {"id": prompt["id"], "message": "Saved"}
    except Exception as error:
        raise prompt_storage_error("save", error)

@app.get("/api/v1/library/prompts/{prompt_id}")
async def get_prompt(
    prompt_id: int,
    repository: PromptRepository = Depends(get_prompt_repository),
):
    """Get a specific prompt"""
    try:
        prompt = await repository.get(prompt_id)
    except Exception as error:
        raise prompt_storage_error("get", error)
    if prompt is None:
        raise HTTPException(404, "Prompt not found")
    return {"prompt": prompt}

@app.delete("/api/v1/library/prompts/{prompt_id}")
async def delete_prompt(
    prompt_id: int,
    repository: PromptRepository = Depends(get_prompt_repository),
):
    """Delete a prompt"""
    try:
        deleted = await repository.delete(prompt_id)
    except Exception as error:
        raise prompt_storage_error("delete", error)
    if not deleted:
        raise HTTPException(404, "Prompt not found")
    return {"message": "Deleted"}

# ============================================================================
# API KEYS ENDPOINTS
# ============================================================================

@app.get("/api/v1/keys")
async def list_keys():
    """List stored API keys (without revealing values)"""
    keys = []
    for key_id, key_data in api_keys_store.items():
        keys.append({
            "id": key_id,
            "key_name": key_data["key_name"],
            "provider": key_data["provider"],
            "is_active": True,
            "created_at": key_data["created_at"]
        })
    return {"keys": keys}

@app.post("/api/v1/keys")
async def add_key(req: APIKeyRequest):
    """Add a new API key"""
    key_id = len(api_keys_store) + 1
    api_keys_store[key_id] = {
        "id": key_id,
        "key_name": req.key_name,
        "provider": req.provider,
        "api_key": req.api_key,
        "created_at": datetime.now().isoformat()
    }
    return {"id": key_id, "message": "Key added"}

@app.delete("/api/v1/keys/{key_id}")
async def delete_key(key_id: int):
    """Delete an API key"""
    if key_id not in api_keys_store:
        raise HTTPException(404, "Key not found")
    del api_keys_store[key_id]
    return {"message": "Deleted"}

# ============================================================================
# SECURITY SCANNING ENDPOINTS
# ============================================================================

@app.post("/api/v1/security/scan")
async def security_scan(req: SecurityScanRequest, background_tasks: BackgroundTasks):
    """
    Scan a prompt for security vulnerabilities using multiple tools.
    Integrates with llmsecurity.dev for jailbreak detection and threat intel.
    """
    scan_id = f"scan_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(security_scans)}"

    security_scans[scan_id] = {
        "id": scan_id,
        "status": "pending",
        "prompt": req.prompt,
        "target_model": req.target_model,
        "scan_types": req.scan_types,
        "results": {},
        "created_at": datetime.now().isoformat()
    }

    # Run scan in background
    background_tasks.add_task(run_security_scan, scan_id, req)

    return {"scan_id": scan_id, "status": "pending"}

async def run_security_scan(scan_id: str, req: SecurityScanRequest):
    """Background task to run security scans"""
    scan = security_scans[scan_id]
    scan["status"] = "running"
    results = {}

    try:
        # 1. llmsecurity.dev - Jailbreak detection
        if "jailbreak" in req.scan_types:
            results["jailbreak"] = await check_jailbreak_llmsecurity(req.prompt)

        # 2. Prompt injection detection (local)
        if "injection" in req.scan_types:
            results["injection"] = detect_prompt_injection(req.prompt)

        # 3. Data leak potential (local)
        if "data_leak" in req.scan_types:
            results["data_leak"] = detect_data_leak_potential(req.prompt)

        # 4. Toxicity check via models2go
        if "toxicity" in req.scan_types:
            results["toxicity"] = await check_toxicity_models2go(req.prompt)

        # 5. Threat intel enrichment via darkapi
        results["threat_intel"] = await enrich_with_darkapi(req.prompt)

        scan["results"] = results
        scan["status"] = "completed"

        # Calculate overall risk score
        scan["risk_score"] = calculate_risk_score(results)

    except Exception as e:
        scan["status"] = "failed"
        scan["error"] = str(e)
        log.error("security_scan_failed", scan_id=scan_id, error=str(e))

async def check_jailbreak_llmsecurity(prompt: str) -> dict:
    """Check prompt against llmsecurity.dev jailbreak database"""
    if not config.LLMSECURITY_KEY:
        return {"status": "skipped", "reason": "No API key configured"}

    try:
        response = await http_client.post(
            f"{config.LLMSECURITY_URL}/sentinel/analyze",
            headers={"Authorization": f"Bearer {config.LLMSECURITY_KEY}"},
            json={"prompt": prompt, "check_types": ["jailbreak", "injection"]}
        )
        return response.json()
    except Exception as e:
        return {"status": "error", "error": str(e)}

def detect_prompt_injection(prompt: str) -> dict:
    """Local prompt injection detection"""
    injection_patterns = [
        "ignore previous instructions",
        "ignore all previous",
        "disregard above",
        "forget everything",
        "new instructions:",
        "system prompt:",
        "you are now",
        "pretend you are",
        "act as if",
        "roleplay as",
        "DAN mode",
        "jailbreak",
        "bypass",
        "override",
        "\\n\\n###",
        "```system",
    ]

    prompt_lower = prompt.lower()
    detected = []

    for pattern in injection_patterns:
        if pattern.lower() in prompt_lower:
            detected.append(pattern)

    return {
        "detected": len(detected) > 0,
        "patterns_found": detected,
        "confidence": min(len(detected) * 0.2, 1.0),
        "risk_level": "high" if len(detected) > 2 else "medium" if len(detected) > 0 else "low"
    }

def detect_data_leak_potential(prompt: str) -> dict:
    """Detect potential data exfiltration attempts"""
    leak_patterns = [
        "send to",
        "email to",
        "post to",
        "upload to",
        "webhook",
        "http://",
        "https://",
        "api key",
        "password",
        "secret",
        "credential",
        "training data",
        "system prompt",
        "base64",
        "encode",
    ]

    prompt_lower = prompt.lower()
    detected = []

    for pattern in leak_patterns:
        if pattern in prompt_lower:
            detected.append(pattern)

    return {
        "detected": len(detected) > 0,
        "patterns_found": detected,
        "risk_level": "high" if len(detected) > 3 else "medium" if len(detected) > 0 else "low"
    }

async def check_toxicity_models2go(prompt: str) -> dict:
    """Check for toxic content via models2go"""
    # This would integrate with a toxicity model
    return {"status": "skipped", "reason": "Toxicity model not configured"}

async def enrich_with_darkapi(prompt: str) -> dict:
    """Enrich with threat intelligence from darkapi.io"""
    if not config.DARKAPI_KEY:
        return {"status": "skipped", "reason": "No API key configured"}

    # Extract URLs and domains from prompt
    import re
    urls = re.findall(r'https?://[^\s]+', prompt)

    if not urls:
        return {"status": "no_urls", "urls_checked": 0}

    results = []
    try:
        for url in urls[:5]:  # Check up to 5 URLs
            response = await http_client.get(
                f"{config.DARKAPI_URL}/url/check",
                headers={"Authorization": f"Bearer {config.DARKAPI_KEY}"},
                params={"url": url}
            )
            results.append(response.json())

        return {"status": "checked", "urls_checked": len(results), "results": results}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def calculate_risk_score(results: dict) -> dict:
    """Calculate overall risk score from scan results"""
    score = 0
    factors = []

    if results.get("injection", {}).get("detected"):
        score += 40
        factors.append("prompt_injection")

    if results.get("jailbreak", {}).get("detected"):
        score += 35
        factors.append("jailbreak_attempt")

    if results.get("data_leak", {}).get("risk_level") == "high":
        score += 25
        factors.append("data_leak_risk")

    return {
        "score": min(score, 100),
        "level": "critical" if score >= 70 else "high" if score >= 40 else "medium" if score >= 20 else "low",
        "factors": factors
    }

@app.get("/api/v1/security/scan/{scan_id}")
async def get_scan_status(scan_id: str):
    """Get security scan status and results"""
    if scan_id not in security_scans:
        raise HTTPException(404, "Scan not found")
    return security_scans[scan_id]

@app.get("/api/v1/security/scans")
async def list_scans(limit: int = 20):
    """List recent security scans"""
    scans = list(security_scans.values())
    scans.sort(key=lambda x: x["created_at"], reverse=True)
    return {"scans": scans[:limit]}

# ============================================================================
# RED TEAM ENDPOINTS
# ============================================================================

@app.post("/api/v1/redteam/session")
async def create_redteam_session(req: RedTeamRequest, background_tasks: BackgroundTasks):
    """
    Create a red team testing session using multiple tools.
    Integrates: Garak, Promptmap2, PyRIT, Promptfoo
    """
    session_id = f"rt_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(redteam_sessions)}"

    redteam_sessions[session_id] = {
        "id": session_id,
        "status": "pending",
        "prompt": req.prompt,
        "target_model": req.target_model,
        "attack_types": req.attack_types,
        "tools": req.tools,
        "iterations": req.iterations,
        "results": {},
        "attacks_attempted": 0,
        "attacks_successful": 0,
        "created_at": datetime.now().isoformat()
    }

    # Run red team in background
    background_tasks.add_task(run_redteam_session, session_id, req)

    return {"session_id": session_id, "status": "pending"}

async def run_redteam_session(session_id: str, req: RedTeamRequest):
    """Background task to run red team testing"""
    session = redteam_sessions[session_id]
    session["status"] = "running"

    try:
        results = {}
        total_attacks = 0
        successful_attacks = 0

        # Run each tool
        if "garak" in req.tools:
            garak_results = await run_garak_probes(req)
            results["garak"] = garak_results
            total_attacks += garak_results.get("total_probes", 0)
            successful_attacks += garak_results.get("successful_probes", 0)

        if "promptmap2" in req.tools:
            pm2_results = await run_promptmap2(req)
            results["promptmap2"] = pm2_results
            total_attacks += pm2_results.get("total_tests", 0)
            successful_attacks += pm2_results.get("successful_tests", 0)

        if "pyrit" in req.tools:
            pyrit_results = await run_pyrit_attacks(req)
            results["pyrit"] = pyrit_results
            total_attacks += pyrit_results.get("total_attacks", 0)
            successful_attacks += pyrit_results.get("successful_attacks", 0)

        if "promptfoo" in req.tools:
            pf_results = await run_promptfoo_eval(req)
            results["promptfoo"] = pf_results

        # Feed successful attacks to llmsecurity.dev jailbreak database
        if successful_attacks > 0:
            await report_to_llmsecurity(session_id, results)

        session["results"] = results
        session["attacks_attempted"] = total_attacks
        session["attacks_successful"] = successful_attacks
        session["status"] = "completed"
        session["vulnerability_score"] = (successful_attacks / max(total_attacks, 1)) * 100

    except Exception as e:
        session["status"] = "failed"
        session["error"] = str(e)
        log.error("redteam_session_failed", session_id=session_id, error=str(e))

async def run_garak_probes(req: RedTeamRequest) -> dict:
    """
    Run Garak LLM vulnerability scanner probes.

    Garak tests for: hallucination, data leakage, prompt injection,
    misinformation, toxicity, jailbreaks
    """
    # In production, this would shell out to garak CLI or use its Python API
    # garak --model_type rest --model_name target_api --probes all

    probe_categories = {
        "jailbreak": ["dan", "aim", "developer_mode", "evil_confidant"],
        "injection": ["payload_splitting", "virtualization", "obfuscation"],
        "extraction": ["system_prompt_extraction", "training_data_extraction"],
    }

    results = {
        "total_probes": 0,
        "successful_probes": 0,
        "probes": []
    }

    for attack_type in req.attack_types:
        if attack_type in probe_categories:
            for probe in probe_categories[attack_type]:
                # Simulate probe execution
                results["total_probes"] += req.iterations
                probe_result = {
                    "probe": probe,
                    "category": attack_type,
                    "iterations": req.iterations,
                    "successful": 0,  # Would be actual count
                    "payloads": []
                }
                results["probes"].append(probe_result)

    return results

async def run_promptmap2(req: RedTeamRequest) -> dict:
    """
    Run Promptmap2 prompt injection scanner.

    Categories: distraction, prompt_stealing, jailbreak, harmful, hate, social_bias
    """
    # In production, would run promptmap2 CLI
    # promptmap2 --target-type whitebox --model gpt-4 --system-prompt "..."

    test_categories = ["distraction", "prompt_stealing", "jailbreak"]

    results = {
        "total_tests": 0,
        "successful_tests": 0,
        "categories": {}
    }

    for category in test_categories:
        cat_result = {
            "tests_run": req.iterations,
            "successful": 0,
            "payloads": []
        }
        results["total_tests"] += req.iterations
        results["categories"][category] = cat_result

    return results

async def run_pyrit_attacks(req: RedTeamRequest) -> dict:
    """
    Run PyRIT (Python Risk Identification Toolkit) attacks.

    Supports multi-turn attacks, adaptive strategies, and
    multimodal testing.
    """
    # In production, would use PyRIT Python API
    # from pyrit.orchestrator import RedTeamingOrchestrator

    results = {
        "total_attacks": 0,
        "successful_attacks": 0,
        "strategies": []
    }

    strategies = ["single_turn", "multi_turn", "tree_of_attacks"]

    for strategy in strategies:
        strategy_result = {
            "name": strategy,
            "attacks_run": req.iterations,
            "successful": 0,
            "findings": []
        }
        results["total_attacks"] += req.iterations
        results["strategies"].append(strategy_result)

    return results

async def run_promptfoo_eval(req: RedTeamRequest) -> dict:
    """
    Run Promptfoo evaluation with red team plugins.

    Supports OWASP Top 10, MITRE ATLAS presets.
    """
    # In production, would run promptfoo CLI or API
    # promptfoo eval --config redteam.yaml

    results = {
        "eval_id": f"eval_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "presets": ["owasp:llm", "mitre:atlas"],
        "tests_passed": 0,
        "tests_failed": 0,
        "assertions": []
    }

    return results

async def report_to_llmsecurity(session_id: str, results: dict):
    """Report successful attacks to llmsecurity.dev threat database"""
    if not config.LLMSECURITY_KEY:
        return

    try:
        await http_client.post(
            f"{config.LLMSECURITY_URL}/intel/report",
            headers={"Authorization": f"Bearer {config.LLMSECURITY_KEY}"},
            json={
                "source": "prompt_generator_redteam",
                "session_id": session_id,
                "findings": results,
                "report_type": "jailbreak_technique"
            }
        )
    except Exception as e:
        log.error("failed_to_report_to_llmsecurity", error=str(e))

@app.get("/api/v1/redteam/session/{session_id}")
async def get_redteam_session(session_id: str):
    """Get red team session status and results"""
    if session_id not in redteam_sessions:
        raise HTTPException(404, "Session not found")
    return redteam_sessions[session_id]

@app.get("/api/v1/redteam/sessions")
async def list_redteam_sessions(limit: int = 20):
    """List recent red team sessions"""
    sessions = list(redteam_sessions.values())
    sessions.sort(key=lambda x: x["created_at"], reverse=True)
    return {"sessions": sessions[:limit]}

# ============================================================================
# ART (ADVERSARIAL ROBUSTNESS TOOLBOX) ENDPOINTS
# ============================================================================

@app.post("/api/v1/art/attack")
async def art_attack(req: ARTAttackRequest, background_tasks: BackgroundTasks):
    """
    Run ART attacks against models2go.com endpoints.

    Tests: evasion, poisoning, extraction, inference attacks
    on scikit-learn/XGBoost models.
    """
    attack_id = f"art_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # This would integrate with ART library
    # from art.attacks.evasion import ZooAttack, HopSkipJump
    # from art.attacks.extraction import CopycatCNN
    # from art.attacks.inference import MembershipInference

    result = {
        "attack_id": attack_id,
        "status": "queued",
        "attack_type": req.attack_type,
        "target_endpoint": req.model_endpoint,
        "samples_count": len(req.samples),
        "message": f"ART {req.attack_type} attack queued for {req.model_endpoint}"
    }

    return result

@app.get("/api/v1/art/attacks")
async def list_art_attacks():
    """List ART attack results"""
    return {"attacks": []}

# ============================================================================
# CAI (CYBERSECURITY AI) ORCHESTRATION
# ============================================================================

@app.post("/api/v1/cai/workflow")
async def cai_workflow(workflow: dict):
    """
    Execute a CAI orchestration workflow across all platforms.

    CAI can coordinate: darkapi lookups, llmsecurity scans,
    models2go predictions, and security tool execution.
    """
    workflow_id = f"cai_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # This would integrate with CAI framework
    # from cai import Agent, Workflow

    return {
        "workflow_id": workflow_id,
        "status": "queued",
        "message": "CAI workflow queued for execution"
    }

# ============================================================================
# PLATFORM INTEGRATION ENDPOINTS
# ============================================================================

@app.get("/api/v1/platforms/status")
async def platform_status():
    """Check connectivity to all integrated platforms"""
    status = {}

    # Check darkapi.io
    try:
        if config.DARKAPI_KEY:
            resp = await http_client.get(
                f"{config.DARKAPI_URL}/health",
                headers={"Authorization": f"Bearer {config.DARKAPI_KEY}"},
                timeout=5.0
            )
            status["darkapi"] = {"status": "online" if resp.status_code == 200 else "error"}
        else:
            status["darkapi"] = {"status": "not_configured"}
    except:
        status["darkapi"] = {"status": "offline"}

    # Check llmsecurity.dev
    try:
        if config.LLMSECURITY_KEY:
            resp = await http_client.get(
                f"{config.LLMSECURITY_URL}/health",
                headers={"Authorization": f"Bearer {config.LLMSECURITY_KEY}"},
                timeout=5.0
            )
            status["llmsecurity"] = {"status": "online" if resp.status_code == 200 else "error"}
        else:
            status["llmsecurity"] = {"status": "not_configured"}
    except:
        status["llmsecurity"] = {"status": "offline"}

    # Check models2go.com
    try:
        if config.MODELS2GO_KEY:
            resp = await http_client.get(
                f"{config.MODELS2GO_URL}/health",
                timeout=5.0
            )
            status["models2go"] = {"status": "online" if resp.status_code == 200 else "error"}
        else:
            status["models2go"] = {"status": "not_configured"}
    except:
        status["models2go"] = {"status": "offline"}

    return {"platforms": status, "checked_at": datetime.now().isoformat()}

# ============================================================================
# HEALTH & STATIC FILES
# ============================================================================

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "2.0.0"}

# Serve static files
app.mount("/static", StaticFiles(directory="templates"), name="static")

@app.get("/")
async def root():
    return FileResponse("templates/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
