# app/main/__init__.py
from flask import Blueprint
from datetime import datetime

# Create the main blueprint instance
bp = Blueprint('main', __name__)

def format_number(value):
    """Format a number with commas as thousand separators"""
    try:
        return "{:,}".format(int(value))
    except (ValueError, TypeError):
        return value

def timesince(dt):
    """
    Convert a datetime to a human-readable "time since" string.
    E.g., "5 minutes ago", "2 hours ago", "3 days ago"
    """
    if dt is None:
        return "Never"

    now = datetime.utcnow()
    diff = now - dt

    seconds = diff.total_seconds()

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    elif seconds < 2592000:
        weeks = int(seconds / 604800)
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    else:
        months = int(seconds / 2592000)
        return f"{months} month{'s' if months != 1 else ''} ago"

# Register the custom filters
bp.add_app_template_filter(format_number)
bp.add_app_template_filter(timesince)

# Import routes at the end to avoid circular dependencies
# Remove the old market_routes and import the new ones
from app.main import routes, profile_routes, my_places_routes, location_routes, company_routes # noqa
from app.main import resource_market_routes, currency_market_routes, zen_market_routes, zen_market_api, messaging_routes # noqa
from app.main import newspaper_routes, newspaper_image_upload, achievement_routes, battle_routes # noqa