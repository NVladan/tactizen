# app/government/routes.py

from datetime import datetime, timezone
from flask import render_template, redirect, url_for, flash, request, current_app, abort, jsonify
from flask_login import current_user, login_required
from sqlalchemy import and_, or_

from app.government import bp
from app.extensions import db
from decimal import Decimal
from app.models import (
    GovernmentElection, ElectionCandidate, ElectionVote,
    CountryPresident, CongressMember, Country, User, PoliticalParty,
    ElectionType, GovernmentElectionStatus, CandidateStatus,
    Minister, MinistryType, Law, LawStatus, War, WarStatus,
    MilitaryInventory, Resource, CountryMarketItem, Region,
    Battle, BattleStatus, RegionalConstruction
)


@bp.route('/elections')
@login_required
def elections():
    """View all government elections in user's country."""
    if not current_user.citizenship_id:
        flash('You must be a citizen of a country to view elections.', 'warning')
        return redirect(url_for('main.index'))

    # Get current and upcoming elections
    elections = db.session.scalars(
        db.select(GovernmentElection)
        .where(GovernmentElection.country_id == current_user.citizenship_id)
        .where(GovernmentElection.status != GovernmentElectionStatus.COMPLETED)
        .order_by(GovernmentElection.nominations_start.desc())
    ).all()

    # Get current politics
    current_president = db.session.scalar(
        db.select(CountryPresident)
        .where(CountryPresident.country_id == current_user.citizenship_id)
        .where(CountryPresident.is_current == True)
    )

    # Get current congress members
    current_congress = db.session.scalars(
        db.select(CongressMember)
        .where(CongressMember.country_id == current_user.citizenship_id)
        .where(CongressMember.is_current == True)
        .order_by(CongressMember.final_rank)
    ).all()

    # Get past elections (completed) - last 10
    past_elections = db.session.scalars(
        db.select(GovernmentElection)
        .where(GovernmentElection.country_id == current_user.citizenship_id)
        .where(GovernmentElection.status == GovernmentElectionStatus.COMPLETED)
        .order_by(GovernmentElection.voting_end.desc())
        .limit(10)
    ).all()

    return render_template('government/elections.html',
                          title='Government Elections',
                          elections=elections,
                          current_president=current_president,
                          current_congress=current_congress,
                          past_elections=past_elections)


@bp.route('/election/<int:election_id>')
@login_required
def election_detail(election_id):
    """View details of a specific election."""
    election = db.session.get(GovernmentElection, election_id)
    if not election:
        abort(404)

    # Check if user can view this election
    if election.country_id != current_user.citizenship_id:
        flash('You can only view elections in your country of citizenship.', 'warning')
        return redirect(url_for('government.elections'))

    # Get candidates (approved for all, pending for party presidents)
    if current_user.party and current_user.party.president_id == current_user.id:
        # Party presidents see both approved and pending candidates from their party
        candidates = db.session.scalars(
            db.select(ElectionCandidate)
            .where(ElectionCandidate.election_id == election_id)
            .where(
                or_(
                    ElectionCandidate.status == CandidateStatus.APPROVED,
                    and_(
                        ElectionCandidate.status == CandidateStatus.PENDING,
                        ElectionCandidate.party_id == current_user.party.id
                    )
                )
            )
            .order_by(ElectionCandidate.votes_received.desc())
        ).all()
    else:
        # Regular users only see approved candidates
        candidates = db.session.scalars(
            db.select(ElectionCandidate)
            .where(ElectionCandidate.election_id == election_id)
            .where(ElectionCandidate.status == CandidateStatus.APPROVED)
            .order_by(ElectionCandidate.votes_received.desc())
        ).all()

    # Check if user has voted
    user_vote = None
    if election.status == GovernmentElectionStatus.VOTING:
        user_vote = db.session.scalar(
            db.select(ElectionVote)
            .where(ElectionVote.election_id == election_id)
            .where(ElectionVote.voter_user_id == current_user.id)
        )

    # Check if user is a candidate
    user_candidacy = db.session.scalar(
        db.select(ElectionCandidate)
        .where(ElectionCandidate.election_id == election_id)
        .where(ElectionCandidate.user_id == current_user.id)
    )

    # Check if user can nominate (for presidential) or apply (for congressional)
    can_nominate = False
    can_apply = False
    is_party_president = current_user.party and current_user.party.president_id == current_user.id
    party_members = []

    if election.election_type == ElectionType.PRESIDENTIAL:
        # Can nominate if user is party politics
        if is_party_president:
            can_nominate = election.is_nominations_open()

            # Get eligible party members for nomination (including the president themselves)
            if can_nominate:
                party_members = db.session.scalars(
                    db.select(User)
                    .where(User.party_id == current_user.party.id)
                    .where(User.citizenship_id == election.country_id)
                    .where(User.is_deleted == False)
                    .where(User.is_banned == False)
                    .order_by(User.username)
                ).all()
    else:  # CONGRESSIONAL
        # Party presidents can approve/reject candidates
        if is_party_president:
            can_nominate = True  # Used to show approve/reject buttons in template

        # Can apply if user is party member
        if current_user.party:
            can_apply = election.is_nominations_open()

    # Vote transparency data
    from app.models.zk_voting import ZKVote
    from app.services.zkverify_service import zkverify_service

    zk_election_type = 'presidential' if election.election_type == ElectionType.PRESIDENTIAL else 'congressional'

    # Count regular votes
    regular_votes = election.votes.count()

    # Count and get ZK votes
    zk_vote_records = db.session.scalars(
        db.select(ZKVote)
        .where(ZKVote.election_type == zk_election_type)
        .where(ZKVote.election_id == election_id)
        .where(ZKVote.proof_verified == True)
    ).all()

    zk_votes = len(zk_vote_records)
    total_votes = regular_votes + zk_votes

    # Get zkVerify proof links
    zk_proofs = [
        zkverify_service.get_explorer_url(v.zkverify_tx_hash)
        for v in zk_vote_records if v.zkverify_tx_hash
    ]

    # Build real-time ZK vote counts per candidate (1-based index -> count)
    # This matches how voting.py assigns vote_choice (1-based index of approved candidates sorted by ID)
    approved_candidates = sorted(
        [c for c in candidates if c.status == CandidateStatus.APPROVED],
        key=lambda c: c.id
    )
    zk_index_to_candidate_id = {idx: c.id for idx, c in enumerate(approved_candidates, start=1)}

    # Count ZK votes per index
    zk_vote_counts_by_index = {}
    for record in zk_vote_records:
        if record.vote_choice > 0:
            zk_vote_counts_by_index[record.vote_choice] = zk_vote_counts_by_index.get(record.vote_choice, 0) + 1

    # Map to candidate IDs for template
    candidate_zk_votes = {}
    for zk_index, count in zk_vote_counts_by_index.items():
        if zk_index in zk_index_to_candidate_id:
            candidate_id = zk_index_to_candidate_id[zk_index]
            candidate_zk_votes[candidate_id] = count

    return render_template('government/election_detail.html',
                          title=f'{election.election_type.value.title()} Election',
                          election=election,
                          candidates=candidates,
                          user_vote=user_vote,
                          user_candidacy=user_candidacy,
                          can_nominate=can_nominate,
                          can_apply=can_apply,
                          party_members=party_members,
                          regular_votes=regular_votes,
                          zk_votes=zk_votes,
                          total_votes=total_votes,
                          zk_proofs=zk_proofs,
                          candidate_zk_votes=candidate_zk_votes)


@bp.route('/election/<int:election_id>/nominate/<int:user_id>', methods=['POST'])
@login_required
def nominate(election_id, user_id):
    """Nominate a user for presidential election (party politics only)."""
    election = db.session.get(GovernmentElection, election_id)
    if not election:
        abort(404)

    # Verify this is a presidential election
    if election.election_type != ElectionType.PRESIDENTIAL:
        flash('Nominations are only for presidential elections.', 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # Verify nomination period is open
    if not election.is_nominations_open():
        flash('Nomination period is not currently open.', 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # Verify user is party politics
    if not current_user.party or current_user.party.president_id != current_user.id:
        flash('Only party presidents can nominate candidates.', 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # Verify party is in the same country
    if current_user.party.country_id != election.country_id:
        flash('Your party must be in the same country as the election.', 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # Check if party already has a nominee
    existing_nomination = db.session.scalar(
        db.select(ElectionCandidate)
        .where(ElectionCandidate.election_id == election_id)
        .where(ElectionCandidate.party_id == current_user.party.id)
    )

    if existing_nomination:
        flash('Your party has already nominated a candidate.', 'warning')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # Get the nominee
    nominee = db.session.get(User, user_id)
    if not nominee:
        abort(404)

    # Verify nominee is in the party
    if not nominee.party or nominee.party.id != current_user.party.id:
        flash('You can only nominate members of your party.', 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # Verify nominee has citizenship
    if nominee.citizenship_id != election.country_id:
        flash('Nominee must be a citizen of the country.', 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # Verify nominee is not banned
    if nominee.is_banned:
        flash('Cannot nominate a banned user.', 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # Check if nominee is citizen of conquered country (political rights suspended)
    can_run, run_reason = nominee.can_run_for_office()
    if not can_run:
        flash(f'Cannot nominate this user: {run_reason}', 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    try:
        # Create candidacy (automatically approved for presidential)
        candidate = ElectionCandidate(
            election_id=election_id,
            user_id=nominee.id,
            party_id=current_user.party.id,
            status=CandidateStatus.APPROVED,
            nominated_by_user_id=current_user.id
        )
        candidate.approve(current_user.id)

        db.session.add(candidate)
        db.session.commit()

        current_app.logger.info(
            f"User {current_user.id} nominated user {nominee.id} for election {election_id}"
        )
        flash(f'Successfully nominated {nominee.username} for politics.', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating nomination: {e}", exc_info=True)
        flash('An error occurred. Please try again.', 'danger')

    return redirect(url_for('government.election_detail', election_id=election_id))


@bp.route('/election/<int:election_id>/apply', methods=['POST'])
@login_required
def apply(election_id):
    """Apply to run for congress (requires party politics approval)."""
    election = db.session.get(GovernmentElection, election_id)
    if not election:
        abort(404)

    # Verify this is a congressional election
    if election.election_type != ElectionType.CONGRESSIONAL:
        flash('Applications are only for congressional elections.', 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # Verify application period is open
    if not election.is_nominations_open():
        flash('Application period is not currently open.', 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # Verify user is in a party
    if not current_user.party:
        flash('You must be a member of a party to run for congress.', 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # Verify party is in the same country
    if current_user.party.country_id != election.country_id:
        flash('Your party must be in the same country as the election.', 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # Verify user has citizenship
    if current_user.citizenship_id != election.country_id:
        flash('You must be a citizen of the country to run for congress.', 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # Check if citizen of conquered country (political rights suspended)
    can_run, run_reason = current_user.can_run_for_office()
    if not can_run:
        flash(run_reason, 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # Prevent country president from running for congress
    if current_user.is_president_of(election.country_id):
        flash('As Country President, you cannot run for Congress. You must complete your presidential term first.', 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # Check if already applied
    existing_application = db.session.scalar(
        db.select(ElectionCandidate)
        .where(ElectionCandidate.election_id == election_id)
        .where(ElectionCandidate.user_id == current_user.id)
    )

    if existing_application:
        flash('You have already applied for this election.', 'warning')
        return redirect(url_for('government.election_detail', election_id=election_id))

    try:
        # Create candidacy (pending approval from party politics)
        candidate = ElectionCandidate(
            election_id=election_id,
            user_id=current_user.id,
            party_id=current_user.party.id,
            status=CandidateStatus.PENDING
        )

        db.session.add(candidate)
        db.session.commit()

        current_app.logger.info(
            f"User {current_user.id} applied for congress election {election_id}"
        )
        flash('Application submitted. Waiting for party politics approval.', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating application: {e}", exc_info=True)
        flash('An error occurred. Please try again.', 'danger')

    return redirect(url_for('government.election_detail', election_id=election_id))


@bp.route('/election/<int:election_id>/approve/<int:candidate_id>', methods=['POST'])
@login_required
def approve_candidate(election_id, candidate_id):
    """Approve a congressional candidate (party politics only)."""
    candidate = db.session.get(ElectionCandidate, candidate_id)
    if not candidate or candidate.election_id != election_id:
        abort(404)

    election = candidate.election

    # Verify this is a congressional election
    if election.election_type != ElectionType.CONGRESSIONAL:
        flash('Approval is only for congressional candidates.', 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # Verify user is the party politics
    if not current_user.party or current_user.party.id != candidate.party_id:
        flash('You can only approve candidates from your party.', 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    if current_user.party.president_id != current_user.id:
        flash('Only party presidents can approve candidates.', 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # Verify candidate is pending
    if candidate.status != CandidateStatus.PENDING:
        flash('Candidate has already been processed.', 'warning')
        return redirect(url_for('government.election_detail', election_id=election_id))

    try:
        candidate.approve(current_user.id)
        db.session.commit()

        current_app.logger.info(
            f"User {current_user.id} approved candidate {candidate_id} for election {election_id}"
        )
        flash(f'Approved {candidate.user.username} to run for congress.', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error approving candidate: {e}", exc_info=True)
        flash('An error occurred. Please try again.', 'danger')

    return redirect(url_for('government.election_detail', election_id=election_id))


@bp.route('/election/<int:election_id>/reject/<int:candidate_id>', methods=['POST'])
@login_required
def reject_candidate(election_id, candidate_id):
    """Reject a congressional candidate (party politics only)."""
    candidate = db.session.get(ElectionCandidate, candidate_id)
    if not candidate or candidate.election_id != election_id:
        abort(404)

    election = candidate.election

    # Verify user is the party politics
    if not current_user.party or current_user.party.id != candidate.party_id:
        flash('You can only reject candidates from your party.', 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    if current_user.party.president_id != current_user.id:
        flash('Only party presidents can reject candidates.', 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # Verify candidate is pending
    if candidate.status != CandidateStatus.PENDING:
        flash('Candidate has already been processed.', 'warning')
        return redirect(url_for('government.election_detail', election_id=election_id))

    try:
        candidate.reject()
        db.session.commit()

        current_app.logger.info(
            f"User {current_user.id} rejected candidate {candidate_id} for election {election_id}"
        )
        flash(f'Rejected {candidate.user.username}\'s application.', 'info')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error rejecting candidate: {e}", exc_info=True)
        flash('An error occurred. Please try again.', 'danger')

    return redirect(url_for('government.election_detail', election_id=election_id))


@bp.route('/election/<int:election_id>/vote/<int:candidate_id>', methods=['POST'])
@login_required
def vote(election_id, candidate_id):
    """Vote for a candidate with blockchain signature verification."""
    election = db.session.get(GovernmentElection, election_id)
    if not election:
        if request.is_json:
            return jsonify({'error': 'Election not found'}), 404
        abort(404)

    # Determine election type for signature
    if election.election_type.value == 'presidential':
        election_type_str = 'country_president'
    else:
        election_type_str = 'congress'

    # Check if this is a JSON request (blockchain-signed vote)
    is_blockchain_vote = request.is_json

    # Verify voting period is open
    if not election.is_voting_open():
        if is_blockchain_vote:
            return jsonify({'error': 'Voting period is not currently open.'}), 400
        flash('Voting period is not currently open.', 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # Verify user has citizenship
    if current_user.citizenship_id != election.country_id:
        if is_blockchain_vote:
            return jsonify({'error': 'You must be a citizen of the country to vote.'}), 403
        flash('You must be a citizen of the country to vote.', 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # Check if citizen of conquered country (political rights suspended)
    can_vote, vote_reason = current_user.can_vote()
    if not can_vote:
        if is_blockchain_vote:
            return jsonify({'error': vote_reason}), 403
        flash(vote_reason, 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # Check if already voted
    existing_vote = db.session.scalar(
        db.select(ElectionVote)
        .where(ElectionVote.election_id == election_id)
        .where(ElectionVote.voter_user_id == current_user.id)
    )

    if existing_vote:
        if is_blockchain_vote:
            return jsonify({'error': 'You have already voted in this election.'}), 400
        flash('You have already voted in this election.', 'warning')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # Verify candidate exists and is approved
    candidate = db.session.get(ElectionCandidate, candidate_id)
    if not candidate or candidate.election_id != election_id:
        if is_blockchain_vote:
            return jsonify({'error': 'Candidate not found'}), 404
        abort(404)

    if candidate.status != CandidateStatus.APPROVED:
        if is_blockchain_vote:
            return jsonify({'error': 'Cannot vote for this candidate.'}), 400
        flash('Cannot vote for this candidate.', 'danger')
        return redirect(url_for('government.election_detail', election_id=election_id))

    # For blockchain votes, validate signature
    wallet_address = None
    vote_message = None
    vote_signature = None

    if is_blockchain_vote:
        from app.blockchain.vote_verification import validate_vote_data

        data = request.get_json()
        wallet_address = data.get('wallet_address')
        vote_message = data.get('vote_message')
        vote_signature = data.get('vote_signature')

        # Validate the signature
        is_valid, error_msg = validate_vote_data(
            wallet_address=wallet_address,
            vote_message=vote_message,
            vote_signature=vote_signature,
            expected_election_type=election_type_str,
            expected_election_id=election_id,
            expected_candidate_id=candidate_id,
            user_wallet=current_user.wallet_address
        )

        if not is_valid:
            return jsonify({'error': error_msg}), 400

        # Check if this wallet has already voted (prevent double voting via different accounts)
        wallet_vote = db.session.scalar(
            db.select(ElectionVote)
            .where(ElectionVote.election_id == election_id)
            .where(ElectionVote.wallet_address == wallet_address.lower())
        )
        if wallet_vote:
            return jsonify({'error': 'This wallet has already been used to vote in this election.'}), 400

    try:
        # Create vote
        new_vote = ElectionVote(
            election_id=election_id,
            candidate_id=candidate_id,
            voter_user_id=current_user.id,
            ip_address=request.remote_addr,
            wallet_address=wallet_address.lower() if wallet_address else None,
            vote_message=vote_message,
            vote_signature=vote_signature
        )

        db.session.add(new_vote)

        # Increment candidate's vote count
        candidate.votes_received += 1

        db.session.commit()

        current_app.logger.info(
            f"User {current_user.id} voted for candidate {candidate_id} in election {election_id}"
            f"{' (blockchain signed)' if is_blockchain_vote else ''}"
        )

        if is_blockchain_vote:
            return jsonify({
                'success': True,
                'message': f'Successfully voted for {candidate.user.username}.',
                'blockchain_verified': True
            })

        flash(f'Successfully voted for {candidate.user.username}.', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error recording vote: {e}", exc_info=True)
        if is_blockchain_vote:
            return jsonify({'error': 'An error occurred. Please try again.'}), 500
        flash('An error occurred. Please try again.', 'danger')

    return redirect(url_for('government.election_detail', election_id=election_id))


@bp.route('/politics/<int:country_id>')
@login_required
def president(country_id):
    """View current politics of a country."""
    country = db.session.get(Country, country_id)
    if not country:
        abort(404)

    # Get current president
    current_president = db.session.scalar(
        db.select(CountryPresident)
        .where(CountryPresident.country_id == country_id)
        .where(CountryPresident.is_current == True)
    )

    # Get cabinet ministers
    ministers = db.session.scalars(
        db.select(Minister)
        .where(Minister.country_id == country_id)
        .where(Minister.is_active == True)
    ).all()

    # Organize ministers by type
    cabinet = {
        'foreign_affairs': None,
        'defence': None,
        'finance': None
    }
    for minister in ministers:
        cabinet[minister.ministry_type.value] = minister

    # Get recent laws (last 5 passed or voting)
    recent_laws = db.session.scalars(
        db.select(Law)
        .where(Law.country_id == country_id)
        .where(Law.status.in_([LawStatus.VOTING, LawStatus.PASSED]))
        .order_by(Law.created_at.desc())
        .limit(5)
    ).all()

    # Get active wars
    active_wars = db.session.scalars(
        db.select(War)
        .where(
            db.or_(
                War.attacker_country_id == country_id,
                War.defender_country_id == country_id
            )
        )
        .where(War.status == WarStatus.ACTIVE)
    ).all()

    # Get next presidential election
    next_election = db.session.scalar(
        db.select(GovernmentElection)
        .where(GovernmentElection.country_id == country_id)
        .where(GovernmentElection.election_type == ElectionType.PRESIDENTIAL)
        .where(GovernmentElection.status.in_([
            GovernmentElectionStatus.NOMINATIONS,
            GovernmentElectionStatus.VOTING
        ]))
        .order_by(GovernmentElection.voting_start.asc())
    )

    # Check if current user is the president
    is_president = current_user.is_president_of(country_id) if current_user.is_authenticated else False

    # Get past presidents
    past_presidents = db.session.scalars(
        db.select(CountryPresident)
        .where(CountryPresident.country_id == country_id)
        .where(CountryPresident.is_current == False)
        .order_by(CountryPresident.term_start.desc())
        .limit(5)
    ).all()

    return render_template('government/president.html',
                          title=f'Government of {country.name}',
                          country=country,
                          current_president=current_president,
                          cabinet=cabinet,
                          recent_laws=recent_laws,
                          active_wars=active_wars,
                          next_election=next_election,
                          is_president=is_president,
                          past_presidents=past_presidents)


@bp.route('/congress/<int:country_id>')
@login_required
def congress(country_id):
    """View current congress of a country."""
    country = db.session.get(Country, country_id)
    if not country:
        abort(404)

    # Get current congress members
    congress_members = db.session.scalars(
        db.select(CongressMember)
        .where(CongressMember.country_id == country_id)
        .where(CongressMember.is_current == True)
        .order_by(CongressMember.final_rank)
    ).all()

    # Calculate party distribution
    party_distribution = {}
    total_votes = 0
    for member in congress_members:
        party_name = member.party.name
        if party_name not in party_distribution:
            party_distribution[party_name] = {'count': 0, 'votes': 0, 'party': member.party}
        party_distribution[party_name]['count'] += 1
        party_distribution[party_name]['votes'] += member.votes_received
        total_votes += member.votes_received

    # Sort by seat count descending
    party_distribution = dict(sorted(party_distribution.items(), key=lambda x: x[1]['count'], reverse=True))

    # Check if user is congress member
    is_congress_member = current_user.is_congress_member_of(country_id) if current_user.is_authenticated else False

    # Get term info from first member if exists
    term_start = congress_members[0].term_start if congress_members else None
    term_end = congress_members[0].term_end if congress_members else None

    return render_template('government/congress.html',
                          title=f'Congress of {country.name}',
                          country=country,
                          congress_members=congress_members,
                          party_distribution=party_distribution,
                          total_votes=total_votes,
                          is_congress_member=is_congress_member,
                          term_start=term_start,
                          term_end=term_end)


# =============================================================================
# MINISTER ROUTES
# =============================================================================

@bp.route('/minister/search-citizens/<int:country_id>')
@login_required
def search_citizens_for_minister(country_id):
    """Search for citizens to assign as minister (AJAX endpoint)."""
    # Check if user is politics of this country
    country = db.session.get(Country, country_id)
    if not country:
        return jsonify({'error': 'Country not found'}), 404

    current_president = db.session.scalar(
        db.select(CountryPresident)
        .where(CountryPresident.country_id == country_id)
        .where(CountryPresident.user_id == current_user.id)
        .where(CountryPresident.is_current == True)
    )

    if not current_president:
        return jsonify({'error': 'You are not the politics of this country'}), 403

    # Get search query
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])

    # Search for citizens (citizens of this country only)
    from sqlalchemy import func
    citizens = db.session.scalars(
        db.select(User)
        .where(User.citizenship_id == country_id)
        .where(User.is_deleted == False)
        .where(User.id != current_user.id)  # President cannot assign themselves
        .where(
            or_(
                func.lower(User.username).like(f'%{query.lower()}%'),
                func.lower(User.email).like(f'%{query.lower()}%')
            )
        )
        .limit(10)
    ).all()

    # Format results
    results = []
    for citizen in citizens:
        results.append({
            'id': citizen.id,
            'username': citizen.username,
            'level': citizen.level,
            'party': citizen.party.name if citizen.party else None,
            'avatar': citizen.avatar
        })

    return jsonify(results)


@bp.route('/minister/assign', methods=['POST'])
@login_required
def assign_minister():
    """Assign a minister to a position."""
    from app.models import Minister, MinistryType

    country_id = request.form.get('country_id', type=int)
    ministry_type = request.form.get('ministry_type')
    user_id = request.form.get('user_id', type=int)

    if not all([country_id, ministry_type, user_id]):
        flash('Missing required fields.', 'danger')
        return redirect(request.referrer or url_for('main.index'))

    # Validate ministry type
    try:
        ministry_enum = MinistryType[ministry_type.upper()]
    except (KeyError, AttributeError):
        flash('Invalid ministry type.', 'danger')
        return redirect(request.referrer or url_for('main.index'))

    # Check if user is politics of this country
    country = db.session.get(Country, country_id)
    if not country:
        flash('Country not found.', 'danger')
        return redirect(request.referrer or url_for('main.index'))

    current_president = db.session.scalar(
        db.select(CountryPresident)
        .where(CountryPresident.country_id == country_id)
        .where(CountryPresident.user_id == current_user.id)
        .where(CountryPresident.is_current == True)
    )

    if not current_president:
        flash('You are not the politics of this country.', 'danger')
        return redirect(request.referrer or url_for('main.index'))

    # Get the citizen to be assigned
    citizen = db.session.get(User, user_id)
    if not citizen or citizen.citizenship_id != country_id:
        flash('Selected user is not a citizen of this country.', 'danger')
        return redirect(request.referrer or url_for('main.index'))

    # President cannot assign themselves
    if citizen.id == current_user.id:
        flash('You cannot assign yourself as a minister.', 'danger')
        return redirect(request.referrer or url_for('main.index'))

    # Check if this position already has a minister
    existing_minister = db.session.scalar(
        db.select(Minister)
        .where(Minister.country_id == country_id)
        .where(Minister.ministry_type == ministry_enum)
        .where(Minister.is_active == True)
    )

    # If there's an existing minister, deactivate them
    if existing_minister:
        existing_minister.resign()

    # Create new minister appointment
    new_minister = Minister(
        country_id=country_id,
        user_id=citizen.id,
        ministry_type=ministry_enum,
        appointed_by_user_id=current_user.id,
        is_active=True
    )
    db.session.add(new_minister)
    db.session.commit()

    ministry_names = {
        'FOREIGN_AFFAIRS': 'Minister of Foreign Affairs',
        'DEFENCE': 'Minister of Defence',
        'FINANCE': 'Minister of Finance'
    }
    ministry_name = ministry_names.get(ministry_enum.name, 'Minister')

    flash(f'Successfully appointed {citizen.username} as {ministry_name}!', 'success')
    return redirect(url_for('main.country', slug=country.slug))


@bp.route('/minister/resign/<int:minister_id>', methods=['POST'])
@login_required
def resign_minister(minister_id):
    """Resign from a minister position."""
    from app.models import Minister

    minister = db.session.get(Minister, minister_id)
    if not minister or not minister.is_active:
        flash('Minister position not found.', 'danger')
        return redirect(request.referrer or url_for('main.index'))

    # Check if current user is the minister
    if minister.user_id != current_user.id:
        flash('You are not authorized to resign this position.', 'danger')
        return redirect(request.referrer or url_for('main.index'))

    # Resign
    minister.resign()
    db.session.commit()

    ministry_names = {
        'FOREIGN_AFFAIRS': 'Minister of Foreign Affairs',
        'DEFENCE': 'Minister of Defence',
        'FINANCE': 'Minister of Finance'
    }
    ministry_name = ministry_names.get(minister.ministry_type.name, 'Minister')

    flash(f'You have resigned from your position as {ministry_name}.', 'info')
    return redirect(url_for('main.country', slug=minister.country.slug))


# =============================================================================
# LAW PROPOSAL ROUTES
# =============================================================================

@bp.route('/law/propose', methods=['GET', 'POST'])
@login_required
def propose_law():
    """Propose a new law (president or ministers only)."""
    from app.models import Law, LawType, LawStatus, Minister, MinistryType, Country
    from datetime import timedelta
    from decimal import Decimal

    if not current_user.citizenship_id:
        flash('You must be a citizen to propose laws.', 'warning')
        return redirect(url_for('main.index'))

    # Check if user is president or minister
    is_president = current_user.is_president_of(current_user.citizenship_id)
    minister_position = current_user.get_active_minister_position()
    is_congress_member = current_user.is_congress_member_of(current_user.citizenship_id)

    if not is_president and not minister_position and not is_congress_member:
        flash('Only the President, ministers, or Congress members can propose laws.', 'danger')
        return redirect(url_for('main.index'))

    # Check if citizen of conquered country (political rights suspended)
    can_propose, propose_reason = current_user.can_propose_laws()
    if not can_propose:
        flash(propose_reason, 'danger')
        return redirect(url_for('main.index'))

    # Check cooldown for congress members (not president)
    if not is_president and is_congress_member:
        if current_user.law_proposal_cooldown_until and current_user.law_proposal_cooldown_until > datetime.utcnow():
            remaining = current_user.law_proposal_cooldown_until - datetime.utcnow()
            hours_remaining = int(remaining.total_seconds() // 3600)
            minutes_remaining = int((remaining.total_seconds() % 3600) // 60)
            flash(f'You cannot propose laws for another {hours_remaining}h {minutes_remaining}m due to a previously rejected proposal.', 'warning')
            return redirect(url_for('main.country', slug=current_user.citizenship.slug))

    # All possible law types (MPA and NAP removed - replaced by Alliance system)
    ALL_LAW_TYPES = [
        'DECLARE_WAR', 'MILITARY_BUDGET', 'PRINT_CURRENCY', 'IMPORT_TAX', 'SALARY_TAX', 'INCOME_TAX', 'IMPEACHMENT',
        'EMBARGO', 'REMOVE_EMBARGO'
    ]

    # Law types that congress members can propose (not just president/ministers)
    CONGRESS_LAW_TYPES = ['IMPEACHMENT']

    # Determine user's role and available law types
    if is_president:
        user_role = 'president'
        # President can propose ALL law types
        available_law_types = ALL_LAW_TYPES.copy()
    elif minister_position:
        if minister_position.ministry_type == MinistryType.FOREIGN_AFFAIRS:
            user_role = 'minister_foreign_affairs'
            # Foreign Affairs minister: can propose embargoes, alliance management is on Alliances page
            available_law_types = ['EMBARGO', 'REMOVE_EMBARGO'] + CONGRESS_LAW_TYPES
        elif minister_position.ministry_type == MinistryType.DEFENCE:
            user_role = 'minister_defence'
            available_law_types = ['DECLARE_WAR'] + CONGRESS_LAW_TYPES
        elif minister_position.ministry_type == MinistryType.FINANCE:
            user_role = 'minister_finance'
            available_law_types = ['MILITARY_BUDGET', 'PRINT_CURRENCY', 'IMPORT_TAX', 'SALARY_TAX', 'INCOME_TAX'] + CONGRESS_LAW_TYPES
        else:
            flash('Your ministry cannot propose laws at this time.', 'warning')
            return redirect(url_for('main.index'))
    elif is_congress_member:
        user_role = 'congress_member'
        # Congress members can only propose impeachment
        available_law_types = CONGRESS_LAW_TYPES.copy()
    else:
        flash('You do not have permission to propose laws.', 'danger')
        return redirect(url_for('main.index'))

    # Check which law types already have an active proposal for this country
    active_laws = db.session.scalars(
        db.select(Law)
        .where(Law.country_id == current_user.citizenship_id)
        .where(Law.status == LawStatus.VOTING)
    ).all()

    # Get list of law types that are currently active (cannot propose another)
    active_law_types = [law.law_type.name for law in active_laws]

    # Filter out law types that already have an active proposal
    available_law_types = [lt for lt in available_law_types if lt not in active_law_types]

    # Get country treasury info for the template
    country = db.session.get(Country, current_user.citizenship_id)
    available_gold = country.treasury_gold - country.reserved_gold if country else Decimal('0')
    available_currency = country.treasury_currency - country.reserved_currency if country else Decimal('0')

    if not available_law_types:
        flash('There are already active proposals for all law types you can propose. Please wait for voting to complete.', 'warning')
        return redirect(url_for('main.country', slug=current_user.citizenship.slug))

    if request.method == 'POST':
        law_type_str = request.form.get('law_type')

        # Validate law type
        try:
            law_type = LawType[law_type_str]
        except (KeyError, AttributeError):
            flash('Invalid law type.', 'danger')
            return redirect(url_for('government.propose_law'))

        if law_type_str not in available_law_types:
            flash('You cannot propose this type of law. It may already have an active proposal.', 'danger')
            return redirect(url_for('government.propose_law'))

        # Double-check that no active law of this type exists (prevent race conditions)
        existing_active = db.session.scalar(
            db.select(Law)
            .where(Law.country_id == current_user.citizenship_id)
            .where(Law.law_type == law_type)
            .where(Law.status == LawStatus.VOTING)
        )
        if existing_active:
            flash(f'There is already an active {law_type.value.replace("_", " ").title()} proposal being voted on.', 'warning')
            return redirect(url_for('government.propose_law'))

        # Build law_details based on law type
        law_details = {}
        gold_to_reserve = Decimal('0')
        currency_to_reserve = Decimal('0')

        if law_type == LawType.DECLARE_WAR:
            target_country_id = request.form.get('target_country_id', type=int)
            if not target_country_id:
                flash('Please select a target country.', 'danger')
                return redirect(url_for('government.propose_law'))

            # Check if our country has any territory (countries with no land can only use resistance wars)
            user_country = db.session.get(Country, current_user.citizenship_id)
            if user_country:
                owned_regions_count = user_country.current_regions.count()
                if owned_regions_count == 0:
                    flash('Your country has no territory and cannot declare war. Use resistance wars to reclaim your lands.', 'danger')
                    return redirect(url_for('government.propose_law'))

            # Check if target country has starter protection
            target_country = db.session.get(Country, target_country_id)
            if target_country and target_country.has_starter_protection:
                flash(f'{target_country.name} has Starter Protection (only 1 region). Countries with starter protection cannot be attacked.', 'danger')
                return redirect(url_for('government.propose_law'))

            law_details = {'target_country_id': target_country_id}

        elif law_type == LawType.MUTUAL_PROTECTION_PACT:
            ally_country_id = request.form.get('ally_country_id', type=int)
            if not ally_country_id:
                flash('Please select an ally country.', 'danger')
                return redirect(url_for('government.propose_law'))

            # Check if we're at war with this country
            from app.models import War, WarStatus
            active_war = db.session.scalar(
                db.select(War).where(
                    or_(
                        db.and_(War.attacker_country_id == current_user.citizenship_id, War.defender_country_id == ally_country_id),
                        db.and_(War.attacker_country_id == ally_country_id, War.defender_country_id == current_user.citizenship_id)
                    )
                ).where(War.status.in_([WarStatus.ACTIVE, WarStatus.PEACE_PROPOSED]))
            )
            if active_war:
                ally_country = db.session.get(Country, ally_country_id)
                flash(f'Cannot propose a Mutual Protection Pact with {ally_country.name} while at war with them.', 'danger')
                return redirect(url_for('government.propose_law'))

            law_details = {'ally_country_id': ally_country_id}

        elif law_type == LawType.NON_AGGRESSION_PACT:
            ally_country_id = request.form.get('ally_country_id', type=int)
            if not ally_country_id:
                flash('Please select a country.', 'danger')
                return redirect(url_for('government.propose_law'))

            # Check if we're at war with this country
            from app.models import War, WarStatus
            active_war = db.session.scalar(
                db.select(War).where(
                    or_(
                        db.and_(War.attacker_country_id == current_user.citizenship_id, War.defender_country_id == ally_country_id),
                        db.and_(War.attacker_country_id == ally_country_id, War.defender_country_id == current_user.citizenship_id)
                    )
                ).where(War.status.in_([WarStatus.ACTIVE, WarStatus.PEACE_PROPOSED]))
            )
            if active_war:
                ally_country = db.session.get(Country, ally_country_id)
                flash(f'Cannot propose a Non-Aggression Pact with {ally_country.name} while at war with them.', 'danger')
                return redirect(url_for('government.propose_law'))

            law_details = {'ally_country_id': ally_country_id}

        elif law_type == LawType.MILITARY_BUDGET:
            currency_type = request.form.get('budget_currency_type')  # 'gold' or 'currency'
            amount = request.form.get('budget_amount', type=int)

            if currency_type not in ['gold', 'currency']:
                flash('Please select a currency type (Gold or Local Currency).', 'danger')
                return redirect(url_for('government.propose_law'))

            if not amount or amount <= 0:
                flash('Please enter a valid budget amount (whole numbers only).', 'danger')
                return redirect(url_for('government.propose_law'))

            if currency_type == 'gold':
                gold_to_reserve = Decimal(str(amount))
            else:
                currency_to_reserve = Decimal(str(amount))

            law_details = {
                'amount': amount,
                'currency_type': currency_type  # 'gold' or 'currency'
            }

        elif law_type == LawType.PRINT_CURRENCY:
            gold_amount = request.form.get('gold_amount', type=int)
            if not gold_amount or gold_amount <= 0:
                flash('Please enter a valid gold amount (whole numbers only).', 'danger')
                return redirect(url_for('government.propose_law'))
            gold_to_reserve = Decimal(str(gold_amount))
            currency_amount = gold_amount * 200  # 1 Gold = 200 local currency
            law_details = {'gold_amount': gold_amount, 'currency_amount': currency_amount}

        elif law_type in [LawType.IMPORT_TAX, LawType.SALARY_TAX, LawType.INCOME_TAX]:
            rate = request.form.get('rate', type=int)
            if rate is None or rate < 0 or rate > 100:
                flash('Please enter a valid tax rate (0-100%, whole numbers only).', 'danger')
                return redirect(url_for('government.propose_law'))
            # Store as decimal (0-1) for calculations
            law_details = {'rate': rate / 100.0, 'rate_percent': rate}

        elif law_type == LawType.IMPEACHMENT:
            replacement_user_id = request.form.get('replacement_user_id', type=int)
            if not replacement_user_id:
                flash('Please select a replacement president.', 'danger')
                return redirect(url_for('government.propose_law'))

            # Validate replacement user
            from app.models import User
            replacement_user = db.session.get(User, replacement_user_id)
            if not replacement_user:
                flash('Selected user not found.', 'danger')
                return redirect(url_for('government.propose_law'))

            if replacement_user.citizenship_id != current_user.citizenship_id:
                flash('Replacement president must be a citizen of this country.', 'danger')
                return redirect(url_for('government.propose_law'))

            # Check if there is a current president (optional - can also appoint when vacant)
            from app.models import CountryPresident
            current_president_record = db.session.scalar(
                db.select(CountryPresident)
                .where(CountryPresident.country_id == current_user.citizenship_id)
                .where(CountryPresident.is_current == True)
            )

            # Cannot impeach yourself (unless resigning and naming successor)
            # Actually this is allowed per user requirements (President can propose as resignation)

            law_details = {
                'replacement_user_id': replacement_user_id,
                'replacement_username': replacement_user.username,
            }

            # Include current president info if there is one
            if current_president_record:
                law_details['current_president_id'] = current_president_record.user_id
                law_details['current_president_username'] = current_president_record.user.username
            else:
                law_details['no_current_president'] = True

        elif law_type == LawType.EMBARGO:
            from app.models import Embargo
            target_country_id = request.form.get('embargo_target_country_id', type=int)
            if not target_country_id:
                flash('Please select a target country.', 'danger')
                return redirect(url_for('government.propose_law'))

            # Cannot embargo yourself
            if target_country_id == current_user.citizenship_id:
                flash('You cannot impose an embargo on your own country.', 'danger')
                return redirect(url_for('government.propose_law'))

            target_country = db.session.get(Country, target_country_id)
            if not target_country:
                flash('Target country not found.', 'danger')
                return redirect(url_for('government.propose_law'))

            # Check if already have active embargo
            existing_embargo = Embargo.has_embargo(current_user.citizenship_id, target_country_id)
            if existing_embargo:
                flash(f'There is already an active embargo between your country and {target_country.name}.', 'warning')
                return redirect(url_for('government.propose_law'))

            law_details = {
                'target_country_id': target_country_id,
                'target_country_name': target_country.name
            }

        elif law_type == LawType.REMOVE_EMBARGO:
            from app.models import Embargo
            embargo_id = request.form.get('embargo_id', type=int)
            if not embargo_id:
                flash('Please select an embargo to lift.', 'danger')
                return redirect(url_for('government.propose_law'))

            # Find the embargo
            embargo = Embargo.query.get(embargo_id)
            if not embargo:
                flash('Embargo not found.', 'danger')
                return redirect(url_for('government.propose_law'))

            # Check this country imposed the embargo
            if embargo.imposing_country_id != current_user.citizenship_id:
                flash('You can only lift embargoes that your country imposed.', 'danger')
                return redirect(url_for('government.propose_law'))

            if not embargo.is_active:
                flash('This embargo has already been lifted.', 'warning')
                return redirect(url_for('government.propose_law'))

            law_details = {
                'embargo_id': embargo_id,
                'target_country_id': embargo.target_country_id,
                'target_country_name': embargo.target_country.name
            }

        # Check and reserve gold for laws that require it
        if gold_to_reserve > 0:
            # Lock country row to prevent race conditions on treasury
            country = db.session.scalar(
                db.select(Country)
                .where(Country.id == current_user.citizenship_id)
                .with_for_update()
            )
            available_gold = country.treasury_gold - country.reserved_gold

            if gold_to_reserve > available_gold:
                flash(f'Insufficient treasury funds. Available: {available_gold:.0f} Gold, Required: {gold_to_reserve:.0f} Gold.', 'danger')
                return redirect(url_for('government.propose_law'))

            # Reserve the gold (row is locked)
            country.reserved_gold += gold_to_reserve
            law_details['reserved_gold'] = float(gold_to_reserve)

        # Check and reserve currency for laws that require it
        if currency_to_reserve > 0:
            # Lock country row to prevent race conditions on treasury (if not already locked)
            if gold_to_reserve <= 0:
                country = db.session.scalar(
                    db.select(Country)
                    .where(Country.id == current_user.citizenship_id)
                    .with_for_update()
                )
            available_currency = country.treasury_currency - country.reserved_currency

            if currency_to_reserve > available_currency:
                flash(f'Insufficient treasury funds. Available: {available_currency:.0f} {country.currency_code}, Required: {currency_to_reserve:.0f} {country.currency_code}.', 'danger')
                return redirect(url_for('government.propose_law'))

            # Reserve the currency (row is locked)
            country.reserved_currency += currency_to_reserve
            law_details['reserved_currency'] = float(currency_to_reserve)

        # Create the law proposal
        new_law = Law(
            country_id=current_user.citizenship_id,
            law_type=law_type,
            status=LawStatus.VOTING,
            proposed_by_user_id=current_user.id,
            proposed_by_role=user_role,
            law_details=law_details,
            voting_start=datetime.utcnow(),
            voting_end=datetime.utcnow() + timedelta(hours=24)  # 24 hours to vote
        )
        db.session.add(new_law)
        db.session.commit()

        flash(f'Law proposal submitted successfully! Voting is open for 24 hours.', 'success')
        return redirect(url_for('government.propose_law'))

    # GET request - show form
    # Get all countries for dropdowns
    countries = db.session.scalars(
        db.select(Country).where(Country.is_deleted == False).order_by(Country.name)
    ).all()

    # Get all laws currently being voted on (for display)
    voting_laws = db.session.scalars(
        db.select(Law)
        .where(Law.country_id == current_user.citizenship_id)
        .where(Law.status == LawStatus.VOTING)
        .order_by(Law.voting_end.asc())
    ).all()

    # Get law history from past 30 days
    from datetime import timedelta
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    law_history = db.session.scalars(
        db.select(Law)
        .where(Law.country_id == current_user.citizenship_id)
        .where(Law.status != LawStatus.VOTING)
        .where(Law.created_at >= thirty_days_ago)
        .order_by(Law.created_at.desc())
        .limit(50)
    ).all()

    # Get current president for impeachment law
    from app.models import CountryPresident, Embargo
    current_president_record = db.session.scalar(
        db.select(CountryPresident)
        .where(CountryPresident.country_id == current_user.citizenship_id)
        .where(CountryPresident.is_current == True)
    )

    # Get active embargoes imposed by this country for REMOVE_EMBARGO
    active_embargoes = db.session.scalars(
        db.select(Embargo)
        .where(Embargo.imposing_country_id == current_user.citizenship_id)
        .where(Embargo.is_active == True)
    ).all()

    return render_template('government/propose_law.html',
                          title='Laws',
                          user_role=user_role,
                          available_law_types=available_law_types,
                          countries=countries,
                          available_gold=available_gold,
                          available_currency=available_currency,
                          voting_laws=voting_laws,
                          law_history=law_history,
                          current_president=current_president_record,
                          active_embargoes=active_embargoes,
                          now=datetime.utcnow)


@bp.route('/law/<int:law_id>')
@login_required
def view_law(law_id):
    """View a specific law proposal."""
    from app.models import Law, LawVote, Country

    law = db.session.get(Law, law_id)
    if not law:
        abort(404)

    # Get all votes
    votes = db.session.scalars(
        db.select(LawVote).where(LawVote.law_id == law_id).order_by(LawVote.voted_at)
    ).all()

    # Check if current user has voted
    user_vote = None
    if current_user.is_authenticated:
        user_vote = db.session.scalar(
            db.select(LawVote)
            .where(LawVote.law_id == law_id)
            .where(LawVote.voter_user_id == current_user.id)
        )

    # Check if user can vote (politics or congress member)
    can_vote = False
    if current_user.is_authenticated and current_user.citizenship_id == law.country_id:
        can_vote = (current_user.is_president_of(law.country_id) or
                   current_user.is_congress_member_of(law.country_id))

    # Get target/ally country for war/pact laws
    target_country = None
    ally_country = None
    if law.law_details:
        target_country_id = law.law_details.get('target_country_id')
        if target_country_id:
            target_country = db.session.get(Country, target_country_id)

        ally_country_id = law.law_details.get('ally_country_id')
        if ally_country_id:
            ally_country = db.session.get(Country, ally_country_id)

    return render_template('government/view_law.html',
                          title=f'Law Proposal #{law.id}',
                          law=law,
                          votes=votes,
                          user_vote=user_vote,
                          can_vote=can_vote,
                          target_country=target_country,
                          ally_country=ally_country)


@bp.route('/law/<int:law_id>/vote', methods=['POST'])
@login_required
def vote_on_law(law_id):
    """Vote on a law proposal."""
    from app.models import Law, LawVote, LawStatus

    law = db.session.get(Law, law_id)
    if not law:
        abort(404)

    # Check if voting is still open
    if not law.is_voting_open():
        flash('Voting is closed for this law.', 'warning')
        return redirect(url_for('government.view_law', law_id=law_id))

    # Check if user is politics or congress member
    is_president = current_user.is_president_of(law.country_id)
    is_congress = current_user.is_congress_member_of(law.country_id)

    if not is_president and not is_congress:
        flash('Only the politics and congress members can vote on laws.', 'danger')
        return redirect(url_for('government.view_law', law_id=law_id))

    # Check if citizen of conquered country (political rights suspended)
    can_vote, vote_reason = current_user.can_vote()
    if not can_vote:
        flash(vote_reason, 'danger')
        return redirect(url_for('government.view_law', law_id=law_id))

    # Check if user already voted
    existing_vote = db.session.scalar(
        db.select(LawVote)
        .where(LawVote.law_id == law_id)
        .where(LawVote.voter_user_id == current_user.id)
    )

    if existing_vote:
        flash('You have already voted on this law.', 'warning')
        return redirect(url_for('government.view_law', law_id=law_id))

    # Get vote choice
    vote_choice = request.form.get('vote')
    if vote_choice not in ['for', 'against']:
        flash('Invalid vote choice.', 'danger')
        return redirect(url_for('government.view_law', law_id=law_id))

    # Create vote
    new_vote = LawVote(
        law_id=law_id,
        voter_user_id=current_user.id,
        vote=(vote_choice == 'for'),
        voter_role='politics' if is_president else 'congress_member',
        ip_address=request.remote_addr
    )
    db.session.add(new_vote)

    # Update vote counts
    if vote_choice == 'for':
        law.votes_for += 1
    else:
        law.votes_against += 1
    law.total_votes += 1

    db.session.commit()

    flash(f'Your vote has been recorded!', 'success')
    return redirect(url_for('government.view_law', law_id=law_id))


@bp.route('/war/<int:war_id>/propose-peace', methods=['POST'])
@login_required
def propose_peace(war_id):
    """Propose a peace treaty for an active war (Minister of Foreign Affairs only)."""
    from app.models import War, WarStatus, Minister, MinistryType

    war = db.session.get(War, war_id)
    if not war:
        abort(404)

    # Check if war is active
    if war.status != WarStatus.ACTIVE:
        flash('This war is not active.', 'warning')
        return redirect(url_for('main.country_detail', slug=current_user.citizenship.slug))

    # Check if user is Minister of Foreign Affairs for one of the warring countries
    minister_position = current_user.get_active_minister_position()

    if not minister_position or minister_position.ministry_type != MinistryType.FOREIGN_AFFAIRS:
        flash('Only the Minister of Foreign Affairs can propose peace treaties.', 'danger')
        return redirect(url_for('main.country_detail', slug=current_user.citizenship.slug))

    # Check if user's country is involved in this war
    if current_user.citizenship_id not in [war.attacker_country_id, war.defender_country_id]:
        flash('Your country is not involved in this war.', 'danger')
        return redirect(url_for('main.country_detail', slug=current_user.citizenship.slug))

    # Check if peace has already been proposed
    if war.status == WarStatus.PEACE_PROPOSED:
        flash('Peace has already been proposed for this war.', 'warning')
        return redirect(url_for('government.view_war', war_id=war_id))

    # Propose peace
    war.status = WarStatus.PEACE_PROPOSED
    war.peace_proposed_at = datetime.utcnow()
    war.peace_proposed_by_country_id = current_user.citizenship_id
    war.attacker_peace_votes_for = 0
    war.attacker_peace_votes_against = 0
    war.defender_peace_votes_for = 0
    war.defender_peace_votes_against = 0

    db.session.commit()

    flash('Peace treaty has been proposed. Both countries must vote to approve.', 'success')
    return redirect(url_for('government.view_war', war_id=war_id))


@bp.route('/war/<int:war_id>')
@login_required
def view_war(war_id):
    """View details of a specific war."""
    from app.models import War, WarStatus, PeaceVote

    war = db.session.get(War, war_id)
    if not war:
        abort(404)

    # Check if user's country is involved
    if not current_user.citizenship_id:
        flash('You must be a citizen of a country to view wars.', 'warning')
        return redirect(url_for('main.index'))

    # Check if user can propose peace (Minister of Foreign Affairs)
    can_propose_peace = False
    minister_position = current_user.get_active_minister_position()
    if (minister_position and
        minister_position.ministry_type.name == 'FOREIGN_AFFAIRS' and
        current_user.citizenship_id in [war.attacker_country_id, war.defender_country_id] and
        war.status == WarStatus.ACTIVE):
        can_propose_peace = True

    # Check if user can vote on peace (politics or congress member)
    can_vote_peace = False
    user_peace_vote = None
    if war.status == WarStatus.PEACE_PROPOSED:
        if current_user.citizenship_id in [war.attacker_country_id, war.defender_country_id]:
            is_president = current_user.is_president_of(current_user.citizenship_id)
            is_congress = current_user.is_congress_member_of(current_user.citizenship_id)

            if is_president or is_congress:
                can_vote_peace = True

                # Check if user has already voted
                user_peace_vote = db.session.scalar(
                    db.select(PeaceVote)
                    .where(PeaceVote.war_id == war_id)
                    .where(PeaceVote.voter_user_id == current_user.id)
                )

    return render_template('government/view_war.html',
                          title='War Details',
                          war=war,
                          can_propose_peace=can_propose_peace,
                          can_vote_peace=can_vote_peace,
                          user_peace_vote=user_peace_vote)


@bp.route('/war/<int:war_id>/vote-peace', methods=['POST'])
@login_required
def vote_peace(war_id):
    """Vote on a peace treaty proposal."""
    from app.models import War, WarStatus, PeaceVote

    war = db.session.get(War, war_id)
    if not war:
        abort(404)

    # Check if peace is being voted on
    if war.status != WarStatus.PEACE_PROPOSED:
        flash('There is no active peace proposal for this war.', 'warning')
        return redirect(url_for('government.view_war', war_id=war_id))

    # Check if user is eligible to vote (politics or congress member of involved country)
    if current_user.citizenship_id not in [war.attacker_country_id, war.defender_country_id]:
        flash('You are not eligible to vote on this peace treaty.', 'danger')
        return redirect(url_for('government.view_war', war_id=war_id))

    is_president = current_user.is_president_of(current_user.citizenship_id)
    is_congress = current_user.is_congress_member_of(current_user.citizenship_id)

    if not is_president and not is_congress:
        flash('Only the politics and congress members can vote on peace treaties.', 'danger')
        return redirect(url_for('government.view_war', war_id=war_id))

    # Check if citizen of conquered country (political rights suspended)
    can_vote, vote_reason = current_user.can_vote()
    if not can_vote:
        flash(vote_reason, 'danger')
        return redirect(url_for('government.view_war', war_id=war_id))

    # Check if user has already voted
    existing_vote = db.session.scalar(
        db.select(PeaceVote)
        .where(PeaceVote.war_id == war_id)
        .where(PeaceVote.voter_user_id == current_user.id)
    )

    if existing_vote:
        flash('You have already voted on this peace treaty.', 'warning')
        return redirect(url_for('government.view_war', war_id=war_id))

    # Get vote choice
    vote_choice = request.form.get('vote')
    if vote_choice not in ['for', 'against']:
        flash('Invalid vote choice.', 'danger')
        return redirect(url_for('government.view_war', war_id=war_id))

    # Record the vote
    voter_role = 'politics' if is_president else 'congress_member'

    peace_vote = PeaceVote(
        war_id=war_id,
        voter_user_id=current_user.id,
        country_id=current_user.citizenship_id,
        vote=(vote_choice == 'for'),
        voter_role=voter_role,
        voted_at=datetime.utcnow()
    )
    db.session.add(peace_vote)

    # Update vote counts
    if current_user.citizenship_id == war.attacker_country_id:
        if vote_choice == 'for':
            war.attacker_peace_votes_for += 1
        else:
            war.attacker_peace_votes_against += 1
    else:  # defender country
        if vote_choice == 'for':
            war.defender_peace_votes_for += 1
        else:
            war.defender_peace_votes_against += 1

    db.session.commit()

    # Check if both countries have approved peace (majority in each)
    if war.check_peace_approval():
        war.end_war_with_peace()
        db.session.commit()
        flash('Peace treaty has been approved by both countries! The war has ended.', 'success')
    else:
        flash(f'Your vote has been recorded!', 'success')

    return redirect(url_for('government.view_war', war_id=war_id))


@bp.route('/api/search-citizens')
@login_required
def search_citizens():
    """API endpoint to search for citizens of the user's country for autocomplete."""
    query = request.args.get('q', '').strip()

    if not current_user.citizenship_id:
        return jsonify([])

    if len(query) < 2:
        return jsonify([])

    # Search for users who are citizens of the same country
    users = db.session.scalars(
        db.select(User)
        .where(User.citizenship_id == current_user.citizenship_id)
        .where(User.is_deleted == False)
        .where(User.username.ilike(f'%{query}%'))
        .order_by(User.username)
        .limit(10)
    ).all()

    results = [
        {
            'id': user.id,
            'username': user.username,
            'avatar_url': user.avatar_url if hasattr(user, 'avatar_url') else None
        }
        for user in users
    ]

    return jsonify(results)


@bp.route('/ministry/defense')
@login_required
def ministry_of_defense():
    """Ministry of Defense page - shows military budget and active wars."""
    from app.models import LawType, MinistryType
    from datetime import timedelta

    if not current_user.citizenship_id:
        flash('You must be a citizen to access the Ministry of Defense.', 'warning')
        return redirect(url_for('main.index'))

    country = db.session.get(Country, current_user.citizenship_id)
    if not country:
        flash('Country not found.', 'danger')
        return redirect(url_for('main.index'))

    # Check if user has access (President, Minister of Defense, or Congress member)
    is_president = current_user.is_president_of(current_user.citizenship_id)
    minister_position = current_user.get_active_minister_position()
    is_defense_minister = minister_position and minister_position.ministry_type == MinistryType.DEFENCE
    is_congress_member = current_user.is_congress_member_of(current_user.citizenship_id)

    # Get current Minister of Defense
    defense_minister = db.session.scalar(
        db.select(Minister)
        .where(Minister.country_id == current_user.citizenship_id)
        .where(Minister.ministry_type == MinistryType.DEFENCE)
        .where(Minister.is_active == True)
    )

    # Get active wars
    active_wars = db.session.scalars(
        db.select(War)
        .where(
            or_(
                War.attacker_country_id == current_user.citizenship_id,
                War.defender_country_id == current_user.citizenship_id
            )
        )
        .where(War.status.in_([WarStatus.ACTIVE, WarStatus.PEACE_PROPOSED]))
        .order_by(War.started_at.desc())
    ).all()

    # Get military budget history (passed MILITARY_BUDGET laws in last 90 days)
    ninety_days_ago = datetime.utcnow() - timedelta(days=90)
    budget_history = db.session.scalars(
        db.select(Law)
        .where(Law.country_id == current_user.citizenship_id)
        .where(Law.law_type == LawType.MILITARY_BUDGET)
        .where(Law.status == LawStatus.PASSED)
        .where(Law.created_at >= ninety_days_ago)
        .order_by(Law.created_at.desc())
        .limit(20)
    ).all()

    # Get pending military budget proposals
    pending_budget = db.session.scalars(
        db.select(Law)
        .where(Law.country_id == current_user.citizenship_id)
        .where(Law.law_type == LawType.MILITARY_BUDGET)
        .where(Law.status == LawStatus.VOTING)
    ).all()

    # Get military inventory
    military_inventory = db.session.scalars(
        db.select(MilitaryInventory)
        .where(MilitaryInventory.country_id == country.id)
        .where(MilitaryInventory.quantity > 0)
    ).all()

    # Get Hospital and Fort resources for purchasing
    hospital_resource = db.session.scalar(
        db.select(Resource).where(Resource.name == 'Hospital')
    )
    fort_resource = db.session.scalar(
        db.select(Resource).where(Resource.name == 'Fort')
    )

    # Get market items for Hospital and Fort (Q1-Q5 only, not Q0)
    hospital_market_items = []
    fort_market_items = []

    if hospital_resource:
        hospital_market_items = db.session.scalars(
            db.select(CountryMarketItem)
            .where(CountryMarketItem.country_id == country.id)
            .where(CountryMarketItem.resource_id == hospital_resource.id)
            .where(CountryMarketItem.quality > 0)  # Exclude Q0
            .order_by(CountryMarketItem.quality)
        ).all()

    if fort_resource:
        fort_market_items = db.session.scalars(
            db.select(CountryMarketItem)
            .where(CountryMarketItem.country_id == country.id)
            .where(CountryMarketItem.resource_id == fort_resource.id)
            .where(CountryMarketItem.quality > 0)  # Exclude Q0
            .order_by(CountryMarketItem.quality)
        ).all()

    # Get regions controlled by this country for construction placement
    controlled_regions = db.session.scalars(
        db.select(Region)
        .join(Region.current_owners)
        .where(Country.id == country.id)
        .order_by(Region.name)
    ).all()

    # Get regions with active battles (cannot place constructions during battle)
    regions_with_active_battles = db.session.scalars(
        db.select(Battle.region_id)
        .where(Battle.status == BattleStatus.ACTIVE)
    ).all()

    # Filter regions that are available for construction (no active battle)
    available_regions_for_construction = [
        r for r in controlled_regions if r.id not in regions_with_active_battles
    ]

    # Get existing constructions in controlled regions
    existing_constructions = db.session.scalars(
        db.select(RegionalConstruction)
        .where(RegionalConstruction.country_id == country.id)
    ).all()

    # Build a dict of region_id -> {hospital: obj or None, fortress: obj or None}
    # Also build a JSON-serializable version for JS
    region_constructions = {}
    region_constructions_json = {}
    for construction in existing_constructions:
        if construction.region_id not in region_constructions:
            region_constructions[construction.region_id] = {'hospital': None, 'fortress': None}
            region_constructions_json[construction.region_id] = {'hospital': None, 'fortress': None}
        region_constructions[construction.region_id][construction.construction_type] = construction
        region_constructions_json[construction.region_id][construction.construction_type] = {
            'id': construction.id,
            'quality': construction.quality
        }

    # Get hospital and fortress inventory counts per quality
    hospital_inventory = {}
    fortress_inventory = {}
    for item in military_inventory:
        if hospital_resource and item.resource_id == hospital_resource.id:
            hospital_inventory[item.quality] = item.quantity
        elif fort_resource and item.resource_id == fort_resource.id:
            fortress_inventory[item.quality] = item.quantity

    return render_template('government/ministry_defense.html',
                          title='Ministry of Defense',
                          country=country,
                          is_president=is_president,
                          is_defense_minister=is_defense_minister,
                          is_congress_member=is_congress_member,
                          defense_minister=defense_minister,
                          active_wars=active_wars,
                          budget_history=budget_history,
                          pending_budget=pending_budget,
                          military_inventory=military_inventory,
                          hospital_resource=hospital_resource,
                          fort_resource=fort_resource,
                          hospital_market_items=hospital_market_items,
                          fort_market_items=fort_market_items,
                          controlled_regions=controlled_regions,
                          available_regions_for_construction=available_regions_for_construction,
                          regions_with_active_battles=regions_with_active_battles,
                          region_constructions=region_constructions,
                          region_constructions_json=region_constructions_json,
                          hospital_inventory=hospital_inventory,
                          fortress_inventory=fortress_inventory,
                          now=datetime.utcnow)


@bp.route('/ministry/defense/buy', methods=['POST'])
@login_required
def ministry_defense_buy():
    """Buy Hospital or Fort from market using military budget currency."""
    if not current_user.citizenship_id:
        return jsonify({'error': 'You must be a citizen of a country.'}), 403

    # Lock country row to prevent race conditions on military_budget
    country = db.session.scalar(
        db.select(Country).where(Country.id == current_user.citizenship_id).with_for_update()
    )
    if not country:
        return jsonify({'error': 'Country not found.'}), 404

    # Check if user is president or defense minister
    is_president = db.session.scalar(
        db.select(CountryPresident)
        .where(CountryPresident.country_id == country.id)
        .where(CountryPresident.user_id == current_user.id)
        .where(CountryPresident.is_current == True)
    ) is not None

    is_defense_minister = db.session.scalar(
        db.select(Minister)
        .where(Minister.country_id == country.id)
        .where(Minister.user_id == current_user.id)
        .where(Minister.ministry_type == MinistryType.DEFENCE)
        .where(Minister.is_active == True)
    ) is not None

    if not is_president and not is_defense_minister:
        return jsonify({'error': 'Only the President or Minister of Defense can purchase military equipment.'}), 403

    # Get form data
    resource_id = request.form.get('resource_id', type=int)
    quality = request.form.get('quality', type=int, default=1)
    quantity = request.form.get('quantity', type=int, default=1)

    if not resource_id or quantity < 1 or quality < 1 or quality > 5:
        return jsonify({'error': 'Invalid purchase parameters.'}), 400

    # Verify resource is Hospital or Fort
    resource = db.session.get(Resource, resource_id)
    if not resource or resource.name not in ['Hospital', 'Fort']:
        return jsonify({'error': 'Only Hospitals and Forts can be purchased through the Ministry of Defense.'}), 400

    # Get market item
    market_item = db.session.scalar(
        db.select(CountryMarketItem)
        .where(CountryMarketItem.country_id == country.id)
        .where(CountryMarketItem.resource_id == resource_id)
        .where(CountryMarketItem.quality == quality)
    )

    if not market_item:
        return jsonify({'error': 'This item is not available on the market.'}), 404

    # Calculate total cost
    buy_price = market_item.buy_price
    total_cost = buy_price * Decimal(str(quantity))

    # Check if military budget has enough currency
    if country.military_budget_currency < total_cost:
        return jsonify({
            'error': f'Insufficient military budget. Need {total_cost:.2f} {country.currency_code}, have {country.military_budget_currency:.2f} {country.currency_code}.'
        }), 400

    try:
        # Deduct from military budget
        country.military_budget_currency -= total_cost

        # Update market price level (buying increases price)
        volume_per_level = market_item.volume_per_level
        new_progress = market_item.progress_within_level + quantity
        levels_gained = new_progress // volume_per_level
        market_item.price_level += levels_gained
        market_item.progress_within_level = new_progress % volume_per_level

        # Add to military inventory (lock row to prevent race conditions)
        inventory_item = db.session.scalar(
            db.select(MilitaryInventory)
            .where(MilitaryInventory.country_id == country.id)
            .where(MilitaryInventory.resource_id == resource_id)
            .where(MilitaryInventory.quality == quality)
            .with_for_update()
        )

        if inventory_item:
            inventory_item.quantity += quantity
        else:
            inventory_item = MilitaryInventory(
                country_id=country.id,
                resource_id=resource_id,
                quality=quality,
                quantity=quantity
            )
            db.session.add(inventory_item)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Successfully purchased {quantity}x {resource.name} Q{quality} for {total_cost:.2f} {country.currency_code}.',
            'new_budget': float(country.military_budget_currency),
            'new_quantity': inventory_item.quantity
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in ministry defense buy: {str(e)}")
        return jsonify({'error': 'An error occurred during purchase.'}), 500


@bp.route('/ministry/defense/place-construction', methods=['POST'])
@login_required
def place_construction():
    """Place a Hospital or Fortress in a region."""
    if not current_user.citizenship_id:
        flash('You must be a citizen of a country.', 'danger')
        return redirect(url_for('main.index'))

    country = db.session.get(Country, current_user.citizenship_id)
    if not country:
        flash('Country not found.', 'danger')
        return redirect(url_for('main.index'))

    # Check if user is president or defense minister
    is_president = current_user.is_president_of(current_user.citizenship_id)
    minister_position = current_user.get_active_minister_position()
    is_defense_minister = minister_position and minister_position.ministry_type == MinistryType.DEFENCE

    if not is_president and not is_defense_minister:
        flash('Only the President or Minister of Defense can place constructions.', 'danger')
        return redirect(url_for('government.ministry_of_defense'))

    # Get form data
    region_id = request.form.get('region_id', type=int)
    construction_type = request.form.get('construction_type')  # 'hospital' or 'fortress'
    quality = request.form.get('quality', type=int)

    if not region_id or not construction_type or not quality:
        flash('Missing required fields.', 'danger')
        return redirect(url_for('government.ministry_of_defense'))

    if construction_type not in ['hospital', 'fortress']:
        flash('Invalid construction type.', 'danger')
        return redirect(url_for('government.ministry_of_defense'))

    if quality < 1 or quality > 5:
        flash('Quality must be between 1 and 5.', 'danger')
        return redirect(url_for('government.ministry_of_defense'))

    # Check if construction can be placed
    can_place, error_msg = RegionalConstruction.can_place_construction(
        region_id, country.id, construction_type
    )
    if not can_place:
        flash(error_msg, 'danger')
        return redirect(url_for('government.ministry_of_defense'))

    # Get the resource ID for hospital/fortress
    if construction_type == 'hospital':
        resource = db.session.scalar(
            db.select(Resource).where(Resource.name == 'Hospital')
        )
    else:
        resource = db.session.scalar(
            db.select(Resource).where(Resource.name == 'Fort')
        )

    if not resource:
        flash(f'{construction_type.title()} resource not found in database.', 'danger')
        return redirect(url_for('government.ministry_of_defense'))

    # Check if country has the item in military inventory
    inventory_item = db.session.scalar(
        db.select(MilitaryInventory)
        .where(MilitaryInventory.country_id == country.id)
        .where(MilitaryInventory.resource_id == resource.id)
        .where(MilitaryInventory.quality == quality)
        .with_for_update()
    )

    if not inventory_item or inventory_item.quantity < 1:
        flash(f'Insufficient {construction_type.title()} Q{quality} in military inventory.', 'danger')
        return redirect(url_for('government.ministry_of_defense'))

    try:
        # Deduct from inventory
        inventory_item.quantity -= 1

        # Create the construction
        new_construction = RegionalConstruction(
            region_id=region_id,
            country_id=country.id,
            construction_type=construction_type,
            quality=quality,
            placed_by_user_id=current_user.id
        )
        db.session.add(new_construction)

        db.session.commit()

        region = db.session.get(Region, region_id)
        flash(f'Successfully placed {construction_type.title()} Q{quality} in {region.name}! (+{quality * 5}% bonus)', 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error placing construction: {str(e)}")
        flash('An error occurred while placing the construction.', 'danger')

    return redirect(url_for('government.ministry_of_defense'))


# Note: Regional constructions (hospitals/fortresses) are permanent and cannot be removed manually.
# They are only destroyed when the region is conquered by another nation.
# See battle resolution code for destruction logic when regions change ownership.


@bp.route('/ministry/foreign-affairs')
@login_required
def ministry_of_foreign_affairs():
    """Ministry of Foreign Affairs page - shows alliances, embargoes, and diplomatic relations."""
    from app.models import LawType, MinistryType, Embargo
    from app.services.alliance_service import AllianceService

    if not current_user.citizenship_id:
        flash('You must be a citizen to access the Ministry of Foreign Affairs.', 'warning')
        return redirect(url_for('main.index'))

    country = db.session.get(Country, current_user.citizenship_id)
    if not country:
        flash('Country not found.', 'danger')
        return redirect(url_for('main.index'))

    # Check user permissions
    is_president = current_user.is_president_of(current_user.citizenship_id)
    minister_position = current_user.get_active_minister_position()
    is_foreign_affairs_minister = minister_position and minister_position.ministry_type == MinistryType.FOREIGN_AFFAIRS

    # Get current Minister of Foreign Affairs
    foreign_affairs_minister = db.session.scalar(
        db.select(Minister)
        .where(Minister.country_id == current_user.citizenship_id)
        .where(Minister.ministry_type == MinistryType.FOREIGN_AFFAIRS)
        .where(Minister.is_active == True)
    )

    # Get user's country alliance
    user_alliance = AllianceService.get_country_alliance(current_user.citizenship_id)

    # Get active embargoes (imposed by this country)
    active_embargoes = db.session.scalars(
        db.select(Embargo)
        .where(Embargo.imposing_country_id == current_user.citizenship_id)
        .where(Embargo.is_active == True)
        .order_by(Embargo.started_at.desc())
    ).all()

    # Get embargoes against this country (received)
    received_embargoes = db.session.scalars(
        db.select(Embargo)
        .where(Embargo.target_country_id == current_user.citizenship_id)
        .where(Embargo.is_active == True)
        .order_by(Embargo.started_at.desc())
    ).all()

    # Get peace treaty proposals involving this country
    peace_treaties = db.session.scalars(
        db.select(War)
        .where(
            or_(
                War.attacker_country_id == current_user.citizenship_id,
                War.defender_country_id == current_user.citizenship_id
            )
        )
        .where(War.status == WarStatus.PEACE_PROPOSED)
        .order_by(War.started_at.desc())
    ).all()

    # Get pending votes for foreign affairs related laws
    pending_votes = db.session.scalars(
        db.select(Law)
        .where(Law.country_id == current_user.citizenship_id)
        .where(Law.status == LawStatus.VOTING)
        .where(Law.law_type.in_([
            LawType.EMBARGO, LawType.REMOVE_EMBARGO,
            LawType.ALLIANCE_INVITE, LawType.ALLIANCE_JOIN,
            LawType.ALLIANCE_KICK, LawType.ALLIANCE_LEAVE, LawType.ALLIANCE_DISSOLVE
        ]))
        .order_by(Law.voting_end)
    ).all()

    return render_template('government/ministry_foreign_affairs.html',
                          title='Ministry of Foreign Affairs',
                          country=country,
                          is_president=is_president,
                          is_foreign_affairs_minister=is_foreign_affairs_minister,
                          foreign_affairs_minister=foreign_affairs_minister,
                          user_alliance=user_alliance,
                          active_embargoes=active_embargoes,
                          received_embargoes=received_embargoes,
                          peace_treaties=peace_treaties,
                          pending_votes=pending_votes,
                          now=datetime.utcnow)


@bp.route('/ministry/finance')
@login_required
def ministry_of_finance():
    """Ministry of Finance page - shows treasury, taxes, and economic data."""
    from app.models import LawType, MinistryType
    from datetime import timedelta

    if not current_user.citizenship_id:
        flash('You must be a citizen to access the Ministry of Finance.', 'warning')
        return redirect(url_for('main.index'))

    country = db.session.get(Country, current_user.citizenship_id)
    if not country:
        flash('Country not found.', 'danger')
        return redirect(url_for('main.index'))

    # Check user permissions
    is_president = current_user.is_president_of(current_user.citizenship_id)
    minister_position = current_user.get_active_minister_position()
    is_finance_minister = minister_position and minister_position.ministry_type == MinistryType.FINANCE
    is_congress_member = current_user.is_congress_member_of(current_user.citizenship_id)

    # Get current Minister of Finance
    finance_minister = db.session.scalar(
        db.select(Minister)
        .where(Minister.country_id == current_user.citizenship_id)
        .where(Minister.ministry_type == MinistryType.FINANCE)
        .where(Minister.is_active == True)
    )

    # Get current tax rates from country
    tax_rates = {
        'import_tax': country.import_tax_rate,
        'vat_tax': country.vat_tax_rate,
        'work_tax': country.work_tax_rate
    }

    # Get pending tax/finance law proposals
    finance_law_types = [LawType.IMPORT_TAX, LawType.SALARY_TAX, LawType.INCOME_TAX,
                        LawType.PRINT_CURRENCY, LawType.MILITARY_BUDGET]
    pending_laws = db.session.scalars(
        db.select(Law)
        .where(Law.country_id == current_user.citizenship_id)
        .where(Law.status == LawStatus.VOTING)
        .where(Law.law_type.in_(finance_law_types))
        .order_by(Law.voting_end)
    ).all()

    # Get recent passed finance laws (last 90 days)
    ninety_days_ago = datetime.utcnow() - timedelta(days=90)
    recent_laws = db.session.scalars(
        db.select(Law)
        .where(Law.country_id == current_user.citizenship_id)
        .where(Law.law_type.in_(finance_law_types))
        .where(Law.status == LawStatus.PASSED)
        .where(Law.created_at >= ninety_days_ago)
        .order_by(Law.created_at.desc())
        .limit(20)
    ).all()

    # Calculate treasury totals
    treasury_gold = country.treasury_gold
    treasury_currency = country.treasury_currency
    reserved_gold = country.reserved_gold
    reserved_currency = country.reserved_currency
    available_gold = treasury_gold - reserved_gold
    available_currency = treasury_currency - reserved_currency

    # Get military budget info
    military_budget_currency = country.military_budget_currency

    return render_template('government/ministry_finance.html',
                          title='Ministry of Finance',
                          country=country,
                          is_president=is_president,
                          is_finance_minister=is_finance_minister,
                          is_congress_member=is_congress_member,
                          finance_minister=finance_minister,
                          tax_rates=tax_rates,
                          pending_laws=pending_laws,
                          recent_laws=recent_laws,
                          treasury_gold=treasury_gold,
                          treasury_currency=treasury_currency,
                          reserved_gold=reserved_gold,
                          reserved_currency=reserved_currency,
                          available_gold=available_gold,
                          available_currency=available_currency,
                          military_budget_currency=military_budget_currency,
                          now=datetime.utcnow)
