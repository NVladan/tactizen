"""
Error Handlers Module

Provides centralized error handling for the Flask application.
Handles HTTP errors, database errors, and unexpected exceptions with:
- Custom error pages for different error types
- JSON error responses for API requests
- Security logging integration
- Production-safe error messages
"""

from flask import render_template, request, jsonify, current_app
from flask_login import current_user
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import SQLAlchemyError


def wants_json_response():
    """
    Determine if the client wants a JSON response.

    Checks Accept header and request path to decide if JSON or HTML response.

    Returns:
        bool: True if JSON response is preferred
    """
    # Check if Accept header prefers JSON
    return (
        request.accept_mimetypes['application/json'] >=
        request.accept_mimetypes['text/html']
    ) or request.path.startswith('/api/')


def log_error_event(error_code, error_message, exception=None):
    """
    Log error event to security logging system.

    Args:
        error_code: HTTP status code
        error_message: Error message
        exception: Original exception object (if any)
    """
    try:
        from app.models import log_security_event, SecurityEventType, SecurityLogSeverity

        # Map error codes to severity levels
        severity_map = {
            400: SecurityLogSeverity.WARNING,  # Bad Request
            401: SecurityLogSeverity.WARNING,  # Unauthorized
            403: SecurityLogSeverity.WARNING,  # Forbidden
            404: SecurityLogSeverity.INFO,     # Not Found (common, low severity)
            429: SecurityLogSeverity.WARNING,  # Rate Limit
            500: SecurityLogSeverity.ERROR,    # Internal Server Error
            503: SecurityLogSeverity.ERROR,    # Service Unavailable
        }

        severity = severity_map.get(error_code, SecurityLogSeverity.ERROR)

        # Don't log 404s from bots/scanners (reduces noise)
        if error_code == 404:
            user_agent = request.headers.get('User-Agent', '').lower()
            bot_indicators = ['bot', 'crawler', 'spider', 'scraper']
            if any(indicator in user_agent for indicator in bot_indicators):
                return  # Skip logging

        # Determine event type
        event_type_map = {
            401: SecurityEventType.UNAUTHORIZED_ACCESS,
            403: SecurityEventType.PERMISSION_DENIED,
            429: SecurityEventType.RATE_LIMIT_EXCEEDED,
        }
        event_type = event_type_map.get(
            error_code,
            SecurityEventType.SYSTEM_ERROR
        )

        # Prepare exception details
        exception_details = None
        if exception and current_app.debug:
            exception_details = f"{type(exception).__name__}: {str(exception)}"

        # Log the event
        log_security_event(
            event_type=event_type,
            message=f"HTTP {error_code}: {error_message}",
            severity=severity,
            user_id=current_user.id if current_user.is_authenticated else None,
            username=current_user.username if current_user.is_authenticated else None,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', ''),
            http_method=request.method,
            endpoint=request.path,
            details=exception_details
        )

    except Exception as e:
        # Don't let logging errors crash the error handler
        current_app.logger.error(f"Error logging error event: {e}", exc_info=True)


def create_error_response(error_code, title, message, description=None):
    """
    Create an error response (HTML or JSON based on request).

    Args:
        error_code: HTTP status code
        title: Error title
        message: Short error message
        description: Optional detailed description

    Returns:
        Flask response object
    """
    if wants_json_response():
        # JSON response for API requests
        response = {
            'error': {
                'code': error_code,
                'title': title,
                'message': message,
            }
        }
        if description:
            response['error']['description'] = description

        return jsonify(response), error_code

    else:
        # HTML response for browser requests
        template_map = {
            401: 'errors/401.html',
            403: 'errors/403.html',
            404: 'errors/404.html',
            429: 'errors/429.html',
            500: 'errors/500.html',
        }

        template = template_map.get(error_code, 'errors/500.html')

        try:
            return render_template(
                template,
                error_code=error_code,
                title=title,
                message=message,
                description=description
            ), error_code
        except Exception as e:
            # Fallback if template rendering fails
            current_app.logger.error(f"Error rendering error template: {e}", exc_info=True)
            return f"<h1>{error_code} {title}</h1><p>{message}</p>", error_code


# ==================== HTTP Error Handlers ====================

def handle_400(e):
    """Handle 400 Bad Request errors."""
    log_error_event(400, "Bad Request", e)
    return create_error_response(
        400,
        "Bad Request",
        "The request could not be understood by the server.",
        "Please check your input and try again."
    )


def handle_401(e):
    """Handle 401 Unauthorized errors."""
    log_error_event(401, "Unauthorized", e)
    return create_error_response(
        401,
        "Authentication Required",
        "You need to be logged in to access this page.",
        "Please sign in with your wallet to continue."
    )


def handle_403(e):
    """Handle 403 Forbidden errors."""
    log_error_event(403, "Forbidden", e)
    return create_error_response(
        403,
        "Access Forbidden",
        "You don't have permission to access this resource.",
        "This page is restricted to authorized users only."
    )


def handle_404(e):
    """Handle 404 Not Found errors."""
    log_error_event(404, "Not Found", e)
    return create_error_response(
        404,
        "Page Not Found",
        "The page you are looking for does not exist.",
        "The page may have been moved, deleted, or you may have mistyped the URL."
    )


def handle_429(e):
    """Handle 429 Too Many Requests errors (rate limiting)."""
    log_error_event(429, "Rate Limit Exceeded", e)

    # Try to get rate limit details from the exception
    description = "Please wait a moment before trying again."
    if hasattr(e, 'description') and e.description:
        description = e.description

    return create_error_response(
        429,
        "Too Many Requests",
        "You've made too many requests in a short period of time.",
        description
    )


def handle_500(e):
    """Handle 500 Internal Server Error."""
    # Log with full exception details
    current_app.logger.error(
        f"Internal Server Error: {str(e)}",
        exc_info=True
    )

    log_error_event(500, "Internal Server Error", e)

    # In production, don't expose internal error details
    if current_app.debug:
        message = str(e)
    else:
        message = "An unexpected error occurred on our end."

    return create_error_response(
        500,
        "Internal Server Error",
        message,
        "We're sorry for the inconvenience. Our team has been notified."
    )


def handle_503(e):
    """Handle 503 Service Unavailable errors."""
    log_error_event(503, "Service Unavailable", e)
    return create_error_response(
        503,
        "Service Unavailable",
        "The service is temporarily unavailable.",
        "Please try again in a few moments."
    )


# ==================== Database Error Handlers ====================

def handle_database_error(e):
    """
    Handle SQLAlchemy database errors.

    Args:
        e: SQLAlchemy exception

    Returns:
        Flask response object
    """
    current_app.logger.error(
        f"Database error: {str(e)}",
        exc_info=True
    )

    log_error_event(500, "Database Error", e)

    # In production, don't expose database details
    if current_app.debug:
        message = f"Database error: {str(e)}"
    else:
        message = "A database error occurred. Please try again."

    return create_error_response(
        500,
        "Database Error",
        message,
        "If this problem persists, please contact support."
    )


# ==================== Generic Exception Handler ====================

def handle_generic_exception(e):
    """
    Handle any uncaught exceptions.

    This is the catch-all handler for unexpected errors.

    Args:
        e: Exception object

    Returns:
        Flask response object
    """
    # Log the full exception with traceback
    current_app.logger.error(
        f"Unhandled exception: {type(e).__name__}: {str(e)}",
        exc_info=True
    )

    log_error_event(500, f"Unhandled Exception: {type(e).__name__}", e)

    # In production, don't expose internal error details
    if current_app.debug:
        # In debug mode, re-raise to get the debugger
        raise
    else:
        # In production, show generic error page
        return create_error_response(
            500,
            "Internal Server Error",
            "An unexpected error occurred.",
            "Our team has been notified and is working to fix the issue."
        )


# ==================== Registration Function ====================

def register_error_handlers(app):
    """
    Register all error handlers with the Flask application.

    Args:
        app: Flask application instance
    """
    # HTTP error handlers
    app.register_error_handler(400, handle_400)
    app.register_error_handler(401, handle_401)
    app.register_error_handler(403, handle_403)
    app.register_error_handler(404, handle_404)
    app.register_error_handler(429, handle_429)
    app.register_error_handler(500, handle_500)
    app.register_error_handler(503, handle_503)

    # Database error handlers
    app.register_error_handler(SQLAlchemyError, handle_database_error)

    # Generic exception handler (catch-all)
    # Note: This should be registered last
    if not app.debug:
        # Only register catch-all in production to allow debugger in development
        app.register_error_handler(Exception, handle_generic_exception)

    app.logger.info("Error handlers registered successfully")
