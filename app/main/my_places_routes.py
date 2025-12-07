# app/main/my_places_routes.py
# Routes for Training, Study, Storage, Travel

from flask import render_template, redirect, url_for, flash, request, current_app, abort
from flask_login import current_user, login_required
from app.main import bp
from app.extensions import db, limiter
# Import models needed (*** ADDED Resource, InventoryItem, ActiveResidence ***)
from app.models import User, Country, Region, country_regions, Resource, InventoryItem, ActiveResidence
# Import forms needed
from .forms import TrainForm, StudyForm, TravelForm
from datetime import datetime, timedelta # Keep if needed for cooldowns
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation # Keep if needed for travel costs
from app.security import InputSanitizer

# --- Training Page Route ---
@bp.route('/training', methods=['GET', 'POST'])
@login_required
def training():
    from app.time_helpers import get_time_until_reset, format_time_remaining

    # Get user's current skill levels
    skills = {
        'infantry': current_user.skill_infantry,
        'armoured': current_user.skill_armoured,
        'aviation': current_user.skill_aviation,
    }

    # Get time allocation data
    allocation = current_user.get_today_allocation()
    remaining_hours = allocation.remaining_hours
    time_until_reset = get_time_until_reset()
    time_remaining_formatted = format_time_remaining(time_until_reset)

    message = None
    message_type = None

    if request.method == 'POST':
        # Validate skill type
        try:
            skill_type = InputSanitizer.sanitize_enum_choice(
                request.form.get('skill_type'),
                ['infantry', 'armoured', 'aviation']
            )
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for('main.training'))

        # Validate hours
        try:
            hours = InputSanitizer.sanitize_integer(
                request.form.get('hours', 0),
                min_val=0,
                max_val=24
            )
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for('main.training'))

        # Allocate training hours
        success, message, skill_gain, energy_cost, leveled_up, new_level = current_user.allocate_training_hours(skill_type, hours)

        if success:
            try:
                db.session.commit()
                message_type = "success"

                # If user leveled up, send alert
                if leveled_up:
                    from app.alert_helpers import send_level_up_alert
                    send_level_up_alert(current_user.id, new_level)

                # Refresh allocation data
                allocation = current_user.get_today_allocation()
                remaining_hours = allocation.remaining_hours

            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error committing training for user {current_user.id}: {e}", exc_info=True)
                message = 'An error occurred during training. Please try again.'
                message_type = "danger"
        else:
            message_type = "danger"

        flash(message, message_type)
        return redirect(url_for('main.training'))

    return render_template('training.html',
                         title='Training Grounds',
                         skills=skills,
                         remaining_hours=remaining_hours,
                         time_remaining=time_remaining_formatted,
                         allocation=allocation)

# --- Study Page Route ---
@bp.route('/study', methods=['GET', 'POST'])
@login_required
def study():
    from app.time_helpers import get_time_until_reset, format_time_remaining

    # Get user's current skill levels
    skills = {
        'resource_extraction': current_user.skill_resource_extraction,
        'manufacture': current_user.skill_manufacture,
        'construction': current_user.skill_construction,
    }

    # Get time allocation data
    allocation = current_user.get_today_allocation()
    remaining_hours = allocation.remaining_hours
    time_until_reset = get_time_until_reset()
    time_remaining_formatted = format_time_remaining(time_until_reset)

    message = None
    message_type = None

    if request.method == 'POST':
        # Validate skill type
        try:
            skill_type = InputSanitizer.sanitize_enum_choice(
                request.form.get('skill_type'),
                ['resource_extraction', 'manufacture', 'construction']
            )
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for('main.study'))

        # Validate hours
        try:
            hours = InputSanitizer.sanitize_integer(
                request.form.get('hours', 0),
                min_val=0,
                max_val=24
            )
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for('main.study'))

        # Allocate studying hours
        success, message, skill_gain, energy_cost, leveled_up, new_level = current_user.allocate_studying_hours(skill_type, hours)

        if success:
            try:
                db.session.commit()
                message_type = "success"

                # If user leveled up, send alert
                if leveled_up:
                    from app.alert_helpers import send_level_up_alert
                    send_level_up_alert(current_user.id, new_level)

                # Refresh allocation data
                allocation = current_user.get_today_allocation()
                remaining_hours = allocation.remaining_hours

            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error committing study for user {current_user.id}: {e}", exc_info=True)
                message = 'An error occurred during study. Please try again.'
                message_type = "danger"
        else:
            message_type = "danger"

        flash(message, message_type)
        return redirect(url_for('main.study'))

    return render_template('study.html',
                         title='Study',
                         skills=skills,
                         remaining_hours=remaining_hours,
                         time_remaining=time_remaining_formatted,
                         allocation=allocation)

# --- Storage Page Route ---
@bp.route('/storage')
@login_required
def storage():
    # Check and reset daily consumption counters if date has changed
    from app.time_helpers import get_allocation_date
    today = get_allocation_date()
    needs_commit = False

    if not current_user.last_bread_reset_date or current_user.last_bread_reset_date < today:
        current_user.bread_consumed_today = 0
        current_user.last_bread_reset_date = today
        needs_commit = True

    if not current_user.last_beer_reset_date or current_user.last_beer_reset_date < today:
        current_user.beer_consumed_today = 0
        current_user.last_beer_reset_date = today
        needs_commit = True

    if not current_user.last_wine_reset_date or current_user.last_wine_reset_date < today:
        current_user.wine_consumed_today = 0
        current_user.last_wine_reset_date = today
        needs_commit = True

    if needs_commit:
        db.session.commit()

    # Fetch inventory items for the current user, joining with Resource to get names/categories
    # Order by category then by name
    user_inventory = db.session.scalars(
        db.select(InventoryItem) # Now defined
        .join(InventoryItem.resource) # Join based on the relationship
        .where(InventoryItem.user_id == current_user.id)
        .filter(InventoryItem.quantity > 0) # Optionally hide items with zero quantity
        .filter(Resource.is_deleted == False) # Only show active resources
        .order_by(Resource.category, Resource.name) # Resource is now defined
    ).all()

    # Group items by category for display
    # Items are already separate by (resource_id, quality) in the database
    inventory_by_category = {}
    for item in user_inventory:
        category_name = item.resource.category.value # Get the string value from enum
        if category_name not in inventory_by_category:
            inventory_by_category[category_name] = []
        inventory_by_category[category_name].append(item)

    # Get bread resource for wellness restoration info
    bread_resource = db.session.scalar(
        db.select(Resource).where(Resource.slug == 'bread')
    )

    # Calculate wellness restoration data
    wellness_data = None
    if bread_resource:
        bread_quantity = current_user.get_resource_quantity(bread_resource.id)
        wellness_remaining = 100.0 - current_user.wellness
        # New system: max 10 breads per day (item count, not wellness points)
        daily_items_remaining = 10 - int(current_user.bread_consumed_today or 0)

        max_from_wellness = int(wellness_remaining / 2.0)  # Assuming Q1 (worst case)
        max_from_daily_limit = daily_items_remaining
        max_bread_available = min(bread_quantity, max_from_wellness, max_from_daily_limit)

        wellness_data = {
            'bread_resource_id': bread_resource.id,
            'daily_limit_remaining': daily_items_remaining,  # Now shows items remaining, not points
            'max_bread_available': max_bread_available,
            'bread_consumed_today': int(current_user.bread_consumed_today or 0)
        }

    # Get beer resource for energy restoration info
    beer_resource = db.session.scalar(
        db.select(Resource).where(Resource.slug == 'beer')
    )

    # Calculate energy restoration data
    energy_data = None
    if beer_resource:
        beer_quantity = current_user.get_resource_quantity(beer_resource.id)
        energy_remaining = 100.0 - current_user.energy
        # New system: max 10 beers per day (item count, not energy points)
        daily_items_remaining = 10 - int(current_user.beer_consumed_today or 0)

        max_from_energy = int(energy_remaining / 2.0)  # Assuming Q1 (worst case)
        max_from_daily_limit = daily_items_remaining
        max_beer_available = min(beer_quantity, max_from_energy, max_from_daily_limit)

        energy_data = {
            'beer_resource_id': beer_resource.id,
            'daily_limit_remaining': daily_items_remaining,  # Now shows items remaining, not points
            'max_beer_available': max_beer_available,
            'beer_consumed_today': int(current_user.beer_consumed_today or 0)
        }

    # Get wine resource for wellness & energy restoration info
    wine_resource = db.session.scalar(
        db.select(Resource).where(Resource.slug == 'wine')
    )

    # Calculate wine restoration data
    wine_data = None
    if wine_resource:
        wine_quantity = current_user.get_resource_quantity(wine_resource.id)
        wellness_remaining = 100.0 - current_user.wellness
        energy_remaining = 100.0 - current_user.energy
        # Max 10 wines per day (item count)
        daily_items_remaining = 10 - int(current_user.wine_consumed_today or 0)

        # Wine restores both, so use the max of what's needed
        max_from_wellness = int(wellness_remaining / 2.0) if wellness_remaining > 0 else 999  # Assuming Q1
        max_from_energy = int(energy_remaining / 2.0) if energy_remaining > 0 else 999  # Assuming Q1
        max_from_stats = max(max_from_wellness, max_from_energy)
        max_wine_available = min(wine_quantity, max_from_stats, daily_items_remaining)

        wine_data = {
            'wine_resource_id': wine_resource.id,
            'daily_limit_remaining': daily_items_remaining,
            'max_wine_available': max_wine_available,
            'wine_consumed_today': int(current_user.wine_consumed_today or 0)
        }

    # Get storage limit with NFT bonus
    from app.services.inventory_service import InventoryService
    storage_limit = InventoryService.get_storage_limit(current_user)
    storage_count = InventoryService.get_total_count(current_user)
    base_storage = InventoryService.BASE_STORAGE_LIMIT
    storage_bonus = storage_limit - base_storage

    return render_template('storage.html',
                           title='My Storage',
                           inventory_items=user_inventory, # Pass the flat list
                           inventory_by_category=inventory_by_category, # Pass the grouped dictionary
                           wellness_data=wellness_data, # Pass wellness restoration data
                           energy_data=energy_data, # Pass energy restoration data
                           wine_data=wine_data, # Pass wine restoration data
                           storage_limit=storage_limit,
                           storage_count=storage_count,
                           storage_bonus=storage_bonus)


# --- Travel Route ---
@bp.route('/travel', methods=['GET', 'POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_TRAVEL", "50 per hour"))
def travel():
    message = None
    message_type = None
    
    # Get current location string first, so it's available throughout the function
    current_location_str = "N/A"
    current_region = current_user.current_region
    if current_region:
        owner_country = current_region.current_owner
        if owner_country:
            current_location_str = f"{owner_country.name}, {current_region.name}"
        else:
            current_location_str = f"{current_region.name} (Owner Unknown)"
    
    if not current_user.citizenship_id or not current_user.username:
        message = "Please complete your profile setup before traveling."
        message_type = "warning"
        if not current_user.citizenship_id: 
            return redirect(url_for('main.choose_citizenship'))
        else: 
            return redirect(url_for('main.edit_profile'))

    form = TravelForm()

    if form.validate_on_submit():
        try:
            selected_country = form.country.data
            region_id = form.region.data # String ID
            
            # Validate the selected region belongs to the selected country
            destination_region = db.session.scalar(
                db.select(Region).join(country_regions).where(
                    country_regions.c.country_id == selected_country.id,
                    Region.id == int(region_id), # Convert to int for query
                    Region.is_deleted == False
                )
            )

            if not destination_region:
                message = 'Invalid region selected for the chosen country.'
                message_type = "danger"
            elif destination_region.id == current_user.current_region_id:
                message = 'You are already in this region.'
                message_type = "info"
            else:
                # Get payment method from form (default to 'gold' for backward compatibility)
                payment_method = request.form.get('payment_method', 'gold')
                success, travel_message = current_user.travel_to(destination_region.id, payment_method=payment_method)
                if success:
                    try:
                        # Track mission progress for travel
                        from app.services.mission_service import MissionService
                        try:
                            MissionService.track_progress(current_user, 'travel', 1)
                        except Exception as mission_error:
                            current_app.logger.error(f"Error tracking travel mission: {mission_error}")

                        db.session.commit()
                        # Update current location string after successful travel
                        current_location_str = f"{selected_country.name}, {destination_region.name}"
                        message = travel_message
                        message_type = "success"
                    except Exception as e:
                        db.session.rollback()
                        current_app.logger.error(f"Error committing travel for {current_user.wallet_address}: {e}", exc_info=True)
                        message = 'An error occurred during travel. Please try again.'
                        message_type = "danger"
                else:
                    message = travel_message
                    message_type = "warning" # Show warnings like 'not enough gold'

        except Exception as e:
            current_app.logger.error(f"Error processing travel request for {current_user.wallet_address}: {e}", exc_info=True)
            message = 'An error occurred while processing your travel request. Please try again.'
            message_type = "danger"

    # Get travel costs with NFT discount applied
    from app.services.bonus_calculator import BonusCalculator
    travel_cost_gold, travel_cost_energy = BonusCalculator.get_travel_costs(
        current_user.id, 1.0, 50  # Base costs: 1 gold, 50 energy
    )

    return render_template('travel.html',
                         title='Travel',
                         form=form,
                         current_location=current_location_str,
                         message=message,
                         message_type=message_type,
                         travel_cost_gold=travel_cost_gold,
                         travel_cost_energy=travel_cost_energy)


# --- Residence Page Route ---
@bp.route('/residence')
@login_required
def residence():
    """Display the user's active residence and restoration info."""
    # Process automatic restoration from residence
    try:
        restored, wellness_restored, energy_restored = current_user.process_residence_restoration()
        if restored:
            db.session.commit()
            # Note: No flash notification - restoration happens automatically in background
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error processing residence restoration for user {current_user.id}: {e}", exc_info=True)

    active_residence = current_user.active_residence

    # Check if residence has expired and clean it up
    if active_residence and active_residence.is_expired:
        try:
            db.session.delete(active_residence)
            db.session.commit()
            active_residence = None
            flash("Your residence has expired and been removed.", "info")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error removing expired residence for user {current_user.id}: {e}", exc_info=True)

    # Prepare residence data for template
    residence_data = None
    if active_residence:
        # Calculate time remaining
        time_remaining = active_residence.time_remaining
        days_remaining = time_remaining.days if time_remaining else 0
        hours_remaining = (time_remaining.seconds // 3600) if time_remaining else 0
        minutes_remaining = ((time_remaining.seconds % 3600) // 60) if time_remaining else 0

        # Calculate next restore time
        next_restore = active_residence.next_restore_at
        now = datetime.utcnow()
        time_until_restore = next_restore - now if next_restore > now else timedelta(0)
        restore_minutes = (time_until_restore.seconds // 60) if time_until_restore.seconds > 0 else 0
        restore_seconds = (time_until_restore.seconds % 60) if time_until_restore.seconds > 0 else 0

        residence_data = {
            'resource': active_residence.resource,
            'quality': active_residence.quality,
            'activated_at': active_residence.activated_at,
            'expires_at': active_residence.expires_at,
            'days_remaining': days_remaining,
            'hours_remaining': hours_remaining,
            'minutes_remaining': minutes_remaining,
            'next_restore_minutes': restore_minutes,
            'next_restore_seconds': restore_seconds,
            'can_restore_wellness': current_user.wellness < 100.0,
            'can_restore_energy': current_user.energy < 100.0
        }

    return render_template('residence.html',
                         title='My Residence',
                         residence_data=residence_data)


# --- Destroy Residence Route ---
@bp.route('/residence/destroy', methods=['POST'])
@login_required
def destroy_residence():
    """Destroy the user's active residence to allow activating a higher quality one."""
    from app.models.resource import ActiveResidence

    # Ensure clean session state
    try:
        db.session.rollback()
    except Exception:
        pass

    # Query fresh to avoid any stale session issues
    active_residence = db.session.query(ActiveResidence).filter_by(user_id=current_user.id).first()

    if not active_residence:
        flash("You don't have an active residence to destroy.", "warning")
        return redirect(url_for('main.residence'))

    try:
        resource_name = active_residence.resource.name
        quality = active_residence.quality

        db.session.delete(active_residence)
        db.session.commit()

        flash(f"Your Q{quality} {resource_name} has been destroyed. You can now activate a new residence.", "success")
        current_app.logger.info(f"User {current_user.id} destroyed their Q{quality} {resource_name} residence")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error destroying residence for user {current_user.id}: {e}", exc_info=True)
        flash("An error occurred while destroying your residence. Please try again.", "danger")

    return redirect(url_for('main.residence'))


# --- Eat Bread Action Route ---
@bp.route('/eat-bread/<int:quality>/<action>', methods=['POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_EAT_DRINK", "60 per hour"))
def eat_bread_action(quality, action):
    """Handle eating bread actions from storage page (one or max)."""
    if action not in ['one', 'max']:
        flash("Invalid action.", "danger")
        return redirect(url_for('main.storage'))

    if quality < 1 or quality > 5:
        flash("Invalid quality level.", "danger")
        return redirect(url_for('main.storage'))

    # Determine quantity
    quantity = 1 if action == 'one' else 'max'

    # Execute eat_bread method with quality
    success, message, bread_eaten, wellness_restored = current_user.eat_bread(quantity, quality)

    if success:
        try:
            db.session.commit()
            flash(message, "success")
            current_app.logger.info(f"User {current_user.id} ate {bread_eaten} Q{quality} bread, restored {wellness_restored} wellness")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error committing bread eating for user {current_user.id}: {e}", exc_info=True)
            flash("An error occurred while eating bread. Please try again.", "danger")
    else:
        flash(message, "warning")

    return redirect(url_for('main.storage'))


# --- Drink Beer Action Route ---
@bp.route('/drink-beer/<int:quality>/<action>', methods=['POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_EAT_DRINK", "60 per hour"))
def drink_beer_action(quality, action):
    """Handle drinking beer actions from storage page (one or max)."""
    if action not in ['one', 'max']:
        flash("Invalid action.", "danger")
        return redirect(url_for('main.storage'))

    if quality < 1 or quality > 5:
        flash("Invalid quality level.", "danger")
        return redirect(url_for('main.storage'))

    # Determine quantity
    quantity = 1 if action == 'one' else 'max'

    # Execute drink_beer method with quality
    success, message, beer_drunk, energy_restored = current_user.drink_beer(quantity, quality)

    if success:
        try:
            db.session.commit()
            flash(message, "success")
            current_app.logger.info(f"User {current_user.id} drank {beer_drunk} Q{quality} beer, restored {energy_restored} energy")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error committing beer drinking for user {current_user.id}: {e}", exc_info=True)
            flash("An error occurred while drinking beer. Please try again.", "danger")
    else:
        flash(message, "warning")

    return redirect(url_for('main.storage'))


@bp.route('/drink-wine/<int:quality>/<action>', methods=['POST'])
@login_required
@limiter.limit("60 per hour")
def drink_wine_action(quality, action):
    """Handle drinking wine actions from storage page (one or max)."""
    from app.services.wellness_service import WellnessService

    if action not in ['one', 'max']:
        flash("Invalid action.", "danger")
        return redirect(url_for('main.storage'))

    if quality < 1 or quality > 5:
        flash("Invalid quality level.", "danger")
        return redirect(url_for('main.storage'))

    # Determine quantity
    quantity = 1 if action == 'one' else 'max'

    # Execute drink_wine method with quality
    success, message, wine_drunk, wellness_restored, energy_restored = WellnessService.drink_wine(current_user, quantity, quality)

    if success:
        try:
            db.session.commit()
            flash(message, "success")
            current_app.logger.info(f"User {current_user.id} drank {wine_drunk} Q{quality} wine, restored {wellness_restored} wellness and {energy_restored} energy")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error committing wine drinking for user {current_user.id}: {e}", exc_info=True)
            flash("An error occurred while drinking wine. Please try again.", "danger")
    else:
        flash(message, "warning")

    return redirect(url_for('main.storage'))


# --- Activate House Action Route ---
@bp.route('/activate-house/<int:resource_id>/<int:quality>', methods=['POST'])
@login_required
@limiter.limit("10 per hour")
def activate_house(resource_id, quality):
    """Handle activating a house from storage."""
    try:
        # Validate quality
        if quality < 1 or quality > 5:
            flash("Invalid quality level.", "danger")
            return redirect(url_for('main.storage'))

        # Get the resource
        resource = db.session.scalar(
            db.select(Resource).where(
                Resource.id == resource_id,
                Resource.is_deleted == False
            )
        )

        if not resource:
            flash("House not found.", "danger")
            return redirect(url_for('main.storage'))

        # Verify it's a house (check by slug)
        if resource.slug != 'house':
            flash("This item is not a house.", "danger")
            return redirect(url_for('main.storage'))

        # Check if user has this house in inventory (with quality)
        user_quantity = current_user.get_resource_quantity(resource_id, quality)
        if user_quantity < 1:
            flash(f"You don't have a Q{quality} house in your inventory.", "danger")
            return redirect(url_for('main.storage'))

        # Check if user already has an active residence
        if current_user.active_residence:
            # Check if it's expired
            if current_user.active_residence.is_expired:
                # Remove expired residence and commit
                db.session.delete(current_user.active_residence)
                db.session.commit()
                current_app.logger.info(f"Removed expired residence for user {current_user.id}")
            else:
                flash("You already have an active residence. Wait for it to expire before activating a new one.", "warning")
                return redirect(url_for('main.storage'))

        # Remove one house from inventory (with quality)
        if not current_user.remove_from_inventory(resource_id, 1, quality):
            flash("Error removing house from inventory.", "danger")
            return redirect(url_for('main.storage'))

        # Create new active residence with quality
        activated_at = datetime.utcnow()
        expires_at = activated_at + timedelta(days=30)

        new_residence = ActiveResidence(
            user_id=current_user.id,
            resource_id=resource_id,
            quality=quality,
            activated_at=activated_at,
            expires_at=expires_at,
            last_restore_at=activated_at
        )

        db.session.add(new_residence)
        db.session.commit()

        wellness_per_restore = quality * 2
        energy_per_restore = quality * 2
        flash(f"Successfully activated Q{quality} {resource.name}! It will restore {wellness_per_restore} wellness and {energy_per_restore} energy every 15 minutes for 30 days.", "success")
        current_app.logger.info(f"User {current_user.id} activated Q{quality} residence: {resource.name}")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error activating house for user {current_user.id}: {e}", exc_info=True)
        flash("An error occurred while activating the house. Please try again.", "danger")

    return redirect(url_for('main.residence'))