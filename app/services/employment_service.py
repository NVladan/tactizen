"""
Employment Service - Handles all work and employment operations.

This service encapsulates employment management logic that was previously in the User model.
"""

import logging
from datetime import datetime
from decimal import Decimal
from sqlalchemy import select
from app.extensions import db
from app.constants import GameConstants

logger = logging.getLogger(__name__)


class EmploymentService:
    """Service for managing user employment and work operations."""

    @staticmethod
    def get_today_allocation(user):
        """Get or create today's time allocation record."""
        from app.models.time_allocation import TimeAllocation
        from app.time_helpers import get_allocation_date

        today = get_allocation_date()

        allocation = db.session.scalar(
            select(TimeAllocation).where(
                TimeAllocation.user_id == user.id,
                TimeAllocation.allocation_date == today
            )
        )

        if not allocation:
            allocation = TimeAllocation(
                user_id=user.id,
                allocation_date=today,
                hours_training=0,
                hours_studying=0,
                hours_working=0
            )
            db.session.add(allocation)
            db.session.flush()

        return allocation

    @staticmethod
    def get_remaining_hours_today(user):
        """Get remaining hours available for allocation today."""
        allocation = EmploymentService.get_today_allocation(user)
        return allocation.remaining_hours

    @staticmethod
    def can_allocate_hours(user, activity_type, hours):
        """
        Check if user can allocate specified hours to an activity.

        Args:
            user: User instance
            activity_type: 'training', 'studying', or 'working'
            hours: Number of hours to allocate

        Returns:
            tuple: (can_allocate: bool, reason: str or None)
        """
        if hours <= 0:
            return False, "Hours must be greater than 0"

        allocation = EmploymentService.get_today_allocation(user)

        # Check if total hours for this specific activity would exceed 12
        if activity_type == 'training':
            current_activity_hours = allocation.hours_training
            activity_name = "training"
        elif activity_type == 'studying':
            current_activity_hours = allocation.hours_studying
            activity_name = "studying"
        elif activity_type == 'working':
            current_activity_hours = allocation.hours_working
            activity_name = "working"
        else:
            return False, "Invalid activity type"

        if current_activity_hours + hours > 12:
            remaining_for_activity = 12 - current_activity_hours
            return False, f"Cannot allocate more than 12 hours to {activity_name} per day. You have {remaining_for_activity} hours remaining for {activity_name}."

        # Check if total hours would exceed 24
        current_total = allocation.total_hours_allocated
        if current_total + hours > 24:
            return False, f"Only {allocation.remaining_hours} hours remaining today"

        return True, None

    @staticmethod
    def allocate_work_hours(user, employment_id, hours):
        """
        Allocate hours to work at a company.

        Args:
            user: User instance
            employment_id: ID of the employment relationship
            hours: Number of hours to work (1-12)

        Returns:
            tuple: (success: bool, message: str, production_points: float, payment: Decimal, energy_cost: int, wellness_cost: int)
        """
        from app.models.company import Employment, Company, CompanyInventory, CompanyTransaction, CompanyTransactionType, CompanyProductionProgress, CompanyType
        from app.models.time_allocation import WorkSession
        from app.models.currency import log_transaction
        from app.models.resource import Resource

        # Get employment
        employment = db.session.get(Employment, employment_id)
        if not employment or employment.user_id != user.id:
            return False, "Invalid employment", 0.0, Decimal('0'), 0, 0

        # Lock company row to prevent race conditions on currency_balance
        company = db.session.scalar(
            select(Company).where(Company.id == employment.company_id).with_for_update()
        )

        # Validate hours
        can_allocate, reason = EmploymentService.can_allocate_hours(user, 'working', hours)
        if not can_allocate:
            return False, reason, 0.0, Decimal('0'), 0, 0

        # Calculate base costs
        base_energy_cost = hours * 2  # 2 energy per hour
        base_wellness_cost = hours * 2  # 2 wellness per hour

        # Apply NFT efficiency bonuses
        from app.services.bonus_calculator import BonusCalculator
        energy_cost, wellness_cost = BonusCalculator.apply_work_costs(
            user.id, base_energy_cost, base_wellness_cost
        )

        # Check energy and wellness
        if user.energy < energy_cost:
            return False, f"Insufficient energy. Need {energy_cost}, have {user.energy:.1f}", 0.0, Decimal('0'), 0, 0

        if user.wellness < wellness_cost:
            return False, f"Insufficient wellness. Need {wellness_cost}, have {user.wellness:.1f}", 0.0, Decimal('0'), 0, 0

        # Get user's skill for this company type
        from app.services.skill_service import SkillService
        user_skill = SkillService.get_skill_for_company_type(user, company.company_type)

        # Calculate base production points: hours × (1 + skill)
        # This ensures even workers with low skills produce meaningful output
        # while still rewarding skill progression
        base_production_points = hours * (1 + user_skill)

        # Check for Electricity boost (+30% production if available and enabled)
        # Electricity requirement: 1 electricity per hour worked
        electricity_boost_active = False
        electricity_consumed = 0
        electricity_required = hours  # Simple: 1 electricity per hour

        # Only check electricity if company has it enabled
        if company.use_electricity:
            # Get electricity resource
            electricity_resource = db.session.scalar(
                select(Resource).where(Resource.name == 'Electricity')
            )

            if electricity_resource:
                # Check if company has enough electricity in inventory (lock row)
                electricity_inventory = db.session.scalar(
                    select(CompanyInventory).where(
                        CompanyInventory.company_id == company.id,
                        CompanyInventory.resource_id == electricity_resource.id,
                        CompanyInventory.quality == 0  # Electricity has no quality
                    ).with_for_update()
                )

                if electricity_inventory and electricity_inventory.quantity >= electricity_required:
                    # Company has enough electricity for full boost!
                    electricity_boost_active = True
                    electricity_consumed = electricity_required
                    # Deduct electricity from inventory (row is locked)
                    electricity_inventory.quantity -= electricity_consumed
                    if electricity_inventory.quantity <= 0:
                        db.session.delete(electricity_inventory)

        # Apply electricity boost if active
        if electricity_boost_active:
            production_points = base_production_points * 1.3  # +30% boost
        else:
            production_points = base_production_points

        # Apply company NFT production boost bonus
        from app.services.bonus_calculator import BonusCalculator
        production_points = BonusCalculator.get_company_production_output(company.id, production_points)

        # Calculate payment (PP * wage_per_pp)
        payment = Decimal(str(production_points)) * employment.wage_per_pp

        # Check if company has enough money
        if company.currency_balance < payment:
            return False, f"Company has insufficient funds to pay wages ({company.currency_balance:.2f} < {payment:.2f})", 0.0, Decimal('0'), 0, 0

        # Check if company is producing something
        if not company.current_production_resource_id:
            return False, "Company has not set a production target", 0.0, Decimal('0'), 0, 0

        # Calculate raw materials needed (consumed immediately per hour worked)
        raw_materials_needed_per_unit = company.raw_materials_required

        # For resource extraction companies, no raw materials needed
        is_extraction = company.company_type in [CompanyType.MINING, CompanyType.RESOURCE_EXTRACTION, CompanyType.FARMING]

        if not is_extraction:
            # For manufacturing companies, check if there are enough raw materials
            # for ALL products that would be produced by this work session
            from app.main.company_routes import get_input_requirements

            production_resource = db.session.get(Resource, company.current_production_resource_id)
            if not production_resource:
                return False, "Invalid production resource", 0.0, Decimal('0'), 0, 0

            # Get material requirements for one unit at the company's quality level
            base_input_requirements = get_input_requirements(production_resource.name, company.quality_level)

            # Apply company NFT material efficiency bonus
            input_requirements = BonusCalculator.get_company_material_cost(company.id, base_input_requirements)

            # Calculate how many products would be completed with this work
            # Progress is stored as PP × 100 for 2 decimal precision
            base_required_pp = company.required_pp_for_current_product
            required_pp = int(BonusCalculator.get_company_production_speed(company.id, base_required_pp) * 100)
            total_progress = company.production_progress + int(production_points * 100)
            expected_products = total_progress // required_pp

            # If at least one product would be completed, check materials
            if expected_products > 0:
                # Check if company has enough raw materials for ALL expected products
                for material_name, quantity_per_unit in input_requirements.items():
                    # Get the resource by name
                    material_resource = db.session.scalar(
                        select(Resource).where(Resource.name == material_name)
                    )

                    if not material_resource:
                        return False, f"Material resource {material_name} not found in database", 0.0, Decimal('0'), 0, 0

                    # Check company inventory for this raw material
                    inventory_item = db.session.scalar(
                        select(CompanyInventory).where(
                            CompanyInventory.company_id == company.id,
                            CompanyInventory.resource_id == material_resource.id,
                            CompanyInventory.quality == 0  # Raw materials have no quality
                        )
                    )

                    total_needed = quantity_per_unit * expected_products
                    available = inventory_item.quantity if inventory_item else 0

                    if available < total_needed:
                        # Worker-friendly message - they don't need to know the technical details
                        return False, f"The company doesn't have enough raw materials ({material_name}) to complete production. Please contact the company manager.", 0.0, Decimal('0'), 0, 0

        # Deduct energy and wellness
        user.energy = max(0, user.energy - energy_cost)
        user.wellness = max(0, user.wellness - wellness_cost)

        # Update time allocation
        allocation = EmploymentService.get_today_allocation(user)
        allocation.hours_working += hours

        # Production handling differs for extraction vs manufacturing
        products_completed = 0

        if is_extraction:
            # EXTRACTION COMPANIES: Apply quality bonus directly to PP
            # Quality bonus increases effective production: Q1=1x, Q2=1.25x, Q3=1.5x, Q4=1.75x, Q5=2x
            effective_pp = production_points * company.quality_production_bonus

            # Apply regional resource bonus (+100% if country has this resource)
            resource_bonus = BonusCalculator.get_extraction_resource_bonus(
                company.id, company.current_production_resource_id
            )
            effective_pp = effective_pp * resource_bonus

            company.production_progress += int(effective_pp * 100)  # Store as integer (PP * 100)
            required_pp = 100  # 1.00 PP required per unit (stored as 100)

            while company.production_progress >= required_pp:
                # Product completed!
                company.production_progress -= required_pp
                products_completed += 1

            # Add all completed products to inventory at once
            if products_completed > 0:
                # Deduct from regional resource deposits
                BonusCalculator.deduct_regional_resource(
                    company.id,
                    company.current_production_resource_id,
                    products_completed
                )

                # Add product to company inventory (raw materials have quality=0)
                # Lock inventory row to prevent race conditions
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
            # MANUFACTURING COMPANIES: Progress stored as PP × 100 for 2 decimal precision
            company.production_progress += int(production_points * 100)
            base_required_pp = company.required_pp_for_current_product

            # Apply company NFT speed boost bonus (reduces PP required)
            # Multiply by 100 to match the stored progress scale
            required_pp = int(BonusCalculator.get_company_production_speed(company.id, base_required_pp) * 100)

            while company.production_progress >= required_pp:
                # Product completed! (materials already validated upfront)
                company.production_progress -= required_pp
                products_completed += 1

                # Manufactured goods have quality
                product_quality = company.quality_level
                quantity_produced = 1

                # Consume raw materials for this product
                from app.main.company_routes import get_input_requirements
                production_resource = db.session.get(Resource, company.current_production_resource_id)
                base_input_requirements = get_input_requirements(production_resource.name, company.quality_level)
                input_requirements = BonusCalculator.get_company_material_cost(company.id, base_input_requirements)

                # Deduct materials from inventory (lock rows to prevent race conditions)
                for material_name, quantity_per_unit in input_requirements.items():
                    material_resource = db.session.scalar(
                        select(Resource).where(Resource.name == material_name)
                    )

                    # Lock inventory row for update
                    inventory_item = db.session.scalar(
                        select(CompanyInventory).where(
                            CompanyInventory.company_id == company.id,
                            CompanyInventory.resource_id == material_resource.id,
                            CompanyInventory.quality == 0  # Raw materials
                        ).with_for_update()
                    )

                    # Deduct the materials (should exist due to validation, but check just in case)
                    if not inventory_item:
                        logger.error(f"Material {material_name} not found in inventory during production for company {company.id}")
                        return False, f"Material {material_name} unexpectedly missing from inventory", 0.0, Decimal('0'), 0, 0

                    inventory_item.quantity -= quantity_per_unit

                    # Remove inventory item if quantity reaches 0
                    if inventory_item.quantity <= 0:
                        db.session.delete(inventory_item)

                # Add product to company inventory (lock row to prevent race conditions)
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

                inventory_item.quantity += quantity_produced

        # Update the production progress tracker for the current resource
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
            # Create new progress tracker
            progress_tracker = CompanyProductionProgress(
                company_id=company.id,
                resource_id=company.current_production_resource_id,
                progress=company.production_progress
            )
            db.session.add(progress_tracker)

        # Calculate work tax (lock country for treasury update)
        from app.models import Country
        market_country = db.session.scalar(
            select(Country).where(Country.id == company.country_id).with_for_update()
        )
        work_tax_rate = market_country.work_tax_rate / Decimal('100')  # Convert percentage to decimal
        work_tax_amount = payment * work_tax_rate
        worker_receives = payment - work_tax_amount

        # Pay worker (company already locked with with_for_update)
        company.currency_balance -= payment

        # Give money to worker (after tax) with row-level locking
        from app.services.currency_service import CurrencyService
        CurrencyService.add_currency(user, company.country_id, worker_receives)

        # Add work tax to country treasury (country already locked)
        market_country.treasury_currency += work_tax_amount

        # Update employment stats
        from app.time_helpers import get_allocation_date
        employment.total_hours_worked += hours
        employment.last_worked = get_allocation_date()

        # Log transaction for company
        transaction_description = f"Wage payment to {user.username or user.wallet_address[:8]} - {hours}h × (1 + {user_skill:.2f}) = {production_points:.2f} PP"
        if electricity_boost_active:
            transaction_description += f" (⚡ +30% boost, used {electricity_consumed} electricity)"

        company_transaction = CompanyTransaction(
            company_id=company.id,
            transaction_type=CompanyTransactionType.WAGE_PAYMENT,
            amount_currency=payment,
            description=transaction_description,
            related_user_id=user.id,
            balance_gold_after=company.gold_balance,
            balance_currency_after=company.currency_balance
        )
        db.session.add(company_transaction)

        # Log transaction for user (with tax deduction shown)
        log_transaction(
            user=user,
            transaction_type='work_payment',
            amount=worker_receives,
            currency_type='local',
            balance_after=CurrencyService.get_amount(user, company.country_id),
            country_id=company.country_id,
            description=f"Work payment from {company.name} (Tax: {work_tax_amount:.2f} {market_country.currency_name})"
        )

        # Create work session record (use game day, not calendar date)
        work_session = WorkSession(
            user_id=user.id,
            company_id=company.id,
            employment_id=employment.id,
            hours_worked=hours,
            skill_level=user_skill,
            production_points=production_points,
            wage_per_pp=employment.wage_per_pp,
            total_payment=payment,
            energy_spent=energy_cost,
            wellness_spent=wellness_cost,
            work_date=get_allocation_date()
        )
        db.session.add(work_session)

        # Track work streak for achievements
        from app.services.achievement_service import AchievementService
        try:
            current_streak, achievement_unlocked = AchievementService.track_work_streak(user)
            if achievement_unlocked:
                logger.info(f"User {user.id} unlocked work-related achievement with {current_streak}-day streak")
        except Exception as e:
            logger.error(f"Error tracking work achievement for user {user.id}: {e}")

        # Build success message (worker-friendly: hours, costs, earnings)
        hour_word = "hour" if hours == 1 else "hours"
        message = f"Worked {hours} {hour_word} at {company.name}. Used {energy_cost} energy and {wellness_cost} wellness. Earned {worker_receives:.2f} {company.country.currency_code} (paid {work_tax_amount:.2f} tax)."

        return True, message, production_points, worker_receives, energy_cost, wellness_cost
