# app/main/resource_market_routes.py
# Routes related to the resource marketplace

from flask import render_template, redirect, url_for, flash, request, current_app, abort, jsonify
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload
from sqlalchemy import select
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta

from app.main import bp
from app.extensions import db, limiter
from app.models import User, Country, Resource, InventoryItem, CountryMarketItem, log_transaction
from app.models.resource import MarketPriceHistory
from app.utils import format_currency, update_market_price_ohlc
from .forms import MarketBuyForm, MarketSellForm
from .market_utils import get_grouped_resource_choices, get_resource_slug_map
from .company_routes import calculate_purchase_breakdown, calculate_sell_breakdown


@bp.route('/market/<country_slug>', defaults={'resource_slug': None}, methods=['GET'])
@bp.route('/market/<country_slug>/<resource_slug>', methods=['GET'])
@login_required
def marketplace(country_slug, resource_slug):
    """Displays the marketplace for a specific country and resource."""
    selected_country = db.session.scalar(db.select(Country).filter_by(slug=country_slug, is_deleted=False))
    if not selected_country:
        flash(f"Market for country '{country_slug}' not found.", "warning")
        redirect_slug = current_user.citizenship.slug if current_user.is_authenticated and current_user.citizenship else None
        if redirect_slug:
             return redirect(url_for('main.marketplace', country_slug=redirect_slug))
        default_country = db.session.scalars(db.select(Country).filter_by(is_deleted=False).order_by(Country.name).limit(1)).first()
        if default_country:
            return redirect(url_for('main.marketplace', country_slug=default_country.slug))
        return redirect(url_for('main.index'))

    selected_resource = None
    selected_market_item = None
    show_quality_filter = False

    # Get quality filter from query parameter
    selected_quality = request.args.get('quality', type=int)

    user_citizenship_slug = current_user.citizenship.slug if current_user.is_authenticated and current_user.citizenship else None

    all_countries = db.session.scalars(db.select(Country).filter_by(is_deleted=False).order_by(Country.name)).all()
    grouped_resource_choices = get_grouped_resource_choices()
    resource_slugs = get_resource_slug_map()

    if resource_slug:
        selected_resource = db.session.scalar(db.select(Resource).filter_by(slug=resource_slug, is_deleted=False))
        if selected_resource:
            show_quality_filter = selected_resource.can_have_quality

            # Determine which quality to show
            quality_to_show = 0  # Default for non-quality items
            if selected_resource.can_have_quality:
                quality_to_show = selected_quality if selected_quality else 1  # Default to Q1 if no quality specified

            selected_market_item = db.session.scalar(
                db.select(CountryMarketItem).options(
                    joinedload(CountryMarketItem.resource),
                    joinedload(CountryMarketItem.country)
                ).where(
                    CountryMarketItem.country_id == selected_country.id,
                    CountryMarketItem.resource_id == selected_resource.id,
                    CountryMarketItem.quality == quality_to_show
                )
            )
            if not selected_market_item:
                 flash(f"{selected_resource.name} not found on the {selected_country.name} market.", "warning")
                 selected_resource = None
                 resource_slug = None
        else:
             flash(f"Resource '{resource_slug}' not found.", "warning")
             resource_slug = None

    # Fetch price history if a market item is selected
    price_history_data = None
    price_change = None
    if selected_market_item:
        # Get past 30 days of price history
        end_date = date.today()
        start_date = end_date - timedelta(days=29)  # 30 days total including today

        price_history = db.session.scalars(
            db.select(MarketPriceHistory)
            .where(MarketPriceHistory.country_id == selected_market_item.country_id)
            .where(MarketPriceHistory.resource_id == selected_market_item.resource_id)
            .where(MarketPriceHistory.quality == selected_market_item.quality)
            .where(MarketPriceHistory.recorded_date >= start_date)
            .where(MarketPriceHistory.recorded_date <= end_date)
            .order_by(MarketPriceHistory.recorded_date)
        ).all()

        if price_history:
            dates = [record.recorded_date.strftime('%m/%d') for record in price_history]
            # Format data for candlestick chart: {x: date, o: open, h: high, l: low, c: close}
            candlestick_data = []
            for record in price_history:
                candlestick_data.append({
                    'x': record.recorded_date.strftime('%m/%d'),
                    'o': float(record.price_open),
                    'h': float(record.price_high),
                    'l': float(record.price_low),
                    'c': float(record.price_close)
                })
            price_history_data = {
                'dates': dates,
                'candlestick': candlestick_data
            }

            # Calculate price change: today's last traded price vs yesterday's close
            if len(price_history) >= 2:
                yesterday_close = float(price_history[-2].price_close)
                today_close = float(price_history[-1].price_close)  # Last traded price today
                if yesterday_close > 0:
                    change_amount = today_close - yesterday_close
                    change_percent = ((today_close - yesterday_close) / yesterday_close) * 100
                    price_change = {
                        'amount': change_amount,
                        'percent': change_percent,
                        'direction': 'up' if change_amount > 0 else 'down' if change_amount < 0 else 'neutral'
                    }

    return render_template('marketplace.html',
                           title=f"{selected_country.name} Market",
                           country=selected_country,
                           all_countries=all_countries,
                           grouped_resource_choices=grouped_resource_choices,
                           resource_slugs=resource_slugs,
                           selected_market_item=selected_market_item,
                           buy_form=MarketBuyForm(),
                           sell_form=MarketSellForm(),
                           user_citizenship_slug=user_citizenship_slug,
                           resource_slug=resource_slug,
                           selected_quality=selected_quality,
                           show_quality_filter=show_quality_filter,
                           price_history_data=price_history_data,
                           price_change=price_change)


@bp.route('/market/<slug>/buy/<int:resource_id>', methods=['POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_MARKET_BUY", "30 per minute"))
def market_buy(slug, resource_id):
    """Handles buying resources with multi-price-level support."""
    from app.models import Embargo

    country = db.session.scalar(db.select(Country).filter_by(slug=slug, is_deleted=False))
    resource = db.session.get(Resource, resource_id)

    if not country: abort(404)
    if not resource or resource.is_deleted: abort(404)

    # Check for trade embargo between buyer's citizenship and market country
    if current_user.citizenship_id and current_user.citizenship_id != country.id:
        if Embargo.has_embargo(current_user.citizenship_id, country.id):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Cannot buy from this market due to a trade embargo between your country and this market\'s country.'}), 403
            flash('Cannot buy from this market due to a trade embargo between your country and this market\'s country.', 'error')
            return redirect(url_for('main.marketplace', country_slug=slug, resource_slug=resource.slug))

    # Get quality from form data
    quality = request.form.get('quality', type=int, default=0)

    market_item = db.session.scalar(
        db.select(CountryMarketItem).options(
            joinedload(CountryMarketItem.resource)
        ).where(
            CountryMarketItem.country_id == country.id,
            CountryMarketItem.resource_id == resource_id,
            CountryMarketItem.quality == quality
        )
    )

    # Build redirect URL with quality parameter preserved
    def get_redirect_url():
        if quality and quality > 0:
            return url_for('main.marketplace', country_slug=slug, resource_slug=resource.slug, quality=quality)
        return url_for('main.marketplace', country_slug=slug, resource_slug=resource.slug)

    if not market_item:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Market item not found'}), 404
        flash('Market item not found', 'error')
        return redirect(get_redirect_url())

    form = MarketBuyForm(request.form)
    confirmed = request.form.get('confirmed') == 'true'
    expected_price_level = request.form.get('expected_price_level', type=int)

    if not form.validate():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Invalid form data'}), 400
        flash('Invalid quantity', 'error')
        return redirect(get_redirect_url())

    quantity = form.quantity.data

    # If not confirmed, calculate breakdown and return for confirmation
    if not confirmed:
        breakdown_data = calculate_purchase_breakdown(market_item, quantity)
        total_cost = Decimal(str(breakdown_data['total_cost']))
        user_currency = current_user.get_currency_amount(country.id)

        if user_currency < total_cost:
            return jsonify({
                'error': f'Insufficient funds. Need {format_currency(total_cost)} {country.currency_code}, have {format_currency(user_currency)} {country.currency_code}.'
            }), 400

        # Format resource name with quality if applicable
        resource_display_name = resource.name
        if market_item.quality > 0:
            resource_display_name = f"{resource.name} Q{market_item.quality}"

        return jsonify({
            'breakdown': breakdown_data['breakdown'],
            'total_cost': breakdown_data['total_cost'],
            'currency_code': country.currency_code,
            'resource_name': resource_display_name,
            'quantity': quantity,
            'current_price_level': int(market_item.price_level)
        })

    # CONFIRMED PURCHASE - Check for race condition
    current_price_level = int(market_item.price_level)
    if expected_price_level is not None and current_price_level != expected_price_level:
        flash('Price has changed since you requested the purchase. Please try again with the updated price.', 'error')
        return redirect(get_redirect_url())

    # Recalculate breakdown
    breakdown_data = calculate_purchase_breakdown(market_item, quantity)
    total_cost = Decimal(str(breakdown_data['total_cost']))
    user_currency = current_user.get_currency_amount(country.id)

    if user_currency < total_cost:
        flash(f'Insufficient funds. Need {format_currency(total_cost)} {country.currency_code}.', 'error')
        return redirect(get_redirect_url())

    try:
        # Check storage space before purchase
        available_space = current_user.get_available_storage_space()
        actual_quantity = min(quantity, available_space)

        if actual_quantity <= 0:
            flash(f'Your storage is full ({current_user.get_total_inventory_count()}/{current_user.USER_STORAGE_LIMIT}). Please sell or consume items before buying more.', 'warning')
            return redirect(get_redirect_url())

        # Recalculate cost for actual quantity if partial
        if actual_quantity < quantity:
            breakdown_data = calculate_purchase_breakdown(market_item, actual_quantity)
            total_cost = Decimal(str(breakdown_data['total_cost']))

        # Remove currency (with row locking)
        if not current_user.remove_currency(country.id, total_cost):
            flash(f'Transaction failed: insufficient {country.currency_code}.', 'error')
            return redirect(get_redirect_url())

        quantity_added, remaining = current_user.add_to_inventory(resource_id=resource_id, quantity=actual_quantity, quality=market_item.quality)

        if quantity_added == 0:
            # Revert currency on inventory error
            current_user.add_currency(country.id, total_cost)
            db.session.rollback()
            flash('Error adding item to inventory.', 'error')
            return redirect(get_redirect_url())

        # Update market progress using breakdown data
        market_item.price_level = breakdown_data['final_price_level']
        market_item.progress_within_level = breakdown_data['final_progress']

        # Log transaction
        avg_price = total_cost / Decimal(str(quantity_added))

        # Format resource name with quality if applicable
        resource_display_name = resource.name
        if market_item.quality > 0:
            resource_display_name = f"{resource.name} Q{market_item.quality}"

        log_transaction(
            user=current_user,
            transaction_type='MARKET_BUY',
            amount=total_cost,
            currency_type=country.currency_code,
            balance_after=current_user.get_currency_amount(country.id),
            country_id=country.id,
            resource_id=resource_id,
            description=f"Bought {quantity_added} {resource_display_name} (avg: {format_currency(avg_price)} each)",
            metadata_json={'quantity': quantity_added, 'avg_unit_price': str(avg_price), 'quality': market_item.quality}
        )

        # Update OHLC price history with the average price paid
        update_market_price_ohlc(country.id, resource_id, market_item.quality, avg_price)

        # Track mission progress for market_buy (count each item bought)
        from app.services.mission_service import MissionService
        MissionService.track_progress(current_user, 'market_buy', quantity_added)

        db.session.commit()

        # Show appropriate message based on whether full or partial purchase
        if quantity_added < quantity:
            flash(f'Storage limit reached! Bought {quantity_added}/{quantity} {resource_display_name} for {format_currency(total_cost)} {country.currency_code}. Current storage: {current_user.get_total_inventory_count()}/{current_user.USER_STORAGE_LIMIT}.', 'warning')
        else:
            flash(f'Bought {quantity_added} {resource_display_name} for {format_currency(total_cost)} {country.currency_code}.', 'success')
        return redirect(get_redirect_url())

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during market buy: {e}", exc_info=True)
        flash('Transaction error during buy processing.', 'error')
        return redirect(get_redirect_url())


@bp.route('/market/<slug>/sell/<int:resource_id>', methods=['POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_MARKET_SELL", "30 per minute"))
def market_sell(slug, resource_id):
    """Handles selling resources with multi-price-level support."""
    from app.models import Embargo

    country = db.session.scalar(db.select(Country).filter_by(slug=slug, is_deleted=False))
    resource = db.session.get(Resource, resource_id)

    if not country: abort(404)
    if not resource or resource.is_deleted: abort(404)

    # Check for trade embargo between seller's citizenship and market country
    if current_user.citizenship_id and current_user.citizenship_id != country.id:
        if Embargo.has_embargo(current_user.citizenship_id, country.id):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Cannot sell to this market due to a trade embargo between your country and this market\'s country.'}), 403
            flash('Cannot sell to this market due to a trade embargo between your country and this market\'s country.', 'error')
            return redirect(url_for('main.marketplace', country_slug=slug, resource_slug=resource.slug))

    # Get quality from form data
    quality = request.form.get('quality', type=int, default=0)

    market_item = db.session.scalar(
        db.select(CountryMarketItem).options(
            joinedload(CountryMarketItem.resource)
        ).where(
            CountryMarketItem.country_id == country.id,
            CountryMarketItem.resource_id == resource_id,
            CountryMarketItem.quality == quality
        )
    )

    # Build redirect URL with quality parameter preserved
    def get_redirect_url():
        if quality and quality > 0:
            return url_for('main.marketplace', country_slug=slug, resource_slug=resource.slug, quality=quality)
        return url_for('main.marketplace', country_slug=slug, resource_slug=resource.slug)

    if not market_item:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Market item not found'}), 404
        flash('Market item not found', 'error')
        return redirect(get_redirect_url())

    form = MarketSellForm(request.form)
    confirmed = request.form.get('confirmed') == 'true'
    expected_price_level = request.form.get('expected_price_level', type=int)

    if not form.validate():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Invalid form data'}), 400
        flash('Invalid quantity', 'error')
        return redirect(get_redirect_url())

    quantity = form.quantity.data

    # Check if user has enough inventory (with quality)
    user_current_qty = current_user.get_resource_quantity(resource_id, market_item.quality)
    if user_current_qty < quantity:
        error_msg = f'Insufficient {resource.name} Q{market_item.quality}. You have {user_current_qty}.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': error_msg}), 400
        flash(error_msg, 'error')
        return redirect(get_redirect_url())

    # If not confirmed, calculate breakdown and return for confirmation
    if not confirmed:
        breakdown_data = calculate_sell_breakdown(market_item, quantity)

        # Format resource name with quality if applicable
        resource_display_name = resource.name
        if market_item.quality > 0:
            resource_display_name = f"{resource.name} Q{market_item.quality}"

        return jsonify({
            'breakdown': breakdown_data['breakdown'],
            'total_proceeds': breakdown_data['total_proceeds'],
            'currency_code': country.currency_code,
            'resource_name': resource_display_name,
            'quantity': quantity,
            'current_price_level': int(market_item.price_level)
        })

    # CONFIRMED SALE - Check for race condition
    current_price_level = int(market_item.price_level)
    if expected_price_level is not None and current_price_level != expected_price_level:
        flash('Price has changed since you requested the sale. Please try again with the updated price.', 'error')
        return redirect(get_redirect_url())

    # Recalculate breakdown
    breakdown_data = calculate_sell_breakdown(market_item, quantity)
    total_proceeds = Decimal(str(breakdown_data['total_proceeds']))

    try:
        if not current_user.remove_from_inventory(resource_id=resource_id, quantity=quantity, quality=market_item.quality):
            flash(f'Error removing {resource.name} Q{market_item.quality} from inventory.', 'error')
            return redirect(get_redirect_url())

        # Add currency to user's wallet
        current_user.add_currency(country.id, total_proceeds)

        # Update market progress using breakdown data
        market_item.price_level = breakdown_data['final_price_level']
        market_item.progress_within_level = breakdown_data['final_progress']

        # Log transaction
        avg_price = total_proceeds / Decimal(str(quantity))

        # Format resource name with quality if applicable
        resource_display_name = resource.name
        if market_item.quality > 0:
            resource_display_name = f"{resource.name} Q{market_item.quality}"

        log_transaction(
            user=current_user,
            transaction_type='MARKET_SELL',
            amount=total_proceeds,
            currency_type=country.currency_code,
            balance_after=current_user.get_currency_amount(country.id),
            country_id=country.id,
            resource_id=resource_id,
            description=f"Sold {quantity} {resource_display_name} (avg: {format_currency(avg_price)} each)",
            metadata_json={'quantity': quantity, 'avg_unit_price': str(avg_price), 'quality': market_item.quality}
        )

        # Update OHLC price history with the average price received
        update_market_price_ohlc(country.id, resource_id, market_item.quality, avg_price)

        # Track mission progress for market_sell (count each item sold)
        from app.services.mission_service import MissionService
        MissionService.track_progress(current_user, 'market_sell', quantity)

        db.session.commit()
        flash(f'Sold {quantity} {resource_display_name} for {format_currency(total_proceeds)} {country.currency_code}.', 'success')
        return redirect(get_redirect_url())

    except Exception as e:
        db.session.rollback()
        # Attempt to restore inventory with quality
        if not current_user.add_to_inventory(resource_id=resource_id, quantity=quantity, quality=market_item.quality):
            current_app.logger.error(f"CRITICAL: Could not restore inventory for user {current_user.id}, resource {resource_id}, quality {market_item.quality}, quantity {quantity}")
            flash('CRITICAL ERROR during buy transaction recovery. Please contact support.', 'error')
        else:
            try:
                db.session.commit()
                flash('Transaction error during sell. Inventory restored.', 'error')
            except Exception as ie:
                db.session.rollback()
                current_app.logger.error(f"CRITICAL: Could not commit inventory restoration: {ie}")
                flash('CRITICAL ERROR during sell transaction recovery commit. Please contact support.', 'error')
        current_app.logger.error(f"Error during market sell: {e}", exc_info=True)
        return redirect(get_redirect_url())