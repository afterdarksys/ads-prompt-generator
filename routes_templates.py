"""API routes for prompt templates."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from templates_library import (
    get_all_categories,
    get_all_tags,
    get_all_templates,
    get_template_by_id,
    get_templates_by_category,
    get_templates_by_difficulty,
    get_templates_by_tag,
    search_templates,
)

templates_bp = Blueprint("templates", __name__, url_prefix="/api/v1/templates")


@templates_bp.route("", methods=["GET"])
def list_templates():
    """List all templates with optional filtering."""
    category = request.args.get("category")
    tag = request.args.get("tag")
    difficulty = request.args.get("difficulty")
    search_query = request.args.get("search")

    if category:
        templates = get_templates_by_category(category)
    elif tag:
        templates = get_templates_by_tag(tag)
    elif difficulty:
        templates = get_templates_by_difficulty(difficulty)
    elif search_query:
        templates = search_templates(search_query)
    else:
        templates = get_all_templates()

    return jsonify(
        {
            "templates": [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "category": t.category,
                    "target": t.target,
                    "tags": t.tags,
                    "difficulty": t.difficulty,
                }
                for t in templates
            ],
            "total": len(templates),
        }
    )


@templates_bp.route("/<template_id>", methods=["GET"])
def get_template(template_id: str):
    """Get a specific template by ID."""
    template = get_template_by_id(template_id)

    if not template:
        return jsonify({"error": "Template not found"}), 404

    return jsonify(
        {
            "id": template.id,
            "name": template.name,
            "description": template.description,
            "category": template.category,
            "target": template.target,
            "task": template.task,
            "context": template.context,
            "constraints": template.constraints,
            "deliverables": template.deliverables,
            "tone": template.tone,
            "tags": template.tags,
            "difficulty": template.difficulty,
        }
    )


@templates_bp.route("/categories", methods=["GET"])
def list_categories():
    """List all available categories."""
    return jsonify({"categories": get_all_categories()})


@templates_bp.route("/tags", methods=["GET"])
def list_tags():
    """List all available tags."""
    return jsonify({"tags": get_all_tags()})


@templates_bp.route("/search", methods=["GET"])
def search():
    """Search templates by query."""
    query = request.args.get("q", "")

    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    results = search_templates(query)

    return jsonify(
        {
            "query": query,
            "results": [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "category": t.category,
                    "tags": t.tags,
                }
                for t in results
            ],
            "total": len(results),
        }
    )
