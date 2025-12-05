# app/time_helpers.py
# Helper functions for time allocation system

from datetime import datetime, date, time, timedelta
from pytz import timezone
import pytz

# CET timezone
CET = timezone('Europe/Paris')  # CET/CEST timezone
RESET_HOUR = 9  # 9 AM CET


def get_current_cet_time():
    """Get current time in CET timezone."""
    return datetime.now(CET)


def get_today_date_cet():
    """Get today's date in CET timezone."""
    return get_current_cet_time().date()


def get_next_reset_time():
    """Get the next 9 AM CET reset time."""
    now = get_current_cet_time()

    # Create 9 AM today in CET
    reset_today = CET.localize(datetime.combine(now.date(), time(RESET_HOUR, 0, 0)))

    # If current time is before 9 AM, reset is today
    if now < reset_today:
        return reset_today

    # Otherwise, reset is tomorrow at 9 AM
    reset_tomorrow = reset_today + timedelta(days=1)
    return reset_tomorrow


def get_time_until_reset():
    """Get timedelta until next reset."""
    now = get_current_cet_time()
    next_reset = get_next_reset_time()
    return next_reset - now


def format_time_remaining(td):
    """Format timedelta as 'Xh Ym' string."""
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours}h {minutes}m"


def get_allocation_date():
    """
    Get the current allocation date (which day's allocation we're working with).
    The game day changes at 9 AM CET, not midnight.

    Before 9 AM CET: returns yesterday's date (still in previous game day)
    After 9 AM CET: returns today's date (new game day has started)
    """
    now = get_current_cet_time()

    # If before 9 AM CET, we're still in "yesterday's" game day
    if now.hour < RESET_HOUR:
        return (now - timedelta(days=1)).date()

    return now.date()


def get_game_day_start():
    """
    Get the UTC datetime of the current game day's start (9 AM CET).

    The game day starts at 9 AM CET. This function returns the UTC datetime
    of when the current game day started.

    Returns:
        datetime: UTC datetime of game day start
    """
    now = get_current_cet_time()

    # Get 9 AM CET for today
    reset_today = CET.localize(datetime.combine(now.date(), time(RESET_HOUR, 0, 0)))

    # If before 9 AM CET, game day started yesterday at 9 AM
    if now < reset_today:
        game_day_start_cet = reset_today - timedelta(days=1)
    else:
        game_day_start_cet = reset_today

    # Convert to UTC
    return game_day_start_cet.astimezone(pytz.UTC).replace(tzinfo=None)


def get_week_start():
    """
    Get the UTC datetime of the current week's start (Monday 9 AM CET).

    Weekly missions reset on Monday at 9 AM CET.

    Returns:
        datetime: UTC datetime of week start
    """
    now = get_current_cet_time()

    # Get Monday 9 AM CET this week
    days_since_monday = now.weekday()
    monday_date = now.date() - timedelta(days=days_since_monday)
    monday_9am = CET.localize(datetime.combine(monday_date, time(RESET_HOUR, 0, 0)))

    # If we're before this Monday 9 AM, use last week's Monday
    if now < monday_9am:
        monday_9am -= timedelta(weeks=1)

    # Convert to UTC
    return monday_9am.astimezone(pytz.UTC).replace(tzinfo=None)


def get_next_week_start():
    """
    Get the UTC datetime of the next week's start (Monday 9 AM CET).

    Returns:
        datetime: UTC datetime of next week start
    """
    return get_week_start() + timedelta(weeks=1)
