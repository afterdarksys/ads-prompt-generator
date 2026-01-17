"""API routes for team collaboration features."""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy import desc, or_

from models import SessionLocal
from models_extended import (
    PromptApproval,
    PromptComment,
    Team,
    TeamMember,
)

collaboration_bp = Blueprint("collaboration", __name__, url_prefix="/api/v1")


# Team Management
@collaboration_bp.route("/teams", methods=["GET"])
def list_teams():
    """List all teams."""
    db = SessionLocal()
    try:
        teams = db.query(Team).filter(Team.is_active == True).all()

        return jsonify(
            {
                "teams": [t.to_dict() for t in teams],
                "total": len(teams),
            }
        )
    finally:
        db.close()


@collaboration_bp.route("/teams", methods=["POST"])
def create_team():
    """Create a new team."""
    data = request.get_json()

    db = SessionLocal()
    try:
        team = Team(
            name=data["name"],
            description=data.get("description"),
            created_by=data["created_by"],
        )

        db.add(team)
        db.commit()
        db.refresh(team)

        # Add creator as owner
        member = TeamMember(
            team_id=team.id,
            user_id=data["created_by"],
            role="owner",
        )
        db.add(member)
        db.commit()

        return jsonify(team.to_dict()), 201
    finally:
        db.close()


@collaboration_bp.route("/teams/<int:team_id>/members", methods=["GET"])
def list_team_members(team_id: int):
    """List team members."""
    db = SessionLocal()
    try:
        members = (
            db.query(TeamMember)
            .filter(TeamMember.team_id == team_id, TeamMember.is_active == True)
            .all()
        )

        return jsonify(
            {
                "team_id": team_id,
                "members": [m.to_dict() for m in members],
                "total": len(members),
            }
        )
    finally:
        db.close()


@collaboration_bp.route("/teams/<int:team_id>/members", methods=["POST"])
def add_team_member(team_id: int):
    """Add member to team."""
    data = request.get_json()

    db = SessionLocal()
    try:
        # Check if member already exists
        existing = (
            db.query(TeamMember)
            .filter(
                TeamMember.team_id == team_id,
                TeamMember.user_id == data["user_id"],
            )
            .first()
        )

        if existing:
            if not existing.is_active:
                existing.is_active = True
                existing.role = data.get("role", "member")
                db.commit()
                db.refresh(existing)
                return jsonify(existing.to_dict())
            return jsonify({"error": "Member already exists"}), 400

        member = TeamMember(
            team_id=team_id,
            user_id=data["user_id"],
            role=data.get("role", "member"),
        )

        db.add(member)
        db.commit()
        db.refresh(member)

        return jsonify(member.to_dict()), 201
    finally:
        db.close()


@collaboration_bp.route("/teams/<int:team_id>/members/<int:member_id>", methods=["DELETE"])
def remove_team_member(team_id: int, member_id: int):
    """Remove member from team."""
    db = SessionLocal()
    try:
        member = (
            db.query(TeamMember)
            .filter(
                TeamMember.id == member_id,
                TeamMember.team_id == team_id,
            )
            .first()
        )

        if not member:
            return jsonify({"error": "Member not found"}), 404

        member.is_active = False
        db.commit()

        return jsonify({"message": "Member removed successfully"})
    finally:
        db.close()


# Comments
@collaboration_bp.route("/prompts/<int:prompt_id>/comments", methods=["GET"])
def list_comments(prompt_id: int):
    """List comments on a prompt."""
    db = SessionLocal()
    try:
        comments = (
            db.query(PromptComment)
            .filter(PromptComment.prompt_id == prompt_id)
            .order_by(PromptComment.created_at)
            .all()
        )

        return jsonify(
            {
                "prompt_id": prompt_id,
                "comments": [c.to_dict() for c in comments],
                "total": len(comments),
            }
        )
    finally:
        db.close()


@collaboration_bp.route("/prompts/<int:prompt_id>/comments", methods=["POST"])
def add_comment(prompt_id: int):
    """Add a comment to a prompt."""
    data = request.get_json()

    db = SessionLocal()
    try:
        comment = PromptComment(
            prompt_id=prompt_id,
            prompt_version_id=data.get("prompt_version_id"),
            user_id=data["user_id"],
            comment=data["comment"],
            parent_comment_id=data.get("parent_comment_id"),
        )

        db.add(comment)
        db.commit()
        db.refresh(comment)

        return jsonify(comment.to_dict()), 201
    finally:
        db.close()


@collaboration_bp.route("/prompts/<int:prompt_id>/comments/<int:comment_id>", methods=["PUT"])
def update_comment(prompt_id: int, comment_id: int):
    """Update a comment."""
    data = request.get_json()

    db = SessionLocal()
    try:
        comment = (
            db.query(PromptComment)
            .filter(
                PromptComment.id == comment_id,
                PromptComment.prompt_id == prompt_id,
            )
            .first()
        )

        if not comment:
            return jsonify({"error": "Comment not found"}), 404

        if "comment" in data:
            comment.comment = data["comment"]
        if "is_resolved" in data:
            comment.is_resolved = data["is_resolved"]

        db.commit()
        db.refresh(comment)

        return jsonify(comment.to_dict())
    finally:
        db.close()


@collaboration_bp.route("/prompts/<int:prompt_id>/comments/<int:comment_id>", methods=["DELETE"])
def delete_comment(prompt_id: int, comment_id: int):
    """Delete a comment."""
    db = SessionLocal()
    try:
        comment = (
            db.query(PromptComment)
            .filter(
                PromptComment.id == comment_id,
                PromptComment.prompt_id == prompt_id,
            )
            .first()
        )

        if not comment:
            return jsonify({"error": "Comment not found"}), 404

        db.delete(comment)
        db.commit()

        return jsonify({"message": "Comment deleted successfully"})
    finally:
        db.close()


# Approvals
@collaboration_bp.route("/prompts/<int:prompt_id>/approvals", methods=["GET"])
def list_approvals(prompt_id: int):
    """List approvals for a prompt."""
    db = SessionLocal()
    try:
        approvals = (
            db.query(PromptApproval)
            .filter(PromptApproval.prompt_id == prompt_id)
            .order_by(desc(PromptApproval.requested_at))
            .all()
        )

        return jsonify(
            {
                "prompt_id": prompt_id,
                "approvals": [a.to_dict() for a in approvals],
                "total": len(approvals),
            }
        )
    finally:
        db.close()


@collaboration_bp.route("/prompts/<int:prompt_id>/approvals", methods=["POST"])
def request_approval(prompt_id: int):
    """Request approval for a prompt."""
    data = request.get_json()

    db = SessionLocal()
    try:
        approval = PromptApproval(
            prompt_id=prompt_id,
            prompt_version_id=data["prompt_version_id"],
            requested_by=data["requested_by"],
        )

        db.add(approval)
        db.commit()
        db.refresh(approval)

        return jsonify(approval.to_dict()), 201
    finally:
        db.close()


@collaboration_bp.route("/prompts/<int:prompt_id>/approvals/<int:approval_id>", methods=["PUT"])
def process_approval(prompt_id: int, approval_id: int):
    """Approve or reject a prompt."""
    data = request.get_json()

    db = SessionLocal()
    try:
        approval = (
            db.query(PromptApproval)
            .filter(
                PromptApproval.id == approval_id,
                PromptApproval.prompt_id == prompt_id,
            )
            .first()
        )

        if not approval:
            return jsonify({"error": "Approval not found"}), 404

        approval.status = data["status"]  # 'approved' or 'rejected'
        approval.approved_by = data["approved_by"]
        approval.approval_comment = data.get("approval_comment")
        approval.approved_at = datetime.utcnow()

        db.commit()
        db.refresh(approval)

        return jsonify(approval.to_dict())
    finally:
        db.close()


@collaboration_bp.route("/approvals/pending", methods=["GET"])
def list_pending_approvals():
    """List all pending approvals for the user."""
    user_id = request.args.get("user_id")

    db = SessionLocal()
    try:
        query = db.query(PromptApproval).filter(PromptApproval.status == "pending")

        if user_id:
            # Get teams where user is admin or owner
            teams = (
                db.query(TeamMember.team_id)
                .filter(
                    TeamMember.user_id == user_id,
                    TeamMember.role.in_(["owner", "admin"]),
                    TeamMember.is_active == True,
                )
                .all()
            )
            team_ids = [t[0] for t in teams]

            # Filter approvals (this is simplified, would need team_id in PromptApproval table)
            # For now, show all pending
            pass

        approvals = query.order_by(PromptApproval.requested_at).all()

        return jsonify(
            {
                "approvals": [a.to_dict() for a in approvals],
                "total": len(approvals),
            }
        )
    finally:
        db.close()
