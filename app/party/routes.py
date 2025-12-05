# app/party/routes.py

import os
from datetime import datetime, timezone
from flask import render_template, redirect, url_for, flash, request, current_app, abort, jsonify
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from decimal import Decimal

from app.party import bp
from app.extensions import db
from app.models import PoliticalParty, PartyMembership, PartyElection, PartyCandidate, PartyVote, Country, User, ElectionStatus
from app.models.government import GovernmentElection, GovernmentElectionStatus, ElectionCandidate, CandidateStatus
from app.party.forms import CreatePartyForm, EditPartyForm, AnnounceCandidacyForm, VoteForm
from app.security import InputSanitizer


@bp.route('/')
@bp.route('/browse')
@login_required
def browse():
    """Browse all parties in user's country."""
    if not current_user.citizenship_id:
        flash('You must be a citizen of a country to view parties.', 'warning')
        return redirect(url_for('main.dashboard'))

    # Get parties in user's country, sorted by member count (descending)
    parties = db.session.scalars(
        db.select(PoliticalParty)
        .where(PoliticalParty.country_id == current_user.citizenship_id)
        .where(PoliticalParty.is_deleted == False)
        .order_by(PoliticalParty.id.desc())  # We'll sort by member count in Python
    ).all()

    # Sort by member count (this could be optimized with a database query)
    parties.sort(key=lambda p: p.member_count, reverse=True)

    return render_template('party/browse.html',
                          title='Political Parties',
                          parties=parties)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create a new political party (costs 5 gold)."""
    # Check if user has citizenship
    if not current_user.citizenship_id:
        flash('You must be a citizen of a country to create a party.', 'warning')
        return redirect(url_for('party.browse'))

    # Check if user is already in a party
    if current_user.party:
        flash('You are already in a party. Leave your current party before creating a new one.', 'warning')
        return redirect(url_for('party.detail', party_id=current_user.party.id))

    # Check if user has enough gold
    if current_user.gold < Decimal('5.0'):
        flash('You need at least 5 gold to create a party.', 'danger')
        return redirect(url_for('party.browse'))

    form = CreatePartyForm(user=current_user)

    if form.validate_on_submit():
        try:
            # Deduct gold with row-level locking
            from app.services.currency_service import CurrencyService
            success, message, _ = CurrencyService.deduct_gold(
                current_user.id, Decimal('5.0'), 'Party creation'
            )
            if not success:
                flash(f'Could not deduct gold: {message}', 'danger')
                return redirect(url_for('party.create'))

            # Create party
            party = PoliticalParty(
                name=form.name.data,
                country_id=current_user.citizenship_id,
                president_id=current_user.id,
                description=InputSanitizer.sanitize_description(form.description.data)
            )
            db.session.add(party)
            db.session.flush()  # Get party ID

            # Add creator as first member
            membership = PartyMembership(
                user_id=current_user.id,
                party_id=party.id
            )
            db.session.add(membership)

            # Update user's party_id to maintain consistency
            current_user.party_id = party.id

            db.session.commit()

            current_app.logger.info(f"User {current_user.id} created party {party.id} '{party.name}'")
            flash(f'Party "{party.name}" created successfully! You are now the party politics.', 'success')
            return redirect(url_for('party.detail', party_id=party.id))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating party for user {current_user.id}: {e}", exc_info=True)
            flash('An error occurred while creating the party. Please try again.', 'danger')

    return render_template('party/create.html',
                          title='Create Party',
                          form=form)


@bp.route('/<int:party_id>')
@login_required
def detail(party_id):
    """View party details."""
    party = db.session.get(PoliticalParty, party_id)

    if not party or party.is_deleted:
        flash('Party not found.', 'danger')
        return redirect(url_for('party.browse'))

    # Get all members (sort by experience since level is computed from it)
    members = db.session.scalars(
        db.select(User)
        .join(PartyMembership)
        .where(PartyMembership.party_id == party_id)
        .order_by(User.experience.desc())
    ).all()

    # Get current election (scheduled or active) if any
    current_election = party.current_election

    # If there's a current election, get candidates and check if user voted
    election_data = None
    if current_election:
        candidates = db.session.scalars(
            db.select(PartyCandidate)
            .where(PartyCandidate.election_id == current_election.id)
        ).all()

        user_voted = False
        if current_user.party and current_user.party.id == party_id:
            user_voted = db.session.scalar(
                db.select(PartyVote)
                .where(PartyVote.election_id == current_election.id)
                .where(PartyVote.voter_id == current_user.id)
            ) is not None

        election_data = {
            'election': current_election,
            'candidates': candidates,
            'user_voted': user_voted,
            'user_is_candidate': any(c.user_id == current_user.id for c in candidates)
        }

    # Check if user can join
    can_join = False
    join_message = None
    if not current_user.party:
        can_join, join_message = current_user.can_join_party(party)

    # Get past elections (completed elections)
    past_elections = db.session.scalars(
        db.select(PartyElection)
        .where(PartyElection.party_id == party_id)
        .where(PartyElection.status == ElectionStatus.COMPLETED)
        .order_by(PartyElection.end_time.desc())
        .limit(10)
    ).all()

    # Add helper properties to past elections
    for election in past_elections:
        election.vote_count = election.get_vote_count()
        election.candidate_count = election.get_candidate_count()
        # For now, set congress_seats to 0 (will be implemented when congress elections are added)
        election.congress_seats = 0

    # Get active country elections for party president candidate management
    active_country_elections = []
    if current_user.is_party_president and current_user.party and current_user.party.id == party_id:
        # Get elections in nominations/applications or voting status for the party's country
        active_elections = db.session.scalars(
            db.select(GovernmentElection)
            .where(GovernmentElection.country_id == party.country_id)
            .where(GovernmentElection.status.in_([
                GovernmentElectionStatus.NOMINATIONS,
                GovernmentElectionStatus.APPLICATIONS,
                GovernmentElectionStatus.VOTING
            ]))
            .order_by(GovernmentElection.nominations_start.desc())
        ).all()

        for election in active_elections:
            # Count pending candidates from this party
            pending_count = db.session.scalar(
                db.select(db.func.count())
                .select_from(ElectionCandidate)
                .where(ElectionCandidate.election_id == election.id)
                .where(ElectionCandidate.party_id == party_id)
                .where(ElectionCandidate.status == CandidateStatus.PENDING)
            )
            election.pending_candidates = pending_count
            active_country_elections.append(election)

    return render_template('party/detail.html',
                          title=party.name,
                          party=party,
                          members=members,
                          election_data=election_data,
                          can_join=can_join,
                          join_message=join_message,
                          past_elections=past_elections,
                          active_country_elections=active_country_elections)


@bp.route('/<int:party_id>/members')
@login_required
def members(party_id):
    """View all members of a political party."""
    party = db.session.get(PoliticalParty, party_id)

    if not party or party.is_deleted:
        flash('Party not found.', 'danger')
        return redirect(url_for('party.browse'))

    # Get all members sorted by experience (politics shown first via template)
    all_members = db.session.scalars(
        db.select(User)
        .join(PartyMembership)
        .where(PartyMembership.party_id == party_id)
        .order_by(User.experience.desc())
    ).all()

    # Separate politics from other members for display
    president = party.president
    other_members = [m for m in all_members if m.id != party.president_id]

    return render_template('party/members.html',
                          title=f'{party.name} - Members',
                          party=party,
                          president=president,
                          other_members=other_members,
                          total_members=len(all_members))


@bp.route('/<int:party_id>/join', methods=['POST'])
@login_required
def join(party_id):
    """Join a political party."""
    party = db.session.get(PoliticalParty, party_id)

    if not party or party.is_deleted:
        flash('Party not found.', 'danger')
        return redirect(url_for('party.browse'))

    # Check if user can join
    can_join, message = current_user.can_join_party(party)

    if not can_join:
        flash(message, 'warning')
        return redirect(url_for('party.detail', party_id=party_id))

    try:
        # Create membership
        membership = PartyMembership(
            user_id=current_user.id,
            party_id=party_id
        )
        db.session.add(membership)

        # Update user's party_id to maintain consistency
        current_user.party_id = party_id

        db.session.commit()

        current_app.logger.info(f"User {current_user.id} joined party {party_id}")
        flash(f'You have successfully joined {party.name}!', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error joining party {party_id} for user {current_user.id}: {e}", exc_info=True)
        flash('An error occurred while joining the party. Please try again.', 'danger')

    return redirect(url_for('party.detail', party_id=party_id))


@bp.route('/<int:party_id>/leave', methods=['POST'])
@login_required
def leave(party_id):
    """Leave a political party."""
    party = db.session.get(PoliticalParty, party_id)

    if not party or party.is_deleted:
        flash('Party not found.', 'danger')
        return redirect(url_for('party.browse'))

    # Check if user is in this party
    if not current_user.party or current_user.party.id != party_id:
        flash('You are not a member of this party.', 'warning')
        return redirect(url_for('party.detail', party_id=party_id))

    # Check if user can leave
    can_leave, message = current_user.can_leave_party()

    if not can_leave:
        flash(message, 'warning')
        return redirect(url_for('party.detail', party_id=party_id))

    try:
        is_president = party.president_id == current_user.id
        member_count = party.member_count

        # Remove membership
        membership = db.session.scalar(
            db.select(PartyMembership)
            .where(PartyMembership.user_id == current_user.id)
            .where(PartyMembership.party_id == party_id)
        )

        if membership:
            db.session.delete(membership)

        # Update user's party_id to maintain consistency
        current_user.party_id = None

        # Handle politics leaving
        if is_president:
            if member_count <= 1:
                # Last member - disband party
                party.is_deleted = True
                party.deleted_at = datetime.now(timezone.utc)
                db.session.commit()
                current_app.logger.info(f"Party {party_id} disbanded (last member left)")
                flash(f'You have left {party.name}. The party has been disbanded.', 'info')
                return redirect(url_for('party.browse'))
            else:
                # Transfer presidency to next eligible member
                next_president = party.get_next_president()
                if next_president:
                    party.president_id = next_president.id
                    current_app.logger.info(f"Party {party_id} presidency transferred from {current_user.id} to {next_president.id}")
                    flash(f'You have left {party.name}. {next_president.username} is now the party politics.', 'info')

        db.session.commit()
        current_app.logger.info(f"User {current_user.id} left party {party_id}")

        if not is_president:
            flash(f'You have successfully left {party.name}.', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error leaving party {party_id} for user {current_user.id}: {e}", exc_info=True)
        flash('An error occurred while leaving the party. Please try again.', 'danger')

    return redirect(url_for('party.browse'))


@bp.route('/<int:party_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(party_id):
    """Edit party details (politics only)."""
    party = db.session.get(PoliticalParty, party_id)

    if not party or party.is_deleted:
        flash('Party not found.', 'danger')
        return redirect(url_for('party.browse'))

    # Check if user is the politics
    if party.president_id != current_user.id:
        flash('Only the party politics can edit party details.', 'danger')
        return redirect(url_for('party.detail', party_id=party_id))

    form = EditPartyForm()

    if form.validate_on_submit():
        try:
            # Update description
            party.description = InputSanitizer.sanitize_description(form.description.data)

            # Handle logo upload
            if form.logo.data:
                file = form.logo.data
                if file and allowed_file(file.filename, {'png', 'jpg', 'jpeg'}):
                    # Create party_logos directory if it doesn't exist
                    upload_folder = os.path.join(current_app.root_path, 'static', 'images', 'party_logos')
                    os.makedirs(upload_folder, exist_ok=True)

                    # Save file with unique name
                    filename = secure_filename(file.filename)
                    unique_filename = f"party_{party_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{filename}"
                    filepath = os.path.join(upload_folder, unique_filename)
                    file.save(filepath)

                    # Delete old logo if exists
                    if party.logo_path:
                        old_path = os.path.join(current_app.root_path, 'static', party.logo_path)
                        if os.path.exists(old_path):
                            try:
                                os.remove(old_path)
                            except Exception as e:
                                current_app.logger.warning(f"Could not delete old logo: {e}")

                    # Update logo path
                    party.logo_path = f"images/party_logos/{unique_filename}"

            db.session.commit()
            current_app.logger.info(f"Party {party_id} updated by user {current_user.id}")
            flash('Party details updated successfully!', 'success')
            return redirect(url_for('party.detail', party_id=party_id))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating party {party_id}: {e}", exc_info=True)
            flash('An error occurred while updating the party. Please try again.', 'danger')

    # Pre-fill form with current data
    elif request.method == 'GET':
        form.description.data = party.description

    return render_template('party/edit.html',
                          title=f'Edit {party.name}',
                          party=party,
                          form=form)


@bp.route('/<int:party_id>/announce-candidacy', methods=['POST'])
@login_required
def announce_candidacy(party_id):
    """Announce candidacy for party politics election."""
    party = db.session.get(PoliticalParty, party_id)

    if not party or party.is_deleted:
        flash('Party not found.', 'danger')
        return redirect(url_for('party.browse'))

    # Check if user is a member
    if not current_user.party or current_user.party.id != party_id:
        flash('You must be a member of this party to run for politics.', 'warning')
        return redirect(url_for('party.detail', party_id=party_id))

    # Get active or scheduled election
    election = db.session.scalar(
        db.select(PartyElection)
        .where(PartyElection.party_id == party_id)
        .where(PartyElection.status.in_([ElectionStatus.SCHEDULED, ElectionStatus.ACTIVE]))
        .order_by(PartyElection.start_time.desc())
    )

    if not election:
        flash('There is no upcoming election for this party.', 'info')
        return redirect(url_for('party.detail', party_id=party_id))

    # Check if candidacy announcements are allowed
    if not election.can_announce_candidacy():
        flash('Candidacy announcements are closed. The election has already started.', 'warning')
        return redirect(url_for('party.detail', party_id=party_id))

    # Check if already a candidate
    existing_candidacy = db.session.scalar(
        db.select(PartyCandidate)
        .where(PartyCandidate.election_id == election.id)
        .where(PartyCandidate.user_id == current_user.id)
    )

    if existing_candidacy:
        flash('You have already announced your candidacy for this election.', 'info')
        return redirect(url_for('party.detail', party_id=party_id))

    try:
        # Create candidacy
        candidate = PartyCandidate(
            election_id=election.id,
            user_id=current_user.id
        )
        db.session.add(candidate)
        db.session.commit()

        current_app.logger.info(f"User {current_user.id} announced candidacy for party {party_id} election {election.id}")
        flash('Your candidacy has been announced! Good luck in the election!', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error announcing candidacy for user {current_user.id} in election {election.id}: {e}", exc_info=True)
        flash('An error occurred while announcing your candidacy. Please try again.', 'danger')

    return redirect(url_for('party.detail', party_id=party_id))


@bp.route('/<int:party_id>/withdraw-candidacy', methods=['POST'])
@login_required
def withdraw_candidacy(party_id):
    """Withdraw candidacy from party politics election."""
    party = db.session.get(PoliticalParty, party_id)

    if not party or party.is_deleted:
        flash('Party not found.', 'danger')
        return redirect(url_for('party.browse'))

    # Check if user is a member
    if not current_user.party or current_user.party.id != party_id:
        flash('You must be a member of this party.', 'warning')
        return redirect(url_for('party.detail', party_id=party_id))

    # Get active or scheduled election
    election = db.session.scalar(
        db.select(PartyElection)
        .where(PartyElection.party_id == party_id)
        .where(PartyElection.status.in_([ElectionStatus.SCHEDULED, ElectionStatus.ACTIVE]))
        .order_by(PartyElection.start_time.desc())
    )

    if not election:
        flash('There is no upcoming election for this party.', 'info')
        return redirect(url_for('party.detail', party_id=party_id))

    # Check if election has started (can only withdraw before voting starts)
    if not election.can_announce_candidacy():
        flash('Cannot withdraw candidacy. The election has already started.', 'warning')
        return redirect(url_for('party.detail', party_id=party_id))

    # Check if user is a candidate
    existing_candidacy = db.session.scalar(
        db.select(PartyCandidate)
        .where(PartyCandidate.election_id == election.id)
        .where(PartyCandidate.user_id == current_user.id)
    )

    if not existing_candidacy:
        flash('You are not a candidate in this election.', 'info')
        return redirect(url_for('party.detail', party_id=party_id))

    try:
        # Remove candidacy
        db.session.delete(existing_candidacy)
        db.session.commit()

        current_app.logger.info(f"User {current_user.id} withdrew candidacy from party {party_id} election {election.id}")
        flash('Your candidacy has been withdrawn.', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error withdrawing candidacy for user {current_user.id} in election {election.id}: {e}", exc_info=True)
        flash('An error occurred while withdrawing your candidacy. Please try again.', 'danger')

    return redirect(url_for('party.detail', party_id=party_id))


@bp.route('/<int:party_id>/vote', methods=['GET', 'POST'])
@login_required
def vote(party_id):
    """Vote in party politics election with blockchain signature verification."""
    party = db.session.get(PoliticalParty, party_id)

    # Check if this is a JSON request (blockchain-signed vote)
    is_blockchain_vote = request.is_json

    if not party or party.is_deleted:
        if is_blockchain_vote:
            return jsonify({'error': 'Party not found.'}), 404
        flash('Party not found.', 'danger')
        return redirect(url_for('party.browse'))

    # Check if user is a member
    if not current_user.party or current_user.party.id != party_id:
        if is_blockchain_vote:
            return jsonify({'error': 'You must be a member of this party to vote.'}), 403
        flash('You must be a member of this party to vote.', 'warning')
        return redirect(url_for('party.detail', party_id=party_id))

    # Get active election
    election = party.active_election

    if not election:
        if is_blockchain_vote:
            return jsonify({'error': 'There is no active election for this party.'}), 400
        flash('There is no active election for this party.', 'info')
        return redirect(url_for('party.detail', party_id=party_id))

    # Check if user already voted
    existing_vote = db.session.scalar(
        db.select(PartyVote)
        .where(PartyVote.election_id == election.id)
        .where(PartyVote.voter_id == current_user.id)
    )

    if existing_vote:
        if is_blockchain_vote:
            return jsonify({'error': 'You have already voted in this election.'}), 400
        flash('You have already voted in this election.', 'info')
        return redirect(url_for('party.detail', party_id=party_id))

    # Get candidates
    candidates = db.session.scalars(
        db.select(PartyCandidate)
        .where(PartyCandidate.election_id == election.id)
    ).all()

    if not candidates:
        if is_blockchain_vote:
            return jsonify({'error': 'There are no candidates in this election.'}), 400
        flash('There are no candidates in this election.', 'warning')
        return redirect(url_for('party.detail', party_id=party_id))

    # Handle blockchain-signed vote (JSON POST)
    if is_blockchain_vote:
        from app.blockchain.vote_verification import validate_vote_data

        data = request.get_json()
        wallet_address = data.get('wallet_address')
        vote_message = data.get('vote_message')
        vote_signature = data.get('vote_signature')
        candidate_id = data.get('candidate_id')

        if not candidate_id:
            return jsonify({'error': 'Candidate ID is required.'}), 400

        # Verify candidate is in this election
        valid_candidate = any(c.user_id == candidate_id for c in candidates)
        if not valid_candidate:
            return jsonify({'error': 'Invalid candidate for this election.'}), 400

        # Validate the signature
        is_valid, error_msg = validate_vote_data(
            wallet_address=wallet_address,
            vote_message=vote_message,
            vote_signature=vote_signature,
            expected_election_type='party_president',
            expected_election_id=election.id,
            expected_candidate_id=candidate_id,
            user_wallet=current_user.wallet_address
        )

        if not is_valid:
            return jsonify({'error': error_msg}), 400

        # Check if this wallet has already voted
        wallet_vote = db.session.scalar(
            db.select(PartyVote)
            .where(PartyVote.election_id == election.id)
            .where(PartyVote.wallet_address == wallet_address.lower())
        )
        if wallet_vote:
            return jsonify({'error': 'This wallet has already been used to vote in this election.'}), 400

        try:
            # Cast vote with blockchain data
            new_vote = PartyVote(
                election_id=election.id,
                voter_id=current_user.id,
                candidate_id=candidate_id,
                wallet_address=wallet_address.lower(),
                vote_message=vote_message,
                vote_signature=vote_signature
            )
            db.session.add(new_vote)
            db.session.commit()

            # Get candidate username
            candidate_user = db.session.get(User, candidate_id)
            candidate_name = candidate_user.username if candidate_user else 'candidate'

            current_app.logger.info(f"User {current_user.id} voted in party election {election.id} (blockchain signed)")
            return jsonify({
                'success': True,
                'message': f'Successfully voted for {candidate_name}!',
                'blockchain_verified': True
            })

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error casting blockchain vote: {e}", exc_info=True)
            return jsonify({'error': 'An error occurred while casting your vote.'}), 500

    # Handle traditional form vote
    form = VoteForm(candidates=candidates)

    if form.validate_on_submit():
        try:
            # Cast vote
            new_vote = PartyVote(
                election_id=election.id,
                voter_id=current_user.id,
                candidate_id=form.candidate_id.data
            )
            db.session.add(new_vote)
            db.session.commit()

            current_app.logger.info(f"User {current_user.id} voted in election {election.id}")
            flash('Your vote has been cast successfully!', 'success')
            return redirect(url_for('party.detail', party_id=party_id))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error casting vote for user {current_user.id} in election {election.id}: {e}", exc_info=True)
            flash('An error occurred while casting your vote. Please try again.', 'danger')

    return render_template('party/vote.html',
                          title=f'Vote - {party.name}',
                          party=party,
                          election=election,
                          candidates=candidates,
                          form=form)


def allowed_file(filename, allowed_extensions):
    """Check if filename has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions
