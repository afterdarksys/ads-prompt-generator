"""Extended database models for versioning, A/B testing, collaboration, and analytics."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from models import Base


class PromptVersion(Base):
    """Version history for prompts."""

    __tablename__ = "prompt_versions"

    id = Column(Integer, primary_key=True)
    prompt_id = Column(Integer, ForeignKey("saved_prompts.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    task = Column(Text, nullable=False)
    context = Column(Text, nullable=True)
    constraints = Column(Text, nullable=True)
    deliverables = Column(Text, nullable=True)
    tone = Column(String(255), nullable=True)
    generated_prompt = Column(Text, nullable=True)
    created_by = Column(String(255), nullable=True)  # Username/email
    created_at = Column(DateTime, default=datetime.utcnow)
    change_description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "prompt_id": self.prompt_id,
            "version_number": self.version_number,
            "name": self.name,
            "task": self.task,
            "context": self.context,
            "constraints": self.constraints,
            "deliverables": self.deliverables,
            "tone": self.tone,
            "generated_prompt": self.generated_prompt,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "change_description": self.change_description,
            "is_active": self.is_active,
        }


class ABTest(Base):
    """A/B test configuration for prompts."""

    __tablename__ = "ab_tests"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    variant_a_id = Column(Integer, ForeignKey("prompt_versions.id"), nullable=False)
    variant_b_id = Column(Integer, ForeignKey("prompt_versions.id"), nullable=False)
    traffic_split = Column(Float, default=0.5)  # 0.5 = 50/50 split
    is_active = Column(Boolean, default=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    winner_id = Column(Integer, ForeignKey("prompt_versions.id"), nullable=True)
    created_by = Column(String(255), nullable=True)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "variant_a_id": self.variant_a_id,
            "variant_b_id": self.variant_b_id,
            "traffic_split": self.traffic_split,
            "is_active": self.is_active,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "winner_id": self.winner_id,
            "created_by": self.created_by,
        }


class PromptExecution(Base):
    """Track prompt executions for analytics."""

    __tablename__ = "prompt_executions"

    id = Column(Integer, primary_key=True)
    prompt_version_id = Column(Integer, ForeignKey("prompt_versions.id"), nullable=True)
    ab_test_id = Column(Integer, ForeignKey("ab_tests.id"), nullable=True)
    user_id = Column(String(255), nullable=True)  # Username/email/session
    provider = Column(String(50), nullable=True)  # anthropic, openai, etc.
    model = Column(String(100), nullable=True)
    tokens_used = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    user_rating = Column(Integer, nullable=True)  # 1-5 stars
    user_feedback = Column(Text, nullable=True)
    executed_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "prompt_version_id": self.prompt_version_id,
            "ab_test_id": self.ab_test_id,
            "user_id": self.user_id,
            "provider": self.provider,
            "model": self.model,
            "tokens_used": self.tokens_used,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error_message": self.error_message,
            "user_rating": self.user_rating,
            "user_feedback": self.user_feedback,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
        }


class Team(Base):
    """Team for collaboration."""

    __tablename__ = "teams"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_active": self.is_active,
        }


class TeamMember(Base):
    """Team membership."""

    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    user_id = Column(String(255), nullable=False)  # Username/email
    role = Column(String(50), default="member")  # owner, admin, member, viewer
    joined_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "team_id": self.team_id,
            "user_id": self.user_id,
            "role": self.role,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
            "is_active": self.is_active,
        }


class PromptComment(Base):
    """Comments on prompts for collaboration."""

    __tablename__ = "prompt_comments"

    id = Column(Integer, primary_key=True)
    prompt_id = Column(Integer, ForeignKey("saved_prompts.id"), nullable=False)
    prompt_version_id = Column(Integer, ForeignKey("prompt_versions.id"), nullable=True)
    user_id = Column(String(255), nullable=False)
    comment = Column(Text, nullable=False)
    parent_comment_id = Column(Integer, ForeignKey("prompt_comments.id"), nullable=True)  # For threads
    is_resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "prompt_id": self.prompt_id,
            "prompt_version_id": self.prompt_version_id,
            "user_id": self.user_id,
            "comment": self.comment,
            "parent_comment_id": self.parent_comment_id,
            "is_resolved": self.is_resolved,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class PromptApproval(Base):
    """Approval workflow for prompts."""

    __tablename__ = "prompt_approvals"

    id = Column(Integer, primary_key=True)
    prompt_id = Column(Integer, ForeignKey("saved_prompts.id"), nullable=False)
    prompt_version_id = Column(Integer, ForeignKey("prompt_versions.id"), nullable=False)
    requested_by = Column(String(255), nullable=False)
    requested_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50), default="pending")  # pending, approved, rejected, cancelled
    approved_by = Column(String(255), nullable=True)
    approval_comment = Column(Text, nullable=True)
    approved_at = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "prompt_id": self.prompt_id,
            "prompt_version_id": self.prompt_version_id,
            "requested_by": self.requested_by,
            "requested_at": self.requested_at.isoformat() if self.requested_at else None,
            "status": self.status,
            "approved_by": self.approved_by,
            "approval_comment": self.approval_comment,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
        }


class AnalyticsMetric(Base):
    """Aggregated analytics metrics."""

    __tablename__ = "analytics_metrics"

    id = Column(Integer, primary_key=True)
    metric_type = Column(String(100), nullable=False)  # daily_usage, cost, performance, etc.
    metric_key = Column(String(255), nullable=False)  # User ID, prompt ID, provider, etc.
    metric_value = Column(Float, nullable=False)
    aggregation_period = Column(String(50), default="daily")  # hourly, daily, weekly, monthly
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    metadata = Column(Text, nullable=True)  # JSON for additional context

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "metric_type": self.metric_type,
            "metric_key": self.metric_key,
            "metric_value": self.metric_value,
            "aggregation_period": self.aggregation_period,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "metadata": self.metadata,
        }
