# app/main/mission_routes.py
# Routes for viewing and managing user missions

from flask import render_template, jsonify, request, flash, redirect, url_for
from flask_login import current_user, login_required
from app.main import bp
from app.services.mission_service import MissionService
from app.extensions import db


@bp.route('/missions')
@login_required
def missions():
    """Display user's missions page."""
    # Ensure missions are assigned
    MissionService.ensure_missions_assigned(current_user)
    db.session.commit()

    # Get active missions grouped by type
    active_missions = MissionService.get_active_missions(current_user)

    # Get mission stats
    stats = MissionService.get_mission_stats(current_user)

    # Get completed unclaimed missions
    completed_unclaimed = MissionService.get_completed_unclaimed(current_user)

    return render_template(
        'missions.html',
        daily_missions=active_missions['daily'],
        weekly_missions=active_missions['weekly'],
        tutorial_missions=active_missions['tutorial'],
        stats=stats,
        completed_unclaimed=completed_unclaimed
    )


@bp.route('/missions/<int:user_mission_id>/claim', methods=['POST'])
@login_required
def claim_mission(user_mission_id):
    """Claim reward for a completed mission."""
    result = MissionService.claim_reward(current_user, user_mission_id)
    db.session.commit()

    if result['success']:
        # Build reward message
        rewards = result['rewards']
        reward_parts = []
        if rewards['gold'] > 0:
            reward_parts.append(f"{rewards['gold']:.2f} gold")
        if rewards['xp'] > 0:
            reward_parts.append(f"{rewards['xp']} XP")
        for item in rewards['items']:
            reward_parts.append(f"{item['quantity']}x {item['resource_name']}")

        reward_msg = ", ".join(reward_parts) if reward_parts else "rewards"

        if result['leveled_up']:
            flash(f'Mission complete! You earned {reward_msg} and leveled up to {result["new_level"]}!', 'success')
        else:
            flash(f'Mission complete! You earned {reward_msg}.', 'success')
    else:
        flash(result['message'], 'error')

    return redirect(url_for('main.missions'))


@bp.route('/api/missions')
@login_required
def api_missions():
    """API endpoint for fetching user's mission data."""
    # Ensure missions are assigned
    MissionService.ensure_missions_assigned(current_user)
    db.session.commit()

    active_missions = MissionService.get_active_missions(current_user)
    stats = MissionService.get_mission_stats(current_user)

    def serialize_mission(um):
        return {
            'id': um.id,
            'mission_id': um.mission.id,
            'code': um.mission.code,
            'name': um.mission.name,
            'description': um.mission.description,
            'mission_type': um.mission.mission_type,
            'category': um.mission.category,
            'icon': um.mission.icon,
            'action_type': um.mission.action_type,
            'requirement_count': um.mission.requirement_count,
            'current_progress': um.current_progress,
            'progress_percent': um.progress_percent,
            'is_completed': um.is_completed,
            'is_claimed': um.is_claimed,
            'expires_at': um.expires_at.isoformat() if um.expires_at else None,
            'rewards': {
                'gold': float(um.mission.gold_reward) if um.mission.gold_reward else 0,
                'xp': um.mission.xp_reward or 0,
                'resource': {
                    'id': um.mission.resource_reward_id,
                    'name': um.mission.resource_reward.name if um.mission.resource_reward else None,
                    'quantity': um.mission.resource_reward_quantity,
                    'quality': um.mission.resource_reward_quality
                } if um.mission.resource_reward_id else None
            }
        }

    return jsonify({
        'stats': stats,
        'daily': [serialize_mission(um) for um in active_missions['daily']],
        'weekly': [serialize_mission(um) for um in active_missions['weekly']],
        'tutorial': [serialize_mission(um) for um in active_missions['tutorial']]
    })


@bp.route('/api/missions/<int:user_mission_id>/claim', methods=['POST'])
@login_required
def api_claim_mission(user_mission_id):
    """API endpoint for claiming mission reward."""
    result = MissionService.claim_reward(current_user, user_mission_id)
    db.session.commit()

    return jsonify(result)


@bp.route('/api/missions/check')
@login_required
def api_check_missions():
    """API endpoint for checking newly completed missions (for AJAX updates)."""
    completed_unclaimed = MissionService.get_completed_unclaimed(current_user)

    return jsonify({
        'completed_count': len(completed_unclaimed),
        'missions': [{
            'id': um.id,
            'name': um.mission.name,
            'mission_type': um.mission.mission_type,
            'rewards': {
                'gold': float(um.mission.gold_reward) if um.mission.gold_reward else 0,
                'xp': um.mission.xp_reward or 0
            }
        } for um in completed_unclaimed]
    })
