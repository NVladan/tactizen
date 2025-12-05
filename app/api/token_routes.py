"""
API Token Management Routes

Provides web UI and API endpoints for users to manage their API tokens.
"""

from flask import render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app.api import bp
from app.extensions import db, limiter
from app.models import APIToken, APITokenScope
from app.api_auth import api_token_required, api_success, api_error
from datetime import datetime


# ==================== Web UI Routes ====================

@bp.route('/tokens')
@login_required
def list_tokens():
    """View all API tokens for current user (Web UI)."""
    if not current_app.config.get('API_ENABLED'):
        flash('API functionality is currently disabled.', 'info')
        return redirect(url_for('main.index'))

    tokens = APIToken.query.filter_by(user_id=current_user.id).order_by(APIToken.created_at.desc()).all()

    return render_template(
        'api/tokens.html',
        title='API Tokens',
        tokens=tokens,
        available_scopes=APITokenScope
    )


@bp.route('/tokens/create', methods=['GET', 'POST'])
@login_required
@limiter.limit("5 per hour")
def create_token():
    """Create a new API token (Web UI)."""
    if not current_app.config.get('API_ENABLED'):
        flash('API functionality is currently disabled.', 'info')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        expires_in_days = request.form.get('expires_in_days', type=int)

        # Get selected scopes
        selected_scopes = request.form.getlist('scopes')

        # Validate
        if not name:
            flash('Token name is required.', 'danger')
            return redirect(url_for('api.create_token'))

        if len(name) > 100:
            flash('Token name must be 100 characters or less.', 'danger')
            return redirect(url_for('api.create_token'))

        if not selected_scopes:
            flash('At least one scope is required.', 'danger')
            return redirect(url_for('api.create_token'))

        # Validate scopes
        valid_scope_values = [s.value for s in APITokenScope]
        for scope in selected_scopes:
            if scope not in valid_scope_values:
                flash(f'Invalid scope: {scope}', 'danger')
                return redirect(url_for('api.create_token'))

        # Prevent non-admins from creating admin tokens
        if not current_user.is_admin:
            admin_scopes = [APITokenScope.ADMIN_READ.value, APITokenScope.ADMIN_WRITE.value]
            if any(scope in admin_scopes for scope in selected_scopes):
                flash('You do not have permission to create admin tokens.', 'danger')
                return redirect(url_for('api.create_token'))

        # Create token
        try:
            token, raw_token = APIToken.create_token(
                user_id=current_user.id,
                name=name,
                scopes=selected_scopes,
                description=description if description else None,
                expires_in_days=expires_in_days if expires_in_days and expires_in_days > 0 else None
            )

            db.session.add(token)
            db.session.commit()

            # Show token ONCE (it won't be shown again)
            flash('API token created successfully! Copy it now - you won\'t see it again.', 'success')
            return render_template(
                'api/token_created.html',
                title='Token Created',
                token=token,
                raw_token=raw_token
            )

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating API token: {e}", exc_info=True)
            flash('An error occurred while creating the token. Please try again.', 'danger')
            return redirect(url_for('api.create_token'))

    # GET request - show form
    return render_template(
        'api/create_token.html',
        title='Create API Token',
        available_scopes=APITokenScope,
        is_admin=current_user.is_admin
    )


@bp.route('/tokens/<int:token_id>/revoke', methods=['POST'])
@login_required
def revoke_token(token_id):
    """Revoke an API token (Web UI)."""
    if not current_app.config.get('API_ENABLED'):
        flash('API functionality is currently disabled.', 'info')
        return redirect(url_for('main.index'))

    token = APIToken.query.filter_by(id=token_id, user_id=current_user.id).first()

    if not token:
        flash('Token not found.', 'danger')
        return redirect(url_for('api.list_tokens'))

    try:
        token.revoke()
        flash(f'Token "{token.name}" has been revoked.', 'success')
    except Exception as e:
        current_app.logger.error(f"Error revoking token: {e}", exc_info=True)
        flash('An error occurred while revoking the token.', 'danger')

    return redirect(url_for('api.list_tokens'))


@bp.route('/tokens/<int:token_id>/delete', methods=['POST'])
@login_required
def delete_token(token_id):
    """Delete an API token (Web UI)."""
    if not current_app.config.get('API_ENABLED'):
        flash('API functionality is currently disabled.', 'info')
        return redirect(url_for('main.index'))

    token = APIToken.query.filter_by(id=token_id, user_id=current_user.id).first()

    if not token:
        flash('Token not found.', 'danger')
        return redirect(url_for('api.list_tokens'))

    try:
        db.session.delete(token)
        db.session.commit()
        flash(f'Token "{token.name}" has been deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting token: {e}", exc_info=True)
        flash('An error occurred while deleting the token.', 'danger')

    return redirect(url_for('api.list_tokens'))


# ==================== API Endpoints for Token Management ====================

@bp.route('/v1/tokens', methods=['GET'])
@api_token_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_API_READ", "200 per hour"))
def api_list_tokens():
    """List all API tokens for authenticated user (API endpoint)."""
    if not current_app.config.get('API_ENABLED'):
        return api_error('API functionality is currently disabled', 503)

    from flask import g
    user_id = g.api_token.user_id

    tokens = APIToken.query.filter_by(user_id=user_id).order_by(APIToken.created_at.desc()).all()

    tokens_data = [token.to_dict() for token in tokens]

    return api_success(tokens_data)


@bp.route('/v1/tokens/<int:token_id>', methods=['GET'])
@api_token_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_API_READ", "200 per hour"))
def api_get_token(token_id):
    """Get details of a specific API token (API endpoint)."""
    if not current_app.config.get('API_ENABLED'):
        return api_error('API functionality is currently disabled', 503)

    from flask import g
    user_id = g.api_token.user_id

    token = APIToken.query.filter_by(id=token_id, user_id=user_id).first()

    if not token:
        return api_error('Token not found', 404)

    return api_success(token.to_dict())


@bp.route('/v1/tokens/<int:token_id>/revoke', methods=['POST'])
@api_token_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_API_WRITE", "50 per hour"))
def api_revoke_token(token_id):
    """Revoke an API token (API endpoint)."""
    if not current_app.config.get('API_ENABLED'):
        return api_error('API functionality is currently disabled', 503)

    from flask import g
    user_id = g.api_token.user_id

    token = APIToken.query.filter_by(id=token_id, user_id=user_id).first()

    if not token:
        return api_error('Token not found', 404)

    # Can't revoke the token being used for the request
    if token.id == g.api_token.id:
        return api_error('Cannot revoke the token being used for this request', 400)

    try:
        token.revoke()
        return api_success(message=f'Token "{token.name}" has been revoked')
    except Exception as e:
        current_app.logger.error(f"Error revoking token via API: {e}", exc_info=True)
        return api_error('An error occurred while revoking the token', 500)
