"""
API Authentication Module

Provides authentication and authorization for API endpoints using tokens.
Includes decorators for protecting API routes and validating token scopes.
"""

from functools import wraps
from flask import request, jsonify, g, current_app
from app.models import APIToken, APITokenScope, log_security_event, SecurityEventType, SecurityLogSeverity
from typing import List, Union


def get_token_from_request():
    """
    Extract API token from request.

    Checks for token in (priority order):
    1. Authorization header (Bearer token)
    2. X-API-Key header
    3. Query parameter 'api_key'

    Returns:
        str: Token string or None
    """
    # Check Authorization header (preferred)
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header[7:]  # Remove 'Bearer ' prefix

    # Check X-API-Key header
    api_key_header = request.headers.get('X-API-Key')
    if api_key_header:
        return api_key_header

    # Check query parameter (least secure, discouraged)
    query_token = request.args.get('api_key')
    if query_token:
        return query_token

    return None


def authenticate_token():
    """
    Authenticate API token from request.

    Returns:
        tuple: (APIToken object or None, error_message or None)
    """
    raw_token = get_token_from_request()

    if not raw_token:
        return None, "No API token provided"

    # Verify token
    token = APIToken.verify_token(raw_token)

    if not token:
        return None, "Invalid or expired API token"

    # Check IP whitelist if configured
    if not token.is_ip_allowed(request.remote_addr):
        log_security_event(
            event_type=SecurityEventType.UNAUTHORIZED_ACCESS,
            message=f"API token used from unauthorized IP: {request.remote_addr}",
            severity=SecurityLogSeverity.WARNING,
            user_id=token.user_id,
            ip_address=request.remote_addr,
            endpoint=request.path,
            http_method=request.method,
            details=f"Token: {token.token_prefix}..., Allowed IPs: {token.allowed_ips}"
        )
        return None, f"API token not authorized from IP {request.remote_addr}"

    # Token is valid
    return token, None


def api_token_required(f):
    """
    Decorator to require valid API token for endpoint.

    Usage:
        @api_token_required
        def my_api_endpoint():
            # Access token via g.api_token
            # Access user via g.api_token.user
            pass

    Returns:
        JSON error response if token is invalid
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token, error = authenticate_token()

        if error:
            log_security_event(
                event_type=SecurityEventType.UNAUTHORIZED_ACCESS,
                message=f"API authentication failed: {error}",
                severity=SecurityLogSeverity.WARNING,
                ip_address=request.remote_addr,
                endpoint=request.path,
                http_method=request.method
            )

            return jsonify({
                'error': {
                    'code': 401,
                    'message': 'Authentication required',
                    'details': error
                }
            }), 401

        # Store token in request context
        g.api_token = token
        g.current_user = token.user

        # Record token usage
        token.record_usage(request.remote_addr)

        # Call the actual endpoint
        return f(*args, **kwargs)

    return decorated_function


def api_scope_required(required_scopes: Union[APITokenScope, List[APITokenScope]], require_all=False):
    """
    Decorator to require specific API scopes.

    Args:
        required_scopes: Single scope or list of scopes
        require_all: If True, require ALL scopes. If False, require ANY scope (default)

    Usage:
        @api_token_required
        @api_scope_required(APITokenScope.WRITE_MARKET)
        def create_market_order():
            pass

        @api_token_required
        @api_scope_required([APITokenScope.READ_PROFILE, APITokenScope.READ_INVENTORY])
        def get_user_data():
            # Has at least one of the required scopes
            pass

        @api_token_required
        @api_scope_required([APITokenScope.ADMIN_READ, APITokenScope.ADMIN_WRITE], require_all=True)
        def admin_action():
            # Must have BOTH scopes
            pass
    """
    # Normalize to list
    if isinstance(required_scopes, APITokenScope):
        required_scopes = [required_scopes]

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Must be used after @api_token_required
            if not hasattr(g, 'api_token'):
                current_app.logger.error(
                    f"@api_scope_required used without @api_token_required on {f.__name__}"
                )
                return jsonify({
                    'error': {
                        'code': 500,
                        'message': 'Internal server error',
                        'details': 'Invalid decorator configuration'
                    }
                }), 500

            token = g.api_token

            # Check scopes
            if require_all:
                # Require ALL scopes
                missing_scopes = []
                for scope in required_scopes:
                    if not token.has_scope(scope):
                        missing_scopes.append(scope.value)

                if missing_scopes:
                    log_security_event(
                        event_type=SecurityEventType.PERMISSION_DENIED,
                        message=f"API token missing required scopes: {missing_scopes}",
                        severity=SecurityLogSeverity.WARNING,
                        user_id=token.user_id,
                        ip_address=request.remote_addr,
                        endpoint=request.path,
                        http_method=request.method,
                        details=f"Token: {token.token_prefix}..., Required: {[s.value for s in required_scopes]}, Has: {token.scopes}"
                    )

                    return jsonify({
                        'error': {
                            'code': 403,
                            'message': 'Insufficient permissions',
                            'details': f'Missing required scopes: {", ".join(missing_scopes)}'
                        }
                    }), 403
            else:
                # Require ANY scope
                has_scope = False
                for scope in required_scopes:
                    if token.has_scope(scope):
                        has_scope = True
                        break

                if not has_scope:
                    required_scope_values = [s.value for s in required_scopes]
                    log_security_event(
                        event_type=SecurityEventType.PERMISSION_DENIED,
                        message=f"API token lacks any of required scopes: {required_scope_values}",
                        severity=SecurityLogSeverity.WARNING,
                        user_id=token.user_id,
                        ip_address=request.remote_addr,
                        endpoint=request.path,
                        http_method=request.method,
                        details=f"Token: {token.token_prefix}..., Required (any): {required_scope_values}, Has: {token.scopes}"
                    )

                    return jsonify({
                        'error': {
                            'code': 403,
                            'message': 'Insufficient permissions',
                            'details': f'Requires one of: {", ".join(required_scope_values)}'
                        }
                    }), 403

            # Scopes validated, call endpoint
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def api_admin_required(f):
    """
    Decorator to require admin API access.

    Shorthand for @api_scope_required([APITokenScope.ADMIN_READ, APITokenScope.ADMIN_WRITE], require_all=True)

    Usage:
        @api_token_required
        @api_admin_required
        def admin_endpoint():
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Must be used after @api_token_required
        if not hasattr(g, 'api_token'):
            current_app.logger.error(
                f"@api_admin_required used without @api_token_required on {f.__name__}"
            )
            return jsonify({
                'error': {
                    'code': 500,
                    'message': 'Internal server error'
                }
            }), 500

        token = g.api_token

        # Check for admin scopes
        if not token.has_scope(APITokenScope.ADMIN_READ) or not token.has_scope(APITokenScope.ADMIN_WRITE):
            log_security_event(
                event_type=SecurityEventType.PERMISSION_DENIED,
                message=f"Non-admin API token attempted admin access",
                severity=SecurityLogSeverity.ERROR,
                user_id=token.user_id,
                ip_address=request.remote_addr,
                endpoint=request.path,
                http_method=request.method,
                details=f"Token: {token.token_prefix}..., Scopes: {token.scopes}"
            )

            return jsonify({
                'error': {
                    'code': 403,
                    'message': 'Admin access required',
                    'details': 'This endpoint requires admin permissions'
                }
            }), 403

        return f(*args, **kwargs)

    return decorated_function


# Helper functions for API responses

def api_success(data=None, message=None, status_code=200):
    """
    Create a standardized success API response.

    Args:
        data: Response data (optional)
        message: Success message (optional)
        status_code: HTTP status code (default: 200)

    Returns:
        tuple: (response, status_code)
    """
    response = {}

    if message:
        response['message'] = message

    if data is not None:
        response['data'] = data

    return jsonify(response), status_code


def api_error(message, code=400, details=None):
    """
    Create a standardized error API response.

    Args:
        message: Error message
        code: HTTP status code (default: 400)
        details: Additional error details (optional)

    Returns:
        tuple: (response, status_code)
    """
    response = {
        'error': {
            'code': code,
            'message': message
        }
    }

    if details:
        response['error']['details'] = details

    return jsonify(response), code


def api_paginated_response(items, page, per_page, total_count, message=None):
    """
    Create a paginated API response.

    Args:
        items: List of items for current page
        page: Current page number
        per_page: Items per page
        total_count: Total number of items
        message: Optional message

    Returns:
        tuple: (response, status_code)
    """
    total_pages = (total_count + per_page - 1) // per_page  # Ceiling division

    response = {
        'data': items,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_items': total_count,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        }
    }

    if message:
        response['message'] = message

    return jsonify(response), 200
