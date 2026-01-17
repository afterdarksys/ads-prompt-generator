"""API routes for prompt versioning and A/B testing."""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy import desc

from models import SessionLocal
from models_extended import ABTest, PromptExecution, PromptVersion

versioning_bp = Blueprint("versioning", __name__, url_prefix="/api/v1/prompts")


@versioning_bp.route("/<int:prompt_id>/versions", methods=["GET"])
def list_versions(prompt_id: int):
    """List all versions of a prompt."""
    db = SessionLocal()
    try:
        versions = (
            db.query(PromptVersion)
            .filter(PromptVersion.prompt_id == prompt_id)
            .order_by(desc(PromptVersion.version_number))
            .all()
        )

        return jsonify(
            {
                "prompt_id": prompt_id,
                "versions": [v.to_dict() for v in versions],
                "total": len(versions),
            }
        )
    finally:
        db.close()


@versioning_bp.route("/<int:prompt_id>/versions", methods=["POST"])
def create_version(prompt_id: int):
    """Create a new version of a prompt."""
    data = request.get_json()

    db = SessionLocal()
    try:
        # Get current max version
        max_version = (
            db.query(PromptVersion.version_number)
            .filter(PromptVersion.prompt_id == prompt_id)
            .order_by(desc(PromptVersion.version_number))
            .first()
        )

        next_version = (max_version[0] + 1) if max_version else 1

        version = PromptVersion(
            prompt_id=prompt_id,
            version_number=next_version,
            name=data.get("name", f"Version {next_version}"),
            task=data["task"],
            context=data.get("context"),
            constraints=data.get("constraints"),
            deliverables=data.get("deliverables"),
            tone=data.get("tone"),
            generated_prompt=data.get("generated_prompt"),
            created_by=data.get("created_by", "anonymous"),
            change_description=data.get("change_description"),
        )

        db.add(version)
        db.commit()
        db.refresh(version)

        return jsonify(version.to_dict()), 201
    finally:
        db.close()


@versioning_bp.route("/<int:prompt_id>/versions/<int:version_id>", methods=["GET"])
def get_version(prompt_id: int, version_id: int):
    """Get a specific version."""
    db = SessionLocal()
    try:
        version = (
            db.query(PromptVersion)
            .filter(
                PromptVersion.prompt_id == prompt_id,
                PromptVersion.id == version_id,
            )
            .first()
        )

        if not version:
            return jsonify({"error": "Version not found"}), 404

        return jsonify(version.to_dict())
    finally:
        db.close()


@versioning_bp.route("/<int:prompt_id>/versions/<int:version_id>/revert", methods=["POST"])
def revert_to_version(prompt_id: int, version_id: int):
    """Revert prompt to a specific version (creates new version)."""
    db = SessionLocal()
    try:
        old_version = (
            db.query(PromptVersion)
            .filter(
                PromptVersion.prompt_id == prompt_id,
                PromptVersion.id == version_id,
            )
            .first()
        )

        if not old_version:
            return jsonify({"error": "Version not found"}), 404

        # Get next version number
        max_version = (
            db.query(PromptVersion.version_number)
            .filter(PromptVersion.prompt_id == prompt_id)
            .order_by(desc(PromptVersion.version_number))
            .first()
        )
        next_version = (max_version[0] + 1) if max_version else 1

        # Create new version with old content
        new_version = PromptVersion(
            prompt_id=prompt_id,
            version_number=next_version,
            name=old_version.name,
            task=old_version.task,
            context=old_version.context,
            constraints=old_version.constraints,
            deliverables=old_version.deliverables,
            tone=old_version.tone,
            generated_prompt=old_version.generated_prompt,
            created_by=request.json.get("created_by", "anonymous"),
            change_description=f"Reverted to version {old_version.version_number}",
        )

        db.add(new_version)
        db.commit()
        db.refresh(new_version)

        return jsonify(new_version.to_dict()), 201
    finally:
        db.close()


# A/B Testing Routes
@versioning_bp.route("/ab-tests", methods=["GET"])
def list_ab_tests():
    """List all A/B tests."""
    db = SessionLocal()
    try:
        tests = db.query(ABTest).order_by(desc(ABTest.started_at)).all()

        return jsonify(
            {
                "tests": [t.to_dict() for t in tests],
                "total": len(tests),
            }
        )
    finally:
        db.close()


@versioning_bp.route("/ab-tests", methods=["POST"])
def create_ab_test():
    """Create a new A/B test."""
    data = request.get_json()

    db = SessionLocal()
    try:
        test = ABTest(
            name=data["name"],
            description=data.get("description"),
            variant_a_id=data["variant_a_id"],
            variant_b_id=data["variant_b_id"],
            traffic_split=data.get("traffic_split", 0.5),
            created_by=data.get("created_by", "anonymous"),
        )

        db.add(test)
        db.commit()
        db.refresh(test)

        return jsonify(test.to_dict()), 201
    finally:
        db.close()


@versioning_bp.route("/ab-tests/<int:test_id>", methods=["GET"])
def get_ab_test(test_id: int):
    """Get A/B test with results."""
    db = SessionLocal()
    try:
        test = db.query(ABTest).filter(ABTest.id == test_id).first()

        if not test:
            return jsonify({"error": "Test not found"}), 404

        # Get execution stats for both variants
        variant_a_stats = get_variant_stats(db, test.variant_a_id, test_id)
        variant_b_stats = get_variant_stats(db, test.variant_b_id, test_id)

        return jsonify(
            {
                **test.to_dict(),
                "variant_a_stats": variant_a_stats,
                "variant_b_stats": variant_b_stats,
            }
        )
    finally:
        db.close()


@versioning_bp.route("/ab-tests/<int:test_id>/finish", methods=["POST"])
def finish_ab_test(test_id: int):
    """Finish an A/B test and declare a winner."""
    data = request.get_json()

    db = SessionLocal()
    try:
        test = db.query(ABTest).filter(ABTest.id == test_id).first()

        if not test:
            return jsonify({"error": "Test not found"}), 404

        test.is_active = False
        test.ended_at = datetime.utcnow()
        test.winner_id = data.get("winner_id")

        db.commit()
        db.refresh(test)

        return jsonify(test.to_dict())
    finally:
        db.close()


def get_variant_stats(db, version_id: int, test_id: int):
    """Get statistics for a variant."""
    executions = (
        db.query(PromptExecution)
        .filter(
            PromptExecution.prompt_version_id == version_id,
            PromptExecution.ab_test_id == test_id,
        )
        .all()
    )

    if not executions:
        return {
            "executions": 0,
            "avg_tokens": 0,
            "avg_duration_ms": 0,
            "success_rate": 0,
            "avg_rating": 0,
        }

    total_executions = len(executions)
    successful = sum(1 for e in executions if e.success)
    avg_tokens = sum(e.tokens_used or 0 for e in executions) / total_executions
    avg_duration = sum(e.duration_ms or 0 for e in executions) / total_executions
    ratings = [e.user_rating for e in executions if e.user_rating]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0

    return {
        "executions": total_executions,
        "avg_tokens": round(avg_tokens, 2),
        "avg_duration_ms": round(avg_duration, 2),
        "success_rate": round(successful / total_executions * 100, 2),
        "avg_rating": round(avg_rating, 2),
    }
