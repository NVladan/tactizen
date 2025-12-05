# app/military_unit/routes.py
"""
Routes for Military Unit operations.
"""

import os
from datetime import datetime
from decimal import Decimal
from flask import render_template, redirect, url_for, flash, request, current_app, abort, jsonify
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from PIL import Image

from app.military_unit import bp
from app.extensions import db, limiter
from app.models import (
    User, Country, Resource, ResourceCategory, Battle, BattleStatus,
    MilitaryUnit, MilitaryUnitMember, MilitaryUnitApplication,
    MilitaryUnitInventory, MilitaryUnitTransaction, MilitaryUnitMessage,
    BountyContract, BountyContractApplication, MilitaryUnitAchievement,
    MilitaryUnitRank, BountyContractStatus, Minister, MinistryType, Alliance,
    CountryMarketItem
)
from app.military_unit.forms import (
    CreateUnitForm, EditUnitForm, UnitApplicationForm, ProcessApplicationForm,
    PromoteMemberForm, TransferCommandForm, DistributeItemForm, UnitMessageForm,
    CreateBountyForm, ApplyForBountyForm, ProcessBountyApplicationForm, ReviewBountyForm
)
from app.security import InputSanitizer


def process_unit_avatar(file_storage, unit_id):
    """Convert uploaded image to 100x100 PNG."""
    if not file_storage:
        return False, None

    avatar_folder = os.path.join(current_app.root_path, 'static', 'avatars', 'units')
    os.makedirs(avatar_folder, exist_ok=True)

    new_filename = f"unit_{unit_id}.png"
    avatar_path = os.path.join(avatar_folder, new_filename)

    try:
        img = Image.open(file_storage)
        img = img.convert('RGB')
        img = img.resize((100, 100), Image.LANCZOS)
        img.save(avatar_path, format='PNG')
        return True, new_filename
    except Exception as e:
        current_app.logger.error(f"Avatar processing error: {e}")
        return False, None


def check_and_award_achievements(unit):
    """Check and award achievements for a military unit."""
    achievements_earned = []

    # First bounty
    if unit.contracts_completed >= 1:
        if not MilitaryUnitAchievement.query.filter_by(unit_id=unit.id, achievement_type='first_bounty').first():
            achievement = MilitaryUnitAchievement(unit_id=unit.id, achievement_type='first_bounty')
            db.session.add(achievement)
            achievements_earned.append('first_bounty')

    # 1M damage
    if unit.total_damage >= 1_000_000:
        if not MilitaryUnitAchievement.query.filter_by(unit_id=unit.id, achievement_type='damage_1m').first():
            achievement = MilitaryUnitAchievement(unit_id=unit.id, achievement_type='damage_1m')
            db.session.add(achievement)
            achievements_earned.append('damage_1m')

    # 10M damage
    if unit.total_damage >= 10_000_000:
        if not MilitaryUnitAchievement.query.filter_by(unit_id=unit.id, achievement_type='damage_10m').first():
            achievement = MilitaryUnitAchievement(unit_id=unit.id, achievement_type='damage_10m')
            db.session.add(achievement)
            achievements_earned.append('damage_10m')

    # 10 contracts
    if unit.contracts_completed >= 10:
        if not MilitaryUnitAchievement.query.filter_by(unit_id=unit.id, achievement_type='contracts_10').first():
            achievement = MilitaryUnitAchievement(unit_id=unit.id, achievement_type='contracts_10')
            db.session.add(achievement)
            achievements_earned.append('contracts_10')

    # 50 contracts
    if unit.contracts_completed >= 50:
        if not MilitaryUnitAchievement.query.filter_by(unit_id=unit.id, achievement_type='contracts_50').first():
            achievement = MilitaryUnitAchievement(unit_id=unit.id, achievement_type='contracts_50')
            db.session.add(achievement)
            achievements_earned.append('contracts_50')

    # 10 battles won
    if unit.battles_won >= 10:
        if not MilitaryUnitAchievement.query.filter_by(unit_id=unit.id, achievement_type='battles_won_10').first():
            achievement = MilitaryUnitAchievement(unit_id=unit.id, achievement_type='battles_won_10')
            db.session.add(achievement)
            achievements_earned.append('battles_won_10')

    # 50 battles won
    if unit.battles_won >= 50:
        if not MilitaryUnitAchievement.query.filter_by(unit_id=unit.id, achievement_type='battles_won_50').first():
            achievement = MilitaryUnitAchievement(unit_id=unit.id, achievement_type='battles_won_50')
            db.session.add(achievement)
            achievements_earned.append('battles_won_50')

    return achievements_earned


def get_defence_authority(user):
    """
    Check if user has authority over military/bounty operations.
    Returns (authority_object, country_id, role) tuple.
    Authority is granted to: Country President or Minister of Defence.
    """
    from app.models import CountryPresident

    if not user.citizenship_id:
        return None, None, None

    # Check if user is Country President
    president = db.session.scalar(
        db.select(CountryPresident)
        .where(CountryPresident.user_id == user.id)
        .where(CountryPresident.is_current == True)
    )
    if president:
        return president.country, president.country_id, 'president'

    # Check if user is Minister of Defence
    minister = db.session.scalar(
        db.select(Minister)
        .where(Minister.user_id == user.id)
        .where(Minister.ministry_type == MinistryType.DEFENCE)
        .where(Minister.is_active == True)
    )

    if minister:
        return minister, minister.country_id, 'minister'

    return None, None, None


# ============== BROWSE & LEADERBOARD ==============

@bp.route('/')
@bp.route('/browse')
@login_required
def browse():
    """Browse all military units (show units from user's country first)."""
    page = request.args.get('page', 1, type=int)
    per_page = 20

    # Get all active units, with user's country units first
    query = db.select(MilitaryUnit).where(MilitaryUnit.is_active == True)

    # Sort by total damage (leaderboard style)
    query = query.order_by(MilitaryUnit.total_damage.desc())

    units = db.paginate(query, page=page, per_page=per_page, error_out=False)

    # Get user's unit if any
    user_unit = MilitaryUnitMember.get_user_unit(current_user.id)

    return render_template('military_unit/browse.html',
                           title='Military Units',
                           units=units,
                           user_unit=user_unit)


@bp.route('/leaderboard')
@login_required
def leaderboard():
    """Redirect to main leaderboards page with military_units tab."""
    category = request.args.get('category', 'damage')
    # Map old category names to new sort_by values
    sort_mapping = {
        'damage': 'damage',
        'battles': 'battles',
        'contracts': 'contracts'
    }
    sort_by = sort_mapping.get(category, 'damage')
    return redirect(url_for('main.leaderboards', tab='military_units', sort_by=sort_by))


# ============== UNIT CREATION ==============

@bp.route('/create', methods=['GET', 'POST'])
@login_required
@limiter.limit("5 per hour")
def create():
    """Create a new military unit (costs 20 gold)."""
    # Check if user has citizenship
    if not current_user.citizenship_id:
        flash('You must be a citizen of a country to create a military unit.', 'warning')
        return redirect(url_for('military_unit.browse'))

    # Check if user is already in a unit
    existing_membership = MilitaryUnitMember.get_user_active_membership(current_user.id)
    if existing_membership:
        flash('You are already in a military unit. Leave your current unit first.', 'warning')
        return redirect(url_for('military_unit.detail', unit_id=existing_membership.unit_id))

    # Check if user has enough gold
    if current_user.gold < Decimal('20.0'):
        flash('You need at least 20 gold to create a military unit.', 'danger')
        return redirect(url_for('military_unit.browse'))

    form = CreateUnitForm()

    if form.validate_on_submit():
        try:
            # Deduct gold with row-level locking to prevent race conditions
            from app.services.currency_service import CurrencyService
            success, message, _ = CurrencyService.deduct_gold(
                current_user.id, Decimal('20.0'), 'Military unit creation'
            )
            if not success:
                flash(f'Could not deduct gold: {message}', 'danger')
                return redirect(url_for('military_unit.browse'))

            # Create unit
            unit = MilitaryUnit(
                name=form.name.data,
                description=InputSanitizer.sanitize_description(form.description.data) if form.description.data else None,
                country_id=current_user.citizenship_id,
                commander_id=current_user.id
            )
            db.session.add(unit)
            db.session.flush()

            # Add creator as commander
            membership = MilitaryUnitMember(
                unit_id=unit.id,
                user_id=current_user.id,
                rank=MilitaryUnitRank.COMMANDER
            )
            db.session.add(membership)

            db.session.commit()

            current_app.logger.info(f"User {current_user.id} created military unit {unit.id} '{unit.name}'")
            flash(f'Military Unit "{unit.name}" created successfully! You are the commander.', 'success')
            return redirect(url_for('military_unit.detail', unit_id=unit.id))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating unit for user {current_user.id}: {e}", exc_info=True)
            flash('An error occurred while creating the unit. Please try again.', 'danger')

    return render_template('military_unit/create.html',
                           title='Create Military Unit',
                           form=form)


# ============== UNIT DETAIL ==============

@bp.route('/<int:unit_id>')
@login_required
def detail(unit_id):
    """View military unit details."""
    unit = db.session.get(MilitaryUnit, unit_id)

    if not unit or not unit.is_active:
        flash('Military unit not found.', 'danger')
        return redirect(url_for('military_unit.browse'))

    # Get all active members
    members = db.session.scalars(
        db.select(MilitaryUnitMember)
        .where(MilitaryUnitMember.unit_id == unit_id)
        .where(MilitaryUnitMember.is_active == True)
        .order_by(MilitaryUnitMember.rank, MilitaryUnitMember.damage_dealt.desc())
    ).all()

    # Check user's relationship to unit
    user_membership = None
    is_commander = False
    is_officer = False
    can_apply = False
    has_pending_application = False

    membership = MilitaryUnitMember.get_user_active_membership(current_user.id)
    if membership and membership.unit_id == unit_id:
        user_membership = membership
        is_commander = current_user.id == unit.commander_id
        is_officer = membership.rank == MilitaryUnitRank.OFFICER

    if not user_membership:
        # Check if user can apply
        if not membership:  # Not in any unit
            if current_user.citizenship_id == unit.country_id:
                can_apply = True
                # Check for pending application
                pending = MilitaryUnitApplication.query.filter_by(
                    unit_id=unit_id,
                    user_id=current_user.id,
                    status='pending'
                ).first()
                has_pending_application = pending is not None

    # Get pending applications (for commander/officers)
    pending_applications = []
    if is_commander or is_officer:
        pending_applications = db.session.scalars(
            db.select(MilitaryUnitApplication)
            .where(MilitaryUnitApplication.unit_id == unit_id)
            .where(MilitaryUnitApplication.status == 'pending')
            .order_by(MilitaryUnitApplication.created_at.asc())
        ).all()

    # Get recent messages
    recent_messages = []
    if user_membership:
        recent_messages = db.session.scalars(
            db.select(MilitaryUnitMessage)
            .where(MilitaryUnitMessage.unit_id == unit_id)
            .where(MilitaryUnitMessage.is_deleted == False)
            .order_by(MilitaryUnitMessage.created_at.desc())
            .limit(10)
        ).all()

    # Get achievements
    achievements = db.session.scalars(
        db.select(MilitaryUnitAchievement)
        .where(MilitaryUnitAchievement.unit_id == unit_id)
        .order_by(MilitaryUnitAchievement.earned_at.desc())
    ).all()

    # Get active bounty contract
    active_contract = unit.get_active_bounty_contract()

    # Get recent completed contracts with reviews
    completed_contracts = db.session.scalars(
        db.select(BountyContractApplication)
        .where(BountyContractApplication.unit_id == unit_id)
        .where(BountyContractApplication.status == BountyContractStatus.COMPLETED)
        .where(BountyContractApplication.review_rating.isnot(None))
        .order_by(BountyContractApplication.review_at.desc())
        .limit(5)
    ).all()

    return render_template('military_unit/detail.html',
                           title=unit.name,
                           unit=unit,
                           members=members,
                           user_membership=user_membership,
                           is_commander=is_commander,
                           is_officer=is_officer,
                           can_apply=can_apply,
                           has_pending_application=has_pending_application,
                           pending_applications=pending_applications,
                           recent_messages=recent_messages,
                           achievements=achievements,
                           active_contract=active_contract,
                           completed_contracts=completed_contracts)


# ============== UNIT MANAGEMENT ==============

@bp.route('/<int:unit_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(unit_id):
    """Edit unit details (commander only)."""
    unit = db.session.get(MilitaryUnit, unit_id)

    if not unit or not unit.is_active:
        flash('Military unit not found.', 'danger')
        return redirect(url_for('military_unit.browse'))

    if unit.commander_id != current_user.id:
        flash('Only the commander can edit unit details.', 'danger')
        return redirect(url_for('military_unit.detail', unit_id=unit_id))

    form = EditUnitForm(obj=unit)

    if form.validate_on_submit():
        try:
            unit.description = InputSanitizer.sanitize_description(form.description.data) if form.description.data else None

            # Handle avatar upload
            if form.avatar.data:
                success, filename = process_unit_avatar(form.avatar.data, unit.id)
                if success:
                    unit.avatar = True

            db.session.commit()
            flash('Unit details updated successfully.', 'success')
            return redirect(url_for('military_unit.detail', unit_id=unit_id))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating unit {unit_id}: {e}", exc_info=True)
            flash('An error occurred while updating the unit.', 'danger')

    return render_template('military_unit/edit.html',
                           title=f'Edit {unit.name}',
                           unit=unit,
                           form=form)


@bp.route('/<int:unit_id>/apply', methods=['POST'])
@login_required
def apply(unit_id):
    """Apply to join a military unit."""
    unit = db.session.get(MilitaryUnit, unit_id)

    if not unit or not unit.is_active:
        flash('Military unit not found.', 'danger')
        return redirect(url_for('military_unit.browse'))

    # Check if user is already in a unit
    existing = MilitaryUnitMember.get_user_active_membership(current_user.id)
    if existing:
        flash('You are already in a military unit.', 'warning')
        return redirect(url_for('military_unit.detail', unit_id=existing.unit_id))

    # Check citizenship
    if current_user.citizenship_id != unit.country_id:
        flash(f'You must be a citizen of {unit.country.name} to apply.', 'warning')
        return redirect(url_for('military_unit.detail', unit_id=unit_id))

    # Check if unit is full
    if unit.is_full:
        flash('This unit is full.', 'warning')
        return redirect(url_for('military_unit.detail', unit_id=unit_id))

    # Check for existing pending application
    existing_app = MilitaryUnitApplication.query.filter_by(
        unit_id=unit_id,
        user_id=current_user.id,
        status='pending'
    ).first()

    if existing_app:
        flash('You already have a pending application to this unit.', 'info')
        return redirect(url_for('military_unit.detail', unit_id=unit_id))

    try:
        application = MilitaryUnitApplication(
            unit_id=unit_id,
            user_id=current_user.id
        )
        db.session.add(application)
        db.session.commit()

        flash('Your application has been submitted.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error submitting application: {e}", exc_info=True)
        flash('An error occurred. Please try again.', 'danger')

    return redirect(url_for('military_unit.detail', unit_id=unit_id))


@bp.route('/<int:unit_id>/application/<int:app_id>/process', methods=['POST'])
@login_required
def process_application(unit_id, app_id):
    """Process a unit application (approve/reject)."""
    unit = db.session.get(MilitaryUnit, unit_id)

    if not unit or not unit.is_active:
        flash('Military unit not found.', 'danger')
        return redirect(url_for('military_unit.browse'))

    if not unit.can_manage_applications(current_user.id):
        flash('You do not have permission to manage applications.', 'danger')
        return redirect(url_for('military_unit.detail', unit_id=unit_id))

    application = db.session.get(MilitaryUnitApplication, app_id)

    if not application or application.unit_id != unit_id or application.status != 'pending':
        flash('Application not found or already processed.', 'warning')
        return redirect(url_for('military_unit.detail', unit_id=unit_id))

    action = request.form.get('action')

    try:
        if action == 'approve':
            # Check if unit is still not full
            if unit.is_full:
                flash('Cannot approve - unit is now full.', 'warning')
                return redirect(url_for('military_unit.detail', unit_id=unit_id))

            # Check if user is still not in a unit
            if MilitaryUnitMember.get_user_active_membership(application.user_id):
                application.reject(current_user.id)
                db.session.commit()
                flash('User is already in another unit.', 'warning')
                return redirect(url_for('military_unit.detail', unit_id=unit_id))

            application.approve(current_user.id)

            # Create membership
            membership = MilitaryUnitMember(
                unit_id=unit_id,
                user_id=application.user_id,
                rank=MilitaryUnitRank.RECRUIT
            )
            db.session.add(membership)
            db.session.commit()

            flash(f'{application.user.username} has been accepted into the unit.', 'success')

        elif action == 'reject':
            application.reject(current_user.id)
            db.session.commit()
            flash('Application rejected.', 'info')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error processing application: {e}", exc_info=True)
        flash('An error occurred. Please try again.', 'danger')

    return redirect(url_for('military_unit.detail', unit_id=unit_id))


@bp.route('/<int:unit_id>/member/<int:user_id>/promote', methods=['POST'])
@login_required
def promote_member(unit_id, user_id):
    """Promote or demote a unit member (commander only)."""
    unit = db.session.get(MilitaryUnit, unit_id)

    if not unit or not unit.is_active:
        flash('Military unit not found.', 'danger')
        return redirect(url_for('military_unit.browse'))

    if unit.commander_id != current_user.id:
        flash('Only the commander can change member ranks.', 'danger')
        return redirect(url_for('military_unit.detail', unit_id=unit_id))

    if user_id == current_user.id:
        flash('You cannot change your own rank.', 'warning')
        return redirect(url_for('military_unit.detail', unit_id=unit_id))

    membership = db.session.scalar(
        db.select(MilitaryUnitMember)
        .where(MilitaryUnitMember.unit_id == unit_id)
        .where(MilitaryUnitMember.user_id == user_id)
        .where(MilitaryUnitMember.is_active == True)
    )

    if not membership:
        flash('Member not found.', 'warning')
        return redirect(url_for('military_unit.detail', unit_id=unit_id))

    new_rank = request.form.get('rank')

    try:
        if new_rank == 'officer':
            membership.rank = MilitaryUnitRank.OFFICER
        elif new_rank == 'soldier':
            membership.rank = MilitaryUnitRank.SOLDIER
        elif new_rank == 'recruit':
            membership.rank = MilitaryUnitRank.RECRUIT
        else:
            flash('Invalid rank.', 'warning')
            return redirect(url_for('military_unit.detail', unit_id=unit_id))

        db.session.commit()
        flash(f'{membership.user.username} is now a {new_rank.title()}.', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error promoting member: {e}", exc_info=True)
        flash('An error occurred. Please try again.', 'danger')

    return redirect(url_for('military_unit.detail', unit_id=unit_id))


@bp.route('/<int:unit_id>/member/<int:user_id>/kick', methods=['POST'])
@login_required
def kick_member(unit_id, user_id):
    """Kick a member from the unit."""
    unit = db.session.get(MilitaryUnit, unit_id)

    if not unit or not unit.is_active:
        flash('Military unit not found.', 'danger')
        return redirect(url_for('military_unit.browse'))

    can_kick, reason = unit.can_kick_member(current_user.id, user_id)
    if not can_kick:
        flash(reason, 'danger')
        return redirect(url_for('military_unit.detail', unit_id=unit_id))

    membership = unit.get_member(user_id)
    if not membership:
        flash('Member not found.', 'warning')
        return redirect(url_for('military_unit.detail', unit_id=unit_id))

    try:
        username = membership.user.username
        membership.leave(reason='kicked')
        db.session.commit()
        flash(f'{username} has been kicked from the unit.', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error kicking member: {e}", exc_info=True)
        flash('An error occurred. Please try again.', 'danger')

    return redirect(url_for('military_unit.detail', unit_id=unit_id))


@bp.route('/<int:unit_id>/leave', methods=['POST'])
@login_required
def leave(unit_id):
    """Leave the military unit."""
    unit = db.session.get(MilitaryUnit, unit_id)

    if not unit or not unit.is_active:
        flash('Military unit not found.', 'danger')
        return redirect(url_for('military_unit.browse'))

    membership = unit.get_member(current_user.id)
    if not membership:
        flash('You are not a member of this unit.', 'warning')
        return redirect(url_for('military_unit.detail', unit_id=unit_id))

    # Commander cannot leave unless transferring command or last member
    if current_user.id == unit.commander_id:
        if unit.member_count > 1:
            flash('You must transfer command before leaving the unit.', 'warning')
            return redirect(url_for('military_unit.detail', unit_id=unit_id))
        else:
            # Last member leaving - disband unit
            try:
                membership.leave(reason='unit_disbanded')
                unit.is_active = False
                unit.disbanded_at = datetime.utcnow()
                db.session.commit()
                flash('You have left and the unit has been disbanded.', 'info')
                return redirect(url_for('military_unit.browse'))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error disbanding unit: {e}", exc_info=True)
                flash('An error occurred. Please try again.', 'danger')
                return redirect(url_for('military_unit.detail', unit_id=unit_id))

    try:
        membership.leave(reason='voluntary')
        db.session.commit()
        flash('You have left the military unit.', 'info')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error leaving unit: {e}", exc_info=True)
        flash('An error occurred. Please try again.', 'danger')

    return redirect(url_for('military_unit.browse'))


@bp.route('/<int:unit_id>/transfer', methods=['GET', 'POST'])
@login_required
def transfer_command(unit_id):
    """Transfer command to another member (commander only)."""
    unit = db.session.get(MilitaryUnit, unit_id)

    if not unit or not unit.is_active:
        flash('Military unit not found.', 'danger')
        return redirect(url_for('military_unit.browse'))

    if unit.commander_id != current_user.id:
        flash('Only the commander can transfer command.', 'danger')
        return redirect(url_for('military_unit.detail', unit_id=unit_id))

    # Get other members
    other_members = db.session.scalars(
        db.select(MilitaryUnitMember)
        .where(MilitaryUnitMember.unit_id == unit_id)
        .where(MilitaryUnitMember.user_id != current_user.id)
        .where(MilitaryUnitMember.is_active == True)
    ).all()

    if not other_members:
        flash('There are no other members to transfer command to.', 'warning')
        return redirect(url_for('military_unit.detail', unit_id=unit_id))

    form = TransferCommandForm(members=other_members)

    if form.validate_on_submit():
        new_commander_id = form.new_commander_id.data

        # Verify new commander is a member
        new_commander_membership = unit.get_member(new_commander_id)
        if not new_commander_membership:
            flash('Selected member not found.', 'warning')
            return redirect(url_for('military_unit.detail', unit_id=unit_id))

        try:
            # Update old commander to officer
            old_commander_membership = unit.get_member(current_user.id)
            old_commander_membership.rank = MilitaryUnitRank.OFFICER

            # Update new commander
            new_commander_membership.rank = MilitaryUnitRank.COMMANDER
            unit.commander_id = new_commander_id

            # Update unit's country based on new commander's citizenship
            new_commander = db.session.get(User, new_commander_id)
            if new_commander.citizenship_id:
                unit.country_id = new_commander.citizenship_id

            db.session.commit()
            flash(f'Command has been transferred to {new_commander.username}.', 'success')
            return redirect(url_for('military_unit.detail', unit_id=unit_id))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error transferring command: {e}", exc_info=True)
            flash('An error occurred. Please try again.', 'danger')

    return render_template('military_unit/transfer.html',
                           title='Transfer Command',
                           unit=unit,
                           form=form)


# ============== INVENTORY & TREASURY ==============

@bp.route('/<int:unit_id>/inventory')
@login_required
def inventory(unit_id):
    """View unit inventory and treasury (members only)."""
    unit = db.session.get(MilitaryUnit, unit_id)

    if not unit or not unit.is_active:
        flash('Military unit not found.', 'danger')
        return redirect(url_for('military_unit.browse'))

    membership = unit.get_member(current_user.id)
    if not membership:
        flash('Only members can view the inventory.', 'warning')
        return redirect(url_for('military_unit.detail', unit_id=unit_id))

    is_commander = current_user.id == unit.commander_id

    # Get inventory items
    inventory_items = db.session.scalars(
        db.select(MilitaryUnitInventory)
        .where(MilitaryUnitInventory.unit_id == unit_id)
        .where(MilitaryUnitInventory.quantity > 0)
    ).all()

    # Get recent transactions
    transactions = db.session.scalars(
        db.select(MilitaryUnitTransaction)
        .where(MilitaryUnitTransaction.unit_id == unit_id)
        .order_by(MilitaryUnitTransaction.created_at.desc())
        .limit(50)
    ).all()

    # Prepare distribution form if commander
    distribute_form = None
    market_resources = []
    if is_commander:
        members = unit.get_active_members()
        distribute_form = DistributeItemForm(members=members, inventory=inventory_items)

        # Get purchasable resources (weapons and food/drinks) for the unit's country
        country_id = unit.country_id
        if country_id:
            # Get weapons (Rifle, Tank, Artillery, Helicopter, Plane)
            weapon_slugs = ['rifle', 'tank', 'artillery', 'helicopter', 'plane']
            # Get food/drinks (Bread, Beer, Wine)
            food_slugs = ['bread', 'beer', 'wine']

            purchasable_slugs = weapon_slugs + food_slugs

            for slug in purchasable_slugs:
                resource = Resource.query.filter_by(slug=slug, is_deleted=False).first()
                if resource:
                    # Get market items for all qualities
                    market_items = db.session.scalars(
                        db.select(CountryMarketItem)
                        .where(CountryMarketItem.country_id == country_id)
                        .where(CountryMarketItem.resource_id == resource.id)
                        .where(CountryMarketItem.quality > 0)
                        .order_by(CountryMarketItem.quality)
                    ).all()

                    if market_items:
                        market_resources.append({
                            'resource': resource,
                            'market_items': market_items
                        })

    return render_template('military_unit/inventory.html',
                           title=f'{unit.name} - Inventory',
                           unit=unit,
                           inventory_items=inventory_items,
                           transactions=transactions,
                           is_commander=is_commander,
                           distribute_form=distribute_form,
                           market_resources=market_resources)


@bp.route('/<int:unit_id>/distribute', methods=['POST'])
@login_required
@limiter.limit("60 per hour")
def distribute_item(unit_id):
    """Distribute items from unit inventory to a member (commander only)."""
    unit = db.session.get(MilitaryUnit, unit_id)

    if not unit or not unit.is_active:
        flash('Military unit not found.', 'danger')
        return redirect(url_for('military_unit.browse'))

    if unit.commander_id != current_user.id:
        flash('Only the commander can distribute items.', 'danger')
        return redirect(url_for('military_unit.inventory', unit_id=unit_id))

    member_id = request.form.get('member_id', type=int)
    resource_id = request.form.get('resource_id', type=int)
    quality = request.form.get('quality', type=int)
    quantity = request.form.get('quantity', type=int)

    if not all([member_id, resource_id, quality, quantity]):
        flash('Invalid request.', 'warning')
        return redirect(url_for('military_unit.inventory', unit_id=unit_id))

    if quantity <= 0:
        flash('Quantity must be positive.', 'warning')
        return redirect(url_for('military_unit.inventory', unit_id=unit_id))

    # Check member exists
    member = unit.get_member(member_id)
    if not member:
        flash('Member not found.', 'warning')
        return redirect(url_for('military_unit.inventory', unit_id=unit_id))

    # Check inventory
    try:
        # Lock the inventory item row to prevent race conditions
        inv_item = db.session.scalar(
            db.select(MilitaryUnitInventory)
            .where(MilitaryUnitInventory.unit_id == unit_id)
            .where(MilitaryUnitInventory.resource_id == resource_id)
            .where(MilitaryUnitInventory.quality == quality)
            .with_for_update()
        )

        if not inv_item or inv_item.quantity < quantity:
            flash('Not enough items in inventory.', 'warning')
            return redirect(url_for('military_unit.inventory', unit_id=unit_id))

        # Remove from unit inventory (row is locked)
        inv_item.quantity -= quantity

        # Add to user inventory
        target_user = db.session.get(User, member_id)
        target_user.add_to_inventory(resource_id, quantity, quality)

        # Log transaction
        transaction = MilitaryUnitTransaction(
            unit_id=unit_id,
            transaction_type='item_given_to_member',
            resource_id=resource_id,
            resource_quality=quality,
            resource_quantity=quantity,
            performed_by_id=current_user.id,
            target_user_id=member_id,
            description=f'Distributed {quantity}x Q{quality} {inv_item.resource.name} to {target_user.username}'
        )
        db.session.add(transaction)

        # Send alert to receiving member
        from app.models.messaging import Alert, AlertType
        quality_str = f'Q{quality} ' if quality > 0 else ''
        alert = Alert(
            user_id=member_id,
            alert_type=AlertType.ITEMS_RECEIVED.value,
            priority='normal',
            title='Items Received from Military Unit',
            content=f'You have received {quantity}x {quality_str}{inv_item.resource.name} from your military unit commander.',
            alert_data={
                'unit_id': unit_id,
                'unit_name': unit.name,
                'resource_name': inv_item.resource.name,
                'quantity': quantity,
                'quality': quality,
                'commander_name': current_user.username
            },
            link_url=url_for('main.storage'),
            link_text='View Storage'
        )
        db.session.add(alert)

        db.session.commit()

        flash(f'Successfully distributed {quantity}x Q{quality} {inv_item.resource.name} to {target_user.username}.', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error distributing items: {e}", exc_info=True)
        flash('An error occurred. Please try again.', 'danger')

    return redirect(url_for('military_unit.inventory', unit_id=unit_id))


def calculate_purchase_breakdown(market_item, quantity):
    """Calculate the cost breakdown when purchasing across multiple price levels."""
    volume_per_level = int(market_item.volume_per_level)
    current_progress = int(market_item.progress_within_level)
    current_price_level = int(market_item.price_level)

    initial_price = float(market_item.initial_price)
    price_adjustment = float(market_item.price_adjustment_per_level)

    breakdown = []
    remaining_qty = quantity
    temp_progress = current_progress
    temp_price_level = current_price_level
    total_cost = Decimal('0')

    while remaining_qty > 0:
        base_price_at_level = initial_price + (temp_price_level * price_adjustment)
        buy_price_at_level = Decimal(str(base_price_at_level * 1.1))  # 10% spread for buying

        available_at_current_price = volume_per_level - temp_progress
        qty_at_this_price = min(remaining_qty, available_at_current_price)

        breakdown.append((qty_at_this_price, float(buy_price_at_level)))
        cost_at_this_price = buy_price_at_level * Decimal(str(qty_at_this_price))
        total_cost += cost_at_this_price

        temp_progress += qty_at_this_price
        remaining_qty -= qty_at_this_price

        if temp_progress >= volume_per_level:
            temp_price_level += 1
            temp_progress = 0

    return {
        'breakdown': breakdown,
        'total_cost': float(total_cost),
        'final_price_level': temp_price_level,
        'final_progress': temp_progress
    }


@bp.route('/<int:unit_id>/inventory/buy', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def buy_inventory(unit_id):
    """Buy resources from the market for military unit (commander only)."""
    # First check without lock for quick validation
    unit = db.session.get(MilitaryUnit, unit_id)

    if not unit or not unit.is_active:
        return jsonify({'error': 'Military unit not found'}), 404

    if unit.commander_id != current_user.id:
        return jsonify({'error': 'Only the commander can purchase items'}), 403

    resource_id = request.form.get('resource_id', type=int)
    quality = request.form.get('quality', type=int)
    quantity = request.form.get('quantity', type=int)
    confirmed = request.form.get('confirmed') == 'true'
    expected_price_level = request.form.get('expected_price_level', type=int)

    if not resource_id or not quality or not quantity or quantity <= 0:
        return jsonify({'error': 'Invalid input'}), 400

    if quality < 1 or quality > 5:
        return jsonify({'error': 'Invalid quality level'}), 400

    # Get the resource
    resource = db.session.get(Resource, resource_id)
    if not resource or resource.is_deleted:
        return jsonify({'error': 'Resource not found'}), 404

    # Validate resource is purchasable (weapons or food/drinks)
    allowed_slugs = ['rifle', 'tank', 'artillery', 'helicopter', 'plane', 'bread', 'beer', 'wine']
    if resource.slug not in allowed_slugs:
        return jsonify({'error': f'Cannot purchase {resource.name} for military units'}), 403

    # Get market item for pricing
    country_id = unit.country_id
    market_item = db.session.scalar(
        db.select(CountryMarketItem)
        .where(CountryMarketItem.country_id == country_id)
        .where(CountryMarketItem.resource_id == resource_id)
        .where(CountryMarketItem.quality == quality)
    )

    if not market_item:
        return jsonify({'error': f'{resource.name} Q{quality} not available in this country\'s market'}), 404

    # Calculate breakdown
    breakdown_data = calculate_purchase_breakdown(market_item, quantity)
    total_cost = Decimal(str(breakdown_data['total_cost']))

    # Get country for currency info
    country = db.session.get(Country, country_id)

    # If not confirmed, return breakdown for confirmation
    if not confirmed:
        if unit.treasury < total_cost:
            return jsonify({
                'error': f'Insufficient funds. Need {total_cost:.2f} {country.currency_code}, but treasury only has {unit.treasury:.2f}.'
            }), 400

        return jsonify({
            'breakdown': breakdown_data['breakdown'],
            'total_cost': breakdown_data['total_cost'],
            'currency_code': country.currency_code,
            'resource_name': resource.name,
            'quantity': quantity,
            'quality': quality,
            'current_price_level': int(market_item.price_level)
        })

    # CONFIRMED PURCHASE - Check for race condition
    current_price_level = int(market_item.price_level)
    if expected_price_level is not None and current_price_level != expected_price_level:
        return jsonify({'error': 'Price has changed. Please try again.'}), 409

    # Recalculate to get exact cost
    breakdown_data = calculate_purchase_breakdown(market_item, quantity)
    total_cost = Decimal(str(breakdown_data['total_cost']))

    try:
        # Lock the unit row to prevent race conditions on treasury
        unit = db.session.scalar(
            db.select(MilitaryUnit)
            .where(MilitaryUnit.id == unit_id)
            .with_for_update()
        )

        # Check if unit has enough treasury (with locked row)
        if unit.treasury < total_cost:
            return jsonify({
                'error': f'Insufficient funds. Need {total_cost:.2f} {country.currency_code}.'
            }), 400

        # Deduct from treasury (row is locked)
        unit.treasury -= total_cost

        # Add to unit inventory (lock row to prevent race conditions)
        inv_item = db.session.scalar(
            db.select(MilitaryUnitInventory)
            .where(MilitaryUnitInventory.unit_id == unit_id)
            .where(MilitaryUnitInventory.resource_id == resource_id)
            .where(MilitaryUnitInventory.quality == quality)
            .with_for_update()
        )

        if inv_item:
            inv_item.quantity += quantity
        else:
            inv_item = MilitaryUnitInventory(
                unit_id=unit_id,
                resource_id=resource_id,
                quality=quality,
                quantity=quantity
            )
            db.session.add(inv_item)

        # Update market price level and progress
        market_item.price_level = breakdown_data['final_price_level']
        market_item.progress_within_level = breakdown_data['final_progress']

        # Log transaction
        transaction = MilitaryUnitTransaction(
            unit_id=unit_id,
            transaction_type='purchase',
            currency_amount=-total_cost,
            resource_id=resource_id,
            resource_quality=quality,
            resource_quantity=quantity,
            performed_by_id=current_user.id,
            description=f'Purchased {quantity}x Q{quality} {resource.name} for {total_cost:.2f} {country.currency_code}'
        )
        db.session.add(transaction)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Successfully purchased {quantity}x Q{quality} {resource.name} for {total_cost:.2f} {country.currency_code}'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error purchasing inventory: {e}", exc_info=True)
        return jsonify({'error': 'An error occurred. Please try again.'}), 500


# ============== MESSAGE BOARD ==============

@bp.route('/<int:unit_id>/messages')
@login_required
def messages(unit_id):
    """View unit message board (members only)."""
    unit = db.session.get(MilitaryUnit, unit_id)

    if not unit or not unit.is_active:
        flash('Military unit not found.', 'danger')
        return redirect(url_for('military_unit.browse'))

    membership = unit.get_member(current_user.id)
    if not membership:
        flash('Only members can view the message board.', 'warning')
        return redirect(url_for('military_unit.detail', unit_id=unit_id))

    page = request.args.get('page', 1, type=int)

    messages_query = db.select(MilitaryUnitMessage).where(
        MilitaryUnitMessage.unit_id == unit_id,
        MilitaryUnitMessage.is_deleted == False
    ).order_by(MilitaryUnitMessage.created_at.desc())

    messages_paginated = db.paginate(messages_query, page=page, per_page=20, error_out=False)

    form = UnitMessageForm()

    return render_template('military_unit/messages.html',
                           title=f'{unit.name} - Messages',
                           unit=unit,
                           messages=messages_paginated,
                           form=form)


@bp.route('/<int:unit_id>/messages/post', methods=['POST'])
@login_required
def post_message(unit_id):
    """Post a message on the unit message board."""
    unit = db.session.get(MilitaryUnit, unit_id)

    if not unit or not unit.is_active:
        flash('Military unit not found.', 'danger')
        return redirect(url_for('military_unit.browse'))

    membership = unit.get_member(current_user.id)
    if not membership:
        flash('Only members can post messages.', 'warning')
        return redirect(url_for('military_unit.detail', unit_id=unit_id))

    form = UnitMessageForm()

    if form.validate_on_submit():
        try:
            message = MilitaryUnitMessage(
                unit_id=unit_id,
                user_id=current_user.id,
                content=InputSanitizer.sanitize_description(form.content.data)
            )
            db.session.add(message)
            db.session.commit()
            flash('Message posted.', 'success')

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error posting message: {e}", exc_info=True)
            flash('An error occurred. Please try again.', 'danger')

    return redirect(url_for('military_unit.messages', unit_id=unit_id))


# ============== BOUNTY CONTRACTS ==============

@bp.route('/bounties')
@login_required
def bounties():
    """Browse available bounty contracts."""
    # Get active bounties
    active_bounties = db.session.scalars(
        db.select(BountyContract)
        .where(BountyContract.is_active == True)
        .where(BountyContract.expires_at > datetime.utcnow())
        .order_by(BountyContract.payment_amount.desc())
    ).all()

    # Get user's unit if any
    user_unit = MilitaryUnitMember.get_user_unit(current_user.id)
    is_commander = user_unit and user_unit.commander_id == current_user.id

    # Check if user can create bounties (President or Minister of Defence)
    authority, country_id, role = get_defence_authority(current_user)
    can_create_bounty = authority is not None

    # Get completed bounties for authorized users (President/Minister)
    completed_bounties = []
    if authority and country_id:
        # Get bounties created by this country that have been completed
        completed_bounties = db.session.scalars(
            db.select(BountyContract)
            .where(BountyContract.country_id == country_id)
            .where(BountyContract.is_active == False)
            .order_by(BountyContract.created_at.desc())
            .limit(20)
        ).all()

    return render_template('military_unit/bounties.html',
                           title='Bounty Contracts',
                           bounties=active_bounties,
                           completed_bounties=completed_bounties,
                           user_unit=user_unit,
                           is_commander=is_commander,
                           can_create_bounty=can_create_bounty,
                           is_authority=authority is not None)


@bp.route('/bounty/<int:bounty_id>')
@login_required
def bounty_detail(bounty_id):
    """View bounty contract details."""
    bounty = db.session.get(BountyContract, bounty_id)

    if not bounty:
        flash('Bounty contract not found.', 'danger')
        return redirect(url_for('military_unit.bounties'))

    # Get applications
    applications = db.session.scalars(
        db.select(BountyContractApplication)
        .where(BountyContractApplication.contract_id == bounty_id)
        .order_by(BountyContractApplication.created_at.asc())
    ).all()

    # Check if user can manage this bounty (creator, President, or Minister of Defence of the country)
    authority, authority_country_id, role = get_defence_authority(current_user)
    is_minister = (bounty.created_by_id == current_user.id or
                   (authority and authority_country_id == bounty.country_id))

    # Check if user's unit can apply
    user_unit = MilitaryUnitMember.get_user_unit(current_user.id)
    can_apply = False
    has_applied = False
    user_application = None

    if user_unit and user_unit.commander_id == current_user.id:
        # Check if unit already has an active contract
        if not user_unit.has_active_contract():
            can_apply = True

        # Check if already applied
        user_application = BountyContractApplication.query.filter_by(
            contract_id=bounty_id,
            unit_id=user_unit.id
        ).first()
        if user_application:
            has_applied = True
            can_apply = False

    return render_template('military_unit/bounty_detail.html',
                           title=f'Bounty Contract #{bounty_id}',
                           bounty=bounty,
                           applications=applications,
                           is_minister=is_minister,
                           can_apply=can_apply,
                           has_applied=has_applied,
                           user_application=user_application,
                           user_unit=user_unit)


@bp.route('/bounty/<int:bounty_id>/apply', methods=['POST'])
@login_required
def apply_for_bounty(bounty_id):
    """Apply for a bounty contract (unit commander only)."""
    bounty = db.session.get(BountyContract, bounty_id)

    if not bounty or not bounty.is_active or bounty.is_expired:
        flash('Bounty contract not found or expired.', 'danger')
        return redirect(url_for('military_unit.bounties'))

    user_unit = MilitaryUnitMember.get_user_unit(current_user.id)

    if not user_unit or user_unit.commander_id != current_user.id:
        flash('Only unit commanders can apply for bounties.', 'danger')
        return redirect(url_for('military_unit.bounty_detail', bounty_id=bounty_id))

    if user_unit.has_active_contract():
        flash('Your unit already has an active contract.', 'warning')
        return redirect(url_for('military_unit.bounty_detail', bounty_id=bounty_id))

    # Check for existing application
    existing = BountyContractApplication.query.filter_by(
        contract_id=bounty_id,
        unit_id=user_unit.id
    ).first()

    if existing:
        flash('You have already applied for this bounty.', 'info')
        return redirect(url_for('military_unit.bounty_detail', bounty_id=bounty_id))

    try:
        application = BountyContractApplication(
            contract_id=bounty_id,
            unit_id=user_unit.id,
            applied_by_id=current_user.id
        )
        db.session.add(application)
        db.session.commit()
        flash('Your application has been submitted.', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error applying for bounty: {e}", exc_info=True)
        flash('An error occurred. Please try again.', 'danger')

    return redirect(url_for('military_unit.bounty_detail', bounty_id=bounty_id))


@bp.route('/bounty/application/<int:app_id>/process', methods=['POST'])
@login_required
def process_bounty_application(app_id):
    """Process a bounty application (approve/reject)."""
    application = db.session.get(BountyContractApplication, app_id)

    if not application:
        flash('Application not found.', 'danger')
        return redirect(url_for('military_unit.bounties'))

    bounty = application.contract

    # Check if user is the creator of the bounty OR has defence authority for this country
    authority, authority_country_id, role = get_defence_authority(current_user)
    can_process = (bounty.created_by_id == current_user.id or
                   (authority and authority_country_id == bounty.country_id))

    if not can_process:
        flash('You do not have permission to process this application.', 'danger')
        return redirect(url_for('military_unit.bounty_detail', bounty_id=bounty.id))

    if application.status != BountyContractStatus.PENDING:
        flash('This application has already been processed.', 'warning')
        return redirect(url_for('military_unit.bounty_detail', bounty_id=bounty.id))

    action = request.form.get('action')

    try:
        if action == 'approve':
            # Check if another unit is already approved
            existing_approved = BountyContractApplication.query.filter_by(
                contract_id=bounty.id,
                status=BountyContractStatus.APPROVED
            ).first()

            if existing_approved:
                flash('Another unit is already approved for this contract.', 'warning')
                return redirect(url_for('military_unit.bounty_detail', bounty_id=bounty.id))

            application.approve(current_user.id)
            db.session.commit()
            flash(f'{application.unit.name} has been approved for the contract.', 'success')

        elif action == 'reject':
            application.reject(current_user.id)
            db.session.commit()
            flash('Application rejected.', 'info')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error processing bounty application: {e}", exc_info=True)
        flash('An error occurred. Please try again.', 'danger')

    return redirect(url_for('military_unit.bounty_detail', bounty_id=bounty.id))


@bp.route('/bounty/application/<int:app_id>/review', methods=['POST'])
@login_required
def review_bounty(app_id):
    """Leave a review for a completed bounty contract."""
    application = db.session.get(BountyContractApplication, app_id)

    if not application:
        flash('Application not found.', 'danger')
        return redirect(url_for('military_unit.bounties'))

    bounty = application.contract

    # Check if user is the creator of the bounty OR has defence authority for this country
    authority, authority_country_id, role = get_defence_authority(current_user)
    can_review = (bounty.created_by_id == current_user.id or
                  (authority and authority_country_id == bounty.country_id))

    if not can_review:
        flash('You do not have permission to review this.', 'danger')
        return redirect(url_for('military_unit.bounty_detail', bounty_id=bounty.id))

    if application.status != BountyContractStatus.COMPLETED:
        flash('Can only review completed contracts.', 'warning')
        return redirect(url_for('military_unit.bounty_detail', bounty_id=bounty.id))

    if application.review_rating is not None:
        flash('This contract has already been reviewed.', 'info')
        return redirect(url_for('military_unit.bounty_detail', bounty_id=bounty.id))

    rating = request.form.get('rating', type=int)

    if not rating or rating < 1 or rating > 5:
        flash('Invalid rating.', 'warning')
        return redirect(url_for('military_unit.bounty_detail', bounty_id=bounty.id))

    try:
        application.add_review(rating)
        db.session.commit()
        flash('Review submitted successfully.', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error submitting review: {e}", exc_info=True)
        flash('An error occurred. Please try again.', 'danger')

    return redirect(url_for('military_unit.bounty_detail', bounty_id=bounty.id))


# ============== PRESIDENT / MINISTER OF DEFENCE - CREATE BOUNTY ==============

@bp.route('/bounty/create', methods=['GET', 'POST'])
@login_required
@limiter.limit("10 per hour")
def create_bounty():
    """Create a new bounty contract (President or Minister of Defence only)."""
    # Check if user has authority (President or Minister of Defence)
    authority, country_id, role = get_defence_authority(current_user)

    if not authority:
        flash('Only Country Presidents or Ministers of Defence can create bounty contracts.', 'danger')
        return redirect(url_for('military_unit.bounties'))

    # Get active battles that the country or allies are involved in

    # Get alliance member countries
    alliance_member_ids = [country_id]
    alliance = Alliance.get_country_alliance(country_id)
    if alliance:
        alliance_member_ids = alliance.get_member_country_ids()

    # Get active battles - import War model for proper query
    from app.models import War

    # Get active battles for the minister's country or allies
    active_battles = db.session.scalars(
        db.select(Battle)
        .join(War, Battle.war_id == War.id)
        .where(Battle.status == BattleStatus.ACTIVE)
        .where(
            db.or_(
                War.attacker_country_id.in_(alliance_member_ids),
                War.defender_country_id.in_(alliance_member_ids)
            )
        )
        .order_by(Battle.ends_at.asc())
    ).all()

    form = CreateBountyForm(battles=active_battles)

    if form.validate_on_submit():
        battle_id = form.battle_id.data
        fight_for_attacker = bool(form.fight_for_attacker.data)
        damage_required = form.damage_required.data
        payment_amount = Decimal(str(form.payment_amount.data))

        # Validate battle
        battle = db.session.get(Battle, battle_id)
        if not battle or battle.status != BattleStatus.ACTIVE:
            flash('Invalid battle selected.', 'warning')
            return redirect(url_for('military_unit.create_bounty'))

        # Lock country row to prevent race conditions on military_budget
        country = db.session.scalar(
            db.select(Country).where(Country.id == country_id).with_for_update()
        )
        if country.military_budget_currency < payment_amount:
            flash('Insufficient funds in military budget.', 'danger')
            return redirect(url_for('military_unit.create_bounty'))

        try:
            # Reserve the payment from military budget
            country.military_budget_currency -= payment_amount

            # Create bounty
            bounty = BountyContract(
                country_id=country_id,
                battle_id=battle_id,
                fight_for_attacker=fight_for_attacker,
                damage_required=damage_required,
                payment_amount=payment_amount,
                created_by_id=current_user.id,
                expires_at=battle.ends_at
            )
            db.session.add(bounty)
            db.session.commit()

            flash('Bounty contract created successfully.', 'success')
            return redirect(url_for('military_unit.bounty_detail', bounty_id=bounty.id))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating bounty: {e}", exc_info=True)
            flash('An error occurred. Please try again.', 'danger')

    return render_template('military_unit/create_bounty.html',
                           title='Create Bounty Contract',
                           form=form,
                           minister=authority,
                           role=role)
