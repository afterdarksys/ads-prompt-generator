from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from prompt_gen.core import PromptRequest, PromptTarget, generate_prompt


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/api/generate")
    def api_generate():
        payload = request.get_json(silent=True) or {}

        target_raw = (payload.get("target") or "chatgpt").strip()
        task = (payload.get("task") or "").strip()
        context = (payload.get("context") or "").strip()
        constraints = (payload.get("constraints") or "").strip()
        deliverables = (payload.get("deliverables") or "").strip()
        tone = (payload.get("tone") or "").strip()

        if not task:
            return jsonify({"error": "task is required"}), 400

        try:
            target = PromptTarget.from_string(target_raw)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        prompt = generate_prompt(
            PromptRequest(
                target=target,
                task=task,
                context=context,
                constraints=constraints,
                deliverables=deliverables,
                tone=tone,
            )
        )

        return jsonify({"prompt": prompt})

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
