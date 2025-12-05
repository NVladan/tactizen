# app/main/location_routes.py
# Routes related to viewing countries and regions

from flask import render_template, redirect, url_for, flash, request, current_app, abort, jsonify
from flask_login import current_user, login_required # Keep login_required if needed for future region actions
from sqlalchemy import func, select, text, or_ # Import text for raw SQL if needed later
from sqlalchemy.orm import aliased # If complex self-joins are needed later
from datetime import datetime, timedelta
from app.main import bp
from app.extensions import db, cache
# Import models needed
from app.models import (
    User, Country, Region, country_regions, Resource, InventoryItem,
    GovernmentElection, ElectionCandidate, CountryPresident, CongressMember,
    GovernmentElectionStatus, CandidateStatus
)
from app.utils import get_level_from_xp # Import utility

# --- Country Page Route ---
@bp.route('/country/<slug>')
def country(slug):
    country = db.session.scalar(db.select(Country).where(Country.slug == slug, Country.is_deleted == False))
    if country is None: abort(404)

    # Use eager loading for regions if performance becomes an issue
    # current_regions = country.current_regions.options(joinedload(...)).order_by(Region.name).all()
    current_regions = country.current_regions.filter_by(is_deleted=False).order_by(Region.name).all()

    # --- Fetch country statistics (expensive queries, cached at route level) ---
    current_app.logger.debug(f"Cache MISS: Fetching country statistics for {slug}")

    # Calculate total population by counting all residents in all regions owned by the country
    region_ids = [region.id for region in current_regions]
    population = 0
    if region_ids:
        population = db.session.scalar(
            select(func.count(User.id)).where(
                User.current_region_id.in_(region_ids),
                User.is_deleted == False
            )
        ) or 0

    # Set the population on the country object for template access
    country.population = population

    # Count active citizens (those with citizenship set to this country)
    active_citizens_count = db.session.scalar(
        select(func.count(User.id)).where(User.citizenship_id == country.id, User.is_deleted == False)
    ) or 0

    # Count total world citizens (can filter by status later if needed)
    world_citizens_count = db.session.scalar(
        select(func.count(User.id)).where(User.is_deleted == False) # Add .where(User.activate == True) if needed
    ) or 0

    # Count new citizens who joined today (registered today with this citizenship)
    from datetime import timedelta
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    new_citizens_today = db.session.scalar(
        select(func.count(User.id)).where(
            User.citizenship_id == country.id,
            User.is_deleted == False,
            User.created_at >= today_start
        )
    ) or 0

    # Calculate average citizen level
    avg_xp_query = db.session.scalar(
        select(func.avg(User.experience)).where(User.citizenship_id == country.id, User.is_deleted == False)
    )
    avg_level = get_level_from_xp(avg_xp_query) if avg_xp_query is not None else 1

    # Count online citizens (active in last 5 minutes)
    five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
    online_now_count = db.session.scalar(
        select(func.count(User.id)).where(
            User.citizenship_id == country.id,
            User.is_deleted == False,
            User.last_seen >= five_minutes_ago
        )
    ) or 0

    # Fetch current and upcoming government elections
    active_elections = db.session.scalars(
        db.select(GovernmentElection)
        .where(GovernmentElection.country_id == country.id)
        .where(GovernmentElection.status != GovernmentElectionStatus.COMPLETED)
        .order_by(GovernmentElection.nominations_start.desc())
    ).all()

    # Get current politics
    current_president = db.session.scalar(
        db.select(CountryPresident)
        .where(CountryPresident.country_id == country.id)
        .where(CountryPresident.is_current == True)
    )

    # Get current congress members (top 10 for display)
    current_congress = db.session.scalars(
        db.select(CongressMember)
        .where(CongressMember.country_id == country.id)
        .where(CongressMember.is_current == True)
        .order_by(CongressMember.final_rank)
        .limit(10)
    ).all()

    # Count total congress members
    total_congress_count = db.session.scalar(
        select(func.count(CongressMember.id))
        .where(CongressMember.country_id == country.id)
        .where(CongressMember.is_current == True)
    ) or 0

    # Get current ministers
    from app.models import Minister, MinistryType
    minister_foreign_affairs = db.session.scalar(
        db.select(Minister)
        .where(Minister.country_id == country.id)
        .where(Minister.ministry_type == MinistryType.FOREIGN_AFFAIRS)
        .where(Minister.is_active == True)
    )
    minister_defence = db.session.scalar(
        db.select(Minister)
        .where(Minister.country_id == country.id)
        .where(Minister.ministry_type == MinistryType.DEFENCE)
        .where(Minister.is_active == True)
    )
    minister_finance = db.session.scalar(
        db.select(Minister)
        .where(Minister.country_id == country.id)
        .where(Minister.ministry_type == MinistryType.FINANCE)
        .where(Minister.is_active == True)
    )

    # Get active wars (where this country is involved)
    from app.models import War, WarStatus
    active_wars = db.session.scalars(
        db.select(War)
        .where(
            or_(
                War.attacker_country_id == country.id,
                War.defender_country_id == country.id
            )
        )
        .where(War.status.in_([WarStatus.ACTIVE, WarStatus.PEACE_PROPOSED]))
        .order_by(War.started_at.desc())
    ).all()

    # Get all countries for the country selector
    all_countries = db.session.scalars(
        db.select(Country).where(Country.is_deleted == False).order_by(Country.name)
    ).all()

    # Check if user can participate in elections (if logged in)
    user_candidacies = {}
    can_nominate_president = False
    can_apply_congress = False

    if current_user.is_authenticated and current_user.citizenship_id == country.id:
        # Check user's candidacies
        for election in active_elections:
            candidacy = db.session.scalar(
                db.select(ElectionCandidate)
                .where(ElectionCandidate.election_id == election.id)
                .where(ElectionCandidate.user_id == current_user.id)
            )
            if candidacy:
                user_candidacies[election.id] = candidacy

        # Check if user can nominate (party politics for presidential elections)
        if current_user.party and current_user.party.president_id == current_user.id:
            can_nominate_president = True

        # Check if user can apply for congress (party member)
        if current_user.party and current_user.party.country_id == country.id:
            can_apply_congress = True

    return render_template('country.html',
                           title=country.name,
                           country=country,
                           current_regions=current_regions,
                           active_citizens_count=active_citizens_count,
                           world_citizens_count=world_citizens_count,
                           new_citizens_today=new_citizens_today,
                           avg_level=avg_level,
                           online_now_count=online_now_count,
                           active_elections=active_elections,
                           current_president=current_president,
                           current_congress=current_congress,
                           total_congress_count=total_congress_count,
                           minister_foreign_affairs=minister_foreign_affairs,
                           minister_defence=minister_defence,
                           minister_finance=minister_finance,
                           active_wars=active_wars,
                           user_candidacies=user_candidacies,
                           can_nominate_president=can_nominate_president,
                           can_apply_congress=can_apply_congress,
                           all_countries=all_countries)


# --- Region Page Route ---
@bp.route('/region/<slug>')
def region(slug):
    region = db.session.scalar(db.select(Region).where(Region.slug == slug, Region.is_deleted == False))
    if region is None: abort(404)

    # Access the single current owner directly (uselist=False)
    owner_country = region.current_owner

    # Count residents currently located in this region
    resident_count = db.session.scalar(
        select(func.count(User.id)).where(User.current_region_id == region.id, User.is_deleted == False)
    ) or 0

    # Get neighboring regions (both directions of the relationship)
    neighbors_list = region.neighbors.filter_by(is_deleted=False).all()
    neighbor_of_list = region.neighbor_of.filter_by(is_deleted=False).all()
    # Combine and deduplicate, then sort by name
    all_neighbors = {r.id: r for r in neighbors_list + neighbor_of_list}
    neighbors = sorted(all_neighbors.values(), key=lambda r: r.name)

    # Count visitors (users in region who are NOT citizens of the owning country)
    if owner_country:
        visitor_count = db.session.scalar(
            select(func.count(User.id)).where(
                User.current_region_id == region.id,
                User.is_deleted == False,
                User.citizenship_id != owner_country.id
            )
        ) or 0
    else:
        # If no owner, all residents are technically visitors
        visitor_count = resident_count

    # Get regional constructions (hospitals and fortresses)
    from app.models import RegionalConstruction, RegionalResource
    constructions = db.session.scalars(
        db.select(RegionalConstruction)
        .where(RegionalConstruction.region_id == region.id)
        .order_by(RegionalConstruction.construction_type)
    ).all()

    # Get regional resources (natural deposits)
    regional_resources = db.session.scalars(
        db.select(RegionalResource)
        .where(RegionalResource.region_id == region.id, RegionalResource.amount > 0)
        .order_by(RegionalResource.resource_id)
    ).all()

    # --- Resistance War Data ---
    from app.models import War, Battle, WarStatus
    from app.models.battle import BattleStatus

    is_conquered = owner_country and owner_country.id != region.original_owner_id
    active_resistance_war = None
    active_resistance_battle = None
    can_start_resistance = False
    resistance_start_error = None

    if is_conquered:
        # Check for active resistance war for the original country
        active_resistance_war = db.session.scalar(
            db.select(War)
            .where(War.is_resistance_war == True)
            .where(War.resistance_country_id == region.original_owner_id)
            .where(War.status == WarStatus.ACTIVE)
        )

        if active_resistance_war:
            # Get active battle if any
            active_resistance_battle = db.session.scalar(
                db.select(Battle)
                .where(Battle.war_id == active_resistance_war.id)
                .where(Battle.status == BattleStatus.ACTIVE)
            )

        # Check if there's any active battle on this region (blocks new wars)
        active_battle_on_region = db.session.scalar(
            db.select(Battle)
            .where(Battle.region_id == region.id)
            .where(Battle.status == BattleStatus.ACTIVE)
        )

        # Check if current user can start resistance war
        if current_user.is_authenticated:
            user_location = current_user.current_region
            if user_location:
                user_location_owner = user_location.current_owner
                if user_location_owner and user_location_owner.id == owner_country.id:
                    # User is in the conquering country
                    if active_battle_on_region:
                        resistance_start_error = f'Battle in progress for {region.name}'
                    elif active_resistance_war:
                        resistance_start_error = f'Resistance war already active for {region.original_owner.name}'
                    elif current_user.gold < 30:
                        resistance_start_error = 'Need 30 Gold to start'
                    else:
                        can_start_resistance = True
                else:
                    resistance_start_error = f'Must be in {owner_country.name}'
            else:
                resistance_start_error = 'No location set'

    return render_template('region.html',
                           title=region.name,
                           region=region,
                           owner_country=owner_country,
                           resident_count=resident_count,
                           visitor_count=visitor_count,
                           constructions=constructions,
                           regional_resources=regional_resources,
                           neighbors=neighbors,
                           is_conquered=is_conquered,
                           active_resistance_war=active_resistance_war,
                           active_resistance_battle=active_resistance_battle,
                           can_start_resistance=can_start_resistance,
                           resistance_start_error=resistance_start_error)


# --- API Route for Regions (Used by forms) ---
@bp.route('/api/regions/<int:country_id>')
def api_regions(country_id):
    # Use get_or_404 for simpler handling of non-existent countries
    country = db.get_or_404(Country, country_id)
    if country.is_deleted:
        return jsonify({'error': 'Country not found'}), 404
    try:
        # Select regions currently owned by the country
        # The relationship `country.current_regions` handles the join via `country_regions` table
        regions = country.current_regions.filter_by(is_deleted=False).order_by(Region.name).all()
        region_list = [{'id': region.id, 'name': region.name} for region in regions]
        return jsonify({'regions': region_list})
    except Exception as e:
        # Log the error for debugging
        current_app.logger.error(f"Error fetching regions for country {country_id}: {e}", exc_info=True)
        # Return a generic error response
        return jsonify({'error': 'Could not retrieve regions'}), 500