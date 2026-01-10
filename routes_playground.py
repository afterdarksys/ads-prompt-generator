"""API routes for playground and API key management."""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, g, jsonify, request
from sqlalchemy.orm import Session

from errors import ValidationError
from logging_config import get_logger
from models import APIKey, PlaygroundSession, get_db, key_encryption
from playground import PROVIDER_MODELS, get_provider

log = get_logger(__name__)

playground_bp = Blueprint("playground", __name__, url_prefix="/api/v1/playground")
keys_bp = Blueprint("keys", __name__, url_prefix="/api/v1/keys")


# ============================================================================
# API Key Management
# ============================================================================


@keys_bp.route("", methods=["GET"])
def list_keys():
    """List all API keys (without actual key values)."""
    db: Session = next(get_db())

    try:
        keys = db.query(APIKey).order_by(APIKey.created_at.desc()).all()
        return jsonify({"keys": [k.to_dict() for k in keys]})
    finally:
        db.close()


@keys_bp.route("", methods=["POST"])
def create_key():
    """Store a new API key."""
    db: Session = next(get_db())

    try:
        data = request.get_json()

        provider = data.get("provider")
        key_name = data.get("key_name")
        api_key = data.get("api_key")

        if not provider or provider not in ["anthropic", "openai", "openrouter"]:
            raise ValidationError("Valid provider is required (anthropic, openai, openrouter)")

        if not key_name:
            raise ValidationError("Key name is required")

        if not api_key:
            raise ValidationError("API key is required")

        # Encrypt the API key
        encrypted = key_encryption.encrypt(api_key)

        key = APIKey(
            provider=provider,
            key_name=key_name,
            encrypted_key=encrypted,
            is_active=True,
        )

        db.add(key)
        db.commit()
        db.refresh(key)

        log.info("api_key_created", key_id=key.id, provider=provider, request_id=g.request_id)

        return jsonify({"key": key.to_dict()}), 201
    except ValidationError:
        raise
    except Exception as e:
        db.rollback()
        log.error("api_key_creation_failed", error=str(e), exc_info=True)
        raise ValidationError(f"Failed to create API key: {str(e)}")
    finally:
        db.close()


@keys_bp.route("/<int:key_id>", methods=["DELETE"])
def delete_key(key_id: int):
    """Delete an API key."""
    db: Session = next(get_db())

    try:
        key = db.query(APIKey).filter(APIKey.id == key_id).first()

        if not key:
            return jsonify({"error": "API key not found"}), 404

        db.delete(key)
        db.commit()

        log.info("api_key_deleted", key_id=key_id, request_id=g.request_id)

        return jsonify({"message": "API key deleted successfully"})
    except Exception as e:
        db.rollback()
        log.error("api_key_deletion_failed", error=str(e), exc_info=True)
        raise ValidationError(f"Failed to delete API key: {str(e)}")
    finally:
        db.close()


@keys_bp.route("/<int:key_id>/toggle", methods=["POST"])
def toggle_key(key_id: int):
    """Toggle API key active status."""
    db: Session = next(get_db())

    try:
        key = db.query(APIKey).filter(APIKey.id == key_id).first()

        if not key:
            return jsonify({"error": "API key not found"}), 404

        key.is_active = not key.is_active
        db.commit()
        db.refresh(key)

        return jsonify({"key": key.to_dict()})
    except Exception as e:
        db.rollback()
        log.error("api_key_toggle_failed", error=str(e), exc_info=True)
        raise ValidationError(f"Failed to toggle API key: {str(e)}")
    finally:
        db.close()


# ============================================================================
# Playground
# ============================================================================


@playground_bp.route("/providers", methods=["GET"])
def list_providers():
    """Get available providers and their models."""
    return jsonify(
        {
            "providers": [
                {
                    "id": "anthropic",
                    "name": "Anthropic Claude",
                    "requires_key": True,
                    "models": PROVIDER_MODELS["anthropic"],
                },
                {
                    "id": "openai",
                    "name": "OpenAI ChatGPT",
                    "requires_key": True,
                    "models": PROVIDER_MODELS["openai"],
                },
                {
                    "id": "openrouter",
                    "name": "OpenRouter",
                    "requires_key": True,
                    "models": PROVIDER_MODELS["openrouter"],
                },
                {
                    "id": "detached",
                    "name": "Detached Mode (No API)",
                    "requires_key": False,
                    "models": PROVIDER_MODELS["detached"],
                },
            ]
        }
    )


@playground_bp.route("/execute", methods=["POST"])
async def execute_prompt():
    """Execute a prompt in the playground."""
    db: Session = next(get_db())

    try:
        data = request.get_json()

        provider = data.get("provider")
        model = data.get("model")
        prompt = data.get("prompt")
        key_id = data.get("key_id")  # Optional: use stored key

        if not provider:
            raise ValidationError("Provider is required")

        if not prompt:
            raise ValidationError("Prompt is required")

        # Get API key
        api_key = None
        if provider != "detached":
            if key_id:
                # Use stored key
                key_obj = (
                    db.query(APIKey)
                    .filter(APIKey.id == key_id, APIKey.provider == provider, APIKey.is_active == True)
                    .first()
                )

                if not key_obj:
                    raise ValidationError("API key not found or inactive")

                api_key = key_encryption.decrypt(key_obj.encrypted_key)
                key_obj.last_used_at = datetime.utcnow()
                db.commit()
            else:
                # Use inline key
                api_key = data.get("api_key")
                if not api_key:
                    raise ValidationError(
                        "API key is required (either key_id or api_key must be provided)"
                    )

        # Execute prompt
        provider_instance = get_provider(provider, api_key)
        result = await provider_instance.execute(prompt, model)

        # Save session
        session = PlaygroundSession(
            provider=provider,
            model=result.get("model"),
            prompt=prompt,
            response=result.get("response"),
            error=result.get("error"),
            tokens_used=result.get("tokens_used"),
            duration_ms=result.get("duration_ms"),
        )

        db.add(session)
        db.commit()
        db.refresh(session)

        log.info(
            "playground_executed",
            session_id=session.id,
            provider=provider,
            success=result.get("success"),
            request_id=g.request_id,
        )

        return jsonify(
            {
                "session_id": session.id,
                "success": result.get("success"),
                "response": result.get("response"),
                "model": result.get("model"),
                "tokens_used": result.get("tokens_used"),
                "duration_ms": result.get("duration_ms"),
                "error": result.get("error"),
                "detached": result.get("detached", False),
                "message": result.get("message"),
            }
        )
    except ValidationError:
        raise
    except Exception as e:
        log.error("playground_execution_failed", error=str(e), exc_info=True)
        raise ValidationError(f"Failed to execute prompt: {str(e)}")
    finally:
        db.close()


@playground_bp.route("/history", methods=["GET"])
def get_history():
    """Get playground execution history."""
    db: Session = next(get_db())

    try:
        limit = min(int(request.args.get("limit", "20")), 100)
        offset = int(request.args.get("offset", "0"))

        sessions = (
            db.query(PlaygroundSession)
            .order_by(PlaygroundSession.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        total = db.query(PlaygroundSession).count()

        return jsonify(
            {
                "sessions": [s.to_dict() for s in sessions],
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        )
    finally:
        db.close()


@playground_bp.route("/history/<int:session_id>", methods=["GET"])
def get_session(session_id: int):
    """Get a specific playground session."""
    db: Session = next(get_db())

    try:
        session = db.query(PlaygroundSession).filter(PlaygroundSession.id == session_id).first()

        if not session:
            return jsonify({"error": "Session not found"}), 404

        return jsonify({"session": session.to_dict()})
    finally:
        db.close()
