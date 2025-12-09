# app/main/routes.py
# Contains core routes like index and request handlers

from flask import render_template, redirect, url_for, flash, request, jsonify, send_from_directory
from flask_login import current_user, login_required
from app.main import bp
from app.extensions import db
from app.models import PartyElection, ElectionStatus, Referral, ReferralStatus, Country, Region, Article, NewspaperSubscription, ArticleVote, GovernmentElection, GovernmentElectionStatus, ElectionType
from app.models.government import Law, LawStatus, War, WarStatus
from app.models.battle import Battle, BattleStatus
from app.services.mission_service import MissionService
from datetime import datetime, timedelta
from sqlalchemy import func
import json
import os
# Note: Other imports moved to specific route files

# --- Before Request Handler ---
@bp.before_request
def before_request():
    # Ensure user is authenticated before checking profile status
    if not current_user.is_authenticated:
        return

    # Process automatic residence restoration
    try:
        restored, wellness_restored, energy_restored = current_user.process_residence_restoration()
        if restored:
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        # Log error but don't block the request
        import logging
        logging.error(f"Error processing residence restoration: {e}")

    # Check if user is banned and log them out immediately
    if current_user.is_banned:
        # Check if temporary ban has expired
        if not current_user.check_and_clear_expired_ban():
            # User is still banned - force logout
            from flask_login import logout_user
            ban_message = current_user.ban_reason if current_user.ban_reason else "Your account has been banned."
            if current_user.banned_until:
                ban_message += f" Ban expires: {current_user.banned_until.strftime('%Y-%m-%d %H:%M UTC')}"
            else:
                ban_message += " This ban is permanent."

            logout_user()
            flash(ban_message, 'danger')
            return redirect(url_for('main.index'))
        else:
            # Ban expired, allow continued access
            db.session.commit()

    # Define allowed endpoints during setup phases
    allowed_endpoints = [
        'static',
        'main.choose_citizenship',
        'main.edit_profile',
        'main.api_regions', # Needed for citizenship/travel forms
        'auth.logout' # Allow logout anytime
    ]

    # 1. Check for Citizenship
    if current_user.citizenship_id is None:
        if request.endpoint and request.endpoint not in allowed_endpoints and not request.endpoint.startswith('auth.'):
             flash('Please choose your citizenship to continue.', 'info')
             return redirect(url_for('main.choose_citizenship'))

    # 2. Check for Username (only if citizenship IS set)
    elif current_user.username is None:
         if request.endpoint and request.endpoint not in allowed_endpoints:
             flash('Please set up your profile username to continue.', 'info')
             return redirect(url_for('main.edit_profile'))


@bp.route('/')
@bp.route('/index')
def index():
    # The before_request handler handles redirects for setup
    if current_user.is_authenticated:
        # Redirect to edit profile if username is still missing (should be caught by before_request mostly)
        if not current_user.username:
             flash('Please set up your profile username.', 'info')
             return redirect(url_for('main.edit_profile'))

        # Check for current party election (only active, not scheduled)
        current_election = None
        if current_user.party:
            current_election = db.session.scalar(
                db.select(PartyElection)
                .where(PartyElection.party_id == current_user.party.id)
                .where(PartyElection.status == ElectionStatus.ACTIVE)
                .order_by(PartyElection.start_time.desc())
            )

        # Check for government elections currently in VOTING status
        active_government_election = None
        active_government_election_type = None
        if current_user.citizenship_id:
            active_gov_election = db.session.scalar(
                db.select(GovernmentElection)
                .where(GovernmentElection.country_id == current_user.citizenship_id)
                .where(GovernmentElection.status == GovernmentElectionStatus.VOTING)
                .order_by(GovernmentElection.voting_end.asc())
            )
            if active_gov_election:
                active_government_election = active_gov_election
                active_government_election_type = 'presidential' if active_gov_election.election_type == ElectionType.PRESIDENTIAL else 'congressional'

        # Find next scheduled election based on calendar
        # Schedule: Presidential voting 5th-6th, Congressional voting 15th-16th, Party voting 25th-26th
        next_election = None
        next_election_type = None
        next_election_info = None  # For calculated future elections
        now = datetime.utcnow()
        current_day = now.day

        # Determine which election type is next based on calendar day
        # After 6th until 14th: Congressional is next (voting 15th-16th)
        # After 16th until 24th: Party is next (voting 25th-26th)
        # After 26th until 4th: Presidential is next (voting 5th-6th)
        if current_day >= 6 and current_day < 15:
            upcoming_type = 'congressional'
        elif current_day >= 16 and current_day < 25:
            upcoming_type = 'party'
        else:
            upcoming_type = 'presidential'

        # Get the appropriate election based on upcoming type
        if upcoming_type == 'party' and current_user.party:
            next_party_election = db.session.scalar(
                db.select(PartyElection)
                .where(PartyElection.party_id == current_user.party.id)
                .where(PartyElection.status == ElectionStatus.SCHEDULED)
                .where(PartyElection.start_time > now)
                .order_by(PartyElection.start_time.asc())
            )
            if next_party_election:
                next_election = next_party_election
                next_election_type = 'party'

        elif upcoming_type in ['presidential', 'congressional'] and current_user.citizenship_id:
            # Look for existing government election in nomination/application/voting phase
            target_election_type = ElectionType.PRESIDENTIAL if upcoming_type == 'presidential' else ElectionType.CONGRESSIONAL
            next_gov_election = db.session.scalar(
                db.select(GovernmentElection)
                .where(GovernmentElection.country_id == current_user.citizenship_id)
                .where(GovernmentElection.election_type == target_election_type)
                .where(GovernmentElection.status.in_([
                    GovernmentElectionStatus.NOMINATIONS,
                    GovernmentElectionStatus.APPLICATIONS,
                    GovernmentElectionStatus.VOTING
                ]))
                .where(GovernmentElection.voting_end > now)
                .order_by(GovernmentElection.voting_start.asc())
            )
            if next_gov_election:
                next_election = next_gov_election
                next_election_type = upcoming_type
            else:
                # No active election found, calculate next scheduled dates
                from dateutil.relativedelta import relativedelta

                # Determine which month the next election will be in
                if upcoming_type == 'presidential':
                    # Voting 5th-6th
                    if current_day >= 6:
                        # Next month
                        election_month = now.replace(day=1) + relativedelta(months=1)
                    else:
                        election_month = now.replace(day=1)
                    voting_start = election_month.replace(day=5, hour=8, minute=0, second=0, microsecond=0)
                    voting_end = election_month.replace(day=6, hour=8, minute=0, second=0, microsecond=0)
                    nominations_start = election_month.replace(day=1, hour=8, minute=0, second=0, microsecond=0)
                else:  # congressional
                    # Voting 15th-16th
                    if current_day >= 16:
                        # Next month
                        election_month = now.replace(day=1) + relativedelta(months=1)
                    else:
                        election_month = now.replace(day=1)
                    voting_start = election_month.replace(day=15, hour=8, minute=0, second=0, microsecond=0)
                    voting_end = election_month.replace(day=16, hour=8, minute=0, second=0, microsecond=0)
                    nominations_start = election_month.replace(day=1, hour=8, minute=0, second=0, microsecond=0)

                # Create info dict for template (no DB record exists yet)
                next_election_info = {
                    'type': upcoming_type,
                    'voting_start': voting_start,
                    'voting_end': voting_end,
                    'nominations_start': nominations_start,
                    'country': current_user.citizenship
                }
                next_election_type = upcoming_type

        # If no election found for the primary upcoming type, fall back to checking all types
        if not next_election and not next_election_info:
            # Check for next party election (if user has a party)
            if current_user.party:
                next_party_election = db.session.scalar(
                    db.select(PartyElection)
                    .where(PartyElection.party_id == current_user.party.id)
                    .where(PartyElection.status == ElectionStatus.SCHEDULED)
                    .where(PartyElection.start_time > now)
                    .order_by(PartyElection.start_time.asc())
                )
                if next_party_election:
                    next_election = next_party_election
                    next_election_type = 'party'

            # Check for next government elections (if user has citizenship)
            if not next_election and current_user.citizenship_id:
                next_gov_election = db.session.scalar(
                    db.select(GovernmentElection)
                    .where(GovernmentElection.country_id == current_user.citizenship_id)
                    .where(GovernmentElection.status.in_([
                        GovernmentElectionStatus.NOMINATIONS,
                        GovernmentElectionStatus.APPLICATIONS
                    ]))
                    .where(GovernmentElection.voting_end > now)
                    .order_by(GovernmentElection.nominations_start.asc())
                )

                if next_gov_election:
                    next_election = next_gov_election
                    next_election_type = 'presidential' if next_gov_election.election_type.value == 'presidential' else 'congressional'

        # Fetch articles for newspaper tabs (only articles from last 24 hours visible in feeds)
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)

        # Tab 1: Latest articles from user's country (last 24 hours)
        latest_country_articles = []
        if current_user.citizenship_id:
            latest_country_articles = db.session.scalars(
                db.select(Article)
                .join(Article.newspaper)
                .where(Article.is_deleted == False)
                .where(Article.created_at >= twenty_four_hours_ago)
                .where(Article.newspaper.has(country_id=current_user.citizenship_id))
                .order_by(Article.created_at.desc())
                .limit(5)
            ).all()

        # Tab 2: Top articles from user's country (last 24 hours, sorted by votes)
        top_country_articles = []
        if current_user.citizenship_id:
            # Use a subquery to count votes
            vote_count_subq = (
                db.select(ArticleVote.article_id, func.count(ArticleVote.id).label('vote_count'))
                .group_by(ArticleVote.article_id)
                .subquery()
            )

            top_country_articles = db.session.scalars(
                db.select(Article)
                .join(Article.newspaper)
                .outerjoin(vote_count_subq, Article.id == vote_count_subq.c.article_id)
                .where(Article.is_deleted == False)
                .where(Article.created_at >= twenty_four_hours_ago)
                .where(Article.newspaper.has(country_id=current_user.citizenship_id))
                .order_by(func.coalesce(vote_count_subq.c.vote_count, 0).desc())
                .limit(5)
            ).all()

        # Tab 3: International (top 5 most voted globally, last 24 hours)
        # Use a subquery to count votes
        vote_count_subq_intl = (
            db.select(ArticleVote.article_id, func.count(ArticleVote.id).label('vote_count'))
            .group_by(ArticleVote.article_id)
            .subquery()
        )

        international_articles = db.session.scalars(
            db.select(Article)
            .outerjoin(vote_count_subq_intl, Article.id == vote_count_subq_intl.c.article_id)
            .where(Article.is_deleted == False)
            .where(Article.created_at >= twenty_four_hours_ago)
            .order_by(func.coalesce(vote_count_subq_intl.c.vote_count, 0).desc())
            .limit(5)
        ).all()

        # Tab 4: Subscribed newspapers (articles from subscribed newspapers, last 24 hours)
        subscribed_articles = []
        subscriptions = db.session.scalars(
            db.select(NewspaperSubscription)
            .where(NewspaperSubscription.subscriber_id == current_user.id)
        ).all()

        if subscriptions:
            newspaper_ids = [sub.newspaper_id for sub in subscriptions]
            subscribed_articles = db.session.scalars(
                db.select(Article)
                .where(Article.is_deleted == False)
                .where(Article.created_at >= twenty_four_hours_ago)
                .where(Article.newspaper_id.in_(newspaper_ids))
                .order_by(Article.created_at.desc())
                .limit(10)
            ).all()

        # Fetch active laws being voted on in user's country
        country_laws = []
        if current_user.citizenship_id:
            country_laws = db.session.scalars(
                db.select(Law)
                .where(Law.country_id == current_user.citizenship_id)
                .where(Law.status == LawStatus.VOTING)
                .where(Law.voting_end > datetime.utcnow())
                .order_by(Law.voting_end.asc())
                .limit(5)
            ).all()

        # Fetch active battles in user's country (where user can participate)
        country_battles = []
        if current_user.citizenship_id:
            # Get battles where user's country is involved (attacker or defender)
            country_battles = db.session.scalars(
                db.select(Battle)
                .join(Battle.war)
                .where(Battle.status == BattleStatus.ACTIVE)
                .where(Battle.ends_at > datetime.utcnow())
                .where(
                    db.or_(
                        War.attacker_country_id == current_user.citizenship_id,
                        War.defender_country_id == current_user.citizenship_id
                    )
                )
                .order_by(Battle.ends_at.asc())
                .limit(5)
            ).all()

        # Fetch all active wars for international events (excluding user's country wars)
        international_wars = db.session.scalars(
            db.select(War)
            .where(War.status == WarStatus.ACTIVE)
            .order_by(War.started_at.desc())
            .limit(10)
        ).all()

        # Fetch active missions for the dashboard widget
        try:
            # Ensure missions are assigned (daily/weekly/tutorial)
            MissionService.ensure_missions_assigned(current_user)
            db.session.commit()

            missions_data = MissionService.get_active_missions(current_user)
            # Get a summary of missions for the widget (show up to 3 most relevant)
            dashboard_missions = []
            # Priority: unclaimed completed > in-progress daily > in-progress weekly
            unclaimed = MissionService.get_completed_unclaimed(current_user)
            if unclaimed:
                dashboard_missions.extend(unclaimed[:2])

            # Add in-progress missions if space
            remaining_slots = 3 - len(dashboard_missions)
            if remaining_slots > 0:
                for mission in missions_data.get('daily', []):
                    if not mission.is_completed and len(dashboard_missions) < 3:
                        dashboard_missions.append(mission)
            if len(dashboard_missions) < 3:
                for mission in missions_data.get('weekly', []):
                    if not mission.is_completed and len(dashboard_missions) < 3:
                        dashboard_missions.append(mission)
        except Exception as e:
            import logging
            logging.error(f"Error fetching missions for dashboard: {e}")
            db.session.rollback()
            dashboard_missions = []

        return render_template('dashboard.html',
                             title='Dashboard',
                             active_election=current_election,
                             active_government_election=active_government_election,
                             active_government_election_type=active_government_election_type,
                             next_election=next_election,
                             next_election_type=next_election_type,
                             next_election_info=next_election_info,
                             latest_country_articles=latest_country_articles,
                             top_country_articles=top_country_articles,
                             international_articles=international_articles,
                             subscribed_articles=subscribed_articles,
                             country_laws=country_laws,
                             country_battles=country_battles,
                             international_wars=international_wars,
                             dashboard_missions=dashboard_missions)
    else:
        return render_template('index.html', title='Welcome')

@bp.route('/referral')
@login_required
def referral():
    """Show user's referral link and statistics."""
    # Ensure user has a referral code
    if not current_user.referral_code:
        current_user.generate_referral_code()
        db.session.commit()

    # Get referral statistics
    stats = current_user.referral_stats

    # Get all referrals with details
    referrals = db.session.scalars(
        db.select(Referral)
        .where(Referral.referrer_id == current_user.id)
        .order_by(Referral.created_at.desc())
    ).all()

    return render_template('referral.html',
                         title='Referral Program',
                         referral_link=url_for('auth.capture_referral',
                                             referral_code=current_user.referral_code,
                                             _external=True),
                         stats=stats,
                         referrals=referrals)


# --- Game Guide ---

@bp.route('/game-guide')
def game_guide():
    """Display comprehensive game mechanics guide. Accessible without login."""
    return render_template('game_guide.html', title='Game Guide')


# --- Latest Updates ---

@bp.route('/updates')
@login_required
def latest_updates():
    """Display latest game updates and announcements."""
    from app.models import GameUpdate, UpdateCategory

    # Get category filter
    category_filter = request.args.get('category', '')

    # Build query
    query = GameUpdate.query.filter_by(is_published=True, is_deleted=False)

    if category_filter:
        try:
            query = query.filter(GameUpdate.category == UpdateCategory[category_filter.upper()])
        except KeyError:
            pass

    # Order by pinned first, then by published date
    updates = query.order_by(
        GameUpdate.is_pinned.desc(),
        GameUpdate.published_at.desc()
    ).all()

    return render_template('latest_updates.html',
                          title='Latest Updates',
                          updates=updates,
                          categories=UpdateCategory,
                          category_filter=category_filter)


# --- World Map (NASA 3D Globe) ---

@bp.route('/world-map')
@login_required
def world_map():
    """Display the 3D world map with country borders."""
    return render_template('world_map.html', title='World Map')


@bp.route('/api/countries')
@login_required
def get_countries():
    """Get all country border data from GeoJSON file."""
    try:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'app', 'data')
        geojson_path = os.path.join(data_dir, 'countries.geojson')

        with open(geojson_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({"error": "Country data not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/api/country/<country_code>')
@login_required
def get_country(country_code):
    """Get specific country data by ISO code."""
    try:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'app', 'data')
        geojson_path = os.path.join(data_dir, 'countries.geojson')

        with open(geojson_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Find the country with matching ISO code
        for feature in data.get('features', []):
            properties = feature.get('properties', {})
            if (properties.get('ISO_A2') == country_code.upper() or
                properties.get('ISO_A3') == country_code.upper()):
                return jsonify(feature)

        return jsonify({"error": f"Country {country_code} not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/api/country/name/<country_name>')
@login_required
def get_country_by_name(country_name):
    """Get specific country data by name."""
    try:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'app', 'data')
        geojson_path = os.path.join(data_dir, 'countries.geojson')

        with open(geojson_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Find the country with matching name
        for feature in data.get('features', []):
            properties = feature.get('properties', {})
            if properties.get('NAME', '').lower() == country_name.lower():
                return jsonify(feature)

        return jsonify({"error": f"Country {country_name} not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Leaderboards ---
@bp.route('/leaderboards')
@login_required
def leaderboards():
    """Display leaderboards for players, countries, parties, and election history."""
    from app.models import User, Country, PoliticalParty, PartyMembership, GovernmentElection, ElectionCandidate, CountryPresident, CongressMember, ElectionType
    from sqlalchemy import desc, func

    # Get query parameters
    tab = request.args.get('tab', 'players')  # players, countries, parties, elections
    scope = request.args.get('scope', 'country')  # international or country (for players/parties)
    sort_by = request.args.get('sort_by', 'experience')  # various sorting options
    page = request.args.get('page', 1, type=int)
    per_page = 20

    # Get user's country for filtering
    user_country_id = current_user.citizenship_id

    # Initialize variables
    leaderboard_data = []
    user_position = None
    total_count = 0

    # === PLAYERS LEADERBOARD ===
    if tab == 'players':
        query = db.select(User).where(User.is_deleted == False, User.is_banned == False)

        # Apply scope filter
        if scope == 'country' and user_country_id:
            query = query.where(User.citizenship_id == user_country_id)

        # Apply sorting
        if sort_by == 'experience':
            query = query.order_by(desc(User.experience))
        # Military rank
        elif sort_by == 'military_rank':
            query = query.order_by(desc(User.military_rank_id), desc(User.military_rank_xp))
        # Military skills
        elif sort_by == 'skill_infantry':
            query = query.order_by(desc(User.skill_infantry))
        elif sort_by == 'skill_armoured':
            query = query.order_by(desc(User.skill_armoured))
        elif sort_by == 'skill_aviation':
            query = query.order_by(desc(User.skill_aviation))
        # Work skills
        elif sort_by == 'skill_resource_extraction':
            query = query.order_by(desc(User.skill_resource_extraction))
        elif sort_by == 'skill_manufacture':
            query = query.order_by(desc(User.skill_manufacture))
        elif sort_by == 'skill_construction':
            query = query.order_by(desc(User.skill_construction))
        elif sort_by == 'newspaper_subscribers':
            # Count newspaper subscriptions for user's newspaper
            from app.models import Newspaper
            query = query.outerjoin(Newspaper, Newspaper.owner_id == User.id).outerjoin(NewspaperSubscription, NewspaperSubscription.newspaper_id == Newspaper.id).group_by(User.id).order_by(desc(func.count(NewspaperSubscription.id)))

        # Get total count for pagination
        total_count = db.session.scalar(db.select(func.count()).select_from(query.subquery()))

        # Apply pagination
        offset = (page - 1) * per_page
        players = db.session.scalars(query.offset(offset).limit(per_page)).all()

        # If sorting by newspaper subscribers, we need to get actual subscriber counts
        if sort_by == 'newspaper_subscribers':
            from app.models import Newspaper
            player_data = []
            for player in players:
                # Get player's newspaper if they have one
                newspaper = db.session.scalar(
                    db.select(Newspaper).where(Newspaper.owner_id == player.id)
                )

                # Count subscribers to their newspaper
                subscriber_count = 0
                if newspaper:
                    subscriber_count = db.session.scalar(
                        db.select(func.count(NewspaperSubscription.id))
                        .where(NewspaperSubscription.newspaper_id == newspaper.id)
                    ) or 0

                player_data.append({
                    'player': player,
                    'subscriber_count': subscriber_count
                })
            leaderboard_data = player_data
        else:
            leaderboard_data = players

        # Find current user's position
        if sort_by == 'experience':
            position_query = db.select(func.count(User.id)).where(
                User.is_deleted == False,
                User.is_banned == False,
                User.experience > current_user.experience
            )
            if scope == 'country' and user_country_id:
                position_query = position_query.where(User.citizenship_id == user_country_id)
            user_position = db.session.scalar(position_query) + 1

    # === COUNTRIES LEADERBOARD ===
    elif tab == 'countries':
        # Base query
        query = db.select(Country).where(Country.is_deleted == False)

        # Set default sort_by if not specified
        if not sort_by or sort_by not in ['territories', 'population']:
            sort_by = 'population'

        # Apply sorting
        if sort_by == 'territories':
            # Count regions owned by country
            query = query.outerjoin(Region).group_by(Country.id).order_by(desc(func.count(Region.id)))
        elif sort_by == 'population':
            # Count citizens
            query = query.outerjoin(User, User.citizenship_id == Country.id).group_by(Country.id).order_by(desc(func.count(User.id)))

        # Get total count
        total_count = db.session.scalar(db.select(func.count(Country.id)).where(Country.is_deleted == False))

        # Apply pagination
        offset = (page - 1) * per_page
        countries = db.session.scalars(query.offset(offset).limit(per_page)).all()

        # For each country, get actual counts
        country_data = []
        for country in countries:
            # Count citizens
            citizen_count = db.session.scalar(
                db.select(func.count(User.id))
                .where(User.citizenship_id == country.id, User.is_deleted == False, User.is_banned == False)
            ) or 0

            # Count territories (regions)
            territory_count = db.session.scalar(
                db.select(func.count(Region.id))
                .where(Region.original_owner_id == country.id)
            ) or 0

            country_data.append({
                'country': country,
                'citizen_count': citizen_count,
                'territory_count': territory_count
            })

        leaderboard_data = country_data

    # === PARTIES LEADERBOARD ===
    elif tab == 'parties':
        # Build subquery to get member count for each party
        member_count_subquery = (
            db.select(
                PartyMembership.party_id,
                func.count(PartyMembership.user_id).label('member_count')
            )
            .group_by(PartyMembership.party_id)
            .subquery()
        )

        # Build subquery to get average XP for each party
        avg_xp_subquery = (
            db.select(
                PartyMembership.party_id,
                func.avg(User.experience).label('avg_xp')
            )
            .join(User, PartyMembership.user_id == User.id)
            .group_by(PartyMembership.party_id)
            .subquery()
        )

        query = db.select(PoliticalParty).where(PoliticalParty.is_deleted == False)

        # Apply scope filter
        if scope == 'country' and user_country_id:
            query = query.where(PoliticalParty.country_id == user_country_id)

        # Apply sorting
        if sort_by == 'members':
            query = query.outerjoin(member_count_subquery, PoliticalParty.id == member_count_subquery.c.party_id).order_by(desc(member_count_subquery.c.member_count))
        elif sort_by == 'avg_xp':
            query = query.outerjoin(avg_xp_subquery, PoliticalParty.id == avg_xp_subquery.c.party_id).order_by(desc(avg_xp_subquery.c.avg_xp))
        elif sort_by == 'president_wins':
            # Count politics wins (will need to track this)
            query = query.outerjoin(CountryPresident, PoliticalParty.president_id == CountryPresident.user_id).group_by(PoliticalParty.id).order_by(desc(func.count(CountryPresident.id)))
        else:
            # Default to member count
            query = query.outerjoin(member_count_subquery, PoliticalParty.id == member_count_subquery.c.party_id).order_by(desc(member_count_subquery.c.member_count))

        # Get total count
        count_query = db.select(func.count(PoliticalParty.id)).where(PoliticalParty.is_deleted == False)
        if scope == 'country' and user_country_id:
            count_query = count_query.where(PoliticalParty.country_id == user_country_id)
        total_count = db.session.scalar(count_query)

        # Apply pagination
        offset = (page - 1) * per_page
        parties = db.session.scalars(query.offset(offset).limit(per_page)).all()

        # For each party, get the actual member count, avg XP, and politics wins
        party_data = []
        for party in parties:
            member_count = db.session.scalar(
                db.select(func.count(PartyMembership.user_id))
                .where(PartyMembership.party_id == party.id)
            ) or 0

            avg_xp = db.session.scalar(
                db.select(func.avg(User.experience))
                .join(PartyMembership, PartyMembership.user_id == User.id)
                .where(PartyMembership.party_id == party.id)
            ) or 0

            # Count how many times party members won country presidential elections
            president_wins = db.session.scalar(
                db.select(func.count(CountryPresident.id))
                .join(PartyMembership, CountryPresident.user_id == PartyMembership.user_id)
                .where(PartyMembership.party_id == party.id)
            ) or 0

            party_data.append({
                'party': party,
                'member_count': member_count,
                'avg_xp': round(avg_xp, 0) if avg_xp else 0,
                'president_wins': president_wins
            })

        leaderboard_data = party_data

    # === MILITARY UNITS LEADERBOARD ===
    elif tab == 'military_units':
        from app.models.military_unit import MilitaryUnit, BountyContractApplication, BountyContractStatus

        # Set default sort_by if not specified
        if not sort_by or sort_by not in ['damage', 'battles', 'contracts', 'rating']:
            sort_by = 'damage'

        # Build query based on sort type
        if sort_by == 'damage':
            query = db.select(MilitaryUnit).where(
                MilitaryUnit.is_active == True,
                MilitaryUnit.total_damage > 0
            ).order_by(desc(MilitaryUnit.total_damage))
        elif sort_by == 'battles':
            query = db.select(MilitaryUnit).where(
                MilitaryUnit.is_active == True,
                MilitaryUnit.battles_won > 0
            ).order_by(desc(MilitaryUnit.battles_won))
        elif sort_by == 'contracts':
            query = db.select(MilitaryUnit).where(
                MilitaryUnit.is_active == True,
                MilitaryUnit.contracts_completed > 0
            ).order_by(desc(MilitaryUnit.contracts_completed))
        elif sort_by == 'rating':
            # For rating, we need to use a subquery since average_rating is a property
            # Get units that have at least one review
            avg_rating_subquery = (
                db.select(
                    BountyContractApplication.unit_id,
                    func.avg(BountyContractApplication.review_rating).label('avg_rating')
                )
                .where(
                    BountyContractApplication.status == BountyContractStatus.COMPLETED,
                    BountyContractApplication.review_rating.isnot(None)
                )
                .group_by(BountyContractApplication.unit_id)
                .subquery()
            )
            query = (
                db.select(MilitaryUnit)
                .join(avg_rating_subquery, MilitaryUnit.id == avg_rating_subquery.c.unit_id)
                .where(MilitaryUnit.is_active == True)
                .order_by(desc(avg_rating_subquery.c.avg_rating))
            )
        else:
            query = db.select(MilitaryUnit).where(
                MilitaryUnit.is_active == True
            ).order_by(desc(MilitaryUnit.total_damage))

        # Apply scope filter if needed
        if scope == 'country' and user_country_id:
            query = query.where(MilitaryUnit.country_id == user_country_id)

        # Get total count
        if sort_by == 'rating':
            # Count units with ratings
            rated_units_subquery = (
                db.select(BountyContractApplication.unit_id)
                .where(
                    BountyContractApplication.status == BountyContractStatus.COMPLETED,
                    BountyContractApplication.review_rating.isnot(None)
                )
                .distinct()
                .subquery()
            )
            count_query = (
                db.select(func.count(MilitaryUnit.id))
                .where(MilitaryUnit.is_active == True)
                .where(MilitaryUnit.id.in_(db.select(rated_units_subquery.c.unit_id)))
            )
        else:
            count_query = db.select(func.count(MilitaryUnit.id)).where(MilitaryUnit.is_active == True)
            if sort_by == 'damage':
                count_query = count_query.where(MilitaryUnit.total_damage > 0)
            elif sort_by == 'battles':
                count_query = count_query.where(MilitaryUnit.battles_won > 0)
            elif sort_by == 'contracts':
                count_query = count_query.where(MilitaryUnit.contracts_completed > 0)

        if scope == 'country' and user_country_id:
            count_query = count_query.where(MilitaryUnit.country_id == user_country_id)
        total_count = db.session.scalar(count_query)

        # Apply pagination
        offset = (page - 1) * per_page
        units = db.session.scalars(query.offset(offset).limit(per_page)).all()
        leaderboard_data = units

    # === ELECTION HISTORY ===
    elif tab == 'elections':
        election_type = request.args.get('election_type', 'party')  # party, presidential, congressional
        month = request.args.get('month')  # YYYY-MM format

        if election_type == 'party':
            # Party politics elections
            query = db.select(PartyElection).where(PartyElection.status == ElectionStatus.COMPLETED).order_by(desc(PartyElection.end_time))

            if month:
                # Filter by month
                from datetime import datetime
                year, month_num = map(int, month.split('-'))
                start_date = datetime(year, month_num, 1)
                if month_num == 12:
                    end_date = datetime(year + 1, 1, 1)
                else:
                    end_date = datetime(year, month_num + 1, 1)
                query = query.where(PartyElection.end_time >= start_date, PartyElection.end_time < end_date)

            total_count = db.session.scalar(db.select(func.count()).select_from(query.subquery()))
            offset = (page - 1) * per_page
            elections = db.session.scalars(query.offset(offset).limit(per_page)).all()
            leaderboard_data = elections

        else:
            # Government elections (presidential/congressional)
            if election_type == 'presidential':
                query = db.select(GovernmentElection).where(
                    GovernmentElection.election_type == ElectionType.PRESIDENTIAL,
                    GovernmentElection.status == 'COMPLETED'
                ).order_by(desc(GovernmentElection.voting_end))
            else:
                query = db.select(GovernmentElection).where(
                    GovernmentElection.election_type == ElectionType.CONGRESSIONAL,
                    GovernmentElection.status == 'COMPLETED'
                ).order_by(desc(GovernmentElection.voting_end))

            if month:
                from datetime import datetime
                year, month_num = map(int, month.split('-'))
                start_date = datetime(year, month_num, 1)
                if month_num == 12:
                    end_date = datetime(year + 1, 1, 1)
                else:
                    end_date = datetime(year, month_num + 1, 1)
                query = query.where(GovernmentElection.voting_end >= start_date, GovernmentElection.voting_end < end_date)

            total_count = db.session.scalar(db.select(func.count()).select_from(query.subquery()))
            offset = (page - 1) * per_page
            elections = db.session.scalars(query.offset(offset).limit(per_page)).all()
            leaderboard_data = elections

    # Calculate total pages
    import math
    total_pages = math.ceil(total_count / per_page) if total_count > 0 else 1

    return render_template('leaderboards.html',
                          tab=tab,
                          scope=scope,
                          sort_by=sort_by,
                          page=page,
                          total_pages=total_pages,
                          total_count=total_count,
                          leaderboard_data=leaderboard_data,
                          user_position=user_position,
                          per_page=per_page)


# --- Legal Pages ---
@bp.route('/terms')
def terms_of_service():
    """Terms of Service page."""
    return render_template('legal/terms.html', title='Terms of Service')


@bp.route('/privacy')
def privacy_policy():
    """Privacy Policy page."""
    return render_template('legal/privacy.html', title='Privacy Policy')


@bp.route('/about')
def about():
    """About Tactizen page."""
    return render_template('legal/about.html', title='About Tactizen')


@bp.route('/faq')
def faq():
    """Frequently Asked Questions page."""
    return render_template('legal/faq.html', title='FAQ')