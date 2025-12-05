"""Scheduled tasks for automated election management."""

from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app
import logging

logger = logging.getLogger(__name__)

scheduler = None


def init_scheduler(app):
    global scheduler

    if scheduler is not None:
        logger.warning("Scheduler already initialized")
        return scheduler

    scheduler = BackgroundScheduler(daemon=True)

    scheduler.add_job(
        func=lambda: check_and_create_elections(app),
        trigger="interval",
        hours=1,
        id='create_elections',
        name='Create monthly elections',
        replace_existing=True
    )

    scheduler.add_job(
        func=lambda: check_and_start_elections(app),
        trigger="interval",
        minutes=5,
        id='start_elections',
        name='Start scheduled elections',
        replace_existing=True
    )

    scheduler.add_job(
        func=lambda: check_and_end_elections(app),
        trigger="interval",
        minutes=5,
        id='end_elections',
        name='End active elections',
        replace_existing=True
    )

    # Government elections
    scheduler.add_job(
        func=lambda: check_and_create_government_elections(app),
        trigger="interval",
        hours=1,
        id='create_government_elections',
        name='Create monthly government elections',
        replace_existing=True
    )

    scheduler.add_job(
        func=lambda: check_and_transition_government_elections(app),
        trigger="interval",
        minutes=5,
        id='transition_government_elections',
        name='Transition government election phases',
        replace_existing=True
    )

    # Record market prices daily at 9 AM CET
    scheduler.add_job(
        func=lambda: record_daily_market_prices(app),
        trigger="cron",
        hour=8,  # 9 AM CET = 8 AM UTC (winter) or 7 AM UTC (summer), using 8 as average
        minute=0,
        id='record_market_prices',
        name='Record daily market prices at 9 AM CET',
        replace_existing=True
    )

    # Record currency exchange rates daily at 9 AM CET
    scheduler.add_job(
        func=lambda: record_daily_currency_rates(app),
        trigger="cron",
        hour=8,  # 9 AM CET = 8 AM UTC (winter) or 7 AM UTC (summer), using 8 as average
        minute=0,
        id='record_currency_rates',
        name='Record daily currency exchange rates at 9 AM CET',
        replace_existing=True
    )

    # Check and close law voting every 10 minutes
    scheduler.add_job(
        func=lambda: check_and_close_law_voting(app),
        trigger="interval",
        minutes=10,
        id='close_law_voting',
        name='Check and close law voting',
        replace_existing=True
    )

    # Check and auto-end wars after 30 days every hour
    scheduler.add_job(
        func=lambda: check_and_end_expired_wars(app),
        trigger="interval",
        hours=1,
        id='end_expired_wars',
        name='Check and end expired wars',
        replace_existing=True
    )

    # Apply NFT energy/wellness regeneration every hour
    scheduler.add_job(
        func=lambda: apply_nft_regeneration(app),
        trigger="interval",
        hours=1,
        id='nft_regeneration',
        name='Apply NFT energy/wellness regeneration',
        replace_existing=True
    )

    # Battle system: Check and complete battle rounds every 5 minutes
    scheduler.add_job(
        func=lambda: check_and_complete_battle_rounds(app),
        trigger="interval",
        minutes=5,
        id='complete_battle_rounds',
        name='Check and complete battle rounds',
        replace_existing=True
    )

    # Battle system: Check and complete battles every 5 minutes
    scheduler.add_job(
        func=lambda: check_and_complete_battles(app),
        trigger="interval",
        minutes=5,
        id='complete_battles',
        name='Check and complete battles',
        replace_existing=True
    )

    # Battle system: Check and expire war initiatives every 10 minutes
    scheduler.add_job(
        func=lambda: check_and_expire_war_initiatives(app),
        trigger="interval",
        minutes=10,
        id='expire_war_initiatives',
        name='Check and expire war initiatives',
        replace_existing=True
    )

    # Alliance system: Execute pending alliance leaves every 5 minutes
    scheduler.add_job(
        func=lambda: check_and_execute_alliance_leaves(app),
        trigger="interval",
        minutes=5,
        id='execute_alliance_leaves',
        name='Execute pending alliance leaves',
        replace_existing=True
    )

    scheduler.start()
    logger.info("Election scheduler started successfully")

    # Run law voting check immediately on startup to catch any expired laws
    # that may have ended while the server was down
    try:
        check_and_close_law_voting(app)
        logger.info("Initial law voting check completed on startup")
    except Exception as e:
        logger.error(f"Error during initial law voting check: {e}")

    # Run battle round and battle checks immediately on startup to catch any expired
    # rounds/battles that may have ended while the server was down
    try:
        check_and_complete_battle_rounds(app)
        logger.info("Initial battle rounds check completed on startup")
    except Exception as e:
        logger.error(f"Error during initial battle rounds check: {e}")

    try:
        check_and_complete_battles(app)
        logger.info("Initial battles check completed on startup")
    except Exception as e:
        logger.error(f"Error during initial battles check: {e}")

    # Run government election checks immediately on startup to catch any
    # elections that should have transitioned while the server was down
    try:
        check_and_create_government_elections(app)
        logger.info("Initial government election creation check completed on startup")
    except Exception as e:
        logger.error(f"Error during initial government election creation check: {e}")

    try:
        check_and_transition_government_elections(app)
        logger.info("Initial government election transition check completed on startup")
    except Exception as e:
        logger.error(f"Error during initial government election transition check: {e}")

    # Run party election checks immediately on startup
    try:
        check_and_create_elections(app)
        logger.info("Initial party election creation check completed on startup")
    except Exception as e:
        logger.error(f"Error during initial party election creation check: {e}")

    try:
        check_and_start_elections(app)
        logger.info("Initial party election start check completed on startup")
    except Exception as e:
        logger.error(f"Error during initial party election start check: {e}")

    try:
        check_and_end_elections(app)
        logger.info("Initial party election end check completed on startup")
    except Exception as e:
        logger.error(f"Error during initial party election end check: {e}")

    return scheduler


def shutdown_scheduler():
    global scheduler
    if scheduler is not None:
        scheduler.shutdown()
        scheduler = None
        logger.info("Election scheduler shut down")


def get_next_election_dates():
    """Party elections run from 25th 9AM CET to 26th 9AM CET."""
    from pytz import timezone as pytz_timezone

    now = datetime.now(timezone.utc)
    cet = pytz_timezone('CET')

    current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    election_start_cet = cet.localize(
        current_month.replace(day=25, hour=9, minute=0, second=0, microsecond=0, tzinfo=None)
    )
    election_start_utc = election_start_cet.astimezone(timezone.utc).replace(tzinfo=None)

    election_end_cet = cet.localize(
        current_month.replace(day=26, hour=9, minute=0, second=0, microsecond=0, tzinfo=None)
    )
    election_end_utc = election_end_cet.astimezone(timezone.utc).replace(tzinfo=None)

    if now > election_end_utc.replace(tzinfo=timezone.utc):
        next_month = current_month + relativedelta(months=1)

        election_start_cet = cet.localize(
            next_month.replace(day=25, hour=9, minute=0, second=0, microsecond=0, tzinfo=None)
        )
        election_start_utc = election_start_cet.astimezone(timezone.utc).replace(tzinfo=None)

        election_end_cet = cet.localize(
            next_month.replace(day=26, hour=9, minute=0, second=0, microsecond=0, tzinfo=None)
        )
        election_end_utc = election_end_cet.astimezone(timezone.utc).replace(tzinfo=None)

    return election_start_utc, election_end_utc


def get_presidential_election_dates(for_month=None):
    """
    Presidential elections: nominations 1st-5th 9AM CET, voting 5th-6th 9AM CET.
    Term: 6th to 6th next month.
    """
    from pytz import timezone as pytz_timezone

    now = datetime.now(timezone.utc)
    cet = pytz_timezone('CET')

    if for_month:
        current_month = for_month
    else:
        current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Nominations: 1st 9AM CET - 5th 9AM CET
    nominations_start_cet = cet.localize(
        current_month.replace(day=1, hour=9, minute=0, second=0, microsecond=0, tzinfo=None)
    )
    nominations_start_utc = nominations_start_cet.astimezone(timezone.utc).replace(tzinfo=None)

    nominations_end_cet = cet.localize(
        current_month.replace(day=5, hour=9, minute=0, second=0, microsecond=0, tzinfo=None)
    )
    nominations_end_utc = nominations_end_cet.astimezone(timezone.utc).replace(tzinfo=None)

    # Voting: 5th 9AM CET - 6th 9AM CET
    voting_start_utc = nominations_end_utc  # Same as nominations end

    voting_end_cet = cet.localize(
        current_month.replace(day=6, hour=9, minute=0, second=0, microsecond=0, tzinfo=None)
    )
    voting_end_utc = voting_end_cet.astimezone(timezone.utc).replace(tzinfo=None)

    # Term: 6th to 6th next month
    term_start_utc = voting_end_utc

    next_month = current_month + relativedelta(months=1)
    term_end_cet = cet.localize(
        next_month.replace(day=6, hour=9, minute=0, second=0, microsecond=0, tzinfo=None)
    )
    term_end_utc = term_end_cet.astimezone(timezone.utc).replace(tzinfo=None)

    return {
        'nominations_start': nominations_start_utc,
        'nominations_end': nominations_end_utc,
        'voting_start': voting_start_utc,
        'voting_end': voting_end_utc,
        'term_start': term_start_utc,
        'term_end': term_end_utc
    }


def get_congressional_election_dates(for_month=None):
    """
    Congressional elections: applications 1st-15th 9AM CET, voting 15th-16th 9AM CET.
    Term: 16th to 16th next month.
    """
    from pytz import timezone as pytz_timezone

    now = datetime.now(timezone.utc)
    cet = pytz_timezone('CET')

    if for_month:
        current_month = for_month
    else:
        current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Applications: 1st 9AM CET - 15th 9AM CET
    applications_start_cet = cet.localize(
        current_month.replace(day=1, hour=9, minute=0, second=0, microsecond=0, tzinfo=None)
    )
    applications_start_utc = applications_start_cet.astimezone(timezone.utc).replace(tzinfo=None)

    applications_end_cet = cet.localize(
        current_month.replace(day=15, hour=9, minute=0, second=0, microsecond=0, tzinfo=None)
    )
    applications_end_utc = applications_end_cet.astimezone(timezone.utc).replace(tzinfo=None)

    # Voting: 15th 9AM CET - 16th 9AM CET
    voting_start_utc = applications_end_utc  # Same as applications end

    voting_end_cet = cet.localize(
        current_month.replace(day=16, hour=9, minute=0, second=0, microsecond=0, tzinfo=None)
    )
    voting_end_utc = voting_end_cet.astimezone(timezone.utc).replace(tzinfo=None)

    # Term: 16th to 16th next month
    term_start_utc = voting_end_utc

    next_month = current_month + relativedelta(months=1)
    term_end_cet = cet.localize(
        next_month.replace(day=16, hour=9, minute=0, second=0, microsecond=0, tzinfo=None)
    )
    term_end_utc = term_end_cet.astimezone(timezone.utc).replace(tzinfo=None)

    return {
        'nominations_start': applications_start_utc,
        'nominations_end': applications_end_utc,
        'voting_start': voting_start_utc,
        'voting_end': voting_end_utc,
        'term_start': term_start_utc,
        'term_end': term_end_utc
    }


def check_and_create_elections(app):
    with app.app_context():
        from app.extensions import db
        from app.models import PoliticalParty, PartyElection, ElectionStatus

        try:
            start_time, end_time = get_next_election_dates()

            parties = db.session.scalars(
                db.select(PoliticalParty)
                .where(PoliticalParty.is_deleted == False)
            ).all()

            created_count = 0

            for party in parties:
                existing_election = db.session.scalar(
                    db.select(PartyElection)
                    .where(PartyElection.party_id == party.id)
                    .where(PartyElection.start_time == start_time)
                )

                if not existing_election:
                    election = PartyElection(
                        party_id=party.id,
                        start_time=start_time,
                        end_time=end_time,
                        status=ElectionStatus.SCHEDULED
                    )
                    db.session.add(election)
                    created_count += 1
                    logger.info(f"Created election for party {party.id} ({party.name})")

            if created_count > 0:
                db.session.commit()
                logger.info(f"Created {created_count} new elections")

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating elections: {e}", exc_info=True)


def check_and_start_elections(app):
    with app.app_context():
        from app.extensions import db
        from app.models import PartyElection, ElectionStatus

        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            scheduled_elections = db.session.scalars(
                db.select(PartyElection)
                .where(PartyElection.status == ElectionStatus.SCHEDULED)
                .where(PartyElection.start_time <= now)
            ).all()

            started_count = 0

            for election in scheduled_elections:
                election.status = ElectionStatus.ACTIVE
                started_count += 1
                logger.info(f"Started election {election.id} for party {election.party_id}")

            if started_count > 0:
                db.session.commit()
                logger.info(f"Started {started_count} elections")

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error starting elections: {e}", exc_info=True)


def check_and_end_elections(app):
    with app.app_context():
        from app.extensions import db
        from app.models import PartyElection, ElectionStatus, PoliticalParty, PartyCandidate
        from app.alert_helpers import send_election_win_alert

        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            active_elections = db.session.scalars(
                db.select(PartyElection)
                .where(PartyElection.status == ElectionStatus.ACTIVE)
                .where(PartyElection.end_time <= now)
            ).all()

            ended_count = 0

            for election in active_elections:
                winner = election.calculate_winner()

                if winner:
                    election.winner_id = winner.id

                    party = db.session.get(PoliticalParty, election.party_id)
                    if party:
                        old_president_id = party.president_id
                        party.president_id = winner.id
                        logger.info(
                            f"Election {election.id}: Party {party.id} politics changed "
                            f"from {old_president_id} to {winner.id}"
                        )

                        # Get the winner's vote count from their candidacy
                        winner_candidate = db.session.get(PartyCandidate, (election.id, winner.id))
                        vote_count = winner_candidate.get_vote_count() if winner_candidate else 0

                        # Send election win alert to the winner
                        send_election_win_alert(
                            user_id=winner.id,
                            party_name=party.name,
                            vote_count=vote_count,
                            position="Party President"
                        )
                        logger.info(f"Sent election win alert to user {winner.id}")
                else:
                    logger.warning(
                        f"Election {election.id} for party {election.party_id} had no winner "
                        "(no votes or no candidates)"
                    )

                election.status = ElectionStatus.COMPLETED
                ended_count += 1
                logger.info(f"Ended election {election.id} for party {election.party_id}")

                # Publish results to blockchain
                try:
                    from app.services.election_blockchain_service import ElectionBlockchainService
                    success, result = ElectionBlockchainService.publish_party_election_results(election)
                    if success:
                        logger.info(f"Party election {election.id} results published to blockchain: {result}")
                    else:
                        logger.warning(f"Failed to publish party election {election.id} to blockchain: {result}")
                except Exception as e:
                    logger.error(f"Error publishing party election {election.id} to blockchain: {e}", exc_info=True)

            if ended_count > 0:
                db.session.commit()
                logger.info(f"Ended {ended_count} elections")

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error ending elections: {e}", exc_info=True)


def check_and_create_government_elections(app):
    """Create government elections for the current month if they don't exist."""
    with app.app_context():
        from app.extensions import db
        from app.models import Country, GovernmentElection, ElectionType, GovernmentElectionStatus

        try:
            # Get dates for current month
            pres_dates = get_presidential_election_dates()
            cong_dates = get_congressional_election_dates()

            # Get all countries
            countries = db.session.scalars(db.select(Country)).all()

            created_count = 0

            for country in countries:
                # Check for presidential election
                existing_pres = db.session.scalar(
                    db.select(GovernmentElection)
                    .where(GovernmentElection.country_id == country.id)
                    .where(GovernmentElection.election_type == ElectionType.PRESIDENTIAL)
                    .where(GovernmentElection.nominations_start == pres_dates['nominations_start'])
                )

                if not existing_pres:
                    pres_election = GovernmentElection(
                        country_id=country.id,
                        election_type=ElectionType.PRESIDENTIAL,
                        status=GovernmentElectionStatus.NOMINATIONS,
                        nominations_start=pres_dates['nominations_start'],
                        nominations_end=pres_dates['nominations_end'],
                        voting_start=pres_dates['voting_start'],
                        voting_end=pres_dates['voting_end'],
                        term_start=pres_dates['term_start'],
                        term_end=pres_dates['term_end']
                    )
                    db.session.add(pres_election)
                    created_count += 1
                    logger.info(f"Created presidential election for country {country.id} ({country.name})")

                # Check for congressional election
                existing_cong = db.session.scalar(
                    db.select(GovernmentElection)
                    .where(GovernmentElection.country_id == country.id)
                    .where(GovernmentElection.election_type == ElectionType.CONGRESSIONAL)
                    .where(GovernmentElection.nominations_start == cong_dates['nominations_start'])
                )

                if not existing_cong:
                    cong_election = GovernmentElection(
                        country_id=country.id,
                        election_type=ElectionType.CONGRESSIONAL,
                        status=GovernmentElectionStatus.APPLICATIONS,
                        nominations_start=cong_dates['nominations_start'],
                        nominations_end=cong_dates['nominations_end'],
                        voting_start=cong_dates['voting_start'],
                        voting_end=cong_dates['voting_end'],
                        term_start=cong_dates['term_start'],
                        term_end=cong_dates['term_end']
                    )
                    db.session.add(cong_election)
                    created_count += 1
                    logger.info(f"Created congressional election for country {country.id} ({country.name})")

            if created_count > 0:
                db.session.commit()
                logger.info(f"Created {created_count} government elections")

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating government elections: {e}", exc_info=True)


def check_and_transition_government_elections(app):
    """Check and transition government elections between phases."""
    with app.app_context():
        from app.extensions import db
        from app.models import GovernmentElection, GovernmentElectionStatus, ElectionType

        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            # Transition from NOMINATIONS/APPLICATIONS to VOTING
            nomination_ending = db.session.scalars(
                db.select(GovernmentElection)
                .where(GovernmentElection.status.in_([GovernmentElectionStatus.NOMINATIONS, GovernmentElectionStatus.APPLICATIONS]))
                .where(GovernmentElection.nominations_end <= now)
                .where(GovernmentElection.voting_start <= now)
            ).all()

            for election in nomination_ending:
                election.status = GovernmentElectionStatus.VOTING
                logger.info(
                    f"Transitioned {election.election_type.value} election {election.id} "
                    f"to VOTING for country {election.country_id}"
                )

            # Transition from VOTING to COMPLETED and calculate results
            voting_ending = db.session.scalars(
                db.select(GovernmentElection)
                .where(GovernmentElection.status == GovernmentElectionStatus.VOTING)
                .where(GovernmentElection.voting_end <= now)
            ).all()

            for election in voting_ending:
                calculate_election_results(election)
                election.status = GovernmentElectionStatus.COMPLETED
                election.results_calculated_at = datetime.utcnow()
                logger.info(
                    f"Completed {election.election_type.value} election {election.id} "
                    f"for country {election.country_id}"
                )

            if nomination_ending or voting_ending:
                db.session.commit()
                logger.info(
                    f"Transitioned {len(nomination_ending)} elections to voting, "
                    f"{len(voting_ending)} elections completed"
                )

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error transitioning government elections: {e}", exc_info=True)


def calculate_election_results(election):
    """Calculate results for a government election and assign winners."""
    from app.extensions import db
    from app.models import (
        ElectionCandidate, ElectionVote, CountryPresident, CongressMember,
        CandidateStatus, ElectionType, User, Country
    )
    from app.alert_helpers import send_election_win_alert

    # Get all approved candidates with vote counts
    candidates = db.session.scalars(
        db.select(ElectionCandidate)
        .where(ElectionCandidate.election_id == election.id)
        .where(ElectionCandidate.status == CandidateStatus.APPROVED)
    ).all()

    # Count votes for each candidate
    for candidate in candidates:
        vote_count = db.session.scalar(
            db.select(db.func.count(ElectionVote.id))
            .where(ElectionVote.candidate_id == candidate.id)
        ) or 0
        candidate.votes_received = vote_count

    # Sort candidates by votes (desc), then XP (desc), then user ID (asc)
    candidates_sorted = sorted(
        candidates,
        key=lambda c: (
            -c.votes_received,  # More votes = better
            -c.user.experience,  # More XP = better
            c.user_id  # Lower ID = better
        )
    )

    # Assign ranks
    for i, candidate in enumerate(candidates_sorted, 1):
        candidate.final_rank = i

    election.total_votes_cast = db.session.scalar(
        db.select(db.func.count(ElectionVote.id))
        .where(ElectionVote.election_id == election.id)
    ) or 0

    # Get country name for alerts
    country = db.session.get(Country, election.country_id)
    country_name = country.name if country else "Unknown Country"

    if election.election_type == ElectionType.PRESIDENTIAL:
        # Presidential: Winner is rank 1
        if candidates_sorted:
            winner = candidates_sorted[0]
            winner.won_seat = True
            election.winner_user_id = winner.user_id

            # Mark old politics as not current
            old_president = db.session.scalar(
                db.select(CountryPresident)
                .where(CountryPresident.country_id == election.country_id)
                .where(CountryPresident.is_current == True)
            )
            if old_president:
                old_president.is_current = False

            # Create new politics record
            new_president = CountryPresident(
                country_id=election.country_id,
                user_id=winner.user_id,
                election_id=election.id,
                term_start=election.term_start,
                term_end=election.term_end,
                is_current=True,
                became_president_via='elected'
            )
            db.session.add(new_president)

            # Remove congress membership if the new president was a congress member
            # (A user cannot hold both President and Congress positions)
            existing_congress_seat = db.session.scalar(
                db.select(CongressMember)
                .where(CongressMember.user_id == winner.user_id)
                .where(CongressMember.country_id == election.country_id)
                .where(CongressMember.is_current == True)
            )
            if existing_congress_seat:
                existing_congress_seat.is_current = False
                existing_congress_seat.left_seat_early = True
                existing_congress_seat.left_seat_at = datetime.utcnow()
                existing_congress_seat.left_seat_reason = 'became_president'
                logger.info(
                    f"User {winner.user_id} removed from congress (became president) "
                    f"in country {election.country_id}"
                )

            logger.info(
                f"Presidential election {election.id}: "
                f"User {winner.user_id} elected politics of country {election.country_id}"
            )

            # Send election win alert to the winner
            send_election_win_alert(
                user_id=winner.user_id,
                party_name=country_name,
                vote_count=winner.votes_received,
                position="Country President"
            )
            logger.info(f"Sent presidential election win alert to user {winner.user_id}")

    else:  # CONGRESSIONAL
        # Congressional: Top 20 win seats
        winners = candidates_sorted[:20]

        # Mark old congress members as not current
        old_congress = db.session.scalars(
            db.select(CongressMember)
            .where(CongressMember.country_id == election.country_id)
            .where(CongressMember.is_current == True)
        ).all()
        for member in old_congress:
            member.is_current = False

        # Create new congress member records
        for candidate in winners:
            candidate.won_seat = True

            new_member = CongressMember(
                country_id=election.country_id,
                user_id=candidate.user_id,
                election_id=election.id,
                party_id=candidate.party_id,
                term_start=election.term_start,
                term_end=election.term_end,
                is_current=True,
                votes_received=candidate.votes_received,
                final_rank=candidate.final_rank
            )
            db.session.add(new_member)

            # Send election win alert to each congress member winner
            send_election_win_alert(
                user_id=candidate.user_id,
                party_name=country_name,
                vote_count=candidate.votes_received,
                position="Congress Member"
            )
            logger.info(f"Sent congressional election win alert to user {candidate.user_id}")

        logger.info(
            f"Congressional election {election.id}: "
            f"{len(winners)} members elected to congress of country {election.country_id}"
        )

    # Publish results to blockchain
    try:
        from app.services.election_blockchain_service import ElectionBlockchainService
        success, result = ElectionBlockchainService.publish_government_election_results(election)
        if success:
            logger.info(f"Election {election.id} results published to blockchain: {result}")
        else:
            logger.warning(f"Failed to publish election {election.id} to blockchain: {result}")
    except Exception as e:
        logger.error(f"Error publishing election {election.id} to blockchain: {e}", exc_info=True)


def record_daily_market_prices(app):
    """Record current market prices for all items at 9 AM CET daily."""
    from datetime import date
    with app.app_context():
        from app.extensions import db
        from app.models.resource import CountryMarketItem, MarketPriceHistory

        try:
            today = date.today()

            # Get all market items
            market_items = db.session.scalars(db.select(CountryMarketItem)).all()

            records_created = 0
            records_skipped = 0

            for market_item in market_items:
                # Check if record already exists for today
                existing = db.session.scalar(
                    db.select(MarketPriceHistory)
                    .where(MarketPriceHistory.country_id == market_item.country_id)
                    .where(MarketPriceHistory.resource_id == market_item.resource_id)
                    .where(MarketPriceHistory.quality == market_item.quality)
                    .where(MarketPriceHistory.recorded_date == today)
                )

                if existing:
                    records_skipped += 1
                    continue

                # Record current base price as opening price for the day
                current_price = market_item.current_base_price

                price_history = MarketPriceHistory(
                    country_id=market_item.country_id,
                    resource_id=market_item.resource_id,
                    quality=market_item.quality,
                    price_open=current_price,
                    price_high=current_price,
                    price_low=current_price,
                    price_close=current_price,
                    price=current_price,  # Keep legacy field
                    recorded_date=today,
                    created_at=datetime.utcnow()
                )

                db.session.add(price_history)
                records_created += 1

                # Commit in batches
                if records_created % 100 == 0:
                    db.session.commit()

            # Final commit
            if records_created > 0:
                db.session.commit()

            logger.info(
                f"Daily market price recording: created {records_created} records, "
                f"skipped {records_skipped} existing records"
            )

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error recording daily market prices: {e}", exc_info=True)


def record_daily_currency_rates(app):
    """Record current currency exchange rates for all gold markets at 9 AM CET daily."""
    from datetime import date
    with app.app_context():
        from app.extensions import db
        from app.models.currency_market import GoldMarket, CurrencyPriceHistory

        try:
            today = date.today()

            # Get all gold markets
            gold_markets = db.session.scalars(db.select(GoldMarket)).all()

            records_created = 0
            records_skipped = 0

            for gold_market in gold_markets:
                # Check if record already exists for today
                existing = db.session.scalar(
                    db.select(CurrencyPriceHistory)
                    .where(CurrencyPriceHistory.country_id == gold_market.country_id)
                    .where(CurrencyPriceHistory.recorded_date == today)
                )

                if existing:
                    records_skipped += 1
                    continue

                # Record current base exchange rate as opening rate for the day
                current_rate = gold_market.current_base_rate_for_one_gold

                price_history = CurrencyPriceHistory(
                    country_id=gold_market.country_id,
                    rate_open=current_rate,
                    rate_high=current_rate,
                    rate_low=current_rate,
                    rate_close=current_rate,
                    exchange_rate=current_rate,  # Keep legacy field
                    recorded_date=today,
                    created_at=datetime.utcnow()
                )

                db.session.add(price_history)
                records_created += 1

                # Commit in batches
                if records_created % 50 == 0:
                    db.session.commit()

            # Final commit
            if records_created > 0:
                db.session.commit()

            logger.info(
                f"Daily currency rate recording: created {records_created} records, "
                f"skipped {records_skipped} existing records"
            )

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error recording daily currency rates: {e}", exc_info=True)


def check_and_close_law_voting(app):
    """Check and close law voting that has expired (after 24 hours)."""
    with app.app_context():
        from app.extensions import db
        from app.models import Law, LawStatus

        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            # Find all laws with voting period ended
            expired_laws = db.session.scalars(
                db.select(Law)
                .where(Law.status == LawStatus.VOTING)
                .where(Law.voting_end <= now)
            ).all()

            closed_count = 0

            for law in expired_laws:
                # Calculate results
                law.calculate_result()
                closed_count += 1
                logger.info(
                    f"Closed voting for law {law.id} ({law.law_type.name}) in country {law.country_id}. "
                    f"Result: {'PASSED' if law.passed else 'REJECTED'} "
                    f"({law.votes_for} for, {law.votes_against} against)"
                )

                # Execute the law if it passed
                if law.passed:
                    execute_law(law, app)

            if closed_count > 0:
                db.session.commit()
                logger.info(f"Closed voting for {closed_count} laws")

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error closing law voting: {e}", exc_info=True)


def execute_law(law, app):
    """Execute a passed law."""
    from app.models import LawType

    try:
        if law.law_type == LawType.DECLARE_WAR:
            execute_war_declaration(law, app)
        elif law.law_type == LawType.MUTUAL_PROTECTION_PACT:
            execute_protection_pact(law, app)
        elif law.law_type == LawType.NON_AGGRESSION_PACT:
            execute_non_aggression_pact(law, app)
        elif law.law_type == LawType.MILITARY_BUDGET:
            execute_military_budget(law, app)
        elif law.law_type == LawType.PRINT_CURRENCY:
            execute_print_currency(law, app)
        elif law.law_type in [LawType.IMPORT_TAX, LawType.SALARY_TAX, LawType.INCOME_TAX]:
            execute_tax_law(law, app)
        elif law.law_type in [LawType.ALLIANCE_INVITE, LawType.ALLIANCE_JOIN,
                               LawType.ALLIANCE_KICK, LawType.ALLIANCE_LEAVE,
                               LawType.ALLIANCE_DISSOLVE]:
            execute_alliance_law(law, app)
        elif law.law_type == LawType.EMBARGO:
            execute_embargo(law, app)
        elif law.law_type == LawType.REMOVE_EMBARGO:
            execute_remove_embargo(law, app)

        logger.info(f"Executed law {law.id} ({law.law_type.name})")

    except Exception as e:
        logger.error(f"Error executing law {law.id}: {e}", exc_info=True)


def execute_war_declaration(law, app):
    """Execute war declaration - creates a new war between two countries."""
    from app.extensions import db
    from app.models import War, WarStatus, Country, Minister, MinistryType

    try:
        attacker_country_id = law.country_id
        defender_country_id = law.law_details.get('target_country_id')

        if not defender_country_id:
            logger.error(f"No target country specified in war declaration law {law.id}")
            return

        # Check if war already exists between these countries
        existing_war = db.session.scalar(
            db.select(War)
            .where(War.status == WarStatus.ACTIVE)
            .where(
                ((War.attacker_country_id == attacker_country_id) &
                 (War.defender_country_id == defender_country_id)) |
                ((War.attacker_country_id == defender_country_id) &
                 (War.defender_country_id == attacker_country_id))
            )
        )

        if existing_war:
            logger.warning(
                f"War already exists between countries {attacker_country_id} and {defender_country_id}"
            )
            return

        # Create new war (lasts 30 days from now)
        now = datetime.utcnow()
        war = War(
            attacker_country_id=attacker_country_id,
            defender_country_id=defender_country_id,
            status=WarStatus.ACTIVE,
            declared_by_law_id=law.id,
            started_at=now,
            scheduled_end_at=now + timedelta(days=30),
            # Attacker gets 24-hour initiative when war is declared
            initiative_holder_id=attacker_country_id,
            initiative_expires_at=now + timedelta(hours=24),
            initiative_lost=False
        )

        db.session.add(war)
        db.session.commit()

        # Get country names for logging and alerts
        attacker = db.session.get(Country, attacker_country_id)
        defender = db.session.get(Country, defender_country_id)

        logger.info(
            f"War {war.id} declared: {attacker.name if attacker else 'Unknown'} (ID {attacker_country_id}) "
            f"vs {defender.name if defender else 'Unknown'} (ID {defender_country_id}). "
            f"Scheduled to end at {war.scheduled_end_at}"
        )

        # Send war declaration alert to defending country's president and ministers
        from app.alert_helpers import send_war_declared_alert
        attacker_name = attacker.name if attacker else 'Unknown Country'
        send_war_declared_alert(defender_country_id, attacker_name, war.id)

        # Automatically end all minister positions when war is declared
        # (Ministers resign when country goes to war - this is optional but adds realism)
        # NOTE: Comment this out if ministers should stay during war
        """
        ministers = db.session.scalars(
            db.select(Minister)
            .where(Minister.country_id.in_([attacker_country_id, defender_country_id]))
            .where(Minister.is_active == True)
        ).all()

        for minister in ministers:
            minister.resign()

        if ministers:
            db.session.commit()
            logger.info(f"Resigned {len(ministers)} ministers due to war declaration")
        """

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error executing war declaration law {law.id}: {e}", exc_info=True)
        raise


def execute_protection_pact(law, app):
    """Execute mutual protection pact."""
    # TODO: Implement pact system
    # Will need Pact/Treaty model
    logger.info(f"Protection pact law {law.id} passed (execution pending pact system implementation)")


def execute_non_aggression_pact(law, app):
    """Execute non-aggression pact."""
    # TODO: Implement pact system
    logger.info(f"Non-aggression pact law {law.id} passed (execution pending pact system implementation)")


def execute_military_budget(law, app):
    """Execute military budget allocation - add reserved funds to military budget.

    Note: The funds were already deducted from treasury in calculate_result() when the law passed.
    Here we just add them to the military budget.
    """
    from app.extensions import db
    from app.models import Country
    from decimal import Decimal

    amount = Decimal(str(law.law_details.get('amount', 0)))
    currency_type = law.law_details.get('currency_type', 'gold')

    if amount <= 0:
        logger.error(f"Invalid amount in military budget law {law.id}")
        return

    # Lock country row to prevent race conditions on military budget
    from sqlalchemy import select
    country = db.session.scalar(
        select(Country).where(Country.id == law.country_id).with_for_update()
    )
    if not country:
        logger.error(f"Country {law.country_id} not found for law {law.id}")
        return

    if currency_type == 'gold':
        # Add gold to military budget (already deducted from treasury in calculate_result)
        country.military_budget_gold += amount
        logger.info(
            f"Military budget law {law.id}: Added {amount} Gold to military budget "
            f"for {country.name}. New military budget: {country.military_budget_gold} Gold"
        )
    else:
        # Add local currency to military budget (already deducted from treasury in calculate_result)
        country.military_budget_currency += amount
        logger.info(
            f"Military budget law {law.id}: Added {amount} {country.currency_code} to military budget "
            f"for {country.name}. New military budget: {country.military_budget_currency} {country.currency_code}"
        )

    db.session.commit()


def execute_print_currency(law, app):
    """Execute currency printing - add printed currency to treasury.

    Note: The gold cost was already deducted from treasury in calculate_result() when the law passed.
    Here we just add the printed currency to the treasury.
    """
    from app.extensions import db
    from app.models import Country
    from decimal import Decimal
    from sqlalchemy import select

    gold_amount = Decimal(str(law.law_details.get('gold_amount', 0)))
    currency_amount = Decimal(str(law.law_details.get('currency_amount', 0)))

    if gold_amount <= 0 or currency_amount <= 0:
        logger.error(f"Invalid amounts in print currency law {law.id}")
        return

    # Lock country row to prevent race conditions on treasury
    country = db.session.scalar(
        select(Country).where(Country.id == law.country_id).with_for_update()
    )
    if not country:
        logger.error(f"Country {law.country_id} not found for law {law.id}")
        return

    # Add printed currency to treasury (gold was already consumed in calculate_result)
    country.treasury_currency += currency_amount

    logger.info(
        f"Print currency law {law.id}: Printed {currency_amount} {country.currency_code} "
        f"(from {gold_amount} Gold) for {country.name}. "
        f"New treasury: {country.treasury_currency} {country.currency_code}"
    )

    db.session.commit()


def execute_tax_law(law, app):
    """Execute tax law (import, salary, or income tax)."""
    from app.extensions import db
    from app.models import Country, LawType
    from decimal import Decimal

    rate = law.law_details.get('rate', 0)
    country = db.session.get(Country, law.country_id)

    if not country:
        logger.error(f"Country {law.country_id} not found for law {law.id}")
        return

    # Convert rate to percentage (e.g., 0.15 -> 15.0)
    rate_percentage = Decimal(str(rate * 100))

    # Map law type to country tax field
    old_rate = None
    if law.law_type == LawType.IMPORT_TAX:
        old_rate = country.import_tax_rate
        country.import_tax_rate = rate_percentage
    elif law.law_type == LawType.SALARY_TAX:
        old_rate = country.work_tax_rate
        country.work_tax_rate = rate_percentage
    elif law.law_type == LawType.INCOME_TAX:
        old_rate = country.vat_tax_rate
        country.vat_tax_rate = rate_percentage
    else:
        logger.warning(f"Unknown tax law type: {law.law_type}")
        return

    db.session.commit()

    tax_name = law.law_type.name.replace('_', ' ').title()
    logger.info(
        f"Updated {tax_name} from {old_rate}% to {rate_percentage}% for country {country.name} (law {law.id})"
    )


def check_and_execute_alliance_leaves(app):
    """Check for approved alliance leaves that need to be executed."""
    with app.app_context():
        from app.services.alliance_service import AllianceService

        try:
            AllianceService.execute_pending_leaves()
            logger.debug("Checked for pending alliance leaves")
        except Exception as e:
            logger.error(f"Error executing alliance leaves: {e}", exc_info=True)


def execute_alliance_law(law, app):
    """Execute alliance-related laws."""
    from app.services.alliance_service import AllianceService
    from app.models import LawType

    try:
        if law.law_type == LawType.ALLIANCE_INVITE:
            AllianceService.process_invitation_vote(law)
        elif law.law_type == LawType.ALLIANCE_JOIN:
            AllianceService.process_invitation_vote(law)
        elif law.law_type == LawType.ALLIANCE_KICK:
            AllianceService.process_kick_vote(law)
        elif law.law_type == LawType.ALLIANCE_LEAVE:
            AllianceService.process_leave_vote(law)
        elif law.law_type == LawType.ALLIANCE_DISSOLVE:
            AllianceService.process_dissolution_vote(law)

        logger.info(f"Processed alliance law {law.id} ({law.law_type.name})")

    except Exception as e:
        logger.error(f"Error executing alliance law {law.id}: {e}", exc_info=True)
        raise


def execute_embargo(law, app):
    """Execute a trade embargo law - creates an embargo between two countries."""
    from app.extensions import db
    from app.models import Embargo, Country

    try:
        imposing_country_id = law.country_id
        target_country_id = law.law_details.get('target_country_id')

        if not target_country_id:
            logger.error(f"No target country specified in embargo law {law.id}")
            return

        # Check if embargo already exists
        existing = Embargo.has_embargo(imposing_country_id, target_country_id)
        if existing:
            logger.warning(
                f"Embargo already exists between countries {imposing_country_id} and {target_country_id}"
            )
            return

        # Create the embargo
        embargo = Embargo(
            imposing_country_id=imposing_country_id,
            target_country_id=target_country_id,
            imposed_by_law_id=law.id,
            started_at=datetime.utcnow(),
            is_active=True
        )

        db.session.add(embargo)
        db.session.commit()

        # Get country names for logging
        imposing = db.session.get(Country, imposing_country_id)
        target = db.session.get(Country, target_country_id)

        logger.info(
            f"Embargo created: {imposing.name if imposing else 'Unknown'} imposed embargo on "
            f"{target.name if target else 'Unknown'} (law {law.id})"
        )

    except Exception as e:
        logger.error(f"Error executing embargo law {law.id}: {e}", exc_info=True)
        db.session.rollback()
        raise


def execute_remove_embargo(law, app):
    """Execute a remove embargo law - lifts an existing embargo."""
    from app.extensions import db
    from app.models import Embargo, Country

    try:
        embargo_id = law.law_details.get('embargo_id')

        if not embargo_id:
            logger.error(f"No embargo ID specified in remove embargo law {law.id}")
            return

        # Find the embargo
        embargo = db.session.get(Embargo, embargo_id)
        if not embargo:
            logger.warning(f"Embargo {embargo_id} not found for law {law.id}")
            return

        if not embargo.is_active:
            logger.warning(f"Embargo {embargo_id} is already inactive")
            return

        # End the embargo
        embargo.is_active = False
        embargo.ended_at = datetime.utcnow()
        embargo.ended_by_law_id = law.id

        db.session.commit()

        # Get country names for logging
        imposing = db.session.get(Country, embargo.imposing_country_id)
        target = db.session.get(Country, embargo.target_country_id)

        logger.info(
            f"Embargo lifted: {imposing.name if imposing else 'Unknown'} lifted embargo on "
            f"{target.name if target else 'Unknown'} (law {law.id})"
        )

    except Exception as e:
        logger.error(f"Error executing remove embargo law {law.id}: {e}", exc_info=True)
        db.session.rollback()
        raise


def check_and_end_expired_wars(app):
    """Check for wars that have reached their 30-day expiration and auto-end them."""
    with app.app_context():
        from app.extensions import db
        from app.models import War, WarStatus, Country

        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            # Find all active wars that have expired
            expired_wars = db.session.scalars(
                db.select(War)
                .where(War.status == WarStatus.ACTIVE)
                .where(War.scheduled_end_at <= now)
            ).all()

            ended_count = 0

            for war in expired_wars:
                war.status = WarStatus.ENDED_EXPIRED
                war.ended_at = now
                ended_count += 1

                # Get country names for logging
                attacker = db.session.get(Country, war.attacker_country_id)
                defender = db.session.get(Country, war.defender_country_id)

                logger.info(
                    f"War {war.id} automatically ended after 30 days: "
                    f"{attacker.name if attacker else 'Unknown'} vs "
                    f"{defender.name if defender else 'Unknown'}"
                )

            if ended_count > 0:
                db.session.commit()
                logger.info(f"Auto-ended {ended_count} expired wars")

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error checking and ending expired wars: {e}", exc_info=True)


def apply_nft_regeneration(app):
    """Apply NFT-based energy and wellness regeneration for all users with equipped NFTs."""
    with app.app_context():
        from app.extensions import db
        from app.models import User
        from app.models.nft import PlayerNFTSlots, NFTInventory
        from app.services.bonus_calculator import BonusCalculator

        try:
            # Get all users who have NFT slots (meaning they might have equipped NFTs)
            users_with_slots = db.session.scalars(
                db.select(User)
                .join(PlayerNFTSlots, User.id == PlayerNFTSlots.user_id)
            ).all()

            regen_count = 0
            total_energy_regen = 0
            total_wellness_regen = 0

            for user in users_with_slots:
                # Get regeneration rates from equipped NFTs (1 hour elapsed)
                energy_regen, wellness_regen = BonusCalculator.regenerate_energy_wellness(user.id, 1.0)

                if energy_regen > 0 or wellness_regen > 0:
                    # Apply regeneration (capped at 100)
                    old_energy = user.energy
                    old_wellness = user.wellness

                    user.energy = min(100, user.energy + energy_regen)
                    user.wellness = min(100, user.wellness + wellness_regen)

                    actual_energy_gain = user.energy - old_energy
                    actual_wellness_gain = user.wellness - old_wellness

                    if actual_energy_gain > 0 or actual_wellness_gain > 0:
                        regen_count += 1
                        total_energy_regen += actual_energy_gain
                        total_wellness_regen += actual_wellness_gain

                        logger.debug(
                            f"NFT regen for user {user.id}: "
                            f"+{actual_energy_gain} energy, +{actual_wellness_gain} wellness"
                        )

            if regen_count > 0:
                db.session.commit()
                logger.info(
                    f"NFT regeneration applied to {regen_count} users: "
                    f"+{total_energy_regen} total energy, +{total_wellness_regen} total wellness"
                )

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error applying NFT regeneration: {e}", exc_info=True)


def check_and_complete_battle_rounds(app):
    """Check for battle rounds that have ended (8 hours) and complete them."""
    with app.app_context():
        from app.extensions import db
        from app.models import Battle, BattleRound
        from app.models.battle import BattleStatus, RoundStatus
        from app.services.battle_service import BattleService

        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            # Find all active rounds that have ended
            expired_rounds = db.session.scalars(
                db.select(BattleRound)
                .join(Battle, BattleRound.battle_id == Battle.id)
                .where(Battle.status == BattleStatus.ACTIVE)
                .where(BattleRound.status == RoundStatus.ACTIVE)
                .where(BattleRound.ends_at <= now)
            ).all()

            completed_count = 0

            for round in expired_rounds:
                battle = db.session.get(Battle, round.battle_id)
                if battle:
                    BattleService.complete_round(battle, round)
                    completed_count += 1
                    logger.info(
                        f"Completed round {round.round_number} for battle {battle.id} "
                        f"(Region: {battle.region.name if battle.region else 'Unknown'})"
                    )

            if completed_count > 0:
                db.session.commit()
                logger.info(f"Completed {completed_count} battle rounds")

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error completing battle rounds: {e}", exc_info=True)


def check_and_complete_battles(app):
    """Check for battles that have ended (all 3 rounds done or 24 hours) and complete them."""
    with app.app_context():
        from app.extensions import db
        from app.models import Battle, BattleRound
        from app.models.battle import BattleStatus, RoundStatus
        from app.services.battle_service import BattleService

        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            # Find all active battles that have ended (24 hours passed)
            expired_battles = db.session.scalars(
                db.select(Battle)
                .where(Battle.status == BattleStatus.ACTIVE)
                .where(Battle.ends_at <= now)
            ).all()

            completed_count = 0

            for battle in expired_battles:
                # First, complete any remaining active rounds
                active_round = battle.get_current_round()
                if active_round and active_round.status == RoundStatus.ACTIVE:
                    BattleService.complete_round(battle, active_round)

                # Now complete the battle
                BattleService.complete_battle(battle)
                completed_count += 1
                logger.info(
                    f"Completed battle {battle.id} "
                    f"(Region: {battle.region.name if battle.region else 'Unknown'}) - "
                    f"Attacker rounds: {battle.attacker_rounds_won}, "
                    f"Defender rounds: {battle.defender_rounds_won}"
                )

            if completed_count > 0:
                db.session.commit()
                logger.info(f"Completed {completed_count} battles")

            # Also check for battles where all 3 rounds are done but battle wasn't completed
            battles_all_rounds_done = db.session.scalars(
                db.select(Battle)
                .where(Battle.status == BattleStatus.ACTIVE)
                .where(Battle.current_round >= 3)
            ).all()

            for battle in battles_all_rounds_done:
                # Check if last round is completed
                round_3 = db.session.scalar(
                    db.select(BattleRound)
                    .where(BattleRound.battle_id == battle.id)
                    .where(BattleRound.round_number == 3)
                )
                if round_3 and round_3.status == RoundStatus.COMPLETED:
                    BattleService.complete_battle(battle)
                    logger.info(
                        f"Completed battle {battle.id} (all 3 rounds finished) - "
                        f"Attacker: {battle.attacker_rounds_won}, Defender: {battle.defender_rounds_won}"
                    )

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error completing battles: {e}", exc_info=True)


def check_and_expire_war_initiatives(app):
    """Check for war initiatives that have expired (24 hours) and mark them."""
    with app.app_context():
        from app.extensions import db
        from app.models import War, WarStatus

        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            # Find wars with expired initiatives
            wars_with_expired_initiative = db.session.scalars(
                db.select(War)
                .where(War.status == WarStatus.ACTIVE)
                .where(War.initiative_holder_id.isnot(None))
                .where(War.initiative_expires_at <= now)
                .where(War.initiative_lost == False)
            ).all()

            expired_count = 0

            for war in wars_with_expired_initiative:
                war.lose_initiative()
                expired_count += 1
                logger.info(
                    f"Initiative expired for war {war.id}: "
                    f"{war.attacker_country.name if war.attacker_country else 'Unknown'} vs "
                    f"{war.defender_country.name if war.defender_country else 'Unknown'}"
                )

            if expired_count > 0:
                db.session.commit()
                logger.info(f"Expired {expired_count} war initiatives")

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error expiring war initiatives: {e}", exc_info=True)
