"""Activity tracking middleware and utilities."""

from datetime import datetime, timedelta
from flask import request, g
from flask_login import current_user
from app.models import ActivityLog, ActivityType
from app.extensions import db


def track_page_view():
    if request.endpoint in ('static', None):
        return

    if request.is_json or request.endpoint and request.endpoint.startswith('api'):
        return

    if current_user.is_authenticated:
        try:
            current_user.last_seen = datetime.utcnow()
            current_user.page_views = (current_user.page_views or 0) + 1
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            import logging
            logging.error(f"Error tracking page view: {e}")


def log_activity(activity_type, details=None, user_id=None):
    try:
        if user_id is None and current_user.is_authenticated:
            user_id = current_user.id

        ip_address = request.remote_addr if request else None
        user_agent = request.user_agent.string[:255] if request and request.user_agent else None
        endpoint = request.endpoint if request else None
        method = request.method if request else None

        activity = ActivityLog.log_activity(
            activity_type=activity_type,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            endpoint=endpoint,
            method=method,
            details=details
        )

        db.session.commit()
        return activity

    except Exception as e:
        db.session.rollback()
        import logging
        logging.error(f"Error logging activity: {e}", exc_info=True)
        return None


def track_login(user):
    try:
        user.last_login = datetime.utcnow()
        user.last_seen = datetime.utcnow()
        user.login_count = (user.login_count or 0) + 1

        log_activity(
            activity_type=ActivityType.LOGIN,
            user_id=user.id,
            details={'username': user.username or 'N/A'}
        )

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        import logging
        logging.error(f"Error tracking login: {e}", exc_info=True)


def track_logout(user):
    try:
        log_activity(
            activity_type=ActivityType.LOGOUT,
            user_id=user.id,
            details={'username': user.username or 'N/A'}
        )

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        import logging
        logging.error(f"Error tracking logout: {e}", exc_info=True)


def get_user_stats(user_id):
    from sqlalchemy import func
    from app.models import User

    user = db.session.get(User, user_id)
    if not user:
        return None

    activity_counts = db.session.query(
        ActivityLog.activity_type,
        func.count(ActivityLog.id).label('count')
    ).filter_by(user_id=user_id).group_by(ActivityLog.activity_type).all()

    recent_activities = ActivityLog.get_user_activities(user_id, limit=10)

    days_since_joining = (datetime.utcnow() - user.created_at).days or 1

    stats = {
        'user': user,
        'total_logins': user.login_count or 0,
        'total_page_views': user.page_views or 0,
        'last_login': user.last_login,
        'last_seen': user.last_seen,
        'days_since_joining': days_since_joining,
        'avg_logins_per_day': round((user.login_count or 0) / days_since_joining, 2),
        'avg_page_views_per_day': round((user.page_views or 0) / days_since_joining, 2),
        'activity_counts': {str(ac.activity_type.value): ac.count for ac in activity_counts},
        'recent_activities': recent_activities,
        'is_online': is_user_online(user),
    }

    return stats


def is_user_online(user, threshold_minutes=5):
    if not user.last_seen:
        return False

    time_diff = datetime.utcnow() - user.last_seen
    return time_diff.total_seconds() < (threshold_minutes * 60)


def get_online_users(threshold_minutes=5):
    from app.models import User

    cutoff_time = datetime.utcnow() - timedelta(minutes=threshold_minutes)

    online_users = db.session.scalars(
        db.select(User).where(
            User.last_seen >= cutoff_time,
            User.is_deleted == False
        ).order_by(User.last_seen.desc())
    ).all()

    return online_users


def cleanup_old_activities(days=90):
    from datetime import timedelta

    cutoff_date = datetime.utcnow() - timedelta(days=days)

    deleted = db.session.query(ActivityLog).filter(
        ActivityLog.created_at < cutoff_date
    ).delete()

    db.session.commit()

    import logging
    logging.info(f"Cleaned up {deleted} old activity logs (older than {days} days)")

    return deleted
