"""API routes for prompt library management."""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, g, jsonify, request
from sqlalchemy.orm import Session

from errors import ValidationError
from logging_config import get_logger
from models import SavedPrompt, get_db

log = get_logger(__name__)

library_bp = Blueprint("library", __name__, url_prefix="/api/v1/library")


@library_bp.route("/prompts", methods=["GET"])
def list_prompts():
    """List all saved prompts."""
    db: Session = next(get_db())

    try:
        # Query parameters
        search = request.args.get("search", "").strip()
        tag = request.args.get("tag", "").strip()
        favorites_only = request.args.get("favorites", "false").lower() == "true"
        limit = min(int(request.args.get("limit", "50")), 100)
        offset = int(request.args.get("offset", "0"))

        # Build query
        query = db.query(SavedPrompt)

        if search:
            query = query.filter(
                (SavedPrompt.name.ilike(f"%{search}%"))
                | (SavedPrompt.description.ilike(f"%{search}%"))
                | (SavedPrompt.task.ilike(f"%{search}%"))
            )

        if tag:
            query = query.filter(SavedPrompt.tags.ilike(f"%{tag}%"))

        if favorites_only:
            query = query.filter(SavedPrompt.is_favorite == True)

        # Get total count
        total = query.count()

        # Apply pagination and ordering
        prompts = (
            query.order_by(SavedPrompt.updated_at.desc()).offset(offset).limit(limit).all()
        )

        return jsonify(
            {
                "prompts": [p.to_dict() for p in prompts],
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        )
    finally:
        db.close()


@library_bp.route("/prompts", methods=["POST"])
def create_prompt():
    """Create a new saved prompt."""
    db: Session = next(get_db())

    try:
        data = request.get_json()

        if not data.get("name"):
            raise ValidationError("Prompt name is required")

        if not data.get("task"):
            raise ValidationError("Task is required")

        prompt = SavedPrompt(
            name=data["name"],
            description=data.get("description", ""),
            target=data.get("target", "chatgpt"),
            task=data["task"],
            context=data.get("context", ""),
            constraints=data.get("constraints", ""),
            deliverables=data.get("deliverables", ""),
            tone=data.get("tone", ""),
            generated_prompt=data.get("generated_prompt", ""),
            tags=",".join(data.get("tags", [])) if isinstance(data.get("tags"), list) else "",
            is_favorite=data.get("is_favorite", False),
        )

        db.add(prompt)
        db.commit()
        db.refresh(prompt)

        log.info("prompt_created", prompt_id=prompt.id, name=prompt.name, request_id=g.request_id)

        return jsonify({"prompt": prompt.to_dict()}), 201
    except ValidationError:
        raise
    except Exception as e:
        db.rollback()
        log.error("prompt_creation_failed", error=str(e), exc_info=True)
        raise ValidationError(f"Failed to create prompt: {str(e)}")
    finally:
        db.close()


@library_bp.route("/prompts/<int:prompt_id>", methods=["GET"])
def get_prompt(prompt_id: int):
    """Get a specific saved prompt."""
    db: Session = next(get_db())

    try:
        prompt = db.query(SavedPrompt).filter(SavedPrompt.id == prompt_id).first()

        if not prompt:
            return jsonify({"error": "Prompt not found"}), 404

        return jsonify({"prompt": prompt.to_dict()})
    finally:
        db.close()


@library_bp.route("/prompts/<int:prompt_id>", methods=["PUT"])
def update_prompt(prompt_id: int):
    """Update a saved prompt."""
    db: Session = next(get_db())

    try:
        prompt = db.query(SavedPrompt).filter(SavedPrompt.id == prompt_id).first()

        if not prompt:
            return jsonify({"error": "Prompt not found"}), 404

        data = request.get_json()

        # Update fields
        if "name" in data:
            prompt.name = data["name"]
        if "description" in data:
            prompt.description = data["description"]
        if "target" in data:
            prompt.target = data["target"]
        if "task" in data:
            prompt.task = data["task"]
        if "context" in data:
            prompt.context = data["context"]
        if "constraints" in data:
            prompt.constraints = data["constraints"]
        if "deliverables" in data:
            prompt.deliverables = data["deliverables"]
        if "tone" in data:
            prompt.tone = data["tone"]
        if "generated_prompt" in data:
            prompt.generated_prompt = data["generated_prompt"]
        if "tags" in data:
            prompt.tags = (
                ",".join(data["tags"]) if isinstance(data["tags"], list) else data["tags"]
            )
        if "is_favorite" in data:
            prompt.is_favorite = data["is_favorite"]

        prompt.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(prompt)

        log.info("prompt_updated", prompt_id=prompt.id, request_id=g.request_id)

        return jsonify({"prompt": prompt.to_dict()})
    except Exception as e:
        db.rollback()
        log.error("prompt_update_failed", error=str(e), exc_info=True)
        raise ValidationError(f"Failed to update prompt: {str(e)}")
    finally:
        db.close()


@library_bp.route("/prompts/<int:prompt_id>", methods=["DELETE"])
def delete_prompt(prompt_id: int):
    """Delete a saved prompt."""
    db: Session = next(get_db())

    try:
        prompt = db.query(SavedPrompt).filter(SavedPrompt.id == prompt_id).first()

        if not prompt:
            return jsonify({"error": "Prompt not found"}), 404

        db.delete(prompt)
        db.commit()

        log.info("prompt_deleted", prompt_id=prompt_id, request_id=g.request_id)

        return jsonify({"message": "Prompt deleted successfully"})
    except Exception as e:
        db.rollback()
        log.error("prompt_deletion_failed", error=str(e), exc_info=True)
        raise ValidationError(f"Failed to delete prompt: {str(e)}")
    finally:
        db.close()


@library_bp.route("/prompts/<int:prompt_id>/favorite", methods=["POST"])
def toggle_favorite(prompt_id: int):
    """Toggle favorite status of a prompt."""
    db: Session = next(get_db())

    try:
        prompt = db.query(SavedPrompt).filter(SavedPrompt.id == prompt_id).first()

        if not prompt:
            return jsonify({"error": "Prompt not found"}), 404

        prompt.is_favorite = not prompt.is_favorite
        prompt.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(prompt)

        return jsonify({"prompt": prompt.to_dict()})
    except Exception as e:
        db.rollback()
        log.error("favorite_toggle_failed", error=str(e), exc_info=True)
        raise ValidationError(f"Failed to toggle favorite: {str(e)}")
    finally:
        db.close()


@library_bp.route("/tags", methods=["GET"])
def list_tags():
    """Get all unique tags from saved prompts."""
    db: Session = next(get_db())

    try:
        prompts = db.query(SavedPrompt.tags).filter(SavedPrompt.tags != "").all()

        tags_set = set()
        for (tags_str,) in prompts:
            if tags_str:
                tags_set.update(tag.strip() for tag in tags_str.split(",") if tag.strip())

        return jsonify({"tags": sorted(tags_set)})
    finally:
        db.close()
