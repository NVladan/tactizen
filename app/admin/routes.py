# app/admin/routes.py
"""
Admin routes for managing soft-deleted records.

SECURITY NOTE: In production, add proper authentication/authorization
to ensure only admins can access these routes. Consider using Flask-Login
with an admin role check decorator.
"""

from flask import render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from decimal import Decimal
from app.admin import bp
from app.extensions import db
from app.models import User, Country, Region, Resource, RegionalResource, ActivityLog, ActivityType, SecurityLog, SecurityEventType, SecurityLogSeverity
from app.cache_utils import (invalidate_country_cache, invalidate_resource_cache,
                             invalidate_all_caches, get_cache_stats, warm_cache)
from app.activity_tracker import get_user_stats, get_online_users


# --- Helper decorator for admin-only access ---
def admin_required(f):
    """
    Decorator to restrict access to admin users only.
    Checks if current user has is_admin flag set to True.
    """
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('main.index'))

        # Check if user is admin
        if not current_user.is_admin:
            current_app.logger.warning(f"Non-admin user {current_user.id} attempted to access admin route")
            abort(403)

        return f(*args, **kwargs)
    return decorated_function


# --- Dashboard Route ---
@bp.route('/')
@login_required
@admin_required
def index():
    """Admin dashboard showing counts of deleted records."""
    deleted_users_count = db.session.query(User).filter_by(is_deleted=True).count()
    deleted_countries_count = db.session.query(Country).filter_by(is_deleted=True).count()
    deleted_regions_count = db.session.query(Region).filter_by(is_deleted=True).count()
    deleted_resources_count = db.session.query(Resource).filter_by(is_deleted=True).count()

    return render_template('admin/index.html',
                         title='Admin Dashboard',
                         deleted_users_count=deleted_users_count,
                         deleted_countries_count=deleted_countries_count,
                         deleted_regions_count=deleted_regions_count,
                         deleted_resources_count=deleted_resources_count)


# --- Deleted Users ---
@bp.route('/deleted-users')
@login_required
@admin_required
def deleted_users():
    """View all soft-deleted users."""
    page = request.args.get('page', 1, type=int)
    per_page = 25

    pagination = db.paginate(
        db.select(User).filter_by(is_deleted=True).order_by(User.deleted_at.desc()),
        page=page,
        per_page=per_page,
        error_out=False
    )

    return render_template('admin/deleted_users.html',
                         title='Deleted Users',
                         users=pagination.items,
                         pagination=pagination)


@bp.route('/restore-user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def restore_user(user_id):
    """Restore a soft-deleted user."""
    user = db.session.get(User, user_id)

    if not user:
        abort(404)

    if not user.is_deleted:
        flash(f'User {user.username} is not deleted.', 'info')
        return redirect(url_for('admin.deleted_users'))

    try:
        user.restore()
        db.session.commit()
        current_app.logger.info(f"User {user.id} ({user.username}) restored by admin {current_user.id}")
        flash(f'User {user.username} has been restored successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error restoring user {user_id}: {e}", exc_info=True)
        flash('Error restoring user. Please try again.', 'danger')

    return redirect(url_for('admin.deleted_users'))


# --- Deleted Countries ---
@bp.route('/deleted-countries')
@login_required
@admin_required
def deleted_countries():
    """View all soft-deleted countries."""
    countries = db.session.scalars(
        db.select(Country).filter_by(is_deleted=True).order_by(Country.deleted_at.desc())
    ).all()

    return render_template('admin/deleted_countries.html',
                         title='Deleted Countries',
                         countries=countries)


@bp.route('/restore-country/<int:country_id>', methods=['POST'])
@login_required
@admin_required
def restore_country(country_id):
    """Restore a soft-deleted country."""
    country = db.session.get(Country, country_id)

    if not country:
        abort(404)

    if not country.is_deleted:
        flash(f'Country {country.name} is not deleted.', 'info')
        return redirect(url_for('admin.deleted_countries'))

    try:
        country.restore()
        db.session.commit()
        # Invalidate country cache
        invalidate_country_cache(country_id)
        current_app.logger.info(f"Country {country.id} ({country.name}) restored by admin {current_user.id}")
        flash(f'Country {country.name} has been restored successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error restoring country {country_id}: {e}", exc_info=True)
        flash('Error restoring country. Please try again.', 'danger')

    return redirect(url_for('admin.deleted_countries'))


# --- Deleted Regions ---
@bp.route('/deleted-regions')
@login_required
@admin_required
def deleted_regions():
    """View all soft-deleted regions."""
    regions = db.session.scalars(
        db.select(Region).filter_by(is_deleted=True).order_by(Region.deleted_at.desc())
    ).all()

    return render_template('admin/deleted_regions.html',
                         title='Deleted Regions',
                         regions=regions)


@bp.route('/restore-region/<int:region_id>', methods=['POST'])
@login_required
@admin_required
def restore_region(region_id):
    """Restore a soft-deleted region."""
    region = db.session.get(Region, region_id)

    if not region:
        abort(404)

    if not region.is_deleted:
        flash(f'Region {region.name} is not deleted.', 'info')
        return redirect(url_for('admin.deleted_regions'))

    try:
        region.restore()
        db.session.commit()
        current_app.logger.info(f"Region {region.id} ({region.name}) restored by admin {current_user.id}")
        flash(f'Region {region.name} has been restored successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error restoring region {region_id}: {e}", exc_info=True)
        flash('Error restoring region. Please try again.', 'danger')

    return redirect(url_for('admin.deleted_regions'))


# --- Deleted Resources ---
@bp.route('/deleted-resources')
@login_required
@admin_required
def deleted_resources():
    """View all soft-deleted resources."""
    resources = db.session.scalars(
        db.select(Resource).filter_by(is_deleted=True).order_by(Resource.deleted_at.desc())
    ).all()

    return render_template('admin/deleted_resources.html',
                         title='Deleted Resources',
                         resources=resources)


@bp.route('/restore-resource/<int:resource_id>', methods=['POST'])
@login_required
@admin_required
def restore_resource(resource_id):
    """Restore a soft-deleted resource."""
    resource = db.session.get(Resource, resource_id)

    if not resource:
        abort(404)

    if not resource.is_deleted:
        flash(f'Resource {resource.name} is not deleted.', 'info')
        return redirect(url_for('admin.deleted_resources'))

    try:
        resource.restore()
        db.session.commit()
        # Invalidate resource cache
        invalidate_resource_cache(resource_id)
        current_app.logger.info(f"Resource {resource.id} ({resource.name}) restored by admin {current_user.id}")
        flash(f'Resource {resource.name} has been restored successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error restoring resource {resource_id}: {e}", exc_info=True)
        flash('Error restoring resource. Please try again.', 'danger')

    return redirect(url_for('admin.deleted_resources'))


# --- Cache Management ---
@bp.route('/cache')
@login_required
@admin_required
def cache_management():
    """View cache statistics and management options."""
    stats = get_cache_stats()

    return render_template('admin/cache.html',
                         title='Cache Management',
                         stats=stats)


@bp.route('/cache/clear', methods=['POST'])
@login_required
@admin_required
def clear_cache():
    """Clear all caches."""
    try:
        invalidate_all_caches()
        current_app.logger.warning(f"All caches cleared by admin {current_user.id}")
        flash('All caches have been cleared successfully.', 'success')
    except Exception as e:
        current_app.logger.error(f"Error clearing caches: {e}", exc_info=True)
        flash('Error clearing caches. Please try again.', 'danger')

    return redirect(url_for('admin.cache_management'))


@bp.route('/cache/warm', methods=['POST'])
@login_required
@admin_required
def warm_cache_route():
    """Pre-populate cache with frequently accessed data."""
    try:
        warm_cache()
        current_app.logger.info(f"Cache warming triggered by admin {current_user.id}")
        flash('Cache warming completed successfully.', 'success')
    except Exception as e:
        current_app.logger.error(f"Error warming cache: {e}", exc_info=True)
        flash('Error during cache warming. Please try again.', 'danger')

    return redirect(url_for('admin.cache_management'))


# --- Activity Tracking ---
@bp.route('/activity')
@login_required
@admin_required
def activity_dashboard():
    """Activity tracking dashboard with statistics."""
    # Get online users
    online_users = get_online_users(threshold_minutes=5)

    # Get activity statistics for past 24 hours
    past_24h = datetime.utcnow() - timedelta(hours=24)

    # Count recent activities by type
    activity_stats = db.session.query(
        ActivityLog.activity_type,
        func.count(ActivityLog.id).label('count')
    ).filter(ActivityLog.created_at >= past_24h).group_by(ActivityLog.activity_type).all()

    # Get total counts
    total_users = db.session.query(func.count(User.id)).filter_by(is_deleted=False).scalar()
    total_logins_24h = db.session.query(func.count(ActivityLog.id)).filter(
        ActivityLog.activity_type == ActivityType.LOGIN,
        ActivityLog.created_at >= past_24h
    ).scalar()

    # Get most active users (past 7 days)
    past_7d = datetime.utcnow() - timedelta(days=7)
    most_active = db.session.query(
        User.id,
        User.username,
        func.count(ActivityLog.id).label('activity_count')
    ).join(ActivityLog).filter(
        ActivityLog.created_at >= past_7d
    ).group_by(User.id).order_by(desc('activity_count')).limit(10).all()

    return render_template('admin/activity_dashboard.html',
                         title='Activity Dashboard',
                         online_users=online_users,
                         online_count=len(online_users),
                         total_users=total_users,
                         total_logins_24h=total_logins_24h,
                         activity_stats=activity_stats,
                         most_active=most_active)


@bp.route('/activity/logs')
@login_required
@admin_required
def activity_logs():
    """View recent activity logs."""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    activity_type_filter = request.args.get('type', None)

    # Build query
    query = db.select(ActivityLog).order_by(ActivityLog.created_at.desc())

    if activity_type_filter:
        query = query.filter_by(activity_type=ActivityType(activity_type_filter))

    # Paginate
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)

    return render_template('admin/activity_logs.html',
                         title='Activity Logs',
                         logs=pagination.items,
                         pagination=pagination,
                         activity_types=ActivityType,
                         selected_type=activity_type_filter)


@bp.route('/activity/user/<int:user_id>')
@login_required
@admin_required
def user_activity(user_id):
    """View activity for a specific user."""
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    # Get user stats
    stats = get_user_stats(user_id)

    # Get detailed activity log for this user
    page = request.args.get('page', 1, type=int)
    per_page = 25

    pagination = db.paginate(
        db.select(ActivityLog).filter_by(user_id=user_id).order_by(ActivityLog.created_at.desc()),
        page=page,
        per_page=per_page,
        error_out=False
    )

    return render_template('admin/user_activity.html',
                         title=f'Activity - {user.username or user.wallet_address[:10]}',
                         user=user,
                         stats=stats,
                         logs=pagination.items,
                         pagination=pagination)


# --- Player Management ---
@bp.route('/players')
@login_required
@admin_required
def players():
    """Manage players - search, filter, view details."""
    page = request.args.get('page', 1, type=int)
    per_page = 25
    search = request.args.get('search', '', type=str)
    filter_type = request.args.get('filter', 'all', type=str)

    # Build query
    query = db.select(User).filter_by(is_deleted=False)

    # Apply search filter
    if search:
        search_term = f'%{search}%'
        query = query.where(
            (User.username.ilike(search_term)) |
            (User.wallet_address.ilike(search_term))
        )

    # Apply additional filters
    if filter_type == 'admin':
        query = query.where(User.is_admin == True)
    elif filter_type == 'active':
        recent = datetime.utcnow() - timedelta(days=7)
        query = query.where(User.last_seen >= recent)
    elif filter_type == 'inactive':
        old = datetime.utcnow() - timedelta(days=30)
        query = query.where((User.last_seen < old) | (User.last_seen == None))

    # Order by last seen (MySQL compatible - nulls last)
    query = query.order_by(User.last_seen.is_(None), User.last_seen.desc())

    # Paginate
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)

    # Get all resources for grant form
    resources = db.session.scalars(
        db.select(Resource).filter_by(is_deleted=False).order_by(Resource.name)
    ).all()

    return render_template('admin/players.html',
                         title='Player Management',
                         players=pagination.items,
                         pagination=pagination,
                         search=search,
                         filter_type=filter_type,
                         resources=resources)


@bp.route('/player/<int:user_id>/grant-resource', methods=['POST'])
@login_required
@admin_required
def grant_resource(user_id):
    """Grant resources to a player."""
    user = db.session.get(User, user_id)
    if not user or user.is_deleted:
        abort(404)

    resource_id = request.form.get('resource_id', type=int)
    quantity = request.form.get('quantity', type=int)

    if not resource_id or not quantity or quantity <= 0:
        flash('Invalid resource or quantity.', 'danger')
        return redirect(url_for('admin.players'))

    resource = db.session.get(Resource, resource_id)
    if not resource or resource.is_deleted:
        flash('Resource not found.', 'danger')
        return redirect(url_for('admin.players'))

    try:
        # Add to player inventory (respects storage limit with partial acquisition)
        quantity_added, remaining = user.add_to_inventory(resource_id, quantity)
        db.session.commit()

        current_app.logger.info(
            f"Admin {current_user.id} granted {quantity_added} {resource.name} to user {user.id} ({user.username})"
        )

        if quantity_added < quantity:
            flash(f'Partially granted {quantity_added}/{quantity} {resource.name} to {user.username or user.wallet_address[:10]}. Storage limit reached ({user.get_total_inventory_count()}/{user.USER_STORAGE_LIMIT}).', 'warning')
        else:
            flash(f'Successfully granted {quantity_added} {resource.name} to {user.username or user.wallet_address[:10]}.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error granting resource: {e}", exc_info=True)
        flash('Error granting resource. Please try again.', 'danger')

    return redirect(url_for('admin.players'))


@bp.route('/player/<int:user_id>/grant-money', methods=['POST'])
@login_required
@admin_required
def grant_money(user_id):
    """Grant gold to a player."""
    user = db.session.get(User, user_id)
    if not user or user.is_deleted:
        abort(404)

    amount = request.form.get('amount', type=float)

    if not amount or amount <= 0:
        flash('Invalid amount.', 'danger')
        return redirect(url_for('admin.players'))

    try:
        from app.services.currency_service import CurrencyService
        success, message, _ = CurrencyService.add_gold(
            user.id, Decimal(str(amount)), f'Admin grant by user {current_user.id}'
        )
        if not success:
            flash(f'Error granting gold: {message}', 'danger')
            return redirect(url_for('admin.players'))

        db.session.commit()

        current_app.logger.info(
            f"Admin {current_user.id} granted {amount} gold to user {user.id} ({user.username})"
        )
        flash(f'Successfully granted {amount} gold to {user.username or user.wallet_address[:10]}.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error granting gold: {e}", exc_info=True)
        flash('Error granting gold. Please try again.', 'danger')

    return redirect(url_for('admin.players'))


@bp.route('/player/<int:user_id>/grant-free-nft', methods=['POST'])
@login_required
@admin_required
def grant_free_nft(user_id):
    """Grant free NFT mints to a player."""
    user = db.session.get(User, user_id)
    if not user or user.is_deleted:
        abort(404)

    amount = request.form.get('amount', type=int)

    if not amount or amount <= 0:
        flash('Invalid amount.', 'danger')
        return redirect(url_for('admin.players'))

    if amount > 100:
        flash('Cannot grant more than 100 free NFT mints at once.', 'danger')
        return redirect(url_for('admin.players'))

    try:
        user.free_nft_mints += amount
        db.session.commit()

        current_app.logger.info(
            f"Admin {current_user.id} granted {amount} free NFT mints to user {user.id} ({user.username})"
        )
        flash(f'Successfully granted {amount} free NFT mint{"s" if amount > 1 else ""} to {user.username or user.wallet_address[:10]}. They now have {user.free_nft_mints} total.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error granting free NFT mints: {e}", exc_info=True)
        flash('Error granting free NFT mints. Please try again.', 'danger')

    return redirect(url_for('admin.players'))


@bp.route('/player/<int:user_id>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def toggle_admin(user_id):
    """Toggle admin status for a player."""
    user = db.session.get(User, user_id)
    if not user or user.is_deleted:
        abort(404)

    # Prevent removing own admin status
    if user.id == current_user.id:
        flash('You cannot modify your own admin status.', 'warning')
        return redirect(url_for('admin.players'))

    try:
        user.is_admin = not user.is_admin
        db.session.commit()

        status = 'granted' if user.is_admin else 'revoked'
        current_app.logger.warning(
            f"Admin {current_user.id} {status} admin privileges for user {user.id} ({user.username})"
        )
        flash(f'Admin privileges {status} for {user.username or user.wallet_address[:10]}.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling admin: {e}", exc_info=True)
        flash('Error modifying admin status. Please try again.', 'danger')

    return redirect(url_for('admin.players'))


@bp.route('/player/<int:user_id>/ban', methods=['POST'])
@login_required
@admin_required
def ban_player(user_id):
    """Ban a player (permanently or temporarily)."""
    user = db.session.get(User, user_id)
    if not user or user.is_deleted:
        abort(404)

    # Prevent banning self or other admins
    if user.id == current_user.id:
        flash('You cannot ban yourself.', 'warning')
        return redirect(url_for('admin.players'))

    if user.is_admin:
        flash('You cannot ban other admins.', 'warning')
        return redirect(url_for('admin.players'))

    ban_type = request.form.get('ban_type', 'permanent')
    ban_reason = request.form.get('ban_reason', 'No reason provided')
    hours = request.form.get('hours', type=int)

    try:
        user.is_banned = True
        user.ban_reason = ban_reason
        user.banned_at = datetime.utcnow()
        user.banned_by_id = current_user.id

        if ban_type == 'temporary' and hours and hours > 0:
            user.banned_until = datetime.utcnow() + timedelta(hours=hours)
            ban_duration = f"{hours} hours"
        else:
            user.banned_until = None
            ban_duration = "permanently"

        db.session.commit()

        current_app.logger.warning(
            f"Admin {current_user.id} banned user {user.id} ({user.username}) {ban_duration}. Reason: {ban_reason}"
        )
        flash(f'{user.username or user.wallet_address[:10]} has been banned {ban_duration}.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error banning user: {e}", exc_info=True)
        flash('Error banning player. Please try again.', 'danger')

    return redirect(url_for('admin.players'))


@bp.route('/player/<int:user_id>/unban', methods=['POST'])
@login_required
@admin_required
def unban_player(user_id):
    """Unban a player."""
    user = db.session.get(User, user_id)
    if not user or user.is_deleted:
        abort(404)

    if not user.is_banned:
        flash('This player is not banned.', 'info')
        return redirect(url_for('admin.players'))

    try:
        user.is_banned = False
        user.ban_reason = None
        user.banned_until = None
        user.banned_at = None
        user.banned_by_id = None
        db.session.commit()

        current_app.logger.info(
            f"Admin {current_user.id} unbanned user {user.id} ({user.username})"
        )
        flash(f'{user.username or user.wallet_address[:10]} has been unbanned.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error unbanning user: {e}", exc_info=True)
        flash('Error unbanning player. Please try again.', 'danger')

    return redirect(url_for('admin.players'))


# ==================== Security Logs ====================

@bp.route('/security-logs')
@login_required
@admin_required
def security_logs():
    """View security logs with filtering."""
    page = request.args.get('page', 1, type=int)
    per_page = 50

    # Filtering parameters
    event_type = request.args.get('event_type')
    severity = request.args.get('severity')
    user_id = request.args.get('user_id', type=int)
    ip_address = request.args.get('ip_address')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    show_resolved = request.args.get('show_resolved', 'all')

    # Build query
    query = db.select(SecurityLog).order_by(desc(SecurityLog.created_at))

    # Apply filters
    if event_type:
        try:
            query = query.where(SecurityLog.event_type == SecurityEventType(event_type))
        except ValueError:
            pass

    if severity:
        try:
            query = query.where(SecurityLog.severity == SecurityLogSeverity(severity))
        except ValueError:
            pass

    if user_id:
        query = query.where(SecurityLog.user_id == user_id)

    if ip_address:
        query = query.where(SecurityLog.ip_address == ip_address)

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.where(SecurityLog.created_at >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.where(SecurityLog.created_at < end_dt)
        except ValueError:
            pass

    if show_resolved == 'unresolved':
        query = query.where(SecurityLog.resolved == False)
    elif show_resolved == 'resolved':
        query = query.where(SecurityLog.resolved == True)

    # Paginate
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    logs = pagination.items

    # Get statistics
    total_logs = db.session.scalar(db.select(func.count()).select_from(SecurityLog))
    unresolved_logs = db.session.scalar(
        db.select(func.count()).select_from(SecurityLog).where(SecurityLog.resolved == False)
    )

    # Get recent critical events
    critical_events = db.session.scalars(
        db.select(SecurityLog)
        .where(SecurityLog.severity == SecurityLogSeverity.CRITICAL)
        .where(SecurityLog.resolved == False)
        .order_by(desc(SecurityLog.created_at))
        .limit(10)
    ).all()

    return render_template('admin/security_logs.html',
                         title='Security Logs',
                         logs=logs,
                         pagination=pagination,
                         total_logs=total_logs,
                         unresolved_logs=unresolved_logs,
                         critical_events=critical_events,
                         event_types=SecurityEventType,
                         severity_levels=SecurityLogSeverity,
                         filters={
                             'event_type': event_type,
                             'severity': severity,
                             'user_id': user_id,
                             'ip_address': ip_address,
                             'start_date': start_date,
                             'end_date': end_date,
                             'show_resolved': show_resolved
                         })


@bp.route('/security-logs/<int:log_id>')
@login_required
@admin_required
def security_log_detail(log_id):
    """View detailed information about a specific security log."""
    log = db.session.get(SecurityLog, log_id)
    if not log:
        abort(404)

    # Get related logs (same IP address, same user, within 1 hour)
    related_logs = []
    if log.ip_address:
        related_logs = db.session.scalars(
            db.select(SecurityLog)
            .where(SecurityLog.ip_address == log.ip_address)
            .where(SecurityLog.id != log.id)
            .where(SecurityLog.created_at.between(
                log.created_at - timedelta(hours=1),
                log.created_at + timedelta(hours=1)
            ))
            .order_by(desc(SecurityLog.created_at))
            .limit(10)
        ).all()

    return render_template('admin/security_log_detail.html',
                         title=f'Security Log #{log_id}',
                         log=log,
                         related_logs=related_logs)


@bp.route('/security-logs/<int:log_id>/resolve', methods=['POST'])
@login_required
@admin_required
def resolve_security_log(log_id):
    """Mark a security log as resolved."""
    log = db.session.get(SecurityLog, log_id)
    if not log:
        abort(404)

    resolution_notes = request.form.get('resolution_notes', '').strip()

    try:
        log.resolved = True
        log.resolved_at = datetime.utcnow()
        log.resolved_by_id = current_user.id
        log.resolution_notes = resolution_notes
        db.session.commit()

        current_app.logger.info(f"Admin {current_user.id} resolved security log {log_id}")
        flash('Security log marked as resolved.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error resolving security log: {e}", exc_info=True)
        flash('Error resolving security log.', 'danger')

    return redirect(url_for('admin.security_log_detail', log_id=log_id))


@bp.route('/security-logs/<int:log_id>/unresolve', methods=['POST'])
@login_required
@admin_required
def unresolve_security_log(log_id):
    """Mark a security log as unresolved."""
    log = db.session.get(SecurityLog, log_id)
    if not log:
        abort(404)

    try:
        log.resolved = False
        log.resolved_at = None
        log.resolved_by_id = None
        log.resolution_notes = None
        db.session.commit()

        current_app.logger.info(f"Admin {current_user.id} marked security log {log_id} as unresolved")
        flash('Security log marked as unresolved.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error unresolving security log: {e}", exc_info=True)
        flash('Error unresolving security log.', 'danger')

    return redirect(url_for('admin.security_log_detail', log_id=log_id))


# --- Government Election Management ---

@bp.route('/government/elections')
@login_required
@admin_required
def government_elections():
    """View and manage all government elections."""
    from app.models import GovernmentElection, ElectionType, GovernmentElectionStatus

    # Get filter parameters
    election_type = request.args.get('type', '')
    status = request.args.get('status', '')
    country_id = request.args.get('country', type=int)

    # Build query
    query = db.select(GovernmentElection)

    if election_type:
        query = query.where(GovernmentElection.election_type == ElectionType[election_type.upper()])

    if status:
        query = query.where(GovernmentElection.status == GovernmentElectionStatus[status.upper()])

    if country_id:
        query = query.where(GovernmentElection.country_id == country_id)

    query = query.order_by(GovernmentElection.nominations_start.desc())

    elections = db.session.scalars(query).all()
    countries = db.session.scalars(db.select(Country)).all()

    return render_template('admin/government_elections.html',
                          title='Government Elections',
                          elections=elections,
                          countries=countries,
                          election_type_filter=election_type,
                          status_filter=status,
                          country_filter=country_id)


@bp.route('/government/elections/<int:election_id>')
@login_required
@admin_required
def government_election_detail(election_id):
    """View details of a specific government election."""
    from app.models import GovernmentElection, ElectionCandidate

    election = db.session.get(GovernmentElection, election_id)
    if not election:
        abort(404)

    # Get all candidates (including pending, rejected, withdrawn)
    candidates = db.session.scalars(
        db.select(ElectionCandidate)
        .where(ElectionCandidate.election_id == election_id)
        .order_by(ElectionCandidate.votes_received.desc())
    ).all()

    return render_template('admin/government_election_detail.html',
                          title=f'Election {election_id}',
                          election=election,
                          candidates=candidates)


@bp.route('/government/elections/<int:election_id>/cancel', methods=['POST'])
@login_required
@admin_required
def cancel_government_election(election_id):
    """Cancel a government election."""
    from app.models import GovernmentElection, GovernmentElectionStatus

    election = db.session.get(GovernmentElection, election_id)
    if not election:
        abort(404)

    if election.status == GovernmentElectionStatus.COMPLETED:
        flash('Cannot cancel a completed election.', 'danger')
        return redirect(url_for('admin.government_election_detail', election_id=election_id))

    try:
        election.status = GovernmentElectionStatus.CANCELLED
        db.session.commit()

        current_app.logger.info(f"Admin {current_user.id} cancelled election {election_id}")
        flash('Election cancelled successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error cancelling election: {e}", exc_info=True)
        flash('Error cancelling election.', 'danger')

    return redirect(url_for('admin.government_election_detail', election_id=election_id))


@bp.route('/government/elections/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_government_election():
    """Manually create a government election."""
    from app.models import GovernmentElection, ElectionType, GovernmentElectionStatus
    from app.scheduler import get_presidential_election_dates, get_congressional_election_dates

    if request.method == 'POST':
        country_id = request.form.get('country_id', type=int)
        election_type = request.form.get('election_type')

        if not country_id or not election_type:
            flash('Country and election type are required.', 'danger')
            return redirect(url_for('admin.create_government_election'))

        try:
            # Get dates for current month
            if election_type == 'PRESIDENTIAL':
                dates = get_presidential_election_dates()
                e_type = ElectionType.PRESIDENTIAL
                e_status = GovernmentElectionStatus.NOMINATIONS
            else:
                dates = get_congressional_election_dates()
                e_type = ElectionType.CONGRESSIONAL
                e_status = GovernmentElectionStatus.APPLICATIONS

            election = GovernmentElection(
                country_id=country_id,
                election_type=e_type,
                status=e_status,
                nominations_start=dates['nominations_start'],
                nominations_end=dates['nominations_end'],
                voting_start=dates['voting_start'],
                voting_end=dates['voting_end'],
                term_start=dates['term_start'],
                term_end=dates['term_end']
            )

            db.session.add(election)
            db.session.commit()

            current_app.logger.info(
                f"Admin {current_user.id} manually created {election_type} election "
                f"{election.id} for country {country_id}"
            )
            flash('Election created successfully.', 'success')
            return redirect(url_for('admin.government_election_detail', election_id=election.id))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating election: {e}", exc_info=True)
            flash('Error creating election.', 'danger')

    countries = db.session.scalars(db.select(Country)).all()
    return render_template('admin/create_government_election.html',
                          title='Create Government Election',
                          countries=countries)


@bp.route('/government/presidents')
@login_required
@admin_required
def government_presidents():
    """View all current and past presidents."""
    from app.models import CountryPresident

    current_presidents = db.session.scalars(
        db.select(CountryPresident)
        .where(CountryPresident.is_current == True)
        .order_by(CountryPresident.country_id)
    ).all()

    past_presidents = db.session.scalars(
        db.select(CountryPresident)
        .where(CountryPresident.is_current == False)
        .order_by(CountryPresident.term_start.desc())
        .limit(50)
    ).all()

    return render_template('admin/government_presidents.html',
                          title='Country Presidents',
                          current_presidents=current_presidents,
                          past_presidents=past_presidents)


@bp.route('/government/congress')
@login_required
@admin_required
def government_congress():
    """View all current congress members."""
    from app.models import CongressMember

    # Get filter parameters
    country_id = request.args.get('country', type=int)

    query = db.select(CongressMember).where(CongressMember.is_current == True)

    if country_id:
        query = query.where(CongressMember.country_id == country_id)

    query = query.order_by(CongressMember.country_id, CongressMember.final_rank)

    congress_members = db.session.scalars(query).all()
    countries = db.session.scalars(db.select(Country)).all()

    return render_template('admin/government_congress.html',
                          title='Congress Members',
                          congress_members=congress_members,
                          countries=countries,
                          country_filter=country_id)


# --- Game Updates Management ---

@bp.route('/updates')
@login_required
@admin_required
def game_updates():
    """View and manage all game updates."""
    from app.models import GameUpdate, UpdateCategory

    # Get filter parameters
    category = request.args.get('category', '')
    status = request.args.get('status', '')  # published, draft, deleted

    # Build query
    query = db.select(GameUpdate)

    if category:
        try:
            query = query.where(GameUpdate.category == UpdateCategory[category.upper()])
        except KeyError:
            pass

    if status == 'published':
        query = query.where(GameUpdate.is_published == True, GameUpdate.is_deleted == False)
    elif status == 'draft':
        query = query.where(GameUpdate.is_published == False, GameUpdate.is_deleted == False)
    elif status == 'deleted':
        query = query.where(GameUpdate.is_deleted == True)
    else:
        query = query.where(GameUpdate.is_deleted == False)

    query = query.order_by(GameUpdate.created_at.desc())

    updates = db.session.scalars(query).all()

    return render_template('admin/game_updates.html',
                          title='Game Updates',
                          updates=updates,
                          categories=UpdateCategory,
                          category_filter=category,
                          status_filter=status)


@bp.route('/updates/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_game_update():
    """Create a new game update."""
    from app.models import GameUpdate, UpdateCategory

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        summary = request.form.get('summary', '').strip() or None
        category = request.form.get('category', 'FEATURE')
        version = request.form.get('version', '').strip() or None
        is_pinned = request.form.get('is_pinned') == 'on'
        is_important = request.form.get('is_important') == 'on'
        publish_now = request.form.get('publish_now') == 'on'

        if not title or not content:
            flash('Title and content are required.', 'danger')
            return redirect(url_for('admin.create_game_update'))

        try:
            update = GameUpdate(
                title=title,
                content=content,
                summary=summary,
                category=UpdateCategory[category.upper()],
                version=version,
                author_id=current_user.id,
                is_pinned=is_pinned,
                is_important=is_important
            )

            if publish_now:
                update.publish()

            db.session.add(update)
            db.session.commit()

            current_app.logger.info(f"Admin {current_user.id} created game update {update.id}: {title}")
            flash('Game update created successfully.', 'success')
            return redirect(url_for('admin.game_updates'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating game update: {e}", exc_info=True)
            flash('Error creating game update.', 'danger')

    return render_template('admin/game_update_form.html',
                          title='Create Game Update',
                          update=None,
                          categories=UpdateCategory)


@bp.route('/updates/<int:update_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_game_update(update_id):
    """Edit an existing game update."""
    from app.models import GameUpdate, UpdateCategory

    update = db.session.get(GameUpdate, update_id)
    if not update:
        abort(404)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        summary = request.form.get('summary', '').strip() or None
        category = request.form.get('category', 'FEATURE')
        version = request.form.get('version', '').strip() or None
        is_pinned = request.form.get('is_pinned') == 'on'
        is_important = request.form.get('is_important') == 'on'

        if not title or not content:
            flash('Title and content are required.', 'danger')
            return redirect(url_for('admin.edit_game_update', update_id=update_id))

        try:
            update.title = title
            update.content = content
            update.summary = summary
            update.category = UpdateCategory[category.upper()]
            update.version = version
            update.is_pinned = is_pinned
            update.is_important = is_important

            db.session.commit()

            current_app.logger.info(f"Admin {current_user.id} edited game update {update.id}")
            flash('Game update saved successfully.', 'success')
            return redirect(url_for('admin.game_updates'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error editing game update: {e}", exc_info=True)
            flash('Error saving game update.', 'danger')

    return render_template('admin/game_update_form.html',
                          title='Edit Game Update',
                          update=update,
                          categories=UpdateCategory)


@bp.route('/updates/<int:update_id>/publish', methods=['POST'])
@login_required
@admin_required
def publish_game_update(update_id):
    """Publish a game update."""
    from app.models import GameUpdate

    update = db.session.get(GameUpdate, update_id)
    if not update:
        abort(404)

    try:
        update.publish()
        db.session.commit()

        current_app.logger.info(f"Admin {current_user.id} published game update {update.id}")
        flash('Game update published successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error publishing game update: {e}", exc_info=True)
        flash('Error publishing game update.', 'danger')

    return redirect(url_for('admin.game_updates'))


@bp.route('/updates/<int:update_id>/unpublish', methods=['POST'])
@login_required
@admin_required
def unpublish_game_update(update_id):
    """Unpublish a game update."""
    from app.models import GameUpdate

    update = db.session.get(GameUpdate, update_id)
    if not update:
        abort(404)

    try:
        update.unpublish()
        db.session.commit()

        current_app.logger.info(f"Admin {current_user.id} unpublished game update {update.id}")
        flash('Game update unpublished.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error unpublishing game update: {e}", exc_info=True)
        flash('Error unpublishing game update.', 'danger')

    return redirect(url_for('admin.game_updates'))


@bp.route('/updates/<int:update_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_game_update(update_id):
    """Soft delete a game update."""
    from app.models import GameUpdate

    update = db.session.get(GameUpdate, update_id)
    if not update:
        abort(404)

    try:
        update.soft_delete()
        db.session.commit()

        current_app.logger.info(f"Admin {current_user.id} deleted game update {update.id}")
        flash('Game update deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting game update: {e}", exc_info=True)
        flash('Error deleting game update.', 'danger')

    return redirect(url_for('admin.game_updates'))


@bp.route('/updates/<int:update_id>/restore', methods=['POST'])
@login_required
@admin_required
def restore_game_update(update_id):
    """Restore a soft-deleted game update."""
    from app.models import GameUpdate

    update = db.session.get(GameUpdate, update_id)
    if not update:
        abort(404)

    try:
        update.restore()
        db.session.commit()

        current_app.logger.info(f"Admin {current_user.id} restored game update {update.id}")
        flash('Game update restored.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error restoring game update: {e}", exc_info=True)
        flash('Error restoring game update.', 'danger')

    return redirect(url_for('admin.game_updates'))


# --- Regional Resources Management ---

@bp.route('/regional-resources')
@login_required
@admin_required
def regional_resources():
    """View and manage regional resources (natural deposits)."""
    from app.models import RegionalResource, Region

    # Get filter parameters
    country_id = request.args.get('country', type=int)
    resource_id = request.args.get('resource', type=int)
    show_depleted = request.args.get('show_depleted', 'no')

    # Build query
    query = db.select(RegionalResource).join(Region)

    if country_id:
        from app.models import country_regions
        query = query.join(
            country_regions,
            Region.id == country_regions.c.region_id
        ).filter(country_regions.c.country_id == country_id)

    if resource_id:
        query = query.filter(RegionalResource.resource_id == resource_id)

    if show_depleted != 'yes':
        query = query.filter(RegionalResource.amount > 0)

    query = query.order_by(Region.name, RegionalResource.resource_id)

    regional_resources_list = db.session.scalars(query).all()

    # Get countries and extractable resources for filters
    countries = db.session.scalars(
        db.select(Country).filter_by(is_deleted=False).order_by(Country.name)
    ).all()

    extractable_slugs = RegionalResource.get_extractable_resources()
    extractable_resources = db.session.scalars(
        db.select(Resource).filter(Resource.slug.in_(extractable_slugs)).order_by(Resource.name)
    ).all()

    # Get all regions for the add form
    regions = db.session.scalars(
        db.select(Region).filter_by(is_deleted=False).order_by(Region.name)
    ).all()

    return render_template('admin/regional_resources.html',
                          title='Regional Resources',
                          regional_resources=regional_resources_list,
                          countries=countries,
                          extractable_resources=extractable_resources,
                          regions=regions,
                          country_filter=country_id,
                          resource_filter=resource_id,
                          show_depleted=show_depleted)


@bp.route('/regional-resources/add', methods=['POST'])
@login_required
@admin_required
def add_regional_resource():
    """Add a resource deposit to a region."""
    from app.models import RegionalResource, Region

    region_id = request.form.get('region_id', type=int)
    resource_id = request.form.get('resource_id', type=int)
    amount = request.form.get('amount', type=int)

    if not region_id or not resource_id or not amount or amount <= 0:
        flash('Please fill all fields with valid values.', 'danger')
        return redirect(url_for('admin.regional_resources'))

    # Validate region exists
    region = db.session.get(Region, region_id)
    if not region:
        flash('Region not found.', 'danger')
        return redirect(url_for('admin.regional_resources'))

    # Validate resource is extractable
    resource = db.session.get(Resource, resource_id)
    if not resource:
        flash('Resource not found.', 'danger')
        return redirect(url_for('admin.regional_resources'))

    extractable_slugs = RegionalResource.get_extractable_resources()
    if resource.slug not in extractable_slugs:
        flash(f'{resource.name} is not an extractable resource.', 'danger')
        return redirect(url_for('admin.regional_resources'))

    try:
        # Check if resource already exists in this region
        existing = db.session.scalar(
            db.select(RegionalResource).filter_by(
                region_id=region_id,
                resource_id=resource_id
            )
        )

        if existing:
            # Add to existing deposit
            existing.replenish(amount)
            current_app.logger.info(
                f"Admin {current_user.id} added {amount} {resource.name} to existing deposit in {region.name} "
                f"(new total: {existing.amount})"
            )
            flash(f'Added {amount:,} {resource.name} to {region.name}. Total: {existing.amount:,}', 'success')
        else:
            # Create new deposit
            new_deposit = RegionalResource(
                region_id=region_id,
                resource_id=resource_id,
                amount=amount,
                initial_amount=amount,
                added_by_id=current_user.id
            )
            db.session.add(new_deposit)
            current_app.logger.info(
                f"Admin {current_user.id} created new deposit of {amount} {resource.name} in {region.name}"
            )
            flash(f'Added {amount:,} {resource.name} to {region.name}.', 'success')

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding regional resource: {e}", exc_info=True)
        flash('Error adding resource. Please try again.', 'danger')

    return redirect(url_for('admin.regional_resources'))


@bp.route('/regional-resources/<int:deposit_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_regional_resource(deposit_id):
    """Edit the amount of a resource deposit."""
    from app.models import RegionalResource

    deposit = db.session.get(RegionalResource, deposit_id)
    if not deposit:
        abort(404)

    new_amount = request.form.get('amount', type=int)
    if new_amount is None or new_amount < 0:
        flash('Invalid amount.', 'danger')
        return redirect(url_for('admin.regional_resources'))

    try:
        old_amount = deposit.amount
        deposit.amount = new_amount
        if new_amount > deposit.initial_amount:
            deposit.initial_amount = new_amount
        db.session.commit()

        current_app.logger.info(
            f"Admin {current_user.id} changed {deposit.resource.name} in {deposit.region.name} "
            f"from {old_amount} to {new_amount}"
        )
        flash(f'Updated {deposit.resource.name} in {deposit.region.name} to {new_amount:,}.', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error editing regional resource: {e}", exc_info=True)
        flash('Error updating resource. Please try again.', 'danger')

    return redirect(url_for('admin.regional_resources'))


@bp.route('/regional-resources/<int:deposit_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_regional_resource(deposit_id):
    """Delete a resource deposit."""
    from app.models import RegionalResource

    deposit = db.session.get(RegionalResource, deposit_id)
    if not deposit:
        abort(404)

    try:
        resource_name = deposit.resource.name
        region_name = deposit.region.name
        db.session.delete(deposit)
        db.session.commit()

        current_app.logger.info(
            f"Admin {current_user.id} deleted {resource_name} deposit from {region_name}"
        )
        flash(f'Deleted {resource_name} from {region_name}.', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting regional resource: {e}", exc_info=True)
        flash('Error deleting resource. Please try again.', 'danger')

    return redirect(url_for('admin.regional_resources'))
