"""Production-ready Flask application with security, logging, and monitoring."""
from __future__ import annotations

import secrets
import uuid
from hashlib import sha256

from flask import Flask, g, jsonify, render_template, request
from flask_caching import Cache
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from prometheus_flask_exporter import PrometheusMetrics
from werkzeug.exceptions import HTTPException

from config import config
from errors import PromptGeneratorError, RateLimitError, ValidationError
from logging_config import get_logger, setup_logging
from prompt_gen.core import PromptRequest, PromptTarget, generate_prompt
from validation import validate_generate_request

# Setup logging
setup_logging()
log = get_logger(__name__)


def create_app() -> Flask:
    """Create and configure the Flask application.

    Returns:
        Configured Flask application instance
    """
    app = Flask(__name__)

    # Load configuration
    app.config.update(
        SECRET_KEY=config.SECRET_KEY,
        MAX_CONTENT_LENGTH=config.MAX_CONTENT_LENGTH,
        JSON_SORT_KEYS=False,
    )

    # Initialize extensions
    _setup_security(app)
    _setup_caching(app)
    _setup_rate_limiting(app)
    _setup_monitoring(app)
    _setup_error_handlers(app)
    _setup_request_handlers(app)
    _setup_routes(app)

    log.info(
        "application_started",
        env=config.ENV,
        debug=config.DEBUG,
        host=config.HOST,
        port=config.PORT,
    )

    return app


def _setup_security(app: Flask) -> None:
    """Configure security features.

    Args:
        app: Flask application instance
    """
    # CORS
    CORS(
        app,
        origins=config.CORS_ORIGINS,
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    # Security headers with Talisman
    if not config.DEBUG:
        Talisman(
            app,
            force_https=True,
            strict_transport_security=True,
            content_security_policy={
                "default-src": "'self'",
                "script-src": ["'self'", "'unsafe-inline'"],
                "style-src": ["'self'", "'unsafe-inline'"],
                "img-src": ["'self'", "data:"],
            },
            content_security_policy_nonce_in=["script-src"],
        )


def _setup_caching(app: Flask) -> None:
    """Configure caching.

    Args:
        app: Flask application instance
    """
    if config.CACHE_ENABLED:
        cache_config = {
            "CACHE_TYPE": "redis" if "redis" in config.REDIS_URL else "simple",
            "CACHE_DEFAULT_TIMEOUT": config.CACHE_TTL,
        }

        if "redis" in config.REDIS_URL:
            cache_config["CACHE_REDIS_URL"] = config.REDIS_URL

        cache = Cache(app, config=cache_config)
        app.extensions["cache"] = cache
        log.info("caching_enabled", cache_type=cache_config["CACHE_TYPE"])
    else:
        log.info("caching_disabled")


def _setup_rate_limiting(app: Flask) -> None:
    """Configure rate limiting.

    Args:
        app: Flask application instance
    """
    if config.RATE_LIMIT_ENABLED:
        limiter = Limiter(
            app=app,
            key_func=get_remote_address,
            default_limits=[f"{config.RATE_LIMIT_PER_MINUTE} per minute"],
            storage_uri=config.REDIS_URL if "redis" in config.REDIS_URL else "memory://",
        )
        app.extensions["limiter"] = limiter
        log.info("rate_limiting_enabled", limit=f"{config.RATE_LIMIT_PER_MINUTE}/min")
    else:
        log.info("rate_limiting_disabled")


def _setup_monitoring(app: Flask) -> None:
    """Configure monitoring and metrics.

    Args:
        app: Flask application instance
    """
    if config.METRICS_ENABLED:
        metrics = PrometheusMetrics(app, path="/metrics")

        # Custom metrics
        metrics.info("app_info", "Application info", version="1.0.0", env=config.ENV)

        log.info("metrics_enabled", path="/metrics")
    else:
        log.info("metrics_disabled")


def _setup_error_handlers(app: Flask) -> None:
    """Configure error handlers.

    Args:
        app: Flask application instance
    """

    @app.errorhandler(PromptGeneratorError)
    def handle_app_error(e: PromptGeneratorError):
        """Handle application-specific errors."""
        log.warning(
            "application_error",
            error=e.__class__.__name__,
            message=e.message,
            status_code=e.status_code,
            request_id=g.get("request_id"),
        )
        return jsonify({"error": e.message, "request_id": g.get("request_id")}), e.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(e: HTTPException):
        """Handle HTTP exceptions."""
        log.warning(
            "http_error",
            status_code=e.code,
            description=e.description,
            request_id=g.get("request_id"),
        )
        return jsonify({"error": e.description, "request_id": g.get("request_id")}), e.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(e: Exception):
        """Handle unexpected errors."""
        log.error(
            "unexpected_error",
            error=e.__class__.__name__,
            message=str(e),
            request_id=g.get("request_id"),
            exc_info=True,
        )
        return (
            jsonify(
                {
                    "error": "Internal server error",
                    "request_id": g.get("request_id"),
                }
            ),
            500,
        )


def _setup_request_handlers(app: Flask) -> None:
    """Configure request/response handlers.

    Args:
        app: Flask application instance
    """

    @app.before_request
    def before_request():
        """Execute before each request."""
        # Generate or extract request ID
        g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Log request
        log.info(
            "request_received",
            method=request.method,
            path=request.path,
            ip=request.remote_addr,
            request_id=g.request_id,
        )

    @app.after_request
    def after_request(response):
        """Execute after each request."""
        # Add request ID to response headers
        response.headers["X-Request-ID"] = g.request_id

        # Add additional security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Log response
        log.info(
            "request_completed",
            method=request.method,
            path=request.path,
            status_code=response.status_code,
            request_id=g.request_id,
        )

        return response


def _setup_routes(app: Flask) -> None:
    """Configure application routes.

    Args:
        app: Flask application instance
    """

    @app.get("/")
    def index():
        """Render the main web interface."""
        return render_template("index.html")

    @app.get("/health")
    def health():
        """Health check endpoint for load balancers.

        Returns:
            JSON response with health status
        """
        return jsonify({"status": "healthy", "version": "1.0.0"}), 200

    @app.get("/ready")
    def ready():
        """Readiness check endpoint for Kubernetes.

        Returns:
            JSON response with readiness status
        """
        # Check dependencies (Redis, etc.)
        checks = {"cache": True}

        if config.CACHE_ENABLED and "cache" in app.extensions:
            try:
                cache = app.extensions["cache"]
                cache.set("health_check", "ok", timeout=1)
                checks["cache"] = cache.get("health_check") == "ok"
            except Exception as e:
                log.error("cache_health_check_failed", error=str(e))
                checks["cache"] = False

        ready_status = all(checks.values())
        status_code = 200 if ready_status else 503

        return (
            jsonify(
                {
                    "status": "ready" if ready_status else "not_ready",
                    "checks": checks,
                }
            ),
            status_code,
        )

    @app.post("/api/v1/generate")
    def api_generate():
        """Generate a prompt based on user input.

        Returns:
            JSON response with generated prompt
        """
        # Get and validate request data
        try:
            payload = request.get_json(silent=False)
            if payload is None:
                raise ValidationError("Request body must be valid JSON")

            req_data = validate_generate_request(payload)
        except ValidationError as e:
            raise
        except Exception as e:
            log.error("request_parsing_failed", error=str(e), exc_info=True)
            raise ValidationError("Invalid request format") from e

        # Check cache if enabled
        cache_key = None
        if config.CACHE_ENABLED and "cache" in app.extensions:
            cache_key = _get_cache_key(req_data.model_dump())
            cache = app.extensions["cache"]
            cached_prompt = cache.get(cache_key)

            if cached_prompt:
                log.info("cache_hit", cache_key=cache_key, request_id=g.request_id)
                return jsonify({"prompt": cached_prompt, "cached": True})

        # Generate prompt
        try:
            target = PromptTarget.from_string(req_data.target)
            prompt = generate_prompt(
                PromptRequest(
                    target=target,
                    task=req_data.task,
                    context=req_data.context,
                    constraints=req_data.constraints,
                    deliverables=req_data.deliverables,
                    tone=req_data.tone,
                )
            )

            # Cache the result
            if cache_key and config.CACHE_ENABLED and "cache" in app.extensions:
                cache.set(cache_key, prompt, timeout=config.CACHE_TTL)
                log.info("cache_set", cache_key=cache_key, request_id=g.request_id)

            log.info(
                "prompt_generated",
                target=req_data.target,
                task_length=len(req_data.task),
                request_id=g.request_id,
            )

            return jsonify({"prompt": prompt, "cached": False})

        except ValueError as e:
            raise ValidationError(str(e)) from e


def _get_cache_key(data: dict) -> str:
    """Generate cache key from request data.

    Args:
        data: Request data dictionary

    Returns:
        SHA256 hash of the request data
    """
    import json

    data_str = json.dumps(data, sort_keys=True)
    return f"prompt:{sha256(data_str.encode()).hexdigest()}"


if __name__ == "__main__":
    # Validate configuration
    try:
        config.validate()
    except ValueError as e:
        log.error("configuration_error", error=str(e))
        raise

    # Create and run app
    app = create_app()

    if config.DEBUG:
        log.warning("running_in_debug_mode", msg="DO NOT use in production!")
        app.run(host=config.HOST, port=config.PORT, debug=True)
    else:
        log.info("starting_production_server", msg="Use Gunicorn for production deployment")
        # In production, this should not be called - use Gunicorn instead
        app.run(host=config.HOST, port=config.PORT, debug=False)
