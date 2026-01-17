"""API routes for advanced analytics and metrics."""
from __future__ import annotations

from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy import and_, desc, func

from models import SessionLocal
from models_extended import (
    AnalyticsMetric,
    PromptExecution,
    PromptVersion,
)

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/v1/analytics")


@analytics_bp.route("/overview", methods=["GET"])
def get_overview():
    """Get high-level analytics overview."""
    days = int(request.args.get("days", 7))
    start_date = datetime.utcnow() - timedelta(days=days)

    db = SessionLocal()
    try:
        # Total executions
        total_executions = (
            db.query(func.count(PromptExecution.id))
            .filter(PromptExecution.executed_at >= start_date)
            .scalar()
        )

        # Success rate
        successful = (
            db.query(func.count(PromptExecution.id))
            .filter(
                PromptExecution.executed_at >= start_date,
                PromptExecution.success == True,
            )
            .scalar()
        )
        success_rate = (successful / total_executions * 100) if total_executions > 0 else 0

        # Total tokens used
        total_tokens = (
            db.query(func.sum(PromptExecution.tokens_used))
            .filter(PromptExecution.executed_at >= start_date)
            .scalar()
        ) or 0

        # Average duration
        avg_duration = (
            db.query(func.avg(PromptExecution.duration_ms))
            .filter(PromptExecution.executed_at >= start_date)
            .scalar()
        ) or 0

        # Average rating
        avg_rating = (
            db.query(func.avg(PromptExecution.user_rating))
            .filter(
                PromptExecution.executed_at >= start_date,
                PromptExecution.user_rating.isnot(None),
            )
            .scalar()
        ) or 0

        # Top prompts by usage
        top_prompts = (
            db.query(
                PromptExecution.prompt_version_id,
                func.count(PromptExecution.id).label("count"),
            )
            .filter(PromptExecution.executed_at >= start_date)
            .group_by(PromptExecution.prompt_version_id)
            .order_by(desc("count"))
            .limit(10)
            .all()
        )

        return jsonify(
            {
                "period_days": days,
                "total_executions": total_executions,
                "success_rate": round(success_rate, 2),
                "total_tokens": int(total_tokens),
                "avg_duration_ms": round(avg_duration, 2),
                "avg_rating": round(avg_rating, 2),
                "top_prompts": [
                    {"version_id": p[0], "executions": p[1]}
                    for p in top_prompts
                ],
            }
        )
    finally:
        db.close()


@analytics_bp.route("/usage", methods=["GET"])
def get_usage_stats():
    """Get detailed usage statistics."""
    days = int(request.args.get("days", 7))
    group_by = request.args.get("group_by", "day")  # hour, day, week
    start_date = datetime.utcnow() - timedelta(days=days)

    db = SessionLocal()
    try:
        # Group executions by time period
        if group_by == "hour":
            time_group = func.strftime("%Y-%m-%d %H:00", PromptExecution.executed_at)
        elif group_by == "week":
            time_group = func.strftime("%Y-W%W", PromptExecution.executed_at)
        else:  # day
            time_group = func.date(PromptExecution.executed_at)

        usage = (
            db.query(
                time_group.label("period"),
                func.count(PromptExecution.id).label("executions"),
                func.sum(PromptExecution.tokens_used).label("tokens"),
                func.avg(PromptExecution.duration_ms).label("avg_duration"),
            )
            .filter(PromptExecution.executed_at >= start_date)
            .group_by("period")
            .order_by("period")
            .all()
        )

        return jsonify(
            {
                "group_by": group_by,
                "period_days": days,
                "usage": [
                    {
                        "period": u[0],
                        "executions": u[1],
                        "tokens": int(u[2]) if u[2] else 0,
                        "avg_duration_ms": round(u[3], 2) if u[3] else 0,
                    }
                    for u in usage
                ],
            }
        )
    finally:
        db.close()


@analytics_bp.route("/costs", methods=["GET"])
def get_cost_analysis():
    """Calculate estimated costs based on token usage."""
    days = int(request.args.get("days", 7))
    start_date = datetime.utcnow() - timedelta(days=days)

    # Pricing (approximate, per 1M tokens)
    pricing = {
        "anthropic": {
            "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
            "claude-3-haiku": {"input": 0.25, "output": 1.25},
        },
        "openai": {
            "gpt-4o": {"input": 5.0, "output": 15.0},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        },
    }

    db = SessionLocal()
    try:
        # Get usage by provider and model
        usage_by_model = (
            db.query(
                PromptExecution.provider,
                PromptExecution.model,
                func.sum(PromptExecution.tokens_used).label("total_tokens"),
                func.count(PromptExecution.id).label("executions"),
            )
            .filter(PromptExecution.executed_at >= start_date)
            .group_by(PromptExecution.provider, PromptExecution.model)
            .all()
        )

        total_cost = 0
        breakdown = []

        for usage in usage_by_model:
            provider = usage[0]
            model = usage[1]
            tokens = usage[2] or 0
            executions = usage[3]

            # Estimate cost (simplified: using average of input/output rates)
            if provider in pricing and model in pricing[provider]:
                avg_rate = (
                    pricing[provider][model]["input"] + pricing[provider][model]["output"]
                ) / 2
                cost = (tokens / 1_000_000) * avg_rate
            else:
                cost = 0  # Unknown pricing

            total_cost += cost

            breakdown.append(
                {
                    "provider": provider,
                    "model": model,
                    "executions": executions,
                    "tokens": int(tokens),
                    "estimated_cost_usd": round(cost, 4),
                }
            )

        return jsonify(
            {
                "period_days": days,
                "total_estimated_cost_usd": round(total_cost, 4),
                "breakdown": breakdown,
                "note": "Costs are estimates based on approximate pricing",
            }
        )
    finally:
        db.close()


@analytics_bp.route("/performance", methods=["GET"])
def get_performance_metrics():
    """Get performance metrics by provider/model."""
    days = int(request.args.get("days", 7))
    start_date = datetime.utcnow() - timedelta(days=days)

    db = SessionLocal()
    try:
        metrics = (
            db.query(
                PromptExecution.provider,
                PromptExecution.model,
                func.count(PromptExecution.id).label("executions"),
                func.avg(PromptExecution.duration_ms).label("avg_duration"),
                func.min(PromptExecution.duration_ms).label("min_duration"),
                func.max(PromptExecution.duration_ms).label("max_duration"),
                func.sum(func.case((PromptExecution.success == True, 1), else_=0)).label("successful"),
            )
            .filter(PromptExecution.executed_at >= start_date)
            .group_by(PromptExecution.provider, PromptExecution.model)
            .all()
        )

        return jsonify(
            {
                "period_days": days,
                "performance": [
                    {
                        "provider": m[0],
                        "model": m[1],
                        "executions": m[2],
                        "avg_duration_ms": round(m[3], 2) if m[3] else 0,
                        "min_duration_ms": m[4] or 0,
                        "max_duration_ms": m[5] or 0,
                        "success_rate": round((m[6] / m[2]) * 100, 2) if m[2] > 0 else 0,
                    }
                    for m in metrics
                ],
            }
        )
    finally:
        db.close()


@analytics_bp.route("/prompts/<int:prompt_id>/stats", methods=["GET"])
def get_prompt_stats(prompt_id: int):
    """Get detailed statistics for a specific prompt."""
    days = int(request.args.get("days", 30))
    start_date = datetime.utcnow() - timedelta(days=days)

    db = SessionLocal()
    try:
        # Get all versions of this prompt
        versions = (
            db.query(PromptVersion.id)
            .filter(PromptVersion.prompt_id == prompt_id)
            .all()
        )
        version_ids = [v[0] for v in versions]

        if not version_ids:
            return jsonify({"error": "No versions found"}), 404

        # Get executions for all versions
        executions = (
            db.query(PromptExecution)
            .filter(
                PromptExecution.prompt_version_id.in_(version_ids),
                PromptExecution.executed_at >= start_date,
            )
            .all()
        )

        if not executions:
            return jsonify(
                {
                    "prompt_id": prompt_id,
                    "period_days": days,
                    "total_executions": 0,
                }
            )

        total = len(executions)
        successful = sum(1 for e in executions if e.success)
        total_tokens = sum(e.tokens_used or 0 for e in executions)
        avg_duration = sum(e.duration_ms or 0 for e in executions) / total
        ratings = [e.user_rating for e in executions if e.user_rating]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0

        # Version breakdown
        version_stats = {}
        for exec in executions:
            vid = exec.prompt_version_id
            if vid not in version_stats:
                version_stats[vid] = {
                    "executions": 0,
                    "tokens": 0,
                    "successful": 0,
                }
            version_stats[vid]["executions"] += 1
            version_stats[vid]["tokens"] += exec.tokens_used or 0
            if exec.success:
                version_stats[vid]["successful"] += 1

        return jsonify(
            {
                "prompt_id": prompt_id,
                "period_days": days,
                "total_executions": total,
                "success_rate": round(successful / total * 100, 2),
                "total_tokens": int(total_tokens),
                "avg_duration_ms": round(avg_duration, 2),
                "avg_rating": round(avg_rating, 2),
                "rating_count": len(ratings),
                "version_breakdown": [
                    {
                        "version_id": vid,
                        **stats,
                        "success_rate": round(stats["successful"] / stats["executions"] * 100, 2),
                    }
                    for vid, stats in version_stats.items()
                ],
            }
        )
    finally:
        db.close()


@analytics_bp.route("/top-prompts", methods=["GET"])
def get_top_prompts():
    """Get top performing prompts by various metrics."""
    days = int(request.args.get("days", 7))
    metric = request.args.get("metric", "usage")  # usage, rating, performance
    limit = int(request.args.get("limit", 10))
    start_date = datetime.utcnow() - timedelta(days=days)

    db = SessionLocal()
    try:
        if metric == "rating":
            # Top rated prompts
            query = (
                db.query(
                    PromptExecution.prompt_version_id,
                    func.avg(PromptExecution.user_rating).label("avg_rating"),
                    func.count(PromptExecution.id).label("executions"),
                )
                .filter(
                    PromptExecution.executed_at >= start_date,
                    PromptExecution.user_rating.isnot(None),
                )
                .group_by(PromptExecution.prompt_version_id)
                .having(func.count(PromptExecution.id) >= 5)  # Min 5 ratings
                .order_by(desc("avg_rating"))
                .limit(limit)
            )

            results = [
                {
                    "version_id": r[0],
                    "avg_rating": round(r[1], 2),
                    "executions": r[2],
                }
                for r in query.all()
            ]

        elif metric == "performance":
            # Fastest prompts
            query = (
                db.query(
                    PromptExecution.prompt_version_id,
                    func.avg(PromptExecution.duration_ms).label("avg_duration"),
                    func.count(PromptExecution.id).label("executions"),
                )
                .filter(PromptExecution.executed_at >= start_date)
                .group_by(PromptExecution.prompt_version_id)
                .having(func.count(PromptExecution.id) >= 5)
                .order_by("avg_duration")
                .limit(limit)
            )

            results = [
                {
                    "version_id": r[0],
                    "avg_duration_ms": round(r[1], 2),
                    "executions": r[2],
                }
                for r in query.all()
            ]

        else:  # usage
            # Most used prompts
            query = (
                db.query(
                    PromptExecution.prompt_version_id,
                    func.count(PromptExecution.id).label("executions"),
                    func.sum(PromptExecution.tokens_used).label("total_tokens"),
                )
                .filter(PromptExecution.executed_at >= start_date)
                .group_by(PromptExecution.prompt_version_id)
                .order_by(desc("executions"))
                .limit(limit)
            )

            results = [
                {
                    "version_id": r[0],
                    "executions": r[1],
                    "total_tokens": int(r[2]) if r[2] else 0,
                }
                for r in query.all()
            ]

        return jsonify(
            {
                "metric": metric,
                "period_days": days,
                "limit": limit,
                "top_prompts": results,
            }
        )
    finally:
        db.close()


@analytics_bp.route("/trends", methods=["GET"])
def get_trends():
    """Get trending metrics over time."""
    days = int(request.args.get("days", 30))
    start_date = datetime.utcnow() - timedelta(days=days)

    db = SessionLocal()
    try:
        # Daily trends
        trends = (
            db.query(
                func.date(PromptExecution.executed_at).label("date"),
                func.count(PromptExecution.id).label("executions"),
                func.sum(PromptExecution.tokens_used).label("tokens"),
                func.avg(PromptExecution.duration_ms).label("avg_duration"),
                func.sum(func.case((PromptExecution.success == True, 1), else_=0)).label("successful"),
            )
            .filter(PromptExecution.executed_at >= start_date)
            .group_by("date")
            .order_by("date")
            .all()
        )

        return jsonify(
            {
                "period_days": days,
                "trends": [
                    {
                        "date": str(t[0]),
                        "executions": t[1],
                        "tokens": int(t[2]) if t[2] else 0,
                        "avg_duration_ms": round(t[3], 2) if t[3] else 0,
                        "success_rate": round((t[4] / t[1]) * 100, 2) if t[1] > 0 else 0,
                    }
                    for t in trends
                ],
            }
        )
    finally:
        db.close()
