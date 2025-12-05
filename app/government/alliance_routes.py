# app/government/alliance_routes.py
"""Routes for alliance management."""

from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import current_user, login_required

from app.government import bp
from app.extensions import db
from app.models import (
    Alliance, AllianceMembership, AllianceInvitation, AllianceKick,
    AllianceLeave, AllianceDissolution, AllianceInvitationStatus,
    Country, User
)
from app.services.alliance_service import AllianceService


@bp.route('/alliances')
@login_required
def alliances():
    """View all alliances."""
    all_alliances = AllianceService.get_all_alliances()

    # Get user's country alliance if any
    user_alliance = None
    if current_user.citizenship_id:
        user_alliance = AllianceService.get_country_alliance(current_user.citizenship_id)

    return render_template('government/alliances.html',
                          title='Alliances',
                          alliances=all_alliances,
                          user_alliance=user_alliance)


@bp.route('/alliance/<int:alliance_id>')
@login_required
def view_alliance(alliance_id):
    """View alliance details."""
    alliance = Alliance.query.get_or_404(alliance_id)

    if not alliance.is_active:
        flash('This alliance no longer exists.', 'warning')
        return redirect(url_for('government.alliances'))

    # Get members
    members = alliance.get_active_members()

    # Check user permissions
    is_member = False
    is_leader = False
    is_president = False
    is_foreign_affairs_minister = False

    if current_user.citizenship_id:
        is_member = alliance.is_member(current_user.citizenship_id)
        is_leader = current_user.citizenship_id == alliance.leader_country_id
        is_president = current_user.is_president_of(current_user.citizenship_id)
        is_foreign_affairs_minister = current_user.is_minister_of(current_user.citizenship_id, 'foreign_affairs')

    # Get pending invitations (for members)
    pending_invitations = []
    if is_member:
        pending_invitations = AllianceInvitation.query.filter_by(
            alliance_id=alliance_id,
            status=AllianceInvitationStatus.PENDING_VOTES
        ).all()

    # Get available countries to invite (not in any alliance, not at war with members)
    invitable_countries = []
    if (is_foreign_affairs_minister or is_president) and is_member and not alliance.is_full:
        all_countries = Country.query.filter_by(is_deleted=False).all()
        for country in all_countries:
            can_invite, _ = alliance.can_invite(country.id)
            if can_invite:
                invitable_countries.append(country)

    return render_template('government/alliance_detail.html',
                          title=alliance.name,
                          alliance=alliance,
                          members=members,
                          is_member=is_member,
                          is_leader=is_leader,
                          is_president=is_president,
                          is_foreign_affairs_minister=is_foreign_affairs_minister,
                          pending_invitations=pending_invitations,
                          invitable_countries=invitable_countries)


@bp.route('/alliance/create', methods=['GET', 'POST'])
@login_required
def create_alliance():
    """Create a new alliance."""
    if not current_user.citizenship_id:
        flash('You must be a citizen of a country to create an alliance.', 'warning')
        return redirect(url_for('government.alliances'))

    # Check if president
    if not current_user.is_president_of(current_user.citizenship_id):
        flash('Only the President can create an alliance.', 'danger')
        return redirect(url_for('government.alliances'))

    # Check if already in alliance
    existing = AllianceService.get_country_alliance(current_user.citizenship_id)
    if existing:
        flash('Your country is already in an alliance.', 'warning')
        return redirect(url_for('government.view_alliance', alliance_id=existing.id))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()

        if not name:
            flash('Alliance name is required.', 'danger')
            return render_template('government/create_alliance.html', title='Create Alliance')

        alliance, message = AllianceService.create_alliance(current_user, name)

        if alliance:
            flash(message, 'success')
            return redirect(url_for('government.view_alliance', alliance_id=alliance.id))
        else:
            flash(message, 'danger')

    return render_template('government/create_alliance.html', title='Create Alliance')


@bp.route('/alliance/<int:alliance_id>/invite', methods=['POST'])
@login_required
def invite_to_alliance(alliance_id):
    """Invite a country to the alliance."""
    alliance = Alliance.query.get_or_404(alliance_id)

    if not alliance.is_active:
        flash('This alliance no longer exists.', 'danger')
        return redirect(url_for('government.alliances'))

    invited_country_id = request.form.get('country_id', type=int)
    if not invited_country_id:
        flash('Please select a country to invite.', 'danger')
        return redirect(url_for('government.view_alliance', alliance_id=alliance_id))

    invitation, message = AllianceService.propose_invitation(
        current_user, alliance_id, invited_country_id
    )

    if invitation:
        flash(message, 'success')
    else:
        flash(message, 'danger')

    return redirect(url_for('government.view_alliance', alliance_id=alliance_id))


@bp.route('/alliance/<int:alliance_id>/kick', methods=['POST'])
@login_required
def kick_from_alliance(alliance_id):
    """Propose kicking a country from the alliance."""
    alliance = Alliance.query.get_or_404(alliance_id)

    if not alliance.is_active:
        flash('This alliance no longer exists.', 'danger')
        return redirect(url_for('government.alliances'))

    target_country_id = request.form.get('country_id', type=int)
    if not target_country_id:
        flash('Please select a country to kick.', 'danger')
        return redirect(url_for('government.view_alliance', alliance_id=alliance_id))

    kick, message = AllianceService.propose_kick(
        current_user, alliance_id, target_country_id
    )

    if kick:
        flash(message, 'success')
    else:
        flash(message, 'danger')

    return redirect(url_for('government.view_alliance', alliance_id=alliance_id))


@bp.route('/alliance/<int:alliance_id>/leave', methods=['POST'])
@login_required
def leave_alliance(alliance_id):
    """Propose leaving the alliance."""
    alliance = Alliance.query.get_or_404(alliance_id)

    if not alliance.is_active:
        flash('This alliance no longer exists.', 'danger')
        return redirect(url_for('government.alliances'))

    leave, message = AllianceService.propose_leave(current_user, alliance_id)

    if leave:
        flash(message, 'success')
    else:
        flash(message, 'danger')

    return redirect(url_for('government.view_alliance', alliance_id=alliance_id))


@bp.route('/alliance/<int:alliance_id>/transfer', methods=['POST'])
@login_required
def transfer_alliance_leadership(alliance_id):
    """Transfer alliance leadership."""
    alliance = Alliance.query.get_or_404(alliance_id)

    if not alliance.is_active:
        flash('This alliance no longer exists.', 'danger')
        return redirect(url_for('government.alliances'))

    new_leader_id = request.form.get('country_id', type=int)
    if not new_leader_id:
        flash('Please select a country to transfer leadership to.', 'danger')
        return redirect(url_for('government.view_alliance', alliance_id=alliance_id))

    success, message = AllianceService.transfer_leadership(
        current_user, alliance_id, new_leader_id
    )

    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')

    return redirect(url_for('government.view_alliance', alliance_id=alliance_id))


@bp.route('/alliance/<int:alliance_id>/rename', methods=['POST'])
@login_required
def rename_alliance(alliance_id):
    """Rename the alliance."""
    alliance = Alliance.query.get_or_404(alliance_id)

    if not alliance.is_active:
        flash('This alliance no longer exists.', 'danger')
        return redirect(url_for('government.alliances'))

    new_name = request.form.get('name', '').strip()
    if not new_name:
        flash('Alliance name is required.', 'danger')
        return redirect(url_for('government.view_alliance', alliance_id=alliance_id))

    success, message = AllianceService.rename_alliance(current_user, alliance_id, new_name)

    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')

    return redirect(url_for('government.view_alliance', alliance_id=alliance_id))


@bp.route('/alliance/<int:alliance_id>/dissolve', methods=['POST'])
@login_required
def dissolve_alliance(alliance_id):
    """Propose dissolving the alliance."""
    alliance = Alliance.query.get_or_404(alliance_id)

    if not alliance.is_active:
        flash('This alliance no longer exists.', 'danger')
        return redirect(url_for('government.alliances'))

    dissolution, message = AllianceService.propose_dissolution(current_user, alliance_id)

    if dissolution:
        flash(message, 'success')
    else:
        flash(message, 'danger')

    return redirect(url_for('government.view_alliance', alliance_id=alliance_id))
