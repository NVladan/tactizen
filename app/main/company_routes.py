# app/main/company_routes.py

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import select, func, or_, and_
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN, ROUND_UP

from app import db
from app.extensions import limiter
from app.models import (
    Company, CompanyType, JobOffer, Employment, CompanyInventory,
    CompanyTransaction, CompanyTransactionType, ExportLicense,
    Resource, Country, User, UserCurrency, GoldMarket, CountryMarketItem,
    CompanyProductionProgress, Alert, AlertType, AlertPriority, WorkSession
)
from app.constants import GameConstants
from app.security import InputSanitizer

company_bp = Blueprint('company', __name__, url_prefix='/company')


# ==================== Helper Functions ====================

def log_company_transaction(company, transaction_type, amount_gold=Decimal('0'),
                           amount_currency=Decimal('0'), description=None, related_user=None):
    """Helper to log company transactions."""
    transaction = CompanyTransaction(
        company_id=company.id,
        transaction_type=transaction_type,
        amount_gold=amount_gold,
        amount_currency=amount_currency,
        description=description,
        related_user_id=related_user.id if related_user else None,
        balance_gold_after=company.gold_balance,
        balance_currency_after=company.currency_balance
    )
    db.session.add(transaction)
    return transaction


def get_skill_for_company_type(user, company_type):
    """Returns the relevant skill level for a company type."""
    # Resource extraction companies
    if company_type in [CompanyType.MINING, CompanyType.RESOURCE_EXTRACTION, CompanyType.FARMING]:
        return user.skill_resource_extraction
    # Manufacturing companies (weapons, consumer goods, semi-products)
    elif company_type in [CompanyType.RIFLE_MANUFACTURING, CompanyType.TANK_MANUFACTURING,
                         CompanyType.HELICOPTER_MANUFACTURING, CompanyType.BREAD_MANUFACTURING,
                         CompanyType.BEER_MANUFACTURING, CompanyType.WINE_MANUFACTURING,
                         CompanyType.SEMI_PRODUCT]:
        return user.skill_manufacture
    # Construction companies
    elif company_type == CompanyType.CONSTRUCTION:
        return user.skill_construction
    return 0


def get_skill_name_for_company_type(company_type):
    """Returns the skill name for a company type."""
    # Resource extraction companies
    if company_type in [CompanyType.MINING, CompanyType.RESOURCE_EXTRACTION, CompanyType.FARMING]:
        return "Resource Extraction"
    # Manufacturing companies (weapons, consumer goods, semi-products)
    elif company_type in [CompanyType.RIFLE_MANUFACTURING, CompanyType.TANK_MANUFACTURING,
                         CompanyType.HELICOPTER_MANUFACTURING, CompanyType.BREAD_MANUFACTURING,
                         CompanyType.BEER_MANUFACTURING, CompanyType.WINE_MANUFACTURING,
                         CompanyType.SEMI_PRODUCT]:
        return "Manufacture"
    # Construction companies
    elif company_type == CompanyType.CONSTRUCTION:
        return "Construction"
    return "Unknown"


def get_production_resources_for_company_type(company_type):
    """Returns list of resources a company type can produce."""
    production_map = {
        # Resource extraction
        CompanyType.MINING: ['Coal', 'Iron ore', 'Stone'],
        CompanyType.RESOURCE_EXTRACTION: ['Clay', 'Oil', 'Sand'],
        CompanyType.FARMING: ['Wheat', 'Grape'],
        # Weapon manufacturing (split - each produces only one product)
        CompanyType.RIFLE_MANUFACTURING: ['Rifle'],
        CompanyType.TANK_MANUFACTURING: ['Tank'],
        CompanyType.HELICOPTER_MANUFACTURING: ['Helicopter'],
        # Consumer goods (split - each produces only one product)
        CompanyType.BREAD_MANUFACTURING: ['Bread'],
        CompanyType.BEER_MANUFACTURING: ['Beer'],
        CompanyType.WINE_MANUFACTURING: ['Wine'],
        # Semi-products
        CompanyType.SEMI_PRODUCT: ['Steel', 'Iron Bar', 'Bricks', 'Concrete', 'Electricity'],
        # Construction
        CompanyType.CONSTRUCTION: ['House', 'Fort', 'Hospital'],
    }
    return production_map.get(company_type, [])


def calculate_purchase_breakdown(market_item, quantity):
    """Calculate the cost breakdown when purchasing across multiple price levels.
    Note: initial_price in market_item is already quality-adjusted per quality level.

    Returns a dict with:
    - breakdown: list of (qty, price) tuples for each price level
    - total_cost: total cost across all levels
    - final_price_level: what the price level will be after purchase
    - final_progress: what the progress will be after purchase
    """
    from decimal import Decimal

    volume_per_level = int(market_item.volume_per_level)
    current_progress = int(market_item.progress_within_level)
    current_price_level = int(market_item.price_level)

    # Get base pricing info (already quality-adjusted for this market item's quality level)
    initial_price = float(market_item.initial_price)
    price_adjustment = float(market_item.price_adjustment_per_level)

    breakdown = []
    remaining_qty = quantity
    temp_progress = current_progress
    temp_price_level = current_price_level
    total_cost = Decimal('0')

    while remaining_qty > 0:
        # Calculate current buy price at this level (base price + level adjustment + 10% spread)
        base_price_at_level = initial_price + (temp_price_level * price_adjustment)
        buy_price_at_level = Decimal(str(base_price_at_level * 1.1))  # 10% spread for buying

        # How many units can we buy at current price before level increases?
        available_at_current_price = volume_per_level - temp_progress

        # Buy either all remaining or up to the limit
        qty_at_this_price = min(remaining_qty, available_at_current_price)

        # Add to breakdown
        breakdown.append((qty_at_this_price, float(buy_price_at_level)))
        cost_at_this_price = buy_price_at_level * Decimal(str(qty_at_this_price))
        total_cost += cost_at_this_price

        # Update progress
        temp_progress += qty_at_this_price
        remaining_qty -= qty_at_this_price

        # If we filled this level, move to next
        if temp_progress >= volume_per_level:
            temp_price_level += 1
            temp_progress = 0

    return {
        'breakdown': breakdown,
        'total_cost': float(total_cost),
        'final_price_level': temp_price_level,
        'final_progress': temp_progress
    }


def calculate_sell_breakdown(market_item, quantity):
    """Calculate the proceeds breakdown when selling across multiple price levels.
    Note: initial_price in market_item is already quality-adjusted per quality level.

    Returns a dict with:
    - breakdown: list of (qty, price) tuples for each price level
    - total_proceeds: total proceeds across all levels
    - final_price_level: what the price level will be after selling
    - final_progress: what the progress will be after selling
    """
    from decimal import Decimal

    volume_per_level = int(market_item.volume_per_level)
    current_progress = int(market_item.progress_within_level)
    current_price_level = int(market_item.price_level)

    # Get base pricing info (already quality-adjusted for this market item's quality level)
    initial_price = float(market_item.initial_price)
    price_adjustment = float(market_item.price_adjustment_per_level)

    breakdown = []
    remaining_qty = quantity
    temp_progress = current_progress
    temp_price_level = current_price_level
    total_proceeds = Decimal('0')

    while remaining_qty > 0:
        # Calculate current sell price at this level (base price + level adjustment - 10% spread)
        base_price_at_level = initial_price + (temp_price_level * price_adjustment)
        sell_price_at_level = Decimal(str(base_price_at_level * 0.9))  # 10% spread for selling

        # How many units can we sell at current price before level decreases?
        available_at_current_price = temp_progress + 1  # Can sell progress + 1 to go down a level

        # Sell either all remaining or up to the limit
        qty_at_this_price = min(remaining_qty, available_at_current_price)

        # Add to breakdown
        breakdown.append((qty_at_this_price, float(sell_price_at_level)))
        proceeds_at_this_price = sell_price_at_level * Decimal(str(qty_at_this_price))
        total_proceeds += proceeds_at_this_price

        # Update progress
        temp_progress -= qty_at_this_price
        remaining_qty -= qty_at_this_price

        # If progress went negative, move to previous level
        if temp_progress < 0:
            temp_price_level -= 1
            temp_progress = volume_per_level + temp_progress  # temp_progress is negative

    return {
        'breakdown': breakdown,
        'total_proceeds': float(total_proceeds),
        'final_price_level': temp_price_level,
        'final_progress': temp_progress
    }


def get_allowed_purchasable_resources(company_type):
    """Returns list of resource names a company type is allowed to purchase from market.

    All companies can purchase Electricity for production boost.
    Manufacturing and construction companies can also purchase raw materials they need.
    Each company type can only buy what it needs for its specific production.
    """
    # All companies can buy Electricity for the +30% production boost
    base_allowed = ['Electricity']

    # Resource extraction companies can only buy Electricity
    if company_type in [CompanyType.MINING, CompanyType.RESOURCE_EXTRACTION, CompanyType.FARMING]:
        return base_allowed

    # Manufacturing and construction companies can purchase their specific required inputs
    additional_allowed = {
        # Weapon manufacturing (split) - each only needs its specific inputs
        CompanyType.RIFLE_MANUFACTURING: ['Iron Bar', 'Coal'],  # Rifle needs Iron Bar + Coal
        CompanyType.TANK_MANUFACTURING: ['Steel', 'Oil'],  # Tank needs Steel + Oil
        CompanyType.HELICOPTER_MANUFACTURING: ['Steel', 'Oil'],  # Helicopter needs Steel + Oil
        # Consumer goods (split) - each only needs its specific inputs
        CompanyType.BREAD_MANUFACTURING: ['Wheat'],  # Bread needs Wheat
        CompanyType.BEER_MANUFACTURING: ['Wheat'],  # Beer needs Wheat
        CompanyType.WINE_MANUFACTURING: ['Grape'],  # Wine needs Grape
        # Semi-products - needs various raw materials
        CompanyType.SEMI_PRODUCT: ['Iron ore', 'Coal', 'Clay', 'Stone', 'Sand', 'Oil'],
        # Construction - needs semi-finished products
        CompanyType.CONSTRUCTION: ['Bricks', 'Concrete'],
    }

    return base_allowed + additional_allowed.get(company_type, [])


def get_input_requirements(resource_name, quality_level):
    """Returns dict of input resources needed to produce one unit."""
    # Manufacturing requirements (inputs needed per output)
    weapon_requirements = {
        'Rifle': {'Iron Bar': 5, 'Coal': 5},
        'Tank': {'Steel': 5, 'Oil': 5},
        'Helicopter': {'Steel': 5, 'Oil': 5},
    }

    consumer_requirements = {
        'Bread': {'Wheat': 5},
        'Beer': {'Wheat': 5},
        'Wine': {'Grape': 5},
    }

    semi_product_requirements = {
        'Steel': {'Iron ore': 5, 'Coal': 5},
        'Iron Bar': {'Iron ore': 5, 'Coal': 5},
        'Bricks': {'Clay': 5, 'Coal': 5},
        'Concrete': {'Stone': 5, 'Sand': 5},
        'Electricity': {'Oil': 5},  # No quality scaling for Electricity
    }

    construction_requirements = {
        # House: 10x base materials (100 Bricks + 100 Concrete per quality)
        'House': {'Bricks': 100, 'Concrete': 100},
        # Fort/Hospital: 20x base materials (200 Bricks + 200 Concrete per quality)
        'Fort': {'Bricks': 200, 'Concrete': 200},
        'Hospital': {'Bricks': 200, 'Concrete': 200},
    }

    # Get base requirements
    base_reqs = {}
    if resource_name in weapon_requirements:
        base_reqs = weapon_requirements[resource_name]
    elif resource_name in consumer_requirements:
        base_reqs = consumer_requirements[resource_name]
    elif resource_name in semi_product_requirements:
        base_reqs = semi_product_requirements[resource_name]
    elif resource_name in construction_requirements:
        base_reqs = construction_requirements[resource_name]

    # Scale by quality level (LINEAR: Q1=1x, Q2=2x, Q3=3x, Q4=4x, Q5=5x)
    # EXCEPT for Electricity which has no quality levels
    if resource_name == 'Electricity':
        return base_reqs  # No quality scaling

    multiplier = quality_level
    return {k: v * multiplier for k, v in base_reqs.items()}


# ==================== Company List & Creation ====================

@company_bp.route('/my-companies')
@login_required
def my_companies():
    """List all companies owned by current user."""
    from app.time_helpers import get_time_until_reset, format_time_remaining

    companies = current_user.companies.filter_by(is_deleted=False).all()

    # Also get employment info
    employments = current_user.employments.join(Company).filter(
        Company.is_deleted == False
    ).all()

    # Get time allocation data
    allocation = current_user.get_today_allocation()
    remaining_hours = allocation.remaining_hours
    time_until_reset = get_time_until_reset()
    time_remaining_formatted = format_time_remaining(time_until_reset)

    return render_template('company/my_companies.html',
                         companies=companies,
                         employments=employments,
                         allocation=allocation,
                         remaining_hours=remaining_hours,
                         time_remaining=time_remaining_formatted)


@company_bp.route('/create', methods=['GET', 'POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_COMPANY_CREATE", "10 per hour"))
def create_company():
    """Create a new company."""
    if request.method == 'POST':
        company_name = request.form.get('name', '').strip()
        company_type_str = request.form.get('company_type')
        description = request.form.get('description', '').strip()

        # Validation
        if not company_name or len(company_name) < 3:
            flash('Company name must be at least 3 characters long.', 'error')
            return redirect(url_for('company.create_company'))

        if not company_type_str:
            flash('Please select a company type.', 'error')
            return redirect(url_for('company.create_company'))

        try:
            company_type = CompanyType[company_type_str]
        except KeyError:
            flash('Invalid company type.', 'error')
            return redirect(url_for('company.create_company'))

        # Validate description length
        if description and len(description) > 500:
            flash('Company description must be 500 characters or less.', 'error')
            return redirect(url_for('company.create_company'))

        # Check if user has citizenship
        if not current_user.citizenship_id:
            flash('You must have citizenship to create a company.', 'error')
            return redirect(url_for('company.create_company'))

        # Get the country where the player is currently located
        if current_user.current_region_id:
            current_country_id = current_user.current_region.original_owner_id
        else:
            # Fallback to citizenship if no current region set
            current_country_id = current_user.citizenship_id

        # Check payment and deduct with row-level locking
        creation_cost = Decimal('20.0')
        from app.services.currency_service import CurrencyService
        success, message, _ = CurrencyService.deduct_gold(
            current_user.id, creation_cost, 'Company creation'
        )
        if not success:
            flash(f'Could not deduct gold: {message}', 'error')
            return redirect(url_for('company.create_company'))

        # Create company in the country where player is currently located
        company = Company(
            name=company_name,
            company_type=company_type,
            quality_level=1,
            owner_id=current_user.id,
            country_id=current_country_id,
            gold_balance=Decimal('0'),
            currency_balance=Decimal('0'),
            production_progress=0,
            description=description if description else None
        )
        db.session.add(company)
        db.session.flush()  # Get company ID

        # Create export license for home country (included in creation cost)
        home_license = ExportLicense(
            company_id=company.id,
            country_id=current_user.citizenship_id
        )
        db.session.add(home_license)

        db.session.commit()

        # Check entrepreneur achievements
        from app.services.achievement_service import AchievementService
        try:
            AchievementService.check_entrepreneur(current_user)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Error checking entrepreneur achievement: {e}")

        flash(f'Company "{company_name}" created successfully!', 'success')
        return redirect(url_for('company.view_company', company_id=company.id))

    # GET request - show creation form
    company_types = [
        {'value': ct.name, 'label': ct.value,
         'resources': ', '.join(get_production_resources_for_company_type(ct))}
        for ct in CompanyType
    ]

    return render_template('company/create_company.html',
                         company_types=company_types,
                         creation_cost=20)


# ==================== Company Management ====================

@company_bp.route('/<int:company_id>/edit-profile', methods=['GET', 'POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_PROFILE_UPDATE", "10 per hour"))
def edit_company_profile(company_id):
    """Edit company name and description."""
    company = db.session.get(Company, company_id)
    if not company or company.is_deleted:
        flash('Company not found.', 'error')
        return redirect(url_for('company.my_companies'))

    # Only owner can edit
    if company.owner_id != current_user.id:
        flash('You do not have permission to edit this company.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    if request.method == 'POST':
        company_name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()

        # Validation
        if not company_name or len(company_name) < 3:
            flash('Company name must be at least 3 characters long.', 'error')
            return redirect(url_for('company.edit_company_profile', company_id=company_id))

        if description and len(description) > 500:
            flash('Company description must be 500 characters or less.', 'error')
            return redirect(url_for('company.edit_company_profile', company_id=company_id))

        # Update company details
        company.name = company_name
        company.description = InputSanitizer.sanitize_description(description) if description else None

        try:
            db.session.commit()
            flash('Company profile updated successfully!', 'success')
            return redirect(url_for('company.view_company', company_id=company_id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating company profile: {e}", exc_info=True)
            flash('An error occurred while updating company profile.', 'error')
            return redirect(url_for('company.edit_company_profile', company_id=company_id))

    # GET request - show edit form
    return render_template('company/edit_profile.html', company=company)


@company_bp.route('/<int:company_id>')
@login_required
def view_company(company_id):
    """View company overview."""
    company = db.session.get(Company, company_id)
    if not company or company.is_deleted:
        flash('Company not found.', 'error')
        return redirect(url_for('company.my_companies'))

    # Check if user is owner or employee
    is_owner = company.owner_id == current_user.id
    employment = None
    if not is_owner:
        employment = db.session.scalar(
            select(Employment).filter_by(company_id=company_id, user_id=current_user.id)
        )
        if not employment:
            flash('You do not have access to this company.', 'error')
            return redirect(url_for('company.my_companies'))

    # Get company data
    employees = company.employees.join(User).all()
    inventory_items = company.inventory.join(Resource).all()
    active_job_offers = company.job_offers.filter_by(is_active=True).all()

    # Get production resource if set
    current_production = None
    if company.current_production_resource_id:
        current_production = db.session.get(Resource, company.current_production_resource_id)

    # Get available production resources
    available_resources = []
    resource_names = get_production_resources_for_company_type(company.company_type)
    for name in resource_names:
        resource = db.session.scalar(select(Resource).filter_by(name=name))
        if resource:
            available_resources.append(resource)

    # Get gold market for currency exchange rates
    gold_market = GoldMarket.query.filter_by(country_id=company.country_id).first()

    # Get all market items for this country (for inventory buy/sell)
    market_items = db.session.scalars(
        select(CountryMarketItem).filter_by(country_id=company.country_id).join(Resource)
    ).all()

    # Create a dict of (resource_id, quality) -> market_item for easy lookup
    # Normalize quality: 0 in market = None in inventory for raw materials
    market_items_dict = {}
    for item in market_items:
        quality_key = None if item.quality == 0 else item.quality
        market_items_dict[(item.resource_id, quality_key)] = item

    # Get all resources for buying
    all_resources = db.session.scalars(
        select(Resource).filter_by(is_deleted=False).order_by(Resource.name)
    ).all()

    # Get allowed purchasable resources for this company type
    allowed_purchasable_resource_names = get_allowed_purchasable_resources(company.company_type)

    # Get time allocation data (for workers to see remaining hours)
    allocation = current_user.get_today_allocation()

    # Get Android Worker NFT data for owner
    android_skill = 0
    android_can_work = False
    from app.time_helpers import get_allocation_date
    today = get_allocation_date()
    if is_owner:
        from app.services.bonus_calculator import BonusCalculator
        android_skill = BonusCalculator.get_android_worker_skill(company.id)
        if android_skill > 0:
            android_can_work = not (company.android_last_worked and company.android_last_worked >= today)

    # Get today's work sessions for all employees (for stats display)
    today_work_sessions = db.session.scalars(
        select(WorkSession).filter(
            WorkSession.company_id == company.id,
            WorkSession.work_date == today
        )
    ).all()

    # Create a dict of user_id -> work session data for template
    employee_today_stats = {}
    for session in today_work_sessions:
        employee_today_stats[session.user_id] = {
            'hours_worked': session.hours_worked,
            'production_points': session.production_points,
            'total_payment': float(session.total_payment),
            'worked': True
        }

    return render_template('company/view_company.html',
                         company=company,
                         is_owner=is_owner,
                         employment=employment,
                         employees=employees,
                         inventory_items=inventory_items,
                         active_job_offers=active_job_offers,
                         current_production=current_production,
                         available_resources=available_resources,
                         gold_market=gold_market,
                         market_items_dict=market_items_dict,
                         all_resources=all_resources,
                         allowed_purchasable_resource_names=allowed_purchasable_resource_names,
                         allocation=allocation,
                         android_skill=android_skill,
                         android_can_work=android_can_work,
                         employee_today_stats=employee_today_stats)


@company_bp.route('/<int:company_id>/production', methods=['POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_COMPANY_ACTION", "50 per hour"))
def set_production(company_id):
    """Set what the company is currently producing."""
    company = db.session.get(Company, company_id)
    if not company or company.is_deleted or company.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    resource_id = request.form.get('resource_id', type=int)
    if not resource_id:
        return jsonify({'error': 'Resource ID required'}), 400

    # Verify resource is valid for this company type
    resource = db.session.get(Resource, resource_id)
    if not resource:
        return jsonify({'error': 'Resource not found'}), 404

    available_names = get_production_resources_for_company_type(company.company_type)
    if resource.name not in available_names:
        return jsonify({'error': 'Invalid resource for this company type'}), 400

    # Save current progress before switching
    if company.current_production_resource_id:
        # Get or create progress tracker for current resource
        current_progress_tracker = db.session.scalar(
            select(CompanyProductionProgress).where(
                CompanyProductionProgress.company_id == company.id,
                CompanyProductionProgress.resource_id == company.current_production_resource_id
            )
        )

        if current_progress_tracker:
            current_progress_tracker.progress = company.production_progress
            current_progress_tracker.updated_at = datetime.utcnow()
        else:
            # Create new progress tracker
            current_progress_tracker = CompanyProductionProgress(
                company_id=company.id,
                resource_id=company.current_production_resource_id,
                progress=company.production_progress
            )
            db.session.add(current_progress_tracker)

    # Load progress for the new resource
    new_progress_tracker = db.session.scalar(
        select(CompanyProductionProgress).where(
            CompanyProductionProgress.company_id == company.id,
            CompanyProductionProgress.resource_id == resource_id
        )
    )

    # Set new production resource and restore its progress
    company.current_production_resource_id = resource_id
    company.production_progress = new_progress_tracker.progress if new_progress_tracker else 0

    db.session.commit()

    flash(f'Now producing: {resource.name}', 'success')
    return redirect(url_for('company.view_company', company_id=company_id))


@company_bp.route('/<int:company_id>/toggle-electricity', methods=['POST'])
@login_required
def toggle_electricity(company_id):
    """Toggle electricity usage for production boost."""
    company = db.session.get(Company, company_id)
    if not company or company.is_deleted:
        flash('Company not found.', 'error')
        return redirect(url_for('company.my_companies'))

    # Check ownership
    if company.owner_id != current_user.id:
        flash('You do not own this company.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Toggle electricity usage
    company.use_electricity = not company.use_electricity
    db.session.commit()

    status = "enabled" if company.use_electricity else "disabled"
    flash(f'Electricity boost {status} for production.', 'success')
    return redirect(url_for('company.view_company', company_id=company_id))


# ==================== Company Work (for employees) ====================

@company_bp.route('/<int:company_id>/work', methods=['POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_WORK", "100 per hour"))
def work(company_id):
    """Employee works at the company with hour allocation."""
    # Get employment
    employment = db.session.scalar(
        select(Employment).filter_by(company_id=company_id, user_id=current_user.id)
    )

    if not employment:
        flash('You are not employed at this company.', 'error')
        return redirect(url_for('company.my_companies'))

    # Get hours from form
    try:
        hours = int(request.form.get('hours', 0))
    except ValueError:
        flash('Invalid hours value', 'error')
        return redirect(url_for('company.my_companies'))

    if hours < 1 or hours > 12:
        flash('Hours must be between 1 and 12', 'error')
        return redirect(url_for('company.my_companies'))

    # Use the new work allocation system
    success, message, production_points, payment, energy_cost, wellness_cost = current_user.allocate_work_hours(employment.id, hours)

    if success:
        try:
            db.session.commit()
            flash(message, 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred while processing work: {str(e)}', 'error')
    else:
        flash(message, 'error')

    return redirect(url_for('company.my_companies'))


# ==================== Job Market ====================

@company_bp.route('/job-market')
@login_required
def job_market():
    """Browse all available job offers."""
    # Get player's current country from their region
    player_country_id = None
    player_country = None
    if current_user.current_region:
        player_country_id = current_user.current_region.original_owner_id
        player_country = db.session.get(Country, player_country_id)

    # If player has no region set, they can't see any jobs
    if not player_country_id or not player_country:
        flash('You must be located in a region to view job offers.', 'warning')
        # Default to citizenship country for navigation links
        default_country = current_user.citizenship if current_user.citizenship else None
        return render_template('company/job_market.html',
                             job_offers=[],
                             user_employments=set(),
                             company_types=CompanyType,
                             countries=[],
                             country=default_country)

    # Get filters
    company_type_filter = request.args.get('company_type')
    min_wage = request.args.get('min_wage', type=float)
    max_skill = request.args.get('max_skill', type=int)
    quality_filter = request.args.get('quality', type=int)
    country_id = request.args.get('country_id', type=int)

    # Base query - MUST filter by player's current country
    query = select(JobOffer).join(Company).filter(
        JobOffer.is_active == True,
        Company.is_deleted == False,
        Company.is_frozen == False,  # Exclude frozen companies (conquered countries)
        Company.country_id == player_country_id  # Only show jobs from player's current country
    )

    # Apply filters
    if company_type_filter:
        # Map grouped categories to specific company types
        type_groups = {
            'resource_extraction': [CompanyType.MINING, CompanyType.FARMING, CompanyType.RESOURCE_EXTRACTION],
            'manufacture': [
                CompanyType.RIFLE_MANUFACTURING, CompanyType.TANK_MANUFACTURING, CompanyType.HELICOPTER_MANUFACTURING,
                CompanyType.BREAD_MANUFACTURING, CompanyType.BEER_MANUFACTURING, CompanyType.WINE_MANUFACTURING,
                CompanyType.SEMI_PRODUCT
            ],
            'construction': [CompanyType.CONSTRUCTION]
        }

        if company_type_filter in type_groups:
            query = query.filter(Company.company_type.in_(type_groups[company_type_filter]))

    if min_wage:
        query = query.filter(JobOffer.daily_wage_currency >= Decimal(str(min_wage)))

    if max_skill is not None:
        query = query.filter(JobOffer.minimum_skill_level <= max_skill)

    if quality_filter:
        query = query.filter(Company.quality_level == quality_filter)

    # Country filter is now ignored since we only show jobs from player's country

    job_offers = db.session.scalars(query).all()

    # Get current user's employments
    user_employments = set(e.company_id for e in current_user.employments.all())

    # Get countries for filter
    countries = db.session.scalars(select(Country).order_by(Country.name)).all()

    return render_template('company/job_market.html',
                         job_offers=job_offers,
                         user_employments=user_employments,
                         company_types=CompanyType,
                         countries=countries,
                         country=player_country)


@company_bp.route('/<int:company_id>/post-job', methods=['POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_COMPANY_ACTION", "50 per hour"))
def post_job(company_id):
    """Post a job offer."""
    company = db.session.get(Company, company_id)
    if not company or company.is_deleted or company.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    # Check if company has available positions
    if company.available_positions <= 0:
        flash('No available positions. Upgrade company or fire employees.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Check if there's already an active job offer
    existing_active_offer = company.job_offers.filter_by(is_active=True).first()
    if existing_active_offer:
        flash('You already have an active job offer. Cancel the existing offer before posting a new one.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    wage_per_pp = request.form.get('wage', type=float)
    min_skill = request.form.get('min_skill', type=float, default=0.0)
    positions = request.form.get('positions', type=int, default=1)

    if not wage_per_pp or wage_per_pp <= 0:
        flash('Invalid wage amount.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    if not positions or positions <= 0:
        flash('Invalid number of positions.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    if positions > company.available_positions:
        flash(f'Cannot post more positions than available ({company.available_positions}).', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Create job offer
    job_offer = JobOffer(
        company_id=company.id,
        wage_per_pp=Decimal(str(wage_per_pp)),
        minimum_skill_level=min_skill,
        positions=positions,
        is_active=True
    )
    db.session.add(job_offer)
    db.session.commit()

    flash(f'Job offer posted! {positions} position(s) at {wage_per_pp} {company.country.currency_code}/PP, Min Skill: {min_skill}', 'success')
    return redirect(url_for('company.view_company', company_id=company_id))


@company_bp.route('/<int:company_id>/job-offer/<int:offer_id>/cancel', methods=['POST'])
@login_required
def cancel_job_offer(company_id, offer_id):
    """Cancel an active job offer."""
    company = db.session.get(Company, company_id)
    if not company or company.is_deleted or company.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    job_offer = db.session.get(JobOffer, offer_id)
    if not job_offer or job_offer.company_id != company_id:
        flash('Job offer not found.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Deactivate the job offer
    job_offer.is_active = False
    db.session.commit()

    flash('Job offer cancelled.', 'success')
    return redirect(url_for('company.view_company', company_id=company_id))


@company_bp.route('/job/<int:job_id>/apply', methods=['POST'])
@login_required
def apply_job(job_id):
    """Apply for a job."""
    job_offer = db.session.get(JobOffer, job_id)
    if not job_offer or not job_offer.is_active:
        flash('Job offer not found or inactive.', 'error')
        return redirect(url_for('company.job_market'))

    company = job_offer.company

    # Check if company is frozen (conquered country)
    if company.is_frozen:
        flash('This company is frozen due to country conquest.', 'error')
        return redirect(url_for('company.job_market'))

    # Check if already employed
    existing_employment = db.session.scalar(
        select(Employment).filter_by(company_id=company.id, user_id=current_user.id)
    )
    if existing_employment:
        flash('You are already employed at this company.', 'error')
        return redirect(url_for('company.job_market'))

    # Check skill requirement
    required_skill = get_skill_for_company_type(current_user, company.company_type)
    if required_skill < job_offer.minimum_skill_level:
        skill_name = get_skill_name_for_company_type(company.company_type)
        flash(f'You need {skill_name} skill level {job_offer.minimum_skill_level} to apply.', 'error')
        return redirect(url_for('company.job_market'))

    # Check if company has space
    if company.available_positions <= 0:
        flash('Company has no available positions.', 'error')
        # Deactivate job offer
        job_offer.is_active = False
        db.session.commit()
        return redirect(url_for('company.job_market'))

    # Check if this specific job offer has positions available
    if job_offer.positions_available <= 0:
        flash('This job offer has been filled.', 'error')
        # Deactivate job offer
        job_offer.is_active = False
        db.session.commit()
        return redirect(url_for('company.job_market'))

    # Create employment
    employment = Employment(
        company_id=company.id,
        user_id=current_user.id,
        wage_per_pp=job_offer.wage_per_pp,
        has_worked_today=False,
        total_days_worked=0,
        total_hours_worked=0
    )
    db.session.add(employment)

    # Commit first so the positions_filled property updates
    db.session.commit()

    # Check if this job offer is now full
    if job_offer.positions_available <= 0:
        job_offer.is_active = False
        db.session.commit()

    flash(f'Successfully hired at {company.name}!', 'success')
    return redirect(url_for('company.my_companies'))


# ==================== Employee Management ====================

@company_bp.route('/<int:company_id>/employee/<int:employee_id>/raise', methods=['POST'])
@login_required
def raise_wage(company_id, employee_id):
    """Raise an employee's wage."""
    company = db.session.get(Company, company_id)
    if not company or company.is_deleted or company.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    employment = db.session.get(Employment, employee_id)
    if not employment or employment.company_id != company_id:
        flash('Employee not found.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    new_wage = request.form.get('new_wage', type=float)
    if not new_wage or new_wage <= float(employment.wage_per_pp):
        flash('New wage must be higher than current wage.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    employment.wage_per_pp = Decimal(str(new_wage))
    db.session.commit()

    flash(f'Wage raised to {new_wage} {company.country.currency_code}/PP for {employment.user.username}.', 'success')
    return redirect(url_for('company.view_company', company_id=company_id))


@company_bp.route('/<int:company_id>/employee/<int:employee_id>/fire', methods=['POST'])
@login_required
def fire_employee(company_id, employee_id):
    """Fire an employee."""
    company = db.session.get(Company, company_id)
    if not company or company.is_deleted or company.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    employment = db.session.get(Employment, employee_id)
    if not employment or employment.company_id != company_id:
        flash('Employee not found.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    employee_name = employment.user.username
    employee_user = employment.user

    # Send alert to the fired employee
    job_market_url = url_for('company.job_market', _external=False)
    alert = Alert(
        user_id=employee_user.id,
        alert_type='employment',
        priority='medium',
        title="You have been fired",
        content=f"You have been fired from {company.name}. But don't worry, you can find a new job on the job market.",
        link_url=job_market_url,
        link_text="View Job Market",
        is_read=False
    )
    db.session.add(alert)

    db.session.delete(employment)
    db.session.commit()

    flash(f'{employee_name} has been fired.', 'success')
    return redirect(url_for('company.view_company', company_id=company_id))


@company_bp.route('/<int:company_id>/quit', methods=['POST'])
@login_required
def quit_job(company_id):
    """Quit job at company."""
    employment = db.session.scalar(
        select(Employment).filter_by(company_id=company_id, user_id=current_user.id)
    )

    if not employment:
        flash('You are not employed at this company.', 'error')
        return redirect(url_for('company.my_companies'))

    company_name = employment.company.name
    db.session.delete(employment)
    db.session.commit()

    flash(f'You have quit your job at {company_name}.', 'success')
    return redirect(url_for('company.my_companies'))


# ==================== Company Finances ====================

@company_bp.route('/<int:company_id>/deposit', methods=['POST'])
@login_required
def deposit_funds(company_id):
    """Owner deposits funds to company."""
    company = db.session.get(Company, company_id)
    if not company or company.is_deleted or company.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    currency_type = request.form.get('currency_type')  # 'gold' or 'currency'
    amount = request.form.get('amount', type=float)

    if not amount or amount <= 0:
        flash('Invalid amount.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Gold must be whole numbers
    if currency_type == 'gold' and amount != int(amount):
        flash('Gold amount must be a whole number.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    amount_decimal = Decimal(str(int(amount) if currency_type == 'gold' else amount))

    if currency_type == 'gold':
        # Deduct gold with row-level locking
        from app.services.currency_service import CurrencyService
        success, message, _ = CurrencyService.deduct_gold(
            current_user.id, amount_decimal, f'Company {company_id} deposit'
        )
        if not success:
            flash(f'Could not deduct gold: {message}', 'error')
            return redirect(url_for('company.view_company', company_id=company_id))

        company.gold_balance += amount_decimal
        log_company_transaction(
            company,
            CompanyTransactionType.OWNER_DEPOSIT_GOLD,
            amount_gold=amount_decimal,
            description='Owner deposit'
        )
        flash(f'Deposited {amount} Gold to company.', 'success')

    else:
        flash('Currency deposits not yet implemented.', 'warning')

    db.session.commit()
    return redirect(url_for('company.view_company', company_id=company_id))


@company_bp.route('/<int:company_id>/withdraw', methods=['POST'])
@login_required
def withdraw_funds(company_id):
    """Owner withdraws funds from company."""
    company = db.session.get(Company, company_id)
    if not company or company.is_deleted or company.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    currency_type = request.form.get('currency_type')
    amount = request.form.get('amount', type=float)

    if not amount or amount <= 0:
        flash('Invalid amount.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Gold must be whole numbers
    if currency_type == 'gold' and amount != int(amount):
        flash('Gold amount must be a whole number.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    amount_decimal = Decimal(str(int(amount) if currency_type == 'gold' else amount))

    if currency_type == 'gold':
        if company.gold_balance < amount_decimal:
            flash('Insufficient company gold.', 'error')
            return redirect(url_for('company.view_company', company_id=company_id))

        # Apply 10% income tax on gold withdrawal (reduced by Tax Breaks NFT)
        from app.services.bonus_calculator import BonusCalculator
        BASE_INCOME_TAX_RATE = Decimal('0.10')  # 10% fixed rate
        base_tax_amount = (amount_decimal * BASE_INCOME_TAX_RATE).quantize(Decimal('0.01'))

        # Apply Tax Breaks NFT reduction
        tax_amount = Decimal(str(BonusCalculator.apply_company_tax(company.id, float(base_tax_amount)))).quantize(Decimal('0.01'))
        owner_receives = amount_decimal - tax_amount

        # Deduct full amount from company
        company.gold_balance -= amount_decimal

        # Owner receives amount after tax with row-level locking
        from app.services.currency_service import CurrencyService
        success, message, _ = CurrencyService.add_gold(
            current_user.id, owner_receives, f'Company {company_id} withdrawal'
        )
        if not success:
            # Rollback company deduction
            company.gold_balance += amount_decimal
            flash(f'Could not add gold: {message}', 'error')
            return redirect(url_for('company.view_company', company_id=company_id))

        # Tax goes to country treasury where company is located (with row-level locking)
        company_country = db.session.scalar(
            db.select(Country).where(Country.id == company.country_id).with_for_update()
        )
        if company_country:
            company_country.treasury_gold += tax_amount

        # Calculate effective tax rate for display
        effective_tax_rate = (tax_amount / amount_decimal * 100).quantize(Decimal('0.1')) if amount_decimal > 0 else Decimal('0')
        tax_reduction = BonusCalculator.get_tax_reduction(company.id)

        log_company_transaction(
            company,
            CompanyTransactionType.OWNER_WITHDRAWAL_GOLD,
            amount_gold=amount_decimal,
            description=f'Owner withdrawal ({effective_tax_rate}% tax: {tax_amount} Gold to {company_country.name if company_country else "treasury"})' + (f' [Tax Breaks NFT: -{tax_reduction}%]' if tax_reduction > 0 else '')
        )

        tax_msg = f'{effective_tax_rate}% income tax: {tax_amount} Gold'
        if tax_reduction > 0:
            tax_msg += f' (reduced by {tax_reduction}% from Tax Breaks NFT)'
        flash(f'Withdrew {owner_receives} Gold from company ({tax_msg} to {company_country.name if company_country else "country"} treasury).', 'success')

    else:
        flash('Currency withdrawals not yet implemented.', 'warning')

    db.session.commit()
    return redirect(url_for('company.view_company', company_id=company_id))


@company_bp.route('/<int:company_id>/exchange/buy_currency', methods=['POST'])
@login_required
def exchange_buy_currency(company_id):
    """Exchange Gold for local Currency (sell gold to get currency)."""
    # Lock company row to prevent race conditions on balances
    company = db.session.scalar(
        db.select(Company).where(Company.id == company_id).with_for_update()
    )
    if not company or company.is_deleted or company.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    gold_amount = request.form.get('gold_amount', type=int)
    if not gold_amount or gold_amount <= 0:
        flash('Invalid gold amount. Must be a whole number.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    gold_amount_decimal = Decimal(str(gold_amount))

    # Check if company has enough gold
    if company.gold_balance < gold_amount_decimal:
        flash('Insufficient company gold.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Get gold market for this country
    gold_market = GoldMarket.query.filter_by(country_id=company.country_id).first()
    if not gold_market:
        flash('Gold market not available for this country.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Calculate multi-level sell (can sell across multiple price levels)
    currency_received = Decimal('0')
    remaining_to_sell = gold_amount
    current_progress = int(gold_market.progress_within_level)
    current_level = int(gold_market.price_level)
    volume_per_level = int(gold_market.volume_per_level)

    while remaining_to_sell > 0:
        # Calculate sell price at this level
        base_rate = Decimal(gold_market.initial_exchange_rate) + (Decimal(current_level) * Decimal(gold_market.price_adjustment_per_level))
        base_rate = max(gold_market.MINIMUM_EXCHANGE_RATE_UNIT, base_rate)
        spread_amount = max(gold_market.MINIMUM_EXCHANGE_RATE_UNIT / 10,
                           (base_rate * gold_market.MARKET_SPREAD_PERCENT)).quantize(
            gold_market.MINIMUM_EXCHANGE_RATE_UNIT / 10, rounding=ROUND_DOWN
        )
        rate_at_level = (base_rate - spread_amount).quantize(gold_market.MINIMUM_EXCHANGE_RATE_UNIT, rounding=ROUND_HALF_UP)
        rate_at_level = max(gold_market.MINIMUM_EXCHANGE_RATE_UNIT, rate_at_level)

        # How much can we sell at this level?
        can_sell_at_level = current_progress + 1

        if remaining_to_sell <= can_sell_at_level:
            currency_received += rate_at_level * Decimal(str(remaining_to_sell))
            current_progress -= remaining_to_sell
            remaining_to_sell = 0
        else:
            currency_received += rate_at_level * Decimal(str(can_sell_at_level))
            remaining_to_sell -= can_sell_at_level
            current_level -= 1
            current_progress = volume_per_level - 1

    # Execute exchange
    company.gold_balance -= gold_amount_decimal
    company.currency_balance += currency_received

    # Update market state
    gold_market.price_level = current_level
    gold_market.progress_within_level = max(0, current_progress)

    # Calculate average rate for logging
    avg_rate = currency_received / gold_amount_decimal

    log_company_transaction(
        company,
        CompanyTransactionType.CURRENCY_EXCHANGE,
        amount_gold=-gold_amount_decimal,
        amount_currency=currency_received,
        description=f'Exchanged {gold_amount} Gold for {currency_received:.2f} {company.country.currency_name}'
    )

    # Update OHLC currency rate history with the average rate
    from app.utils import update_currency_rate_ohlc
    update_currency_rate_ohlc(company.country_id, avg_rate)

    db.session.commit()
    flash(f'Exchanged {gold_amount} Gold for {currency_received:.2f} {company.country.currency_name}.', 'success')
    return redirect(url_for('company.view_company', company_id=company_id))


@company_bp.route('/<int:company_id>/exchange/sell_currency', methods=['POST'])
@login_required
def exchange_sell_currency(company_id):
    """Exchange local Currency for Gold (buy gold with currency)."""
    # Lock company row to prevent race conditions on balances
    company = db.session.scalar(
        db.select(Company).where(Company.id == company_id).with_for_update()
    )
    if not company or company.is_deleted or company.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    gold_amount = request.form.get('gold_amount', type=int)
    if not gold_amount or gold_amount <= 0:
        flash('Invalid gold amount. Must be a whole number.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    gold_amount_decimal = Decimal(str(gold_amount))

    # Get gold market for this country
    gold_market = GoldMarket.query.filter_by(country_id=company.country_id).first()
    if not gold_market:
        flash('Gold market not available for this country.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Calculate multi-level buy (can buy across multiple price levels)
    currency_cost = Decimal('0')
    remaining_to_buy = gold_amount
    current_progress = int(gold_market.progress_within_level)
    current_level = int(gold_market.price_level)
    volume_per_level = int(gold_market.volume_per_level)

    while remaining_to_buy > 0:
        # Calculate buy price at this level
        base_rate = Decimal(gold_market.initial_exchange_rate) + (Decimal(current_level) * Decimal(gold_market.price_adjustment_per_level))
        base_rate = max(gold_market.MINIMUM_EXCHANGE_RATE_UNIT, base_rate)
        spread_amount = max(gold_market.MINIMUM_EXCHANGE_RATE_UNIT / 10,
                           (base_rate * gold_market.MARKET_SPREAD_PERCENT)).quantize(
            gold_market.MINIMUM_EXCHANGE_RATE_UNIT / 10, rounding=ROUND_UP
        )
        rate_at_level = (base_rate + spread_amount).quantize(gold_market.MINIMUM_EXCHANGE_RATE_UNIT, rounding=ROUND_HALF_UP)
        rate_at_level = max(gold_market.MINIMUM_EXCHANGE_RATE_UNIT * 2, rate_at_level)

        # How much can we buy at this level?
        can_buy_at_level = volume_per_level - current_progress

        if remaining_to_buy <= can_buy_at_level:
            currency_cost += rate_at_level * Decimal(str(remaining_to_buy))
            current_progress += remaining_to_buy
            remaining_to_buy = 0
        else:
            currency_cost += rate_at_level * Decimal(str(can_buy_at_level))
            remaining_to_buy -= can_buy_at_level
            current_level += 1
            current_progress = 0

    # Check if company has enough currency for this amount of gold
    if company.currency_balance < currency_cost:
        flash(f'Insufficient company currency. Need {currency_cost:.2f} {company.country.currency_name} to buy {gold_amount} Gold.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Execute exchange
    company.currency_balance -= currency_cost
    company.gold_balance += gold_amount_decimal

    # Update market state
    gold_market.price_level = current_level
    gold_market.progress_within_level = current_progress

    # Calculate average rate for logging
    avg_rate = currency_cost / gold_amount_decimal

    log_company_transaction(
        company,
        CompanyTransactionType.CURRENCY_EXCHANGE_SELL,
        amount_gold=gold_amount_decimal,
        amount_currency=-currency_cost,
        description=f'Exchanged {currency_cost:.2f} {company.country.currency_name} for {gold_amount} Gold'
    )

    # Update OHLC currency rate history with the average rate
    from app.utils import update_currency_rate_ohlc
    update_currency_rate_ohlc(company.country_id, avg_rate)

    db.session.commit()
    flash(f'Exchanged {currency_cost:.2f} {company.country.currency_name} for {gold_amount} Gold.', 'success')
    return redirect(url_for('company.view_company', company_id=company_id))


@company_bp.route('/<int:company_id>/exchange/preview_sell_gold', methods=['POST'])
@login_required
def preview_sell_gold(company_id):
    """Preview selling gold with multi-level breakdown."""
    company = db.session.get(Company, company_id)
    if not company or company.is_deleted or company.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    gold_amount = request.form.get('gold_amount', type=int)
    if not gold_amount or gold_amount <= 0:
        return jsonify({'error': 'Invalid gold amount.'}), 400

    gold_amount_decimal = Decimal(str(gold_amount))

    if company.gold_balance < gold_amount_decimal:
        return jsonify({'error': f'Insufficient gold. Company has {company.gold_balance:.0f} Gold.'}), 400

    gold_market = GoldMarket.query.filter_by(country_id=company.country_id).first()
    if not gold_market:
        return jsonify({'error': 'Gold market not available.'}), 400

    # Calculate breakdown
    breakdown = []
    total_received = Decimal('0')
    remaining = gold_amount
    current_progress = int(gold_market.progress_within_level)
    current_level = int(gold_market.price_level)
    volume_per_level = int(gold_market.volume_per_level)

    while remaining > 0:
        base_rate = Decimal(gold_market.initial_exchange_rate) + (Decimal(current_level) * Decimal(gold_market.price_adjustment_per_level))
        base_rate = max(gold_market.MINIMUM_EXCHANGE_RATE_UNIT, base_rate)
        spread_amount = max(gold_market.MINIMUM_EXCHANGE_RATE_UNIT / 10,
                           (base_rate * gold_market.MARKET_SPREAD_PERCENT)).quantize(
            gold_market.MINIMUM_EXCHANGE_RATE_UNIT / 10, rounding=ROUND_DOWN
        )
        rate_at_level = (base_rate - spread_amount).quantize(gold_market.MINIMUM_EXCHANGE_RATE_UNIT, rounding=ROUND_HALF_UP)
        rate_at_level = max(gold_market.MINIMUM_EXCHANGE_RATE_UNIT, rate_at_level)

        can_sell_at_level = current_progress + 1

        if remaining <= can_sell_at_level:
            breakdown.append([remaining, float(rate_at_level)])
            total_received += rate_at_level * Decimal(str(remaining))
            remaining = 0
        else:
            breakdown.append([can_sell_at_level, float(rate_at_level)])
            total_received += rate_at_level * Decimal(str(can_sell_at_level))
            remaining -= can_sell_at_level
            current_level -= 1
            current_progress = volume_per_level - 1

    return jsonify({
        'breakdown': breakdown,
        'total_proceeds': float(total_received),
        'currency_name': company.country.currency_name,
        'quantity': gold_amount
    })


@company_bp.route('/<int:company_id>/exchange/preview_buy_gold', methods=['POST'])
@login_required
def preview_buy_gold(company_id):
    """Preview buying gold with multi-level breakdown."""
    company = db.session.get(Company, company_id)
    if not company or company.is_deleted or company.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    gold_amount = request.form.get('gold_amount', type=int)
    if not gold_amount or gold_amount <= 0:
        return jsonify({'error': 'Invalid gold amount.'}), 400

    gold_market = GoldMarket.query.filter_by(country_id=company.country_id).first()
    if not gold_market:
        return jsonify({'error': 'Gold market not available.'}), 400

    # Calculate breakdown
    breakdown = []
    total_cost = Decimal('0')
    remaining = gold_amount
    current_progress = int(gold_market.progress_within_level)
    current_level = int(gold_market.price_level)
    volume_per_level = int(gold_market.volume_per_level)

    while remaining > 0:
        base_rate = Decimal(gold_market.initial_exchange_rate) + (Decimal(current_level) * Decimal(gold_market.price_adjustment_per_level))
        base_rate = max(gold_market.MINIMUM_EXCHANGE_RATE_UNIT, base_rate)
        spread_amount = max(gold_market.MINIMUM_EXCHANGE_RATE_UNIT / 10,
                           (base_rate * gold_market.MARKET_SPREAD_PERCENT)).quantize(
            gold_market.MINIMUM_EXCHANGE_RATE_UNIT / 10, rounding=ROUND_UP
        )
        rate_at_level = (base_rate + spread_amount).quantize(gold_market.MINIMUM_EXCHANGE_RATE_UNIT, rounding=ROUND_HALF_UP)
        rate_at_level = max(gold_market.MINIMUM_EXCHANGE_RATE_UNIT * 2, rate_at_level)

        can_buy_at_level = volume_per_level - current_progress

        if remaining <= can_buy_at_level:
            breakdown.append([remaining, float(rate_at_level)])
            total_cost += rate_at_level * Decimal(str(remaining))
            remaining = 0
        else:
            breakdown.append([can_buy_at_level, float(rate_at_level)])
            total_cost += rate_at_level * Decimal(str(can_buy_at_level))
            remaining -= can_buy_at_level
            current_level += 1
            current_progress = 0

    if company.currency_balance < total_cost:
        return jsonify({
            'error': f'Insufficient currency. Need {total_cost:.2f} {company.country.currency_name}, have {company.currency_balance:.2f}.'
        }), 400

    return jsonify({
        'breakdown': breakdown,
        'total_cost': float(total_cost),
        'currency_name': company.country.currency_name,
        'quantity': gold_amount
    })


@company_bp.route('/<int:company_id>/inventory/sell', methods=['POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_COMPANY_ACTION", "50 per hour"))
def sell_inventory(company_id):
    """Sell company inventory to the market with confirmation modal."""
    from app.models import Embargo

    # Lock company row to prevent race conditions on balances
    company = db.session.scalar(
        db.select(Company).where(Company.id == company_id).with_for_update()
    )
    if not company or company.is_deleted or company.owner_id != current_user.id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Unauthorized'}), 403
        flash('Unauthorized.', 'error')
        return redirect(url_for('company.my_companies'))

    # Check for trade embargo between owner's citizenship and company's country
    if current_user.citizenship_id and current_user.citizenship_id != company.country_id:
        if Embargo.has_embargo(current_user.citizenship_id, company.country_id):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Cannot sell to this market due to a trade embargo between your country and the company\'s country.'}), 403
            flash('Cannot sell to this market due to a trade embargo between your country and the company\'s country.', 'error')
            return redirect(url_for('company.view_company', company_id=company_id))

    resource_id = request.form.get('resource_id', type=int)
    quantity = request.form.get('quantity', type=int)
    # Normalize quality: empty string or missing = 0 (raw materials), otherwise use the value
    quality_str = request.form.get('quality', '')
    quality = int(quality_str) if quality_str and quality_str.strip() else 0
    confirmed = request.form.get('confirmed') == 'true'
    expected_price_level = request.form.get('expected_price_level', type=int)

    if not resource_id or not quantity or quantity <= 0:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Invalid input'}), 400
        flash('Invalid input.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Get the resource
    resource = db.session.get(Resource, resource_id)
    if not resource or resource.is_deleted:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Resource not found'}), 404
        flash('Resource not found.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Get company inventory (lock row to prevent race conditions on sell)
    inventory_item = db.session.scalar(
        select(CompanyInventory).filter_by(
            company_id=company.id,
            resource_id=resource_id,
            quality=quality
        ).with_for_update()
    )

    if not inventory_item or inventory_item.quantity < quantity:
        error_msg = 'Insufficient inventory.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': error_msg}), 400
        flash(error_msg, 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Get market item for pricing (with quality)
    # Default to quality=0 for non-quality items (raw materials)
    market_quality = quality if quality else 0
    market_item = db.session.scalar(
        select(CountryMarketItem).filter_by(
            country_id=company.country_id,
            resource_id=resource_id,
            quality=market_quality
        )
    )

    if not market_item:
        error_msg = f'{resource.name} market not available in {company.country.name}.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': error_msg}), 404
        flash(error_msg, 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # If not confirmed, calculate breakdown and return for confirmation
    if not confirmed:
        breakdown_data = calculate_sell_breakdown(market_item, quantity)
        quality_str = f'Q{quality}' if quality else 'Raw'

        return jsonify({
            'breakdown': breakdown_data['breakdown'],
            'total_proceeds': breakdown_data['total_proceeds'],
            'currency_code': company.country.currency_name,
            'resource_name': f"{quality_str} {resource.name}" if quality else resource.name,
            'quantity': quantity,
            'current_price_level': int(market_item.price_level)
        })

    # CONFIRMED SALE - Check for race condition
    current_price_level = int(market_item.price_level)
    if expected_price_level is not None and current_price_level != expected_price_level:
        flash('Price has changed since you requested the sale. Please try again with the updated price.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Recalculate breakdown
    breakdown_data = calculate_sell_breakdown(market_item, quantity)
    total_proceeds = Decimal(str(breakdown_data['total_proceeds']))

    # Calculate taxes (lock country row for treasury update)
    market_country = db.session.scalar(
        db.select(Country).where(Country.id == company.country_id).with_for_update()
    )
    vat_rate = market_country.vat_tax_rate / Decimal('100')  # Convert percentage to decimal
    vat_amount = total_proceeds * vat_rate

    # Check if this is an import (company from different country selling in market country)
    # For import tax, we need to check if company has export license
    # TODO: Check export license when that system is implemented
    is_import = False  # Will implement export license check later
    import_tax_amount = Decimal('0')

    if is_import:
        import_rate = market_country.import_tax_rate / Decimal('100')
        import_tax_amount = total_proceeds * import_rate

    total_tax = vat_amount + import_tax_amount
    company_receives = total_proceeds - total_tax

    try:
        # Remove from inventory
        inventory_item.quantity -= quantity
        if inventory_item.quantity == 0:
            db.session.delete(inventory_item)

        # Add currency to company (after tax)
        company.currency_balance += company_receives

        # Add tax to country treasury
        market_country.treasury_currency += total_tax

        # Update market progress using breakdown data
        market_item.price_level = breakdown_data['final_price_level']
        market_item.progress_within_level = breakdown_data['final_progress']

        # Log transaction with tax details
        quality_str = f'Q{quality} ' if quality else 'Raw '
        avg_price = total_proceeds / Decimal(str(quantity))
        tax_description = f' (VAT: {vat_amount:.2f}'
        if import_tax_amount > 0:
            tax_description += f', Import Tax: {import_tax_amount:.2f}'
        tax_description += ')'

        log_company_transaction(
            company,
            CompanyTransactionType.INVENTORY_SALE,
            amount_currency=company_receives,
            description=f'Sold {quantity} {quality_str}{resource.name} (avg: {avg_price:.2f} {company.country.currency_name} each){tax_description}'
        )

        db.session.commit()
        flash(f'Sold {quantity} {quality_str}{resource.name}. Received {company_receives:.2f} {company.country.currency_name} (Tax: {total_tax:.2f}).', 'success')
        return redirect(url_for('company.view_company', company_id=company_id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during company inventory sell: {e}", exc_info=True)
        flash('Transaction error during sell processing.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))


@company_bp.route('/<int:company_id>/inventory/buy', methods=['POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_COMPANY_ACTION", "50 per hour"))
def buy_inventory(company_id):
    """Buy resources from the market for company."""
    # Lock company row to prevent race conditions on balances
    company = db.session.scalar(
        db.select(Company).where(Company.id == company_id).with_for_update()
    )
    if not company or company.is_deleted or company.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    resource_id = request.form.get('resource_id', type=int)
    quantity = request.form.get('quantity', type=int)
    quality_str = request.form.get('quality', '').strip()
    confirmed = request.form.get('confirmed') == 'true'
    expected_price_level = request.form.get('expected_price_level', type=int)

    # Parse quality: empty string means raw material (quality=0), otherwise parse as int
    if quality_str == '':
        quality = 0
    else:
        try:
            quality = int(quality_str)
            if quality < 1 or quality > 5:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': 'Invalid quality level'}), 400
                flash('Invalid quality level.', 'error')
                return redirect(url_for('company.view_company', company_id=company_id))
        except ValueError:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Invalid quality level'}), 400
            flash('Invalid quality level.', 'error')
            return redirect(url_for('company.view_company', company_id=company_id))

    if not resource_id or not quantity or quantity <= 0:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Invalid input'}), 400
        flash('Invalid input.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Get the resource
    resource = db.session.get(Resource, resource_id)
    if not resource or resource.is_deleted:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Resource not found'}), 404
        flash('Resource not found.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Check if company type is allowed to purchase this resource
    allowed_resources = get_allowed_purchasable_resources(company.company_type)
    if resource.name not in allowed_resources:
        error_msg = f'{company.company_type.value} companies cannot purchase resources from the market.' if company.company_type in [CompanyType.MINING, CompanyType.RESOURCE_EXTRACTION, CompanyType.FARMING] else f'{company.company_type.value} companies can only purchase: {", ".join(allowed_resources)}.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': error_msg}), 403
        flash(error_msg, 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Get market item for pricing - lock row to prevent race conditions on price changes
    market_item = db.session.scalar(
        select(CountryMarketItem).filter_by(
            country_id=company.country_id,
            resource_id=resource_id,
            quality=quality
        ).with_for_update()
    )

    if not market_item:
        error_msg = f'{resource.name} market not available in {company.country.name}.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': error_msg}), 404
        flash(error_msg, 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # If not confirmed, calculate breakdown and return for confirmation
    if not confirmed:
        breakdown_data = calculate_purchase_breakdown(market_item, quantity)
        total_cost = Decimal(str(breakdown_data['total_cost']))

        # Check if company has enough currency
        if company.currency_balance < total_cost:
            return jsonify({
                'error': f'Insufficient funds. Need {total_cost:.2f} {company.country.currency_name}, but only have {company.currency_balance:.2f}.'
            }), 400

        return jsonify({
            'breakdown': breakdown_data['breakdown'],
            'total_cost': breakdown_data['total_cost'],
            'currency_name': company.country.currency_name,
            'resource_name': resource.name,
            'quantity': quantity,
            'current_price_level': int(market_item.price_level)
        })

    # CONFIRMED PURCHASE - Check for race condition
    current_price_level = int(market_item.price_level)
    if expected_price_level is not None and current_price_level != expected_price_level:
        flash('Price has changed since you requested the purchase. Please try again with the updated price.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Recalculate to get exact cost and verify funds
    breakdown_data = calculate_purchase_breakdown(market_item, quantity)
    total_cost = Decimal(str(breakdown_data['total_cost']))

    # Check if company has enough currency
    if company.currency_balance < total_cost:
        flash(f'Insufficient funds. Need {total_cost:.2f} {company.country.currency_name}.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Deduct currency
    company.currency_balance -= total_cost

    # Add to company inventory (quality=0 for raw materials, 1-5 for manufactured goods)
    # Lock inventory row to prevent race conditions
    inventory_item = db.session.scalar(
        select(CompanyInventory).filter_by(
            company_id=company.id,
            resource_id=resource_id,
            quality=quality
        ).with_for_update()
    )

    if inventory_item:
        inventory_item.quantity += quantity
    else:
        inventory_item = CompanyInventory(
            company_id=company.id,
            resource_id=resource_id,
            quantity=quantity,
            quality=quality
        )
        db.session.add(inventory_item)

    # Log transaction with breakdown info
    avg_price = total_cost / Decimal(str(quantity))
    quality_label = f'Q{quality} ' if quality > 0 else ''
    log_company_transaction(
        company,
        CompanyTransactionType.INVENTORY_PURCHASE,
        amount_currency=-total_cost,
        description=f'Bought {quantity} {quality_label}{resource.name} (avg: {avg_price:.2f} {company.country.currency_name} each)'
    )

    # Update market progress using breakdown data
    market_item.price_level = breakdown_data['final_price_level']
    market_item.progress_within_level = breakdown_data['final_progress']

    db.session.commit()
    flash(f'Bought {quantity} {quality_label}{resource.name} for {total_cost:.2f} {company.country.currency_name}.', 'success')
    return redirect(url_for('company.view_company', company_id=company_id))


@company_bp.route('/<int:company_id>/transactions')
@login_required
def view_transactions(company_id):
    """View company transaction history."""
    company = db.session.get(Company, company_id)
    if not company or company.is_deleted or company.owner_id != current_user.id:
        flash('Unauthorized.', 'error')
        return redirect(url_for('company.my_companies'))

    transactions = company.transactions.order_by(
        CompanyTransaction.created_at.desc()
    ).limit(100).all()

    return render_template('company/transactions.html',
                         company=company,
                         transactions=transactions)


# ==================== Company Upgrades & Settings ====================

@company_bp.route('/<int:company_id>/upgrade', methods=['POST'])
@login_required
def upgrade_company(company_id):
    """Upgrade company quality level."""
    company = db.session.get(Company, company_id)
    if not company or company.is_deleted or company.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    if company.quality_level >= 5:
        flash('Company is already at maximum quality (Q5).', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    upgrade_cost = Decimal(str(company.upgrade_cost))
    if company.gold_balance < upgrade_cost:
        flash(f'Company needs {upgrade_cost} Gold to upgrade.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    company.gold_balance -= upgrade_cost
    company.quality_level += 1
    log_company_transaction(
        company,
        CompanyTransactionType.UPGRADE,
        amount_gold=upgrade_cost,
        description=f'Upgrade to Q{company.quality_level}'
    )

    db.session.commit()

    flash(f'Company upgraded to Q{company.quality_level}!', 'success')
    return redirect(url_for('company.view_company', company_id=company_id))


@company_bp.route('/<int:id>/dissolve', methods=['POST'])
@login_required
def dissolve_company(id):
    """Dissolve a company and refund 50% of upgrade costs."""
    company = db.session.get(Company, id)

    # Authorization check
    if not company or company.is_deleted or company.owner_id != current_user.id:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('company.my_companies'))

    # Calculate refund based on quality level
    # Q1=10, Q2=30, Q3=70, Q4=150, Q5=310 gold
    refund_amounts = [10, 30, 70, 150, 310]
    refund_amount = Decimal(str(refund_amounts[company.quality_level - 1]))

    # Fire all employees
    employees = list(company.employees)
    employees_count = len(employees)
    for employee in employees:
        employee.is_deleted = True
        employee.end_date = datetime.utcnow()
        # Create alert for fired employee
        alert = Alert(
            user_id=employee.user_id,
            alert_type=AlertType.EMPLOYMENT,
            title='Employment Ended',
            content=f'You were fired from {company.name} because the company was dissolved.',
            link_url=url_for('company.job_market'),
            link_text='Find New Job'
        )
        db.session.add(alert)

    # Cancel all job offers
    job_offers = list(company.job_offers.filter_by(is_active=True))
    job_offers_count = len(job_offers)
    for job_offer in job_offers:
        job_offer.is_active = False

    # Delete all inventory (company inventory will be cascade deleted when company is soft-deleted)
    inventory_count = company.inventory.count()

    # Record the company money being lost
    company_currency = company.currency_balance

    # Give refund to owner's gold with row-level locking
    from app.services.currency_service import CurrencyService
    success, message, _ = CurrencyService.add_gold(
        current_user.id, refund_amount, f'Company dissolution refund for company {company.id}'
    )
    if not success:
        flash(f'Error processing refund: {message}', 'danger')
        return redirect(url_for('company.manage_company', company_id=company_id))

    # Log the dissolution transaction
    log_company_transaction(
        company,
        CompanyTransactionType.OWNER_WITHDRAWAL_GOLD,
        amount_gold=refund_amount,
        description=f'Company dissolved - refund of {refund_amount} gold'
    )

    # Soft delete the company
    company.is_deleted = True
    company.deleted_at = datetime.utcnow()

    db.session.commit()

    flash(f'Company "{company.name}" has been dissolved. You received {refund_amount} Gold as a refund. {employees_count} employees were fired, {job_offers_count} job offers were cancelled, {inventory_count} inventory items were lost, and {company_currency} {company.country.currency_name} was lost.', 'success')
    return redirect(url_for('company.my_companies'))


# ==================== Company Market Sales ====================

@company_bp.route('/<int:company_id>/sell', methods=['POST'])
@login_required
def sell_product(company_id):
    """Sell company products on the market."""
    # Lock company row to prevent race conditions on balances
    company = db.session.scalar(
        db.select(Company).where(Company.id == company_id).with_for_update()
    )
    if not company or company.is_deleted or company.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    inventory_id = request.form.get('inventory_id', type=int)
    quantity = request.form.get('quantity', type=int)
    target_country_id = request.form.get('country_id', type=int)

    if not all([inventory_id, quantity, target_country_id]):
        flash('Missing required fields.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Get inventory item (need to fetch by composite key)
    # Lock row to prevent race conditions on sell
    resource_id = request.form.get('resource_id', type=int)
    quality_level = request.form.get('quality', type=int, default=0)

    inventory_item = db.session.scalar(
        select(CompanyInventory).filter_by(
            company_id=company.id,
            resource_id=resource_id,
            quality=quality_level
        ).with_for_update()
    )

    if not inventory_item or inventory_item.quantity < quantity:
        flash('Insufficient inventory.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Check export license
    export_license = db.session.scalar(
        select(ExportLicense).filter_by(
            company_id=company.id,
            country_id=target_country_id
        )
    )

    if not export_license:
        flash(f'No export license for this country. Purchase one first.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Get market item for this country
    from app.models import CountryMarketItem
    market_item = db.session.scalar(
        select(CountryMarketItem).filter_by(
            country_id=target_country_id,
            resource_id=resource_id
        )
    )

    if not market_item:
        flash('Market item not found for this country.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Calculate sale price
    sell_price_per_unit = market_item.sell_price
    total_revenue = sell_price_per_unit * Decimal(str(quantity))

    # Get country currency
    target_country = db.session.get(Country, target_country_id)

    # Remove from inventory
    inventory_item.quantity -= quantity
    if inventory_item.quantity == 0:
        db.session.delete(inventory_item)

    # Add revenue to company (in country's currency for now, simplified)
    company.currency_balance += total_revenue

    # Log transaction
    log_company_transaction(
        company,
        CompanyTransactionType.PRODUCT_SALE,
        amount_currency=total_revenue,
        description=f'Sold {quantity}x {inventory_item.resource.name} in {target_country.name}'
    )

    # Update market (sold = supply increased)
    market_item.progress_within_level += quantity
    while market_item.progress_within_level >= market_item.volume_per_level:
        market_item.progress_within_level -= market_item.volume_per_level
        market_item.price_level -= 1

    db.session.commit()

    flash(f'Sold {quantity}x {inventory_item.resource.name} for {total_revenue:.2f} currency!', 'success')
    return redirect(url_for('company.view_company', company_id=company_id))


@company_bp.route('/<int:company_id>/export-license/buy', methods=['POST'])
@login_required
def buy_export_license(company_id):
    """Purchase export license for a country."""
    company = db.session.get(Company, company_id)
    if not company or company.is_deleted or company.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    country_id = request.form.get('country_id', type=int)
    if not country_id:
        flash('Country not specified.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Check if already have license
    existing_license = db.session.scalar(
        select(ExportLicense).filter_by(
            company_id=company.id,
            country_id=country_id
        )
    )

    if existing_license:
        flash('You already have an export license for this country.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Check payment
    license_cost = Decimal('10.0')
    if company.gold_balance < license_cost:
        flash(f'Company needs {license_cost} Gold for export license.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Purchase license
    company.gold_balance -= license_cost
    export_license = ExportLicense(
        company_id=company.id,
        country_id=country_id
    )
    db.session.add(export_license)

    log_company_transaction(
        company,
        CompanyTransactionType.EXPORT_LICENSE,
        amount_gold=license_cost,
        description=f'Export license for {db.session.get(Country, country_id).name}'
    )

    db.session.commit()

    flash('Export license purchased!', 'success')
    return redirect(url_for('company.view_company', company_id=company_id))


@company_bp.route('/<int:company_id>/activate-android', methods=['POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_COMPANY_ACTION", "50 per hour"))
def activate_android(company_id):
    """Activate Android Worker NFT to contribute production points."""
    from app.services.bonus_calculator import BonusCalculator
    from app.time_helpers import get_allocation_date
    from app.models.time_allocation import WorkSession

    company = db.session.get(Company, company_id)
    if not company or company.is_deleted or company.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    # Check if Android Worker NFT is equipped
    android_skill = BonusCalculator.get_android_worker_skill(company.id)
    if android_skill == 0:
        flash('No Android Worker NFT equipped to this company.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Check if company is producing something
    if not company.current_production_resource_id:
        flash('Company has not set a production target. Set production first.', 'error')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Check if Android already worked today (based on game day)
    today = get_allocation_date()
    if company.android_last_worked and company.android_last_worked >= today:
        flash('Android Worker has already completed its shift today. Try again tomorrow.', 'warning')
        return redirect(url_for('company.view_company', company_id=company_id))

    # Android works a full 12-hour shift with its skill level
    # Production = hours × (1 + skill)
    hours = 12  # Full shift
    base_production_points = hours * (1 + android_skill)

    # Apply company NFT production boost bonus
    production_points = BonusCalculator.get_company_production_output(company.id, base_production_points)

    # Handle production for extraction vs manufacturing companies
    is_extraction = company.company_type in [CompanyType.MINING, CompanyType.RESOURCE_EXTRACTION, CompanyType.FARMING]
    products_completed = 0

    if is_extraction:
        # EXTRACTION: Apply quality bonus directly to PP
        effective_pp = production_points * company.quality_production_bonus

        # Apply regional resource bonus (+100% if country has this resource)
        resource_bonus = BonusCalculator.get_extraction_resource_bonus(
            company.id, company.current_production_resource_id
        )
        effective_pp = effective_pp * resource_bonus

        company.production_progress += int(effective_pp * 100)
        required_pp = 100  # 1.00 PP required per unit

        while company.production_progress >= required_pp:
            company.production_progress -= required_pp
            products_completed += 1

        if products_completed > 0:
            # Deduct from regional resource deposits
            BonusCalculator.deduct_regional_resource(
                company.id,
                company.current_production_resource_id,
                products_completed
            )

            # Add products to inventory
            inventory_item = db.session.scalar(
                select(CompanyInventory).where(
                    CompanyInventory.company_id == company.id,
                    CompanyInventory.resource_id == company.current_production_resource_id,
                    CompanyInventory.quality == 0
                ).with_for_update()
            )

            if not inventory_item:
                inventory_item = CompanyInventory(
                    company_id=company.id,
                    resource_id=company.current_production_resource_id,
                    quality=0,
                    quantity=0
                )
                db.session.add(inventory_item)

            inventory_item.quantity += products_completed

    else:
        # MANUFACTURING: Check materials upfront
        base_required_pp = company.required_pp_for_current_product
        required_pp = int(BonusCalculator.get_company_production_speed(company.id, base_required_pp) * 100)
        total_progress = company.production_progress + int(production_points * 100)
        expected_products = total_progress // required_pp

        # Check if company has enough materials
        if expected_products > 0:
            production_resource = db.session.get(Resource, company.current_production_resource_id)
            base_input_requirements = get_input_requirements(production_resource.name, company.quality_level)
            input_requirements = BonusCalculator.get_company_material_cost(company.id, base_input_requirements)

            for material_name, quantity_per_unit in input_requirements.items():
                material_resource = db.session.scalar(
                    select(Resource).where(Resource.name == material_name)
                )
                if not material_resource:
                    flash(f'Material {material_name} not found.', 'error')
                    return redirect(url_for('company.view_company', company_id=company_id))

                inventory_item = db.session.scalar(
                    select(CompanyInventory).where(
                        CompanyInventory.company_id == company.id,
                        CompanyInventory.resource_id == material_resource.id,
                        CompanyInventory.quality == 0
                    )
                )

                total_needed = quantity_per_unit * expected_products
                available = inventory_item.quantity if inventory_item else 0

                if available < total_needed:
                    flash(f"Not enough {material_name} for production. Need {total_needed}, have {available}.", 'error')
                    return redirect(url_for('company.view_company', company_id=company_id))

        # Process manufacturing production
        company.production_progress += int(production_points * 100)

        while company.production_progress >= required_pp:
            company.production_progress -= required_pp
            products_completed += 1

            product_quality = company.quality_level

            # Consume raw materials
            production_resource = db.session.get(Resource, company.current_production_resource_id)
            base_input_requirements = get_input_requirements(production_resource.name, company.quality_level)
            input_requirements = BonusCalculator.get_company_material_cost(company.id, base_input_requirements)

            for material_name, quantity_per_unit in input_requirements.items():
                material_resource = db.session.scalar(
                    select(Resource).where(Resource.name == material_name)
                )
                inventory_item = db.session.scalar(
                    select(CompanyInventory).where(
                        CompanyInventory.company_id == company.id,
                        CompanyInventory.resource_id == material_resource.id,
                        CompanyInventory.quality == 0
                    ).with_for_update()
                )
                inventory_item.quantity -= quantity_per_unit
                if inventory_item.quantity <= 0:
                    db.session.delete(inventory_item)

            # Add finished product to inventory
            inventory_item = db.session.scalar(
                select(CompanyInventory).where(
                    CompanyInventory.company_id == company.id,
                    CompanyInventory.resource_id == company.current_production_resource_id,
                    CompanyInventory.quality == product_quality
                ).with_for_update()
            )

            if not inventory_item:
                inventory_item = CompanyInventory(
                    company_id=company.id,
                    resource_id=company.current_production_resource_id,
                    quality=product_quality,
                    quantity=0
                )
                db.session.add(inventory_item)

            inventory_item.quantity += 1

    # Update production progress tracker
    progress_tracker = db.session.scalar(
        select(CompanyProductionProgress).where(
            CompanyProductionProgress.company_id == company.id,
            CompanyProductionProgress.resource_id == company.current_production_resource_id
        )
    )

    if progress_tracker:
        progress_tracker.progress = company.production_progress
        progress_tracker.updated_at = datetime.utcnow()
    else:
        progress_tracker = CompanyProductionProgress(
            company_id=company.id,
            resource_id=company.current_production_resource_id,
            progress=company.production_progress
        )
        db.session.add(progress_tracker)

    # Mark Android as having worked today
    company.android_last_worked = today

    # Log the work
    log_company_transaction(
        company,
        CompanyTransactionType.WAGE_PAYMENT,  # Using existing type
        amount_currency=Decimal('0'),  # Android doesn't get paid
        description=f'Android Worker (Skill {android_skill}) produced {production_points:.2f} PP'
    )

    db.session.commit()

    flash(f'Android Worker (Skill {android_skill}) worked a 12-hour shift! Produced {production_points:.2f} PP, completing {products_completed} units.', 'success')
    return redirect(url_for('company.view_company', company_id=company_id))
