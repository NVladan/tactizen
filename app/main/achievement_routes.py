# app/main/achievement_routes.py
# Routes for viewing and managing user achievements

from flask import render_template, jsonify
from flask_login import current_user, login_required
from app.main import bp
from app.services.achievement_service import AchievementService


@bp.route('/profile/achievements')
@login_required
def achievements():
    """Display user's achievements page."""
    stats = AchievementService.get_achievement_stats(current_user)
    achievements_with_progress = AchievementService.get_all_achievements_with_progress(current_user)

    # Group achievements by category
    achievements_by_category = {}
    for item in achievements_with_progress:
        category = item['achievement'].category
        if category not in achievements_by_category:
            achievements_by_category[category] = []
        achievements_by_category[category].append(item)

    return render_template(
        'achievements.html',
        stats=stats,
        achievements_by_category=achievements_by_category
    )


@bp.route('/api/achievements')
@login_required
def api_achievements():
    """API endpoint for fetching user's achievement data."""
    stats = AchievementService.get_achievement_stats(current_user)
    achievements_with_progress = AchievementService.get_all_achievements_with_progress(current_user)

    return jsonify({
        'stats': stats,
        'achievements': [{
            'id': item['achievement'].id,
            'code': item['achievement'].code,
            'name': item['achievement'].name,
            'description': item['achievement'].description,
            'category': item['achievement'].category,
            'icon': item['achievement'].icon,
            'gold_reward': item['achievement'].gold_reward,
            'requirement': item['requirement'],
            'current_value': item['current_value'],
            'progress_percentage': item['progress_percentage'],
            'unlocked': item['unlocked'],
            'unlocked_at': item['unlocked_at'].isoformat() if item['unlocked_at'] else None
        } for item in achievements_with_progress]
    })
