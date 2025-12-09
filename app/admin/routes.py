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
    import os

    deleted_users_count = db.session.query(User).filter_by(is_deleted=True).count()
    deleted_countries_count = db.session.query(Country).filter_by(is_deleted=True).count()
    deleted_regions_count = db.session.query(Region).filter_by(is_deleted=True).count()
    deleted_resources_count = db.session.query(Resource).filter_by(is_deleted=True).count()

    # Check maintenance mode status
    maintenance_file = os.path.join(current_app.root_path, '..', 'MAINTENANCE_MODE')
    maintenance_active = os.path.exists(maintenance_file)
    maintenance_reason = None
    maintenance_eta = None
    if maintenance_active:
        try:
            with open(maintenance_file, 'r') as f:
                lines = f.read().strip().split('\n')
                if len(lines) >= 1 and lines[0]:
                    maintenance_reason = lines[0]
                if len(lines) >= 2 and lines[1]:
                    maintenance_eta = lines[1]
        except:
            pass

    return render_template('admin/index.html',
                         title='Admin Dashboard',
                         deleted_users_count=deleted_users_count,
                         deleted_countries_count=deleted_countries_count,
                         deleted_regions_count=deleted_regions_count,
                         deleted_resources_count=deleted_resources_count,
                         maintenance_active=maintenance_active,
                         maintenance_reason=maintenance_reason,
                         maintenance_eta=maintenance_eta)


@bp.route('/maintenance/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_maintenance():
    """Toggle maintenance mode on/off."""
    import os

    maintenance_file = os.path.join(current_app.root_path, '..', 'MAINTENANCE_MODE')

    if os.path.exists(maintenance_file):
        # Turn off maintenance mode
        os.remove(maintenance_file)
        current_app.logger.info(f"Admin {current_user.id} disabled maintenance mode")
        flash('Maintenance mode DISABLED. Site is now live.', 'success')
    else:
        # Turn on maintenance mode
        reason = request.form.get('reason', 'Scheduled maintenance in progress')
        eta = request.form.get('eta', '')
        with open(maintenance_file, 'w') as f:
            f.write(f"{reason}\n{eta}")
        current_app.logger.info(f"Admin {current_user.id} enabled maintenance mode: {reason}")
        flash('Maintenance mode ENABLED. Only admins can access the site.', 'warning')

    return redirect(url_for('admin.index'))


@bp.route('/maintenance/update', methods=['POST'])
@login_required
@admin_required
def update_maintenance():
    """Update maintenance mode message without toggling."""
    import os

    maintenance_file = os.path.join(current_app.root_path, '..', 'MAINTENANCE_MODE')

    if not os.path.exists(maintenance_file):
        flash('Maintenance mode is not active.', 'warning')
        return redirect(url_for('admin.index'))

    reason = request.form.get('reason', 'Scheduled maintenance in progress')
    eta = request.form.get('eta', '')
    with open(maintenance_file, 'w') as f:
        f.write(f"{reason}\n{eta}")

    flash('Maintenance message updated.', 'success')
    return redirect(url_for('admin.index'))


@bp.route('/elections')
@login_required
@admin_required
def elections():
    """Elections management page."""
    from app.models import GovernmentElection, GovernmentElectionStatus

    # Get active elections (not completed or cancelled)
    active_elections = db.session.scalars(
        db.select(GovernmentElection)
        .where(GovernmentElection.status.notin_([
            GovernmentElectionStatus.COMPLETED,
            GovernmentElectionStatus.CANCELLED
        ]))
        .order_by(GovernmentElection.country_id.asc(), GovernmentElection.id.desc())
    ).all()

    # Get completed elections (last 50)
    completed_elections = db.session.scalars(
        db.select(GovernmentElection)
        .where(GovernmentElection.status == GovernmentElectionStatus.COMPLETED)
        .order_by(GovernmentElection.voting_end.desc())
        .limit(50)
    ).all()

    return render_template('admin/elections.html',
                         title='Elections Management',
                         active_elections=active_elections,
                         completed_elections=completed_elections)


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

    # Apply search filter (username, wallet, or IP address)
    if search:
        search_term = f'%{search}%'
        query = query.where(
            (User.username.ilike(search_term)) |
            (User.wallet_address.ilike(search_term)) |
            (User.last_ip.ilike(search_term)) |
            (User.registration_ip.ilike(search_term))
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

    # Security: Maximum admin grant limit to prevent abuse from compromised admin accounts
    MAX_ADMIN_GOLD_GRANT = 1000000  # 1 million gold max per grant

    if not amount or amount <= 0:
        flash('Invalid amount.', 'danger')
        return redirect(url_for('admin.players'))

    if amount > MAX_ADMIN_GOLD_GRANT:
        flash(f'Amount exceeds maximum admin grant limit of {MAX_ADMIN_GOLD_GRANT:,} gold.', 'danger')
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
    from app.models import GovernmentElection, ElectionCandidate, ElectionType
    from app.models.zk_voting import ZKVote

    election = db.session.get(GovernmentElection, election_id)
    if not election:
        abort(404)

    # Get all candidates (including pending, rejected, withdrawn)
    candidates = db.session.scalars(
        db.select(ElectionCandidate)
        .where(ElectionCandidate.election_id == election_id)
        .order_by(ElectionCandidate.votes_received.desc())
    ).all()

    # Count ZK anonymous votes for this election
    zk_election_type = 'presidential' if election.election_type == ElectionType.PRESIDENTIAL else 'congressional'
    zk_vote_count = db.session.scalar(
        db.select(db.func.count(ZKVote.id))
        .where(ZKVote.election_type == zk_election_type)
        .where(ZKVote.election_id == election_id)
        .where(ZKVote.proof_verified == True)
    ) or 0

    return render_template('admin/government_election_detail.html',
                          title=f'Election {election_id}',
                          election=election,
                          candidates=candidates,
                          zk_vote_count=zk_vote_count)


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


@bp.route('/government/elections/<int:election_id>/advance', methods=['POST'])
@login_required
@admin_required
def advance_government_election(election_id):
    """Advance election to next phase (for testing)."""
    from app.models import GovernmentElection, GovernmentElectionStatus

    election = db.session.get(GovernmentElection, election_id)
    if not election:
        abort(404)

    # Only allow advancing: NOMINATIONS -> APPLICATIONS -> VOTING
    # To go from VOTING -> COMPLETED, must use "Close & Calculate" button
    status_transitions = {
        GovernmentElectionStatus.NOMINATIONS: GovernmentElectionStatus.APPLICATIONS,
        GovernmentElectionStatus.APPLICATIONS: GovernmentElectionStatus.VOTING,
    }

    if election.status == GovernmentElectionStatus.VOTING:
        flash('Election is in VOTING phase. Use "Close & Calculate Results" button to close voting and count votes.', 'warning')
        return redirect(url_for('admin.elections'))

    if election.status not in status_transitions:
        flash('Cannot advance this election further.', 'warning')
        return redirect(url_for('admin.elections'))

    try:
        next_status = status_transitions[election.status]
        election.status = next_status
        db.session.commit()
        current_app.logger.info(f"Admin {current_user.id} advanced election {election_id} to {election.status.value}")
        flash(f'Election advanced to {election.status.value}.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error advancing election: {e}", exc_info=True)
        flash('Error advancing election.', 'danger')

    return redirect(url_for('admin.elections'))


@bp.route('/government/elections/<int:election_id>/close', methods=['POST'])
@login_required
@admin_required
def close_government_election(election_id):
    """Close voting and calculate results (includes ZK anonymous votes)."""
    from app.models import GovernmentElection, GovernmentElectionStatus
    from app.scheduler import calculate_election_results

    election = db.session.get(GovernmentElection, election_id)
    if not election:
        abort(404)

    if election.status != GovernmentElectionStatus.VOTING:
        flash('Can only close elections that are in VOTING phase.', 'warning')
        return redirect(url_for('admin.elections'))

    try:
        # Calculate results (includes both regular and ZK votes)
        calculate_election_results(election)

        # Mark as completed
        election.status = GovernmentElectionStatus.COMPLETED
        db.session.commit()

        current_app.logger.info(f"Admin {current_user.id} closed election {election_id} and calculated results")

        # Build appropriate message based on election type
        from app.models import ElectionType, CongressMember, User
        if election.election_type == ElectionType.PRESIDENTIAL:
            if election.winner_user_id:
                winner = db.session.get(User, election.winner_user_id)
                winner_name = winner.username if winner else f"User #{election.winner_user_id}"
                flash(f'Election closed! Total votes: {election.total_votes_cast}. President elected: {winner_name}', 'success')
            else:
                flash(f'Election closed! Total votes: {election.total_votes_cast}. No winner (no candidates with votes).', 'warning')
        else:  # Congressional
            # Count how many congress members were elected
            elected_count = db.session.scalar(
                db.select(db.func.count(CongressMember.id))
                .where(CongressMember.election_id == election.id)
                .where(CongressMember.is_current == True)
            ) or 0
            flash(f'Election closed! Total votes: {election.total_votes_cast}. {elected_count} congress member(s) elected.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error closing election: {e}", exc_info=True)
        flash(f'Error closing election: {str(e)}', 'danger')

    return redirect(url_for('admin.elections'))


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


# --- Game Settings Management ---

@bp.route('/game-settings')
@login_required
@admin_required
def game_settings():
    """View and manage game settings."""
    from app.models import GameSettings

    # Get current settings
    starter_protection = GameSettings.is_starter_protection_enabled()
    game_day = GameSettings.get_game_day()
    game_start_date = GameSettings.get_value(GameSettings.GAME_START_DATE)

    # Get all settings from database for display
    all_settings = db.session.scalars(
        db.select(GameSettings).order_by(GameSettings.key)
    ).all()

    return render_template('admin/game_settings.html',
                          title='Game Settings',
                          starter_protection=starter_protection,
                          game_day=game_day,
                          game_start_date=game_start_date,
                          all_settings=all_settings)


@bp.route('/game-settings/toggle-starter-protection', methods=['POST'])
@login_required
@admin_required
def toggle_starter_protection():
    """Toggle the starter protection setting."""
    from app.models import GameSettings

    current_value = GameSettings.is_starter_protection_enabled()
    new_value = not current_value

    GameSettings.set_value(
        GameSettings.STARTER_PROTECTION_ENABLED,
        new_value,
        description='When enabled, countries with only 1 region cannot be attacked.',
        updated_by_id=current_user.id
    )

    status = 'enabled' if new_value else 'disabled'
    current_app.logger.info(f"Admin {current_user.id} {status} starter protection")
    flash(f'Starter Protection has been {status}.', 'success')

    return redirect(url_for('admin.game_settings'))


@bp.route('/game-settings/set-start-date', methods=['POST'])
@login_required
@admin_required
def set_game_start_date():
    """Set the game start date for the day counter."""
    from app.models import GameSettings
    from datetime import datetime

    start_date = request.form.get('start_date')

    if not start_date:
        flash('Please provide a start date.', 'danger')
        return redirect(url_for('admin.game_settings'))

    # Validate date format
    try:
        datetime.strptime(start_date, '%Y-%m-%d')
    except ValueError:
        flash('Invalid date format. Please use YYYY-MM-DD format.', 'danger')
        return redirect(url_for('admin.game_settings'))

    GameSettings.set_value(
        GameSettings.GAME_START_DATE,
        start_date,
        description='The game start date for calculating the current game day.',
        updated_by_id=current_user.id
    )

    # Calculate current day
    game_day = GameSettings.get_game_day()

    current_app.logger.info(f"Admin {current_user.id} set game start date to {start_date} (Day {game_day})")
    flash(f'Game start date set to {start_date}. Current game day is now Day {game_day}.', 'success')

    return redirect(url_for('admin.game_settings'))


# --- Wealth Investigation / Rankings Route ---
@bp.route('/wealth-investigation')
@login_required
@admin_required
def wealth_investigation():
    """
    Admin page to investigate potential exploiters by viewing rankings of:
    - Players sorted by gold, local currency
    - Companies sorted by gold, local currency
    - Military units sorted by treasury

    Helps detect multi-accounting and exploit abuse.
    """
    from app.models.company import Company
    from app.models.military_unit import MilitaryUnit
    from app.models.currency import UserCurrency

    # Get query parameters
    tab = request.args.get('tab', 'players')
    sort_by = request.args.get('sort', 'gold')
    order = request.args.get('order', 'desc')
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 50

    # Determine sort direction
    sort_dir = desc if order == 'desc' else lambda x: x

    players = None
    companies = None
    military_units = None
    pagination = None

    if tab == 'players':
        # Build player query
        query = db.select(User).filter_by(is_deleted=False)

        if search:
            search_term = f'%{search}%'
            query = query.where(
                (User.username.ilike(search_term)) |
                (User.wallet_address.ilike(search_term)) |
                (User.last_ip.ilike(search_term))
            )

        # Sort by selected field
        if sort_by == 'gold':
            query = query.order_by(sort_dir(User.gold))
        elif sort_by == 'level':
            query = query.order_by(sort_dir(User.experience))
        elif sort_by == 'created':
            query = query.order_by(sort_dir(User.created_at))
        else:
            query = query.order_by(sort_dir(User.gold))

        pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
        players = pagination.items

        # Get local currency totals for each player
        player_currencies = {}
        if players:
            player_ids = [p.id for p in players]
            currencies = db.session.query(
                UserCurrency.user_id,
                func.sum(UserCurrency.amount).label('total_currency')
            ).filter(
                UserCurrency.user_id.in_(player_ids)
            ).group_by(UserCurrency.user_id).all()

            player_currencies = {c.user_id: float(c.total_currency or 0) for c in currencies}

    elif tab == 'companies':
        # Build company query
        query = db.select(Company).filter_by(is_deleted=False)

        if search:
            search_term = f'%{search}%'
            query = query.where(Company.name.ilike(search_term))

        # Sort by selected field
        if sort_by == 'gold':
            query = query.order_by(sort_dir(Company.gold_balance))
        elif sort_by == 'currency':
            query = query.order_by(sort_dir(Company.currency_balance))
        elif sort_by == 'created':
            query = query.order_by(sort_dir(Company.created_at))
        else:
            query = query.order_by(sort_dir(Company.gold_balance))

        pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
        companies = pagination.items

    elif tab == 'military':
        # Build military unit query
        query = db.select(MilitaryUnit)

        if search:
            search_term = f'%{search}%'
            query = query.where(MilitaryUnit.name.ilike(search_term))

        # Sort by selected field
        if sort_by == 'treasury':
            query = query.order_by(sort_dir(MilitaryUnit.treasury))
        elif sort_by == 'damage':
            query = query.order_by(sort_dir(MilitaryUnit.total_damage))
        elif sort_by == 'created':
            query = query.order_by(sort_dir(MilitaryUnit.created_at))
        else:
            query = query.order_by(sort_dir(MilitaryUnit.treasury))

        pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
        military_units = pagination.items

    return render_template('admin/wealth_investigation.html',
                         title='Wealth Investigation',
                         tab=tab,
                         sort_by=sort_by,
                         order=order,
                         search=search,
                         players=players,
                         companies=companies,
                         military_units=military_units,
                         pagination=pagination,
                         player_currencies=player_currencies if tab == 'players' else {})


# --- Transaction Monitor Route ---
@bp.route('/transaction-monitor')
@login_required
@admin_required
def transaction_monitor():
    """
    Real-time feed of large/recent transactions to spot unusual activity.
    Shows player transactions, company transactions, and NFT trades.
    """
    from app.models.currency import FinancialTransaction
    from app.models.company import CompanyTransaction
    from app.models.nft import NFTTradeHistory

    # Get query parameters
    tx_type = request.args.get('type', 'all')  # all, player, company, nft
    min_amount = request.args.get('min_amount', 0, type=float)
    hours = request.args.get('hours', 24, type=int)
    page = request.args.get('page', 1, type=int)
    per_page = 50

    time_threshold = datetime.utcnow() - timedelta(hours=hours)

    # Combined transactions list
    transactions = []

    if tx_type in ['all', 'player']:
        # Player financial transactions
        player_txs = db.session.query(FinancialTransaction).filter(
            FinancialTransaction.timestamp >= time_threshold,
            FinancialTransaction.amount >= min_amount
        ).order_by(desc(FinancialTransaction.timestamp)).limit(200).all()

        for tx in player_txs:
            transactions.append({
                'type': 'player',
                'timestamp': tx.timestamp,
                'user': tx.user,
                'tx_type': tx.transaction_type,
                'amount': float(tx.amount),
                'currency': tx.currency_type,
                'description': tx.description,
                'balance_after': float(tx.balance_after)
            })

    if tx_type in ['all', 'company']:
        # Company transactions
        company_txs = db.session.query(CompanyTransaction).filter(
            CompanyTransaction.created_at >= time_threshold,
            (CompanyTransaction.amount_gold >= min_amount) | (CompanyTransaction.amount_currency >= min_amount)
        ).order_by(desc(CompanyTransaction.created_at)).limit(200).all()

        for tx in company_txs:
            amount = float(tx.amount_gold) if float(tx.amount_gold) > 0 else float(tx.amount_currency)
            currency = 'GOLD' if float(tx.amount_gold) > 0 else 'LOCAL'
            transactions.append({
                'type': 'company',
                'timestamp': tx.created_at,
                'company': tx.company,
                'user': tx.related_user,
                'tx_type': tx.transaction_type.value if hasattr(tx.transaction_type, 'value') else tx.transaction_type,
                'amount': amount,
                'currency': currency,
                'description': tx.description,
                'balance_after': float(tx.balance_gold_after) if currency == 'GOLD' else float(tx.balance_currency_after)
            })

    if tx_type in ['all', 'nft']:
        # NFT trades
        nft_txs = db.session.query(NFTTradeHistory).filter(
            NFTTradeHistory.traded_at >= time_threshold,
            NFTTradeHistory.price_zen >= min_amount
        ).order_by(desc(NFTTradeHistory.traded_at)).limit(200).all()

        for tx in nft_txs:
            transactions.append({
                'type': 'nft',
                'timestamp': tx.traded_at,
                'from_user': tx.from_user,
                'to_user': tx.to_user,
                'tx_type': tx.trade_type,
                'amount': float(tx.price_zen) if tx.price_zen else 0,
                'currency': 'ZEN',
                'description': f'NFT #{tx.nft_id} - Tier {tx.nft.tier if tx.nft else "?"}',
                'nft': tx.nft
            })

    # Sort all transactions by timestamp
    transactions.sort(key=lambda x: x['timestamp'], reverse=True)

    # Paginate
    total = len(transactions)
    start = (page - 1) * per_page
    end = start + per_page
    transactions = transactions[start:end]

    return render_template('admin/transaction_monitor.html',
                         title='Transaction Monitor',
                         transactions=transactions,
                         tx_type=tx_type,
                         min_amount=min_amount,
                         hours=hours,
                         page=page,
                         per_page=per_page,
                         total=total,
                         total_pages=(total + per_page - 1) // per_page)


# --- Suspicious Activity Alerts Route ---
@bp.route('/suspicious-activity')
@login_required
@admin_required
def suspicious_activity():
    """
    Auto-detect and flag suspicious accounts/activity:
    - Same IP with multiple accounts
    - Rapid wealth accumulation
    - Unusual trading patterns
    """
    from app.models.currency import FinancialTransaction, UserCurrency
    from app.models.company import Company

    alerts = []

    # 1. Find duplicate IPs (potential multi-accounting)
    duplicate_ips = db.session.query(
        User.last_ip,
        func.count(User.id).label('account_count'),
        func.group_concat(User.id).label('user_ids'),
        func.group_concat(User.username).label('usernames')
    ).filter(
        User.last_ip.isnot(None),
        User.last_ip != '',
        User.is_deleted == False
    ).group_by(User.last_ip).having(func.count(User.id) > 1).all()

    for ip_data in duplicate_ips:
        user_ids = [int(uid) for uid in ip_data.user_ids.split(',')]
        usernames = ip_data.usernames.split(',') if ip_data.usernames else []
        users = db.session.query(User).filter(User.id.in_(user_ids)).all()

        # Calculate combined wealth
        total_gold = sum(float(u.gold) for u in users)
        total_currency = 0
        for u in users:
            currencies = db.session.query(func.sum(UserCurrency.amount)).filter(
                UserCurrency.user_id == u.id
            ).scalar() or 0
            total_currency += float(currencies)

        alerts.append({
            'type': 'duplicate_ip',
            'severity': 'high' if ip_data.account_count > 2 else 'medium',
            'ip': ip_data.last_ip,
            'account_count': ip_data.account_count,
            'users': users,
            'total_gold': total_gold,
            'total_currency': total_currency,
            'description': f'{ip_data.account_count} accounts share IP {ip_data.last_ip}'
        })

    # 2. Find accounts with rapid wealth accumulation (gained >10k gold in last 24h)
    yesterday = datetime.utcnow() - timedelta(hours=24)
    wealth_gains = db.session.query(
        FinancialTransaction.user_id,
        func.sum(FinancialTransaction.amount).label('total_gained')
    ).filter(
        FinancialTransaction.timestamp >= yesterday,
        FinancialTransaction.transaction_type.in_(['GOLD_GAIN', 'MARKET_SELL', 'CURRENCY_EXCHANGE']),
        FinancialTransaction.currency_type == 'GOLD'
    ).group_by(FinancialTransaction.user_id).having(func.sum(FinancialTransaction.amount) > 10000).all()

    for gain in wealth_gains:
        user = db.session.get(User, gain.user_id)
        if user and not user.is_admin:
            # Get recent transactions for context
            recent_txs = db.session.query(FinancialTransaction).filter(
                FinancialTransaction.user_id == gain.user_id,
                FinancialTransaction.timestamp >= yesterday
            ).order_by(desc(FinancialTransaction.timestamp)).limit(10).all()

            alerts.append({
                'type': 'rapid_wealth',
                'severity': 'high' if float(gain.total_gained) > 50000 else 'medium',
                'user': user,
                'amount_gained': float(gain.total_gained),
                'recent_transactions': recent_txs,
                'description': f'{user.username or user.wallet_address[:10]} gained {float(gain.total_gained):,.2f} gold in 24h'
            })

    # 3. Find new accounts with high wealth (created in last 7 days with >5k gold)
    week_ago = datetime.utcnow() - timedelta(days=7)
    wealthy_newbies = db.session.query(User).filter(
        User.created_at >= week_ago,
        User.gold > 5000,
        User.is_admin == False,
        User.is_deleted == False
    ).all()

    for user in wealthy_newbies:
        alerts.append({
            'type': 'wealthy_newbie',
            'severity': 'medium' if float(user.gold) < 20000 else 'high',
            'user': user,
            'gold': float(user.gold),
            'account_age_days': (datetime.utcnow() - user.created_at).days,
            'description': f'New account ({(datetime.utcnow() - user.created_at).days} days old) has {float(user.gold):,.2f} gold'
        })

    # 4. Find users with many companies (potential resource farming)
    company_counts = db.session.query(
        Company.owner_id,
        func.count(Company.id).label('company_count')
    ).filter(Company.is_deleted == False).group_by(Company.owner_id).having(func.count(Company.id) > 5).all()

    for cc in company_counts:
        user = db.session.get(User, cc.owner_id)
        if user and not user.is_admin:
            companies = db.session.query(Company).filter(
                Company.owner_id == cc.owner_id,
                Company.is_deleted == False
            ).all()

            total_company_gold = sum(float(c.gold_balance) for c in companies)

            alerts.append({
                'type': 'many_companies',
                'severity': 'low' if cc.company_count <= 8 else 'medium',
                'user': user,
                'company_count': cc.company_count,
                'companies': companies,
                'total_company_gold': total_company_gold,
                'description': f'{user.username or user.wallet_address[:10]} owns {cc.company_count} companies'
            })

    # Sort alerts by severity
    severity_order = {'high': 0, 'medium': 1, 'low': 2}
    alerts.sort(key=lambda x: severity_order.get(x['severity'], 3))

    return render_template('admin/suspicious_activity.html',
                         title='Suspicious Activity',
                         alerts=alerts)


# --- Economy Dashboard Route ---
@bp.route('/economy-dashboard')
@login_required
@admin_required
def economy_dashboard():
    """
    Overview of the game economy:
    - Total gold/currency in circulation
    - Market prices and trends
    - Inflation indicators
    """
    from app.models.currency import FinancialTransaction, UserCurrency
    from app.models.company import Company
    from app.models.military_unit import MilitaryUnit
    from app.models.zen_market import ZenMarket

    # Total gold in circulation (players + companies + military units)
    total_player_gold = db.session.query(func.sum(User.gold)).filter(User.is_deleted == False).scalar() or 0
    total_company_gold = db.session.query(func.sum(Company.gold_balance)).filter(Company.is_deleted == False).scalar() or 0

    # Total local currency by country
    currency_by_country = db.session.query(
        Country.id,
        Country.name,
        Country.currency_code,
        func.sum(UserCurrency.amount).label('player_holdings'),
        func.sum(Company.currency_balance).label('company_holdings')
    ).outerjoin(UserCurrency, UserCurrency.country_id == Country.id
    ).outerjoin(Company, Company.country_id == Country.id
    ).filter(Country.is_deleted == False
    ).group_by(Country.id, Country.name, Country.currency_code).all()

    # Player count and wealth distribution
    total_players = db.session.query(func.count(User.id)).filter(User.is_deleted == False).scalar() or 0
    active_players = db.session.query(func.count(User.id)).filter(
        User.is_deleted == False,
        User.last_seen >= datetime.utcnow() - timedelta(days=7)
    ).scalar() or 0

    # Wealth distribution brackets
    wealth_brackets = {
        '0-100': db.session.query(func.count(User.id)).filter(User.is_deleted == False, User.gold < 100).scalar() or 0,
        '100-1k': db.session.query(func.count(User.id)).filter(User.is_deleted == False, User.gold >= 100, User.gold < 1000).scalar() or 0,
        '1k-10k': db.session.query(func.count(User.id)).filter(User.is_deleted == False, User.gold >= 1000, User.gold < 10000).scalar() or 0,
        '10k-100k': db.session.query(func.count(User.id)).filter(User.is_deleted == False, User.gold >= 10000, User.gold < 100000).scalar() or 0,
        '100k+': db.session.query(func.count(User.id)).filter(User.is_deleted == False, User.gold >= 100000).scalar() or 0,
    }

    # Company statistics
    total_companies = db.session.query(func.count(Company.id)).filter(Company.is_deleted == False).scalar() or 0

    # ZEN market data
    zen_markets = db.session.query(ZenMarket).all()

    # Transaction volume (last 24h, 7d, 30d)
    now = datetime.utcnow()
    tx_24h = db.session.query(func.sum(FinancialTransaction.amount)).filter(
        FinancialTransaction.timestamp >= now - timedelta(hours=24),
        FinancialTransaction.currency_type == 'GOLD'
    ).scalar() or 0

    tx_7d = db.session.query(func.sum(FinancialTransaction.amount)).filter(
        FinancialTransaction.timestamp >= now - timedelta(days=7),
        FinancialTransaction.currency_type == 'GOLD'
    ).scalar() or 0

    tx_30d = db.session.query(func.sum(FinancialTransaction.amount)).filter(
        FinancialTransaction.timestamp >= now - timedelta(days=30),
        FinancialTransaction.currency_type == 'GOLD'
    ).scalar() or 0

    # Top 10 richest players
    top_players = db.session.query(User).filter(
        User.is_deleted == False
    ).order_by(desc(User.gold)).limit(10).all()

    # Top 10 richest companies
    top_companies = db.session.query(Company).filter(
        Company.is_deleted == False
    ).order_by(desc(Company.gold_balance)).limit(10).all()

    return render_template('admin/economy_dashboard.html',
                         title='Economy Dashboard',
                         total_player_gold=float(total_player_gold),
                         total_company_gold=float(total_company_gold),
                         total_gold=float(total_player_gold) + float(total_company_gold),
                         currency_by_country=currency_by_country,
                         total_players=total_players,
                         active_players=active_players,
                         wealth_brackets=wealth_brackets,
                         total_companies=total_companies,
                         zen_markets=zen_markets,
                         tx_24h=float(tx_24h),
                         tx_7d=float(tx_7d),
                         tx_30d=float(tx_30d),
                         top_players=top_players,
                         top_companies=top_companies)


# --- Global Multipliers Dashboard ---
@bp.route('/global-multipliers', methods=['GET', 'POST'])
@login_required
@admin_required
def global_multipliers():
    """
    Admin dashboard to adjust global game multipliers.
    """
    from app.models.game_settings import GameSettings
    from app.models.game_event import GameEvent

    if request.method == 'POST':
        # Update multipliers
        multipliers = {
            GameSettings.XP_MULTIPLIER: request.form.get('xp_multiplier', '1.0'),
            GameSettings.GOLD_DROP_MULTIPLIER: request.form.get('gold_drop_multiplier', '1.0'),
            GameSettings.PRODUCTION_SPEED_MULTIPLIER: request.form.get('production_speed_multiplier', '1.0'),
            GameSettings.WORK_XP_MULTIPLIER: request.form.get('work_xp_multiplier', '1.0'),
            GameSettings.TRAINING_XP_MULTIPLIER: request.form.get('training_xp_multiplier', '1.0'),
            GameSettings.BATTLE_XP_MULTIPLIER: request.form.get('battle_xp_multiplier', '1.0'),
            GameSettings.TRAVEL_COST_MULTIPLIER: request.form.get('travel_cost_multiplier', '1.0'),
            GameSettings.COMPANY_TAX_MULTIPLIER: request.form.get('company_tax_multiplier', '1.0'),
        }

        for key, value in multipliers.items():
            try:
                float_val = float(value)
                # Validate range (0.1 to 10.0)
                if 0.1 <= float_val <= 10.0:
                    GameSettings.set_value(key, str(float_val), updated_by_id=current_user.id)
            except (ValueError, TypeError):
                pass

        flash('Global multipliers updated successfully!', 'success')
        return redirect(url_for('admin.global_multipliers'))

    # Get current multipliers
    multipliers = GameSettings.get_all_multipliers()

    # Get active events affecting multipliers
    active_events = GameEvent.get_active_events()

    # Calculate effective multipliers (base * events)
    effective_multipliers = {
        'xp': GameEvent.get_effective_multiplier(GameSettings.XP_MULTIPLIER),
        'gold_drop': GameEvent.get_effective_multiplier(GameSettings.GOLD_DROP_MULTIPLIER),
        'production_speed': GameEvent.get_effective_multiplier(GameSettings.PRODUCTION_SPEED_MULTIPLIER),
        'work_xp': GameEvent.get_effective_multiplier(GameSettings.WORK_XP_MULTIPLIER),
        'training_xp': GameEvent.get_effective_multiplier(GameSettings.TRAINING_XP_MULTIPLIER),
        'battle_xp': GameEvent.get_effective_multiplier(GameSettings.BATTLE_XP_MULTIPLIER),
        'travel_cost': GameEvent.get_effective_multiplier(GameSettings.TRAVEL_COST_MULTIPLIER),
        'company_tax': GameEvent.get_effective_multiplier(GameSettings.COMPANY_TAX_MULTIPLIER),
    }

    return render_template('admin/global_multipliers.html',
                         title='Global Multipliers',
                         multipliers=multipliers,
                         effective_multipliers=effective_multipliers,
                         active_events=active_events)


# --- Event System Routes ---
@bp.route('/events')
@login_required
@admin_required
def events():
    """
    View and manage game events.
    """
    from app.models.game_event import GameEvent, EventType

    # Get all events, ordered by start time
    active_events = GameEvent.query.filter(
        GameEvent.is_active == True,
        GameEvent.end_time >= datetime.utcnow()
    ).order_by(GameEvent.start_time).all()

    past_events = GameEvent.query.filter(
        GameEvent.end_time < datetime.utcnow()
    ).order_by(desc(GameEvent.end_time)).limit(20).all()

    event_types = [(e.value, e.value.replace('_', ' ').title()) for e in EventType]

    return render_template('admin/events.html',
                         title='Game Events',
                         active_events=active_events,
                         past_events=past_events,
                         event_types=event_types,
                         EventType=EventType)


@bp.route('/events/create', methods=['POST'])
@login_required
@admin_required
def create_event():
    """Create a new game event."""
    from app.models.game_event import GameEvent, EventType

    name = request.form.get('name', '').strip()
    event_type = request.form.get('event_type', EventType.CUSTOM.value)
    multiplier = float(request.form.get('multiplier', 2.0))
    description = request.form.get('description', '').strip()
    start_date = request.form.get('start_date')
    start_time = request.form.get('start_time', '00:00')
    end_date = request.form.get('end_date')
    end_time = request.form.get('end_time', '23:59')

    if not name or not start_date or not end_date:
        flash('Please fill in all required fields.', 'danger')
        return redirect(url_for('admin.events'))

    try:
        start_datetime = datetime.strptime(f'{start_date} {start_time}', '%Y-%m-%d %H:%M')
        end_datetime = datetime.strptime(f'{end_date} {end_time}', '%Y-%m-%d %H:%M')

        if end_datetime <= start_datetime:
            flash('End time must be after start time.', 'danger')
            return redirect(url_for('admin.events'))

        event = GameEvent.create_event(
            event_type=event_type,
            name=name,
            start_time=start_datetime,
            end_time=end_datetime,
            multiplier=multiplier,
            description=description or None,
            created_by_id=current_user.id
        )
        db.session.commit()

        flash(f'Event "{name}" created successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating event: {str(e)}', 'danger')

    return redirect(url_for('admin.events'))


@bp.route('/events/<int:event_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_event(event_id):
    """Toggle event active status."""
    from app.models.game_event import GameEvent

    event = db.session.get(GameEvent, event_id)
    if event:
        event.is_active = not event.is_active
        db.session.commit()
        status = 'activated' if event.is_active else 'deactivated'
        flash(f'Event "{event.name}" {status}.', 'success')
    else:
        flash('Event not found.', 'danger')

    return redirect(url_for('admin.events'))


@bp.route('/events/<int:event_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_event(event_id):
    """Delete an event."""
    from app.models.game_event import GameEvent

    event = db.session.get(GameEvent, event_id)
    if event:
        name = event.name
        db.session.delete(event)
        db.session.commit()
        flash(f'Event "{name}" deleted.', 'success')
    else:
        flash('Event not found.', 'danger')

    return redirect(url_for('admin.events'))


# --- Country Management Routes ---
@bp.route('/country-management')
@login_required
@admin_required
def country_management():
    """
    Manage countries - edit stats, view regions, manage territories.
    """
    from app.models.location import Country, Region

    countries = Country.query.filter_by(is_deleted=False).order_by(Country.name).all()

    # Get stats for each country
    country_stats = []
    for country in countries:
        stats = {
            'country': country,
            'citizen_count': country.citizens.count(),
            'region_count': country.current_regions.count(),
            'total_treasury': float(country.treasury_gold) + float(country.treasury_currency),
        }
        country_stats.append(stats)

    return render_template('admin/country_management.html',
                         title='Country Management',
                         country_stats=country_stats)


@bp.route('/country/<int:country_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_country(country_id):
    """Edit country details and settings."""
    from app.models.location import Country, Region
    from decimal import Decimal

    country = db.session.get(Country, country_id)
    if not country or country.is_deleted:
        flash('Country not found.', 'danger')
        return redirect(url_for('admin.country_management'))

    if request.method == 'POST':
        # Update basic info
        country.name = request.form.get('name', country.name).strip()
        country.currency_name = request.form.get('currency_name', country.currency_name)
        country.currency_code = request.form.get('currency_code', country.currency_code)
        country.flag_code = request.form.get('flag_code', country.flag_code)

        # Update treasury
        try:
            country.treasury_gold = Decimal(request.form.get('treasury_gold', '0'))
            country.treasury_currency = Decimal(request.form.get('treasury_currency', '0'))
            country.military_budget_gold = Decimal(request.form.get('military_budget_gold', '0'))
            country.military_budget_currency = Decimal(request.form.get('military_budget_currency', '0'))
        except:
            pass

        # Update tax rates
        try:
            country.vat_tax_rate = Decimal(request.form.get('vat_tax_rate', '5.0'))
            country.import_tax_rate = Decimal(request.form.get('import_tax_rate', '10.0'))
            country.work_tax_rate = Decimal(request.form.get('work_tax_rate', '10.0'))
        except:
            pass

        # Update visibility
        country.is_hidden = request.form.get('is_hidden') == 'on'

        db.session.commit()
        flash(f'Country "{country.name}" updated successfully!', 'success')
        return redirect(url_for('admin.edit_country', country_id=country_id))

    # Get country's regions
    regions = country.current_regions.all()

    # Get all countries for transfer dropdown
    all_countries = Country.query.filter_by(is_deleted=False).order_by(Country.name).all()

    return render_template('admin/edit_country.html',
                         title=f'Edit {country.name}',
                         country=country,
                         regions=regions,
                         all_countries=all_countries)


@bp.route('/country/<int:country_id>/transfer-region', methods=['POST'])
@login_required
@admin_required
def transfer_region(country_id):
    """Transfer a region from one country to another."""
    from app.models.location import Country, Region, country_regions

    region_id = request.form.get('region_id', type=int)
    target_country_id = request.form.get('target_country_id', type=int)

    if not region_id or not target_country_id:
        flash('Invalid region or target country.', 'danger')
        return redirect(url_for('admin.edit_country', country_id=country_id))

    region = db.session.get(Region, region_id)
    target_country = db.session.get(Country, target_country_id)
    source_country = db.session.get(Country, country_id)

    if not region or not target_country or not source_country:
        flash('Region or country not found.', 'danger')
        return redirect(url_for('admin.edit_country', country_id=country_id))

    # Remove region from source country
    db.session.execute(
        country_regions.delete().where(
            (country_regions.c.country_id == country_id) &
            (country_regions.c.region_id == region_id)
        )
    )

    # Add region to target country
    db.session.execute(
        country_regions.insert().values(country_id=target_country_id, region_id=region_id)
    )

    db.session.commit()
    flash(f'Region "{region.name}" transferred to {target_country.name}.', 'success')

    return redirect(url_for('admin.edit_country', country_id=country_id))


@bp.route('/country/create', methods=['POST'])
@login_required
@admin_required
def create_country():
    """Create a new country."""
    from app.models.location import Country

    name = request.form.get('name', '').strip()
    currency_name = request.form.get('currency_name', '').strip()
    currency_code = request.form.get('currency_code', '').strip().upper()
    flag_code = request.form.get('flag_code', '').strip().lower()

    if not name:
        flash('Country name is required.', 'danger')
        return redirect(url_for('admin.country_management'))

    # Check if country already exists
    existing = Country.query.filter_by(name=name).first()
    if existing:
        flash(f'Country "{name}" already exists.', 'danger')
        return redirect(url_for('admin.country_management'))

    country = Country(
        name=name,
        currency_name=currency_name or f'{name} Dollar',
        currency_code=currency_code or name[:3].upper(),
        flag_code=flag_code or None
    )
    db.session.add(country)
    db.session.commit()

    flash(f'Country "{name}" created successfully!', 'success')
    return redirect(url_for('admin.edit_country', country_id=country.id))


@bp.route('/region/create', methods=['POST'])
@login_required
@admin_required
def create_region():
    """Create a new region and assign it to a country."""
    from app.models.location import Region, Country, country_regions

    name = request.form.get('name', '').strip()
    country_id = request.form.get('country_id', type=int)

    if not name or not country_id:
        flash('Region name and country are required.', 'danger')
        return redirect(url_for('admin.country_management'))

    country = db.session.get(Country, country_id)
    if not country:
        flash('Country not found.', 'danger')
        return redirect(url_for('admin.country_management'))

    # Check if region already exists
    existing = Region.query.filter_by(name=name).first()
    if existing:
        flash(f'Region "{name}" already exists.', 'danger')
        return redirect(url_for('admin.edit_country', country_id=country_id))

    region = Region(name=name, original_owner_id=country_id)
    db.session.add(region)
    db.session.flush()  # Get the region ID

    # Add region to country's current regions
    db.session.execute(
        country_regions.insert().values(country_id=country_id, region_id=region.id)
    )

    db.session.commit()
    flash(f'Region "{name}" created and assigned to {country.name}.', 'success')

    return redirect(url_for('admin.edit_country', country_id=country_id))


# --- Player Retention Dashboard ---
@bp.route('/player-retention')
@login_required
@admin_required
def player_retention():
    """
    Player Retention Dashboard:
    - New signups over time
    - Daily active users (DAU)
    - Weekly active users (WAU)
    - Monthly active users (MAU)
    - Churn rate analysis
    - Retention cohorts
    """
    from sqlalchemy import cast, Date, and_

    now = datetime.utcnow()

    # --- New Signups ---
    # Today's signups
    signups_today = db.session.query(func.count(User.id)).filter(
        User.is_deleted == False,
        cast(User.created_at, Date) == now.date()
    ).scalar() or 0

    # This week's signups
    week_start = now - timedelta(days=now.weekday())
    signups_this_week = db.session.query(func.count(User.id)).filter(
        User.is_deleted == False,
        User.created_at >= week_start.replace(hour=0, minute=0, second=0)
    ).scalar() or 0

    # This month's signups
    month_start = now.replace(day=1, hour=0, minute=0, second=0)
    signups_this_month = db.session.query(func.count(User.id)).filter(
        User.is_deleted == False,
        User.created_at >= month_start
    ).scalar() or 0

    # Signups per day for last 30 days
    daily_signups = []
    for i in range(30):
        day = (now - timedelta(days=i)).date()
        count = db.session.query(func.count(User.id)).filter(
            User.is_deleted == False,
            cast(User.created_at, Date) == day
        ).scalar() or 0
        daily_signups.append({'date': day.strftime('%Y-%m-%d'), 'count': count})
    daily_signups.reverse()

    # --- Active Users ---
    # DAU - Users active today
    dau = db.session.query(func.count(User.id)).filter(
        User.is_deleted == False,
        cast(User.last_seen, Date) == now.date()
    ).scalar() or 0

    # WAU - Users active in last 7 days
    wau = db.session.query(func.count(User.id)).filter(
        User.is_deleted == False,
        User.last_seen >= now - timedelta(days=7)
    ).scalar() or 0

    # MAU - Users active in last 30 days
    mau = db.session.query(func.count(User.id)).filter(
        User.is_deleted == False,
        User.last_seen >= now - timedelta(days=30)
    ).scalar() or 0

    # Total users
    total_users = db.session.query(func.count(User.id)).filter(User.is_deleted == False).scalar() or 0

    # DAU history for last 14 days
    dau_history = []
    for i in range(14):
        day = (now - timedelta(days=i)).date()
        count = db.session.query(func.count(User.id)).filter(
            User.is_deleted == False,
            cast(User.last_seen, Date) == day
        ).scalar() or 0
        dau_history.append({'date': day.strftime('%Y-%m-%d'), 'count': count})
    dau_history.reverse()

    # --- Churn Analysis ---
    # Users who haven't been active in 7+ days but were active before
    churned_7d = db.session.query(func.count(User.id)).filter(
        User.is_deleted == False,
        User.last_seen < now - timedelta(days=7),
        User.last_seen >= now - timedelta(days=30)
    ).scalar() or 0

    # Users who haven't been active in 30+ days
    churned_30d = db.session.query(func.count(User.id)).filter(
        User.is_deleted == False,
        User.last_seen < now - timedelta(days=30)
    ).scalar() or 0

    # Calculate churn rates
    churn_rate_7d = (churned_7d / total_users * 100) if total_users > 0 else 0
    churn_rate_30d = (churned_30d / total_users * 100) if total_users > 0 else 0

    # --- Retention Cohorts ---
    # Users who signed up and were active on different days
    retention_cohorts = []
    for days_ago in [7, 14, 21, 28]:
        cohort_start = (now - timedelta(days=days_ago)).date()
        cohort_end = (now - timedelta(days=days_ago - 6)).date()

        # Users who signed up in this cohort
        cohort_users = db.session.query(func.count(User.id)).filter(
            User.is_deleted == False,
            cast(User.created_at, Date) >= cohort_start,
            cast(User.created_at, Date) <= cohort_end
        ).scalar() or 0

        # Users from cohort who are still active (seen in last 7 days)
        retained_users = db.session.query(func.count(User.id)).filter(
            User.is_deleted == False,
            cast(User.created_at, Date) >= cohort_start,
            cast(User.created_at, Date) <= cohort_end,
            User.last_seen >= now - timedelta(days=7)
        ).scalar() or 0

        retention_rate = (retained_users / cohort_users * 100) if cohort_users > 0 else 0

        retention_cohorts.append({
            'period': f'{days_ago}-{days_ago-6} days ago',
            'cohort_size': cohort_users,
            'retained': retained_users,
            'retention_rate': round(retention_rate, 1)
        })

    # --- User Level Distribution ---
    # Level is calculated from experience, so we need to use XP thresholds
    # Formula: XP for level = BASE_XP_INCREMENT * (2^(level-1) - 1), where BASE_XP_INCREMENT = 20
    from app.utils import get_total_xp_for_level

    level_distribution = []
    level_brackets = [(1, 5), (6, 10), (11, 20), (21, 30), (31, 50), (51, 100)]
    for min_level, max_level in level_brackets:
        min_xp = get_total_xp_for_level(min_level)
        max_xp = get_total_xp_for_level(max_level + 1) - 1  # XP just before next level
        count = db.session.query(func.count(User.id)).filter(
            User.is_deleted == False,
            User.experience >= min_xp,
            User.experience <= max_xp
        ).scalar() or 0
        level_distribution.append({
            'bracket': f'Level {min_level}-{max_level}',
            'count': count
        })

    # --- Recent Signups ---
    recent_signups = db.session.query(User).filter(
        User.is_deleted == False
    ).order_by(desc(User.created_at)).limit(20).all()

    return render_template('admin/player_retention.html',
                         title='Player Retention Dashboard',
                         signups_today=signups_today,
                         signups_this_week=signups_this_week,
                         signups_this_month=signups_this_month,
                         daily_signups=daily_signups,
                         dau=dau,
                         wau=wau,
                         mau=mau,
                         total_users=total_users,
                         dau_history=dau_history,
                         churned_7d=churned_7d,
                         churned_30d=churned_30d,
                         churn_rate_7d=round(churn_rate_7d, 1),
                         churn_rate_30d=round(churn_rate_30d, 1),
                         retention_cohorts=retention_cohorts,
                         level_distribution=level_distribution,
                         recent_signups=recent_signups,
                         now=now)


# --- Economy Reports Dashboard ---
@bp.route('/economy-reports')
@login_required
@admin_required
def economy_reports():
    """
    Economy Reports Dashboard:
    - ZEN buying/selling statistics (Gold flowing in/out)
    - NFT minting statistics
    - NFT trading statistics with fee tracking
    - Daily/Weekly/Monthly summaries
    - Revenue tracking (your earnings)
    """
    from app.models.zen_market import ZenTransaction, ZenMarket
    from app.models.nft import NFTInventory, NFTTradeHistory, NFTMarketplace
    from app.blockchain.marketplace_contract import get_marketplace_fee
    from sqlalchemy import cast, Date

    now = datetime.utcnow()

    # Get time period from query params (default: 30 days)
    period = request.args.get('period', '30')
    try:
        days = int(period)
    except ValueError:
        days = 30

    period_start = now - timedelta(days=days)

    # --- ZEN Market Statistics ---
    # Get current ZEN market
    zen_market = db.session.query(ZenMarket).first()
    current_zen_buy_price = float(zen_market.buy_zen_price) if zen_market else 50.0
    current_zen_sell_price = float(zen_market.sell_zen_price) if zen_market else 47.50

    # ZEN bought by players (players pay Gold, receive ZEN) - Gold INFLOW
    zen_buys = db.session.query(
        func.sum(ZenTransaction.zen_amount),
        func.sum(ZenTransaction.gold_amount),
        func.count(ZenTransaction.id)
    ).filter(
        ZenTransaction.transaction_type == 'buy',
        ZenTransaction.created_at >= period_start
    ).first()

    zen_bought_amount = float(zen_buys[0] or 0)
    gold_spent_on_zen = float(zen_buys[1] or 0)
    zen_buy_count = zen_buys[2] or 0

    # ZEN sold by players (players receive Gold, give ZEN) - Gold OUTFLOW
    zen_sells = db.session.query(
        func.sum(ZenTransaction.zen_amount),
        func.sum(ZenTransaction.gold_amount),
        func.count(ZenTransaction.id)
    ).filter(
        ZenTransaction.transaction_type == 'sell',
        ZenTransaction.created_at >= period_start
    ).first()

    zen_sold_amount = float(zen_sells[0] or 0)
    gold_received_from_zen = float(zen_sells[1] or 0)
    zen_sell_count = zen_sells[2] or 0

    # Net Gold flow (positive = earning, negative = paying out)
    net_gold_from_zen = gold_spent_on_zen - gold_received_from_zen

    # --- Daily ZEN transactions for chart ---
    daily_zen_stats = []
    for i in range(min(days, 30)):  # Max 30 days for chart
        day = (now - timedelta(days=i)).date()

        # ZEN bought by players = ZEN outflow (you give out ZEN)
        day_zen_outflow = db.session.query(
            func.sum(ZenTransaction.zen_amount)
        ).filter(
            ZenTransaction.transaction_type == 'buy',
            cast(ZenTransaction.created_at, Date) == day
        ).scalar() or 0

        # ZEN sold by players = ZEN inflow (you receive ZEN)
        day_zen_inflow = db.session.query(
            func.sum(ZenTransaction.zen_amount)
        ).filter(
            ZenTransaction.transaction_type == 'sell',
            cast(ZenTransaction.created_at, Date) == day
        ).scalar() or 0

        daily_zen_stats.append({
            'date': day.strftime('%Y-%m-%d'),
            'inflow': float(day_zen_inflow),   # ZEN you receive
            'outflow': float(day_zen_outflow),  # ZEN you give out
            'net': float(day_zen_inflow) - float(day_zen_outflow)
        })
    daily_zen_stats.reverse()

    # --- NFT Minting Statistics ---
    # NFTs minted (acquired via 'purchase' which means minted)
    nfts_minted = db.session.query(
        func.count(NFTInventory.id)
    ).filter(
        NFTInventory.acquired_via == 'purchase',
        NFTInventory.acquired_at >= period_start
    ).scalar() or 0

    # NFTs dropped (free drops)
    nfts_dropped = db.session.query(
        func.count(NFTInventory.id)
    ).filter(
        NFTInventory.acquired_via == 'drop',
        NFTInventory.acquired_at >= period_start
    ).scalar() or 0

    # NFTs upgraded (burned + minted new)
    nfts_upgraded = db.session.query(
        func.count(NFTInventory.id)
    ).filter(
        NFTInventory.acquired_via == 'upgrade',
        NFTInventory.acquired_at >= period_start
    ).scalar() or 0

    # NFT minting by tier
    nft_by_tier = {}
    for tier in range(1, 6):
        count = db.session.query(func.count(NFTInventory.id)).filter(
            NFTInventory.acquired_via == 'purchase',
            NFTInventory.tier == tier,
            NFTInventory.acquired_at >= period_start
        ).scalar() or 0
        nft_by_tier[f'Q{tier}'] = count

    # --- NFT Trading Statistics ---
    # Get marketplace fee (basis points)
    try:
        marketplace_fee_bps = get_marketplace_fee()
    except:
        marketplace_fee_bps = 500  # Default 5%
    marketplace_fee_percent = marketplace_fee_bps / 100

    # NFT trades (sales only, not gifts/transfers)
    nft_trades = db.session.query(
        func.count(NFTTradeHistory.id),
        func.sum(NFTTradeHistory.price_zen)
    ).filter(
        NFTTradeHistory.trade_type == 'sale',
        NFTTradeHistory.traded_at >= period_start
    ).first()

    nft_trade_count = nft_trades[0] or 0
    total_trade_volume_zen = float(nft_trades[1] or 0)

    # Calculate fees earned from trades
    fees_earned_zen = total_trade_volume_zen * (marketplace_fee_bps / 10000)

    # Average trade price
    avg_trade_price = (total_trade_volume_zen / nft_trade_count) if nft_trade_count > 0 else 0

    # --- Active NFT Marketplace Listings ---
    active_listings = db.session.query(func.count(NFTMarketplace.id)).filter(
        NFTMarketplace.is_active == True
    ).scalar() or 0

    total_listing_value = db.session.query(func.sum(NFTMarketplace.price_zen)).filter(
        NFTMarketplace.is_active == True
    ).scalar() or 0

    # --- Daily NFT trade volume ---
    daily_nft_stats = []
    for i in range(min(days, 30)):
        day = (now - timedelta(days=i)).date()

        day_trades = db.session.query(
            func.count(NFTTradeHistory.id),
            func.sum(NFTTradeHistory.price_zen)
        ).filter(
            NFTTradeHistory.trade_type == 'sale',
            cast(NFTTradeHistory.traded_at, Date) == day
        ).first()

        trade_count = day_trades[0] or 0
        trade_volume = float(day_trades[1] or 0)
        day_fees = trade_volume * (marketplace_fee_bps / 10000)

        daily_nft_stats.append({
            'date': day.strftime('%Y-%m-%d'),
            'trades': trade_count,
            'volume_zen': trade_volume,
            'fees_earned': day_fees
        })
    daily_nft_stats.reverse()

    # --- Revenue Summary ---
    # Total revenue = ZEN spread earnings + NFT marketplace fees
    # ZEN spread is already captured in net_gold_from_zen (buy price > sell price)
    zen_spread_earnings = net_gold_from_zen

    # Convert ZEN fees to Gold equivalent for total
    fees_earned_gold = fees_earned_zen * current_zen_buy_price

    total_revenue_gold = zen_spread_earnings + fees_earned_gold

    # --- Recent ZEN Transactions ---
    recent_zen_txs = db.session.query(ZenTransaction).order_by(
        desc(ZenTransaction.created_at)
    ).limit(20).all()

    # --- Recent NFT Trades ---
    recent_nft_trades = db.session.query(NFTTradeHistory).filter(
        NFTTradeHistory.trade_type == 'sale'
    ).order_by(desc(NFTTradeHistory.traded_at)).limit(20).all()

    # --- Period Comparison ---
    # Compare with previous period
    prev_period_start = period_start - timedelta(days=days)

    prev_zen_buys = db.session.query(func.sum(ZenTransaction.gold_amount)).filter(
        ZenTransaction.transaction_type == 'buy',
        ZenTransaction.created_at >= prev_period_start,
        ZenTransaction.created_at < period_start
    ).scalar() or 0

    prev_zen_sells = db.session.query(func.sum(ZenTransaction.gold_amount)).filter(
        ZenTransaction.transaction_type == 'sell',
        ZenTransaction.created_at >= prev_period_start,
        ZenTransaction.created_at < period_start
    ).scalar() or 0

    prev_net_gold = float(prev_zen_buys) - float(prev_zen_sells)

    zen_change_percent = ((net_gold_from_zen - prev_net_gold) / prev_net_gold * 100) if prev_net_gold != 0 else 0

    return render_template('admin/economy_reports.html',
                         title='Economy Reports',
                         period=days,
                         # ZEN Stats
                         current_zen_buy_price=current_zen_buy_price,
                         current_zen_sell_price=current_zen_sell_price,
                         zen_bought_amount=zen_bought_amount,
                         gold_spent_on_zen=gold_spent_on_zen,
                         zen_buy_count=zen_buy_count,
                         zen_sold_amount=zen_sold_amount,
                         gold_received_from_zen=gold_received_from_zen,
                         zen_sell_count=zen_sell_count,
                         net_gold_from_zen=net_gold_from_zen,
                         daily_zen_stats=daily_zen_stats,
                         zen_change_percent=round(zen_change_percent, 1),
                         # NFT Minting
                         nfts_minted=nfts_minted,
                         nfts_dropped=nfts_dropped,
                         nfts_upgraded=nfts_upgraded,
                         nft_by_tier=nft_by_tier,
                         # NFT Trading
                         marketplace_fee_percent=marketplace_fee_percent,
                         nft_trade_count=nft_trade_count,
                         total_trade_volume_zen=total_trade_volume_zen,
                         fees_earned_zen=fees_earned_zen,
                         avg_trade_price=avg_trade_price,
                         active_listings=active_listings,
                         total_listing_value=float(total_listing_value or 0),
                         daily_nft_stats=daily_nft_stats,
                         # Revenue
                         zen_spread_earnings=zen_spread_earnings,
                         fees_earned_gold=fees_earned_gold,
                         total_revenue_gold=total_revenue_gold,
                         # Recent transactions
                         recent_zen_txs=recent_zen_txs,
                         recent_nft_trades=recent_nft_trades)
