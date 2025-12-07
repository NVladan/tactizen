# app/main/battle_routes.py
"""
Battle Routes

Routes for the war and battle system:
- /wars - List active wars
- /war/<id> - War details with battles
- /battle/<id> - Battle screen with 3 walls
- /battle/<id>/fight - POST to deal damage
- /battle/<id>/start - POST to start a battle
"""

from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

from app.main import bp
from app.extensions import db
from app.models import (
    War, Battle, BattleRound, BattleParticipation, BattleDamage,
    Country, Region, User, WarStatus
)
from app.models.battle import BattleStatus, RoundStatus, WallType
from app.services.battle_service import BattleService


@bp.route('/wars')
@login_required
def wars_list():
    """Display list of active wars."""
    # Get all active wars
    active_wars = War.query.filter_by(status=WarStatus.ACTIVE).all()

    # Get wars with peace proposals
    peace_wars = War.query.filter_by(status=WarStatus.PEACE_PROPOSED).all()

    # Get recent ended wars (last 10)
    ended_wars = War.query.filter(
        War.status.in_([WarStatus.ENDED_PEACE, WarStatus.ENDED_EXPIRED])
    ).order_by(War.ended_at.desc()).limit(10).all()

    # Check if user's country is involved in any active war
    user_country_id = current_user.citizenship_id
    user_country_at_war = False
    user_country_wars = []

    if user_country_id:
        for war in active_wars:
            if war.attacker_country_id == user_country_id or war.defender_country_id == user_country_id:
                user_country_at_war = True
                user_country_wars.append(war)

    return render_template(
        'battle/wars_list.html',
        active_wars=active_wars,
        peace_wars=peace_wars,
        ended_wars=ended_wars,
        user_country_at_war=user_country_at_war,
        user_country_wars=user_country_wars,
        now=datetime.utcnow()
    )


@bp.route('/war/<int:war_id>')
@login_required
def war_detail(war_id):
    """Display war details and battles."""
    war = War.query.get_or_404(war_id)

    # Get active battle if any
    active_battle = war.get_active_battle()

    # Get past battles
    past_battles = Battle.query.filter(
        Battle.war_id == war_id,
        Battle.status != BattleStatus.ACTIVE
    ).order_by(Battle.ended_at.desc()).all()

    # Check if current user can start a battle
    can_start_battle = False
    attackable_regions = []

    if war.is_active():
        user_country_id = current_user.citizenship_id

        # Only check permissions if user has citizenship
        if user_country_id:
            # Check if user is president or minister of defence
            is_president = current_user.is_president_of(user_country_id)
            is_defence_minister = current_user.is_minister_of(user_country_id, 'defence')

            if (is_president or is_defence_minister) and war.can_country_attack(user_country_id):
                can_start_battle = True
                attackable_regions = BattleService.get_attackable_regions(war, user_country_id)

    # Get initiative info
    initiative_info = None
    if war.initiative_holder_id:
        initiative_holder = Country.query.get(war.initiative_holder_id)
        initiative_info = {
            'holder': initiative_holder,
            'expires_at': war.initiative_expires_at,
            'is_expired': war.initiative_expires_at and datetime.utcnow() >= war.initiative_expires_at
        }

    return render_template(
        'battle/war_detail.html',
        war=war,
        active_battle=active_battle,
        past_battles=past_battles,
        can_start_battle=can_start_battle,
        attackable_regions=attackable_regions,
        initiative_info=initiative_info,
        now=datetime.utcnow()
    )


@bp.route('/war/<int:war_id>/start-battle', methods=['POST'])
@login_required
def start_battle(war_id):
    """Start a new battle."""
    war = War.query.get_or_404(war_id)

    region_id = request.form.get('region_id', type=int)
    if not region_id:
        flash('Please select a region to attack.', 'danger')
        return redirect(url_for('main.war_detail', war_id=war_id))

    region = Region.query.get_or_404(region_id)

    # Determine attacking country (user's citizenship)
    attacking_country_id = current_user.citizenship_id
    if not attacking_country_id:
        flash('You must have citizenship to start a battle.', 'danger')
        return redirect(url_for('main.war_detail', war_id=war_id))

    battle, message = BattleService.start_battle(
        war=war,
        attacking_country_id=attacking_country_id,
        target_region=region,
        user=current_user
    )

    if battle:
        flash(message, 'success')
        return redirect(url_for('main.battle_screen', battle_id=battle.id))
    else:
        flash(message, 'danger')
        return redirect(url_for('main.war_detail', war_id=war_id))


@bp.route('/battle/<int:battle_id>')
@login_required
def battle_screen(battle_id):
    """Display battle screen with 3 walls."""
    battle = Battle.query.get_or_404(battle_id)
    current_round = battle.get_current_round()
    war = battle.war

    # Determine user's side
    can_fight, is_attacker, side_message = BattleService.determine_user_side(current_user, battle)

    # Check if this is a resistance war and user needs to choose side
    needs_side_choice = False
    if war.is_resistance_war and side_message == "CHOOSE_SIDE":
        needs_side_choice = True
        side_message = ""  # Clear the internal message

    # Get user's participation in current round
    participation = None
    if current_round:
        participation = BattleParticipation.query.filter_by(
            battle_id=battle.id,
            round_number=current_round.round_number,
            user_id=current_user.id
        ).first()

    # Get user's weapons for each wall type
    user_weapons = {}
    available_weapons = {}
    for wall_type in WallType:
        resource_id, quality = BattleService.get_best_weapon(current_user, wall_type)
        user_weapons[wall_type.value] = {
            'has_weapon': quality is not None,
            'quality': quality
        }
        available_weapons[wall_type.value] = BattleService.get_available_weapons(current_user, wall_type)

    # Get leaderboards for current round
    leaderboards = {}
    if current_round:
        for wall_type in WallType:
            leaderboards[wall_type.value] = {
                'attacker': BattleService.get_battle_leaderboard(battle_id, wall_type, True, 1),
                'defender': BattleService.get_battle_leaderboard(battle_id, wall_type, False, 1)
            }

    # Get recent damage records (last 15 seconds shown on screen)
    recent_damage = BattleService.get_recent_damage(battle_id, 20)

    # Calculate wall progress percentages for visual display
    wall_progress = {}
    if current_round:
        for wall_type in WallType:
            damage_diff = current_round.get_wall_damage(wall_type)
            # Scale to -100 to +100 range (50000 = full bar)
            progress = max(-100, min(100, (damage_diff / 500) * 100))
            wall_progress[wall_type.value] = {
                'damage_diff': damage_diff,
                'progress': progress,  # -100 to +100
                'attacker_leads': damage_diff > 0,
                'defender_leads': damage_diff < 0
            }

    # Check fight cooldown
    can_fight_now = True
    cooldown_remaining = 0
    if participation and not participation.can_fight:
        can_fight_now = False
        cooldown_remaining = participation.cooldown_remaining

    # Hospital information for defenders (disabled in resistance wars)
    from app.models import RegionalConstruction
    from datetime import timedelta

    hospital = RegionalConstruction.get_region_hospital(battle.region_id)
    fortress = RegionalConstruction.get_region_fortress(battle.region_id)

    # Check if user can use hospital (defender side, has participated, not on cooldown)
    # Hospitals are disabled in resistance wars
    can_use_hospital = False
    hospital_cooldown_remaining = 0
    hospital_info = None

    if hospital and not is_attacker and can_fight and not war.is_resistance_war:
        hospital_info = {
            'quality': hospital.quality,
            'wellness_restore': hospital.quality * 10
        }
        # Check if user has participated in this battle
        any_participation = BattleParticipation.query.filter_by(
            battle_id=battle.id,
            user_id=current_user.id
        ).first()

        if any_participation:
            # Check cooldown
            if current_user.last_hospital_use:
                cooldown_end = current_user.last_hospital_use + timedelta(hours=6)
                if datetime.utcnow() < cooldown_end:
                    hospital_cooldown_remaining = int((cooldown_end - datetime.utcnow()).total_seconds())
                else:
                    can_use_hospital = True
            else:
                can_use_hospital = True

    # Fortress info for display (reduces attacker damage)
    # Fortresses are disabled in resistance wars
    fortress_info = None
    if fortress and not war.is_resistance_war:
        fortress_info = {
            'quality': fortress.quality,
            'damage_reduction': fortress.quality * 5  # Q1=5%, Q2=10%, etc.
        }

    return render_template(
        'battle/battle_screen.html',
        battle=battle,
        current_round=current_round,
        can_fight=can_fight,
        is_attacker=is_attacker,
        side_message=side_message,
        participation=participation,
        user_weapons=user_weapons,
        available_weapons=available_weapons,
        leaderboards=leaderboards,
        recent_damage=recent_damage,
        wall_progress=wall_progress,
        can_fight_now=can_fight_now,
        cooldown_remaining=cooldown_remaining,
        WallType=WallType,
        hospital_info=hospital_info,
        can_use_hospital=can_use_hospital,
        hospital_cooldown_remaining=hospital_cooldown_remaining,
        fortress_info=fortress_info,
        is_resistance_war=war.is_resistance_war,
        needs_side_choice=needs_side_choice,
        resistance_country=war.resistance_country if war.is_resistance_war else None,
        occupying_country=war.defender_country if war.is_resistance_war else None
    )


@bp.route('/battle/<int:battle_id>/choose-side', methods=['POST'])
@login_required
def choose_side(battle_id):
    """Choose a side for resistance war battles."""
    battle = Battle.query.get_or_404(battle_id)
    war = battle.war

    if not war.is_resistance_war:
        flash('Side selection is only available for resistance wars.', 'danger')
        return redirect(url_for('main.battle_screen', battle_id=battle_id))

    side = request.form.get('side')
    if side not in ['resistance', 'occupier']:
        flash('Invalid side selection.', 'danger')
        return redirect(url_for('main.battle_screen', battle_id=battle_id))

    is_attacker = side == 'resistance'

    # Store the choice in session for the fight action
    from flask import session
    session[f'battle_{battle_id}_side'] = is_attacker

    if is_attacker:
        flash(f'You are fighting for the resistance! Help liberate this region for {war.resistance_country.name}!', 'success')
    else:
        flash(f'You are fighting for {war.defender_country.name}! Defend this territory!', 'success')

    return redirect(url_for('main.battle_screen', battle_id=battle_id))


@bp.route('/battle/<int:battle_id>/fight', methods=['POST'])
@login_required
def fight(battle_id):
    """Execute a fight action."""
    battle = Battle.query.get_or_404(battle_id)
    war = battle.war

    # For resistance wars, check if we have a chosen side
    chosen_side = None
    if war.is_resistance_war:
        from flask import session
        chosen_side = session.get(f'battle_{battle_id}_side')

    # Get wall type from form
    wall_type_str = request.form.get('wall_type', 'infantry')
    try:
        wall_type = WallType(wall_type_str)
    except ValueError:
        wall_type = WallType.INFANTRY

    # Check if user wants to use weapon and which quality
    use_weapon = request.form.get('use_weapon', 'true').lower() == 'true'
    weapon_quality = request.form.get('weapon_quality')
    if weapon_quality:
        try:
            weapon_quality = int(weapon_quality)
        except ValueError:
            weapon_quality = None

    # Execute fight (pass chosen_side for resistance wars)
    success, message, damage_info = BattleService.fight(
        user=current_user,
        battle=battle,
        wall_type=wall_type,
        use_weapon=use_weapon,
        preferred_quality=weapon_quality,
        chosen_side=chosen_side
    )

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # AJAX request - return JSON
        if success:
            # Get updated weapon counts
            updated_weapons = {}
            for wt in WallType:
                updated_weapons[wt.value] = BattleService.get_available_weapons(current_user, wt)

            # Get updated leaderboards for all walls
            leaderboards = {}
            for wt in WallType:
                leaderboards[wt.value] = {
                    'attacker': BattleService.get_battle_leaderboard(battle_id, wt, True, 1),
                    'defender': BattleService.get_battle_leaderboard(battle_id, wt, False, 1)
                }

            return jsonify({
                'success': True,
                'message': message,
                'damage': damage_info['damage'],
                'wall_type': damage_info['wall_type'],
                'is_attacker': damage_info['is_attacker'],
                'weapon_used': damage_info['weapon_used'],
                'weapon_quality': damage_info['weapon_quality'],
                'military_xp_gained': damage_info['military_xp_gained'],
                'leveled_up': damage_info.get('leveled_up', False),
                'new_level': damage_info.get('new_level'),
                'user_energy': float(current_user.energy),
                'user_wellness': float(current_user.wellness),
                'max_energy': int(current_user.max_energy),
                'max_wellness': int(current_user.max_wellness),
                'available_weapons': updated_weapons,
                'leaderboards': leaderboards
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
    else:
        # Regular request - redirect
        if success:
            flash(message, 'success')
        else:
            flash(message, 'danger')
        return redirect(url_for('main.battle_screen', battle_id=battle_id))


@bp.route('/battle/<int:battle_id>/status')
@login_required
def battle_status(battle_id):
    """Get battle status for AJAX polling."""
    battle = Battle.query.get_or_404(battle_id)
    current_round = battle.get_current_round()

    # Get participation for cooldown
    participation = None
    if current_round:
        participation = BattleParticipation.query.filter_by(
            battle_id=battle.id,
            round_number=current_round.round_number,
            user_id=current_user.id
        ).first()

    # Build wall status
    wall_status = {}
    if current_round:
        for wall_type in WallType:
            damage_diff = current_round.get_wall_damage(wall_type)
            progress = max(-100, min(100, (damage_diff / 500) * 100))
            wall_status[wall_type.value] = {
                'damage_diff': damage_diff,
                'progress': progress
            }

    # Get recent damage (last 15 seconds)
    recent_damage = BattleService.get_recent_damage(battle_id, 10)

    # Get available weapons for each wall type
    available_weapons = {}
    for wall_type in WallType:
        available_weapons[wall_type.value] = BattleService.get_available_weapons(current_user, wall_type)

    # Get leaderboards for each wall (top 3)
    leaderboards = {}
    for wall_type in WallType:
        leaderboards[wall_type.value] = {
            'attacker': BattleService.get_battle_leaderboard(battle_id, wall_type, True, 1),
            'defender': BattleService.get_battle_leaderboard(battle_id, wall_type, False, 1)
        }

    return jsonify({
        'battle_status': battle.status.value,
        'current_round': current_round.round_number if current_round else 0,
        'round_status': current_round.status.value if current_round else 'completed',
        'attacker_rounds_won': battle.attacker_rounds_won,
        'defender_rounds_won': battle.defender_rounds_won,
        'wall_status': wall_status,
        'recent_damage': recent_damage,
        'cooldown_remaining': participation.cooldown_remaining if participation else 0,
        'user_energy': current_user.energy,
        'user_wellness': current_user.wellness,
        'max_energy': int(current_user.max_energy),
        'max_wellness': int(current_user.max_wellness),
        'available_weapons': available_weapons,
        'leaderboards': leaderboards,
        'round_ends_at': current_round.ends_at.isoformat() + 'Z' if current_round and current_round.ends_at else None,
        'battle_ends_at': battle.ends_at.isoformat() + 'Z' if battle.ends_at else None
    })


@bp.route('/battle/<int:battle_id>/leaderboard/<wall_type>')
@login_required
def battle_leaderboard(battle_id, wall_type):
    """Get leaderboard for a specific wall."""
    battle = Battle.query.get_or_404(battle_id)

    try:
        wall = WallType(wall_type)
    except ValueError:
        return jsonify({'error': 'Invalid wall type'}), 400

    attacker_board = BattleService.get_battle_leaderboard(battle_id, wall, True, 10)
    defender_board = BattleService.get_battle_leaderboard(battle_id, wall, False, 10)

    return jsonify({
        'attacker': attacker_board,
        'defender': defender_board
    })


@bp.route('/battle/<int:battle_id>/use-hospital', methods=['POST'])
@login_required
def use_hospital(battle_id):
    """
    Use hospital in battle region to restore wellness.

    Requirements:
    - Battle must be active
    - User must have fought in this battle at least once (as defender or ally)
    - Region must have a hospital
    - User must be fighting for the defending side (defenders and their allies only)
    - 6 hour global cooldown between hospital uses

    Hospital restores: Q1=10, Q2=20, Q3=30, Q4=40, Q5=50 wellness
    """
    from datetime import timedelta
    from app.models import RegionalConstruction
    from app.services.battle_service import BattleService

    battle = Battle.query.get_or_404(battle_id)

    # Check battle is active
    if not battle.is_active:
        message = "This battle is no longer active."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': message}), 400
        flash(message, 'danger')
        return redirect(url_for('main.battle_screen', battle_id=battle_id))

    # Check if this is a resistance war (hospitals disabled in resistance wars)
    if battle.war.is_resistance_war:
        message = "Hospitals cannot be used in resistance wars."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': message}), 400
        flash(message, 'danger')
        return redirect(url_for('main.battle_screen', battle_id=battle_id))

    # Check if user is on the defending side (only defenders and their allies can use hospital)
    can_fight, is_attacker, side_message = BattleService.determine_user_side(current_user, battle)

    if not can_fight:
        message = "You cannot use the hospital in this battle."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': message}), 400
        flash(message, 'danger')
        return redirect(url_for('main.battle_screen', battle_id=battle_id))

    if is_attacker:
        message = "Only defenders and their allies can use the hospital."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': message}), 400
        flash(message, 'danger')
        return redirect(url_for('main.battle_screen', battle_id=battle_id))

    # Check if user has participated in this battle (fought at least once)
    participation = BattleParticipation.query.filter_by(
        battle_id=battle.id,
        user_id=current_user.id
    ).first()

    if not participation:
        message = "You must fight in this battle at least once before using the hospital."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': message}), 400
        flash(message, 'danger')
        return redirect(url_for('main.battle_screen', battle_id=battle_id))

    # Check for hospital in the battle's region
    hospital = RegionalConstruction.get_region_hospital(battle.region_id)
    if not hospital:
        message = "There is no hospital in this region."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': message}), 400
        flash(message, 'danger')
        return redirect(url_for('main.battle_screen', battle_id=battle_id))

    # Check 6 hour global cooldown
    if current_user.last_hospital_use:
        cooldown_end = current_user.last_hospital_use + timedelta(hours=6)
        if datetime.utcnow() < cooldown_end:
            remaining = cooldown_end - datetime.utcnow()
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            message = f"Hospital cooldown: {hours}h {minutes}m remaining."
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': message,
                    'cooldown_remaining': int(remaining.total_seconds())
                }), 400
            flash(message, 'danger')
            return redirect(url_for('main.battle_screen', battle_id=battle_id))

    # Calculate wellness restoration based on hospital quality
    # Q1=10, Q2=20, Q3=30, Q4=40, Q5=50
    wellness_restore = hospital.quality * 10

    # Get user's max wellness (based on house quality and other bonuses)
    max_wellness = current_user.max_wellness

    # Check if user already has max wellness
    if current_user.wellness >= max_wellness:
        message = "Your wellness is already at maximum."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': message}), 400
        flash(message, 'warning')
        return redirect(url_for('main.battle_screen', battle_id=battle_id))

    # Calculate actual restoration (cannot exceed max)
    old_wellness = current_user.wellness
    new_wellness = min(max_wellness, current_user.wellness + wellness_restore)
    actual_restore = new_wellness - old_wellness

    # Apply the restoration
    current_user.wellness = new_wellness
    current_user.last_hospital_use = datetime.utcnow()

    try:
        db.session.commit()
        message = f"Hospital restored {actual_restore:.0f} wellness (Q{hospital.quality}). Wellness: {new_wellness:.0f}/{max_wellness:.0f}"

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': message,
                'wellness_restored': actual_restore,
                'new_wellness': new_wellness,
                'max_wellness': max_wellness,
                'hospital_quality': hospital.quality,
                'cooldown_seconds': 6 * 3600  # 6 hours in seconds
            })

        flash(message, 'success')

    except Exception as e:
        db.session.rollback()
        message = "An error occurred while using the hospital."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': message}), 500
        flash(message, 'danger')

    return redirect(url_for('main.battle_screen', battle_id=battle_id))


# ====================
# RESISTANCE WAR ROUTES
# ====================

@bp.route('/region/<slug>/start-resistance', methods=['POST'])
@login_required
def start_resistance_war(slug):
    """
    Start a resistance war in a conquered region.

    Requirements:
    - User must be located in the conquering country (current region's owner)
    - Region must be conquered (current owner != original owner)
    - No active resistance war for the original country
    - User must have 30 Gold
    """
    from decimal import Decimal
    from flask import current_app
    from app.models import WarType

    region = Region.query.filter_by(slug=slug, is_deleted=False).first_or_404()
    current_owner = region.current_owner
    original_owner = region.original_owner

    # Check if region is conquered (current owner != original owner)
    if not current_owner or current_owner.id == original_owner.id:
        flash('This region is not conquered territory. Resistance wars can only be started in occupied regions.', 'danger')
        return redirect(url_for('main.region', slug=slug))

    # Check if user is located in the conquering country
    user_location = current_user.current_region
    if not user_location:
        flash('You must be located in a region to start a resistance war.', 'danger')
        return redirect(url_for('main.region', slug=slug))

    user_location_owner = user_location.current_owner
    if not user_location_owner or user_location_owner.id != current_owner.id:
        flash(f'You must be located in {current_owner.name} to start a resistance war here.', 'danger')
        return redirect(url_for('main.region', slug=slug))

    # Check if there's already an active resistance war for the original country
    existing_resistance = War.query.filter(
        War.is_resistance_war == True,
        War.resistance_country_id == original_owner.id,
        War.status == WarStatus.ACTIVE
    ).first()

    if existing_resistance:
        flash(f'There is already an active resistance war for {original_owner.name}. Only one resistance war can be active per country.', 'warning')
        return redirect(url_for('main.region', slug=slug))

    # Check if there's ANY active battle on this region (region lock)
    active_battle_on_region = Battle.query.filter(
        Battle.region_id == region.id,
        Battle.status == BattleStatus.ACTIVE
    ).first()

    if active_battle_on_region:
        flash(f'There is already an active battle for {region.name}. Wait for it to end before starting a new war.', 'warning')
        return redirect(url_for('main.region', slug=slug))

    # Check if user has enough Gold (30 Gold)
    cost = Decimal('30.0')
    if current_user.gold < cost:
        flash(f'You need 30 Gold to start a resistance war. You have {current_user.gold:.2f} Gold.', 'danger')
        return redirect(url_for('main.region', slug=slug))

    # Deduct Gold from user
    current_user.gold -= cost
    current_user.resistance_wars_started += 1

    # Create the resistance war
    from datetime import timedelta
    now = datetime.utcnow()

    resistance_war = War(
        # In resistance wars: attacker = resistance (original owner), defender = occupying country
        attacker_country_id=original_owner.id,
        defender_country_id=current_owner.id,
        status=WarStatus.ACTIVE,
        war_type=WarType.RESISTANCE,
        is_resistance_war=True,
        resistance_region_id=region.id,
        resistance_started_by_user_id=current_user.id,
        resistance_country_id=original_owner.id,
        declared_by_law_id=None,
        started_at=now,
        scheduled_end_at=now + timedelta(days=7),  # Resistance wars last 7 days max
        initiative_holder_id=original_owner.id,
        initiative_expires_at=now + timedelta(hours=24),
        initiative_lost=False
    )
    db.session.add(resistance_war)
    db.session.flush()  # Get the war ID

    # Create the initial battle for this resistance war
    battle = Battle(
        war_id=resistance_war.id,
        region_id=region.id,
        started_by_country_id=original_owner.id,
        started_by_user_id=current_user.id,
        status=BattleStatus.ACTIVE,
        current_round=1,
        started_at=now,
        ends_at=now + timedelta(hours=24)  # Battle lasts 24 hours
    )
    db.session.add(battle)
    db.session.flush()

    # Create only the first round - subsequent rounds are created when needed
    # This matches the regular battle behavior and avoids timing issues
    first_round = BattleRound(
        battle_id=battle.id,
        round_number=1,
        status=RoundStatus.ACTIVE,
        started_at=now,
        ends_at=now + timedelta(hours=8)
    )
    db.session.add(first_round)

    try:
        db.session.commit()
        flash(f'Resistance war started! Fight to liberate {region.name} for {original_owner.name}!', 'success')
        return redirect(url_for('main.battle_screen', battle_id=battle.id))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error starting resistance war: {e}")
        flash('An error occurred while starting the resistance war.', 'danger')
        return redirect(url_for('main.region', slug=slug))


@bp.route('/region/<slug>/resistance-status')
@login_required
def resistance_status(slug):
    """Get resistance war status for a region (AJAX endpoint)."""
    region = Region.query.filter_by(slug=slug, is_deleted=False).first_or_404()
    current_owner = region.current_owner
    original_owner = region.original_owner

    # Check if region is conquered
    is_conquered = current_owner and current_owner.id != original_owner.id

    # Check for active resistance war
    active_resistance = None
    active_battle = None
    if is_conquered:
        active_resistance = War.query.filter(
            War.is_resistance_war == True,
            War.resistance_region_id == region.id,
            War.status == WarStatus.ACTIVE
        ).first()

        if active_resistance:
            active_battle = Battle.query.filter(
                Battle.war_id == active_resistance.id,
                Battle.status == BattleStatus.ACTIVE
            ).first()

    # Check if user can start resistance war
    can_start = False
    start_error = None

    if is_conquered:
        # Check if user is in the conquering country
        user_location = current_user.current_region
        if user_location:
            user_location_owner = user_location.current_owner
            if user_location_owner and user_location_owner.id == current_owner.id:
                # Check no active resistance war for this country
                existing = War.query.filter(
                    War.is_resistance_war == True,
                    War.resistance_country_id == original_owner.id,
                    War.status == WarStatus.ACTIVE
                ).first()
                if existing:
                    start_error = f'Resistance war already active for {original_owner.name}'
                elif current_user.gold < 30:
                    start_error = 'Need 30 Gold to start'
                else:
                    can_start = True
            else:
                start_error = f'Must be in {current_owner.name}'
        else:
            start_error = 'No location set'
    else:
        start_error = 'Region not conquered'

    return jsonify({
        'is_conquered': is_conquered,
        'original_owner': {'id': original_owner.id, 'name': original_owner.name} if original_owner else None,
        'current_owner': {'id': current_owner.id, 'name': current_owner.name} if current_owner else None,
        'can_start': can_start,
        'start_error': start_error,
        'active_resistance': {
            'id': active_resistance.id,
            'started_at': active_resistance.started_at.isoformat() + 'Z'
        } if active_resistance else None,
        'active_battle': {
            'id': active_battle.id,
            'ends_at': active_battle.ends_at.isoformat() + 'Z'
        } if active_battle else None
    })
