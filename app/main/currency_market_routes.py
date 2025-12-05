# app/main/currency_market_routes.py
# Routes related to the currency (Gold) market

from flask import render_template, redirect, url_for, flash, request, current_app, abort
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload
from sqlalchemy import select
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN, ROUND_UP
from datetime import date, timedelta

from app.main import bp
from app.extensions import db, limiter
from app.models import Country, GoldMarket, log_transaction # User might be needed if more attributes are used
from app.models.currency_market import CurrencyPriceHistory
from app.utils import format_currency, update_currency_rate_ohlc
from .forms import MarketBuyForm, MarketSellForm # These forms expect 'quantity'


@bp.route('/currency-market', methods=['GET'])
@login_required
def currency_market_default():
    """Redirect to currency market for player's current location."""
    # Get the country where the player is currently located
    if current_user.current_region and current_user.current_region.current_owner:
        location_country = current_user.current_region.current_owner
        return redirect(url_for('main.currency_market', country_slug=location_country.slug))

    # Fallback to citizenship country
    if current_user.citizenship:
        return redirect(url_for('main.currency_market', country_slug=current_user.citizenship.slug))

    # Last resort: first available country
    default_country = db.session.scalars(db.select(Country).filter_by(is_deleted=False).order_by(Country.name).limit(1)).first()
    if default_country:
        return redirect(url_for('main.currency_market', country_slug=default_country.slug))

    flash("No currency markets available.", "warning")
    return redirect(url_for('main.index'))


@bp.route('/currency-market/<country_slug>', methods=['GET'])
@login_required
def currency_market(country_slug):
    country = db.session.scalar(
        db.select(Country).filter_by(slug=country_slug, is_deleted=False).options(joinedload(Country.gold_market)))
    if not country:
        flash(f"Country '{country_slug}' not found for currency market.", "warning")
        # Redirect to user's current location country or citizenship
        if current_user.current_region and current_user.current_region.current_owner:
            return redirect(url_for('main.currency_market', country_slug=current_user.current_region.current_owner.slug))
        if current_user.citizenship:
            return redirect(url_for('main.currency_market', country_slug=current_user.citizenship.slug))
        default_country_for_market = db.session.scalars(db.select(Country).filter_by(is_deleted=False).order_by(Country.name).limit(1)).first()
        if default_country_for_market:
            return redirect(url_for('main.currency_market', country_slug=default_country_for_market.slug))
        return redirect(url_for('main.index'))


    gold_market_item = country.gold_market
    if not gold_market_item:
        flash(f"Gold market is not yet available for {country.name}.", "warning")
        # GoldMarket might be None, template needs to handle this

    user_citizenship_slug = current_user.citizenship.slug if current_user.is_authenticated and current_user.citizenship else None
    all_countries = db.session.scalars(db.select(Country).filter_by(is_deleted=False).order_by(Country.name)).all()

    message_from_post = request.args.get('message') # Get message if redirected from POST

    # Fetch currency price history if gold market exists
    currency_history_data = None
    price_change = None
    if gold_market_item:
        # Get past 30 days of price history
        end_date = date.today()
        start_date = end_date - timedelta(days=29)  # 30 days total including today

        price_history = db.session.scalars(
            db.select(CurrencyPriceHistory)
            .where(CurrencyPriceHistory.country_id == country.id)
            .where(CurrencyPriceHistory.recorded_date >= start_date)
            .where(CurrencyPriceHistory.recorded_date <= end_date)
            .order_by(CurrencyPriceHistory.recorded_date)
        ).all()

        if price_history:
            dates = [record.recorded_date.strftime('%m/%d') for record in price_history]
            # Format data for candlestick chart: {x: date, o: open, h: high, l: low, c: close}
            candlestick_data = []
            for record in price_history:
                candlestick_data.append({
                    'x': record.recorded_date.strftime('%m/%d'),
                    'o': float(record.rate_open),
                    'h': float(record.rate_high),
                    'l': float(record.rate_low),
                    'c': float(record.rate_close)
                })
            currency_history_data = {
                'dates': dates,
                'candlestick': candlestick_data
            }

            # Calculate price change: today's last traded price vs yesterday's close
            if len(price_history) >= 2:
                yesterday_close = float(price_history[-2].rate_close)
                today_close = float(price_history[-1].rate_close)  # Last traded price today
                if yesterday_close > 0:
                    change_amount = today_close - yesterday_close
                    change_percent = ((today_close - yesterday_close) / yesterday_close) * 100
                    price_change = {
                        'amount': change_amount,
                        'percent': change_percent,
                        'direction': 'up' if change_amount > 0 else 'down' if change_amount < 0 else 'neutral'
                    }

    return render_template(
        'currency_market.html',
        title=f"Currency Market - {country.name}",
        country=country,
        gold_market_item=gold_market_item,
        buy_form=MarketBuyForm(),
        sell_form=MarketSellForm(),
        user_citizenship_slug=user_citizenship_slug,
        all_countries=all_countries,
        message=message_from_post, # Pass message to template
        currency_history_data=currency_history_data,
        price_change=price_change
    )


@bp.route('/currency-market/<slug>/buy-gold', methods=['POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_GOLD_TRADE", "20 per minute"))
def currency_market_buy_gold(slug):
    country = db.session.scalar(db.select(Country).filter_by(slug=slug).options(joinedload(Country.gold_market)))
    if not country or not country.gold_market:
        flash("Market not found.", "danger")
        return redirect(url_for('main.currency_market', country_slug=slug, message="Market not found."))

    gold_market_item = country.gold_market
    form = MarketBuyForm(request.form)
    message = None

    if form.validate():
        gold_to_buy = form.quantity.data

        try:
            # Convert to Decimal for precision
            gold_to_buy_decimal = Decimal(str(gold_to_buy))

            # Calculate multi-level buy (can buy across multiple price levels)
            total_local_currency_cost = Decimal('0')
            remaining_to_buy = gold_to_buy
            current_progress = int(gold_market_item.progress_within_level)
            current_level = int(gold_market_item.price_level)
            volume_per_level = int(gold_market_item.volume_per_level)

            while remaining_to_buy > 0:
                # Calculate buy price at this level
                base_rate = Decimal(gold_market_item.initial_exchange_rate) + (Decimal(current_level) * Decimal(gold_market_item.price_adjustment_per_level))
                base_rate = max(gold_market_item.MINIMUM_EXCHANGE_RATE_UNIT, base_rate)
                spread_amount = max(gold_market_item.MINIMUM_EXCHANGE_RATE_UNIT / 10,
                                   (base_rate * gold_market_item.MARKET_SPREAD_PERCENT)).quantize(
                    gold_market_item.MINIMUM_EXCHANGE_RATE_UNIT / 10, rounding=ROUND_UP
                )
                rate_at_level = (base_rate + spread_amount).quantize(gold_market_item.MINIMUM_EXCHANGE_RATE_UNIT, rounding=ROUND_HALF_UP)
                rate_at_level = max(gold_market_item.MINIMUM_EXCHANGE_RATE_UNIT * 2, rate_at_level)

                # How much can we buy at this level before it increases?
                can_buy_at_level = volume_per_level - current_progress

                if remaining_to_buy <= can_buy_at_level:
                    # Can complete the purchase at this level
                    total_local_currency_cost += rate_at_level * Decimal(str(remaining_to_buy))
                    current_progress += remaining_to_buy
                    remaining_to_buy = 0
                else:
                    # Buy what we can at this level and move to higher level
                    total_local_currency_cost += rate_at_level * Decimal(str(can_buy_at_level))
                    remaining_to_buy -= can_buy_at_level
                    current_level += 1
                    current_progress = 0

            # Get user's currency balance for THIS country
            user_local_currency = current_user.get_currency_amount(country.id)

            if user_local_currency < total_local_currency_cost:
                message = f"Insufficient {country.currency_code}. Need {format_currency(total_local_currency_cost)}, have {format_currency(user_local_currency)}."
            else:
                # Remove local currency (with row locking)
                if not current_user.remove_currency(country.id, total_local_currency_cost):
                    message = f"Transaction failed: insufficient {country.currency_code}."
                else:
                    # Add gold with row-level locking
                    from app.services.currency_service import CurrencyService
                    success, gold_msg, _ = CurrencyService.add_gold(
                        current_user.id, gold_to_buy_decimal, 'Currency market gold purchase'
                    )
                    if not success:
                        # Rollback the currency removal
                        current_user.add_currency(country.id, total_local_currency_cost)
                        message = f"Transaction failed: {gold_msg}"
                        return redirect(url_for('main.currency_market', country_slug=slug, message=message))

                    # Update market state
                    gold_market_item.price_level = current_level
                    gold_market_item.progress_within_level = current_progress

                    # Calculate average rate for logging
                    avg_rate = total_local_currency_cost / gold_to_buy_decimal

                    # Log transaction
                    log_transaction(
                        user=current_user,
                        transaction_type='CURRENCY_EXCHANGE',
                        amount=total_local_currency_cost,
                        currency_type=country.currency_code,
                        balance_after=current_user.get_currency_amount(country.id),
                        country_id=country.id,
                        description=f"Bought {gold_to_buy} Gold",
                        metadata_json={'gold_amount': str(gold_to_buy_decimal), 'rate': str(avg_rate)}
                    )

                    # Update OHLC currency rate history with the average rate
                    update_currency_rate_ohlc(country.id, avg_rate)

                    db.session.commit()
                    message = f"Successfully bought {gold_to_buy} Gold for {format_currency(total_local_currency_cost)} {country.currency_code}."

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error buying Gold: {e}", exc_info=True)
            message = "An error occurred during the transaction."
    else:
        error_messages = [f"{getattr(form, field).label.text if hasattr(getattr(form, field), 'label') else field.capitalize()}: {', '.join(errs)}" for field, errs in form.errors.items()]
        message = "Invalid input. " + " ".join(error_messages)

    return redirect(url_for('main.currency_market', country_slug=slug, message=message))


@bp.route('/currency-market/<slug>/sell-gold', methods=['POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_GOLD_TRADE", "20 per minute"))
def currency_market_sell_gold(slug):
    country = db.session.scalar(db.select(Country).filter_by(slug=slug).options(joinedload(Country.gold_market)))
    if not country or not country.gold_market:
        flash("Market not found.", "danger")
        return redirect(url_for('main.currency_market', country_slug=slug, message="Market not found."))

    gold_market_item = country.gold_market
    form = MarketSellForm(request.form)
    message = None

    if form.validate():
        gold_to_sell = form.quantity.data

        try:
            # Convert to Decimal for precision
            gold_to_sell_decimal = Decimal(str(gold_to_sell))

            if current_user.gold < gold_to_sell_decimal:
                message = f"Insufficient Gold. You have {format_currency(current_user.gold)} Gold."
            else:
                # Calculate multi-level sell (can sell across multiple price levels)
                total_local_currency_received = Decimal('0')
                remaining_to_sell = gold_to_sell
                current_progress = int(gold_market_item.progress_within_level)
                current_level = int(gold_market_item.price_level)
                volume_per_level = int(gold_market_item.volume_per_level)

                # Track weighted average rate for logging
                while remaining_to_sell > 0:
                    # Get current sell price at this level
                    # Temporarily calculate rate based on current level
                    base_rate = Decimal(gold_market_item.initial_exchange_rate) + (Decimal(current_level) * Decimal(gold_market_item.price_adjustment_per_level))
                    base_rate = max(gold_market_item.MINIMUM_EXCHANGE_RATE_UNIT, base_rate)
                    spread_amount = max(gold_market_item.MINIMUM_EXCHANGE_RATE_UNIT / 10,
                                       (base_rate * gold_market_item.MARKET_SPREAD_PERCENT)).quantize(
                        gold_market_item.MINIMUM_EXCHANGE_RATE_UNIT / 10, rounding=ROUND_DOWN
                    )
                    rate_at_level = (base_rate - spread_amount).quantize(gold_market_item.MINIMUM_EXCHANGE_RATE_UNIT, rounding=ROUND_HALF_UP)
                    rate_at_level = max(gold_market_item.MINIMUM_EXCHANGE_RATE_UNIT, rate_at_level)

                    # How much can we sell at this level? (progress goes down when selling)
                    can_sell_at_level = current_progress + 1  # +1 because we can sell down to 0 progress

                    if remaining_to_sell <= can_sell_at_level:
                        # Can complete the sale at this level
                        total_local_currency_received += rate_at_level * Decimal(str(remaining_to_sell))
                        current_progress -= remaining_to_sell
                        remaining_to_sell = 0
                    else:
                        # Sell what we can at this level and move to lower level
                        total_local_currency_received += rate_at_level * Decimal(str(can_sell_at_level))
                        remaining_to_sell -= can_sell_at_level
                        current_level -= 1
                        current_progress = volume_per_level - 1  # Start at top of previous level

                # Deduct gold with row-level locking
                from app.services.currency_service import CurrencyService
                success, gold_msg, _ = CurrencyService.deduct_gold(
                    current_user.id, gold_to_sell_decimal, 'Currency market gold sale'
                )
                if not success:
                    message = f"Transaction failed: {gold_msg}"
                    return redirect(url_for('main.currency_market', country_slug=slug, message=message))

                # Add local currency
                current_user.add_currency(country.id, total_local_currency_received)

                # Update market state
                gold_market_item.price_level = current_level
                gold_market_item.progress_within_level = max(0, current_progress)

                # Calculate average rate for logging
                avg_rate = total_local_currency_received / gold_to_sell_decimal

                # Log transaction
                log_transaction(
                    user=current_user,
                    transaction_type='CURRENCY_EXCHANGE',
                    amount=total_local_currency_received,
                    currency_type=country.currency_code,
                    balance_after=current_user.get_currency_amount(country.id),
                    country_id=country.id,
                    description=f"Sold {gold_to_sell} Gold",
                    metadata_json={'gold_amount': str(gold_to_sell_decimal), 'rate': str(avg_rate)}
                )

                # Update OHLC currency rate history with the average rate
                update_currency_rate_ohlc(country.id, avg_rate)

                db.session.commit()
                message = f"Successfully sold {gold_to_sell} Gold for {format_currency(total_local_currency_received)} {country.currency_code}."

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error selling Gold: {e}", exc_info=True)
            message = "An error occurred during the transaction."
    else:
        error_messages = [f"{getattr(form, field).label.text if hasattr(getattr(form, field), 'label') else field.capitalize()}: {', '.join(errs)}" for field, errs in form.errors.items()]
        message = "Invalid input. " + " ".join(error_messages)

    return redirect(url_for('main.currency_market', country_slug=slug, message=message))


def calculate_gold_buy_breakdown(gold_market_item, quantity):
    """Calculate breakdown for buying gold across multiple price levels."""
    breakdown = []
    total_cost = Decimal('0')
    remaining = quantity
    current_progress = int(gold_market_item.progress_within_level)
    current_level = int(gold_market_item.price_level)
    volume_per_level = int(gold_market_item.volume_per_level)

    while remaining > 0:
        # Calculate buy price at this level
        base_rate = Decimal(gold_market_item.initial_exchange_rate) + (Decimal(current_level) * Decimal(gold_market_item.price_adjustment_per_level))
        base_rate = max(gold_market_item.MINIMUM_EXCHANGE_RATE_UNIT, base_rate)
        spread_amount = max(gold_market_item.MINIMUM_EXCHANGE_RATE_UNIT / 10,
                           (base_rate * gold_market_item.MARKET_SPREAD_PERCENT)).quantize(
            gold_market_item.MINIMUM_EXCHANGE_RATE_UNIT / 10, rounding=ROUND_UP
        )
        rate_at_level = (base_rate + spread_amount).quantize(gold_market_item.MINIMUM_EXCHANGE_RATE_UNIT, rounding=ROUND_HALF_UP)
        rate_at_level = max(gold_market_item.MINIMUM_EXCHANGE_RATE_UNIT * 2, rate_at_level)

        # How much can we buy at this level before it increases?
        can_buy_at_level = volume_per_level - current_progress

        if remaining <= can_buy_at_level:
            # Can complete the purchase at this level
            breakdown.append([remaining, float(rate_at_level)])
            total_cost += rate_at_level * Decimal(str(remaining))
            current_progress += remaining
            remaining = 0
        else:
            # Buy what we can at this level and move to higher level
            breakdown.append([can_buy_at_level, float(rate_at_level)])
            total_cost += rate_at_level * Decimal(str(can_buy_at_level))
            remaining -= can_buy_at_level
            current_level += 1
            current_progress = 0

    return {
        'breakdown': breakdown,
        'total_cost': float(total_cost),
        'final_level': current_level,
        'final_progress': current_progress
    }


def calculate_gold_sell_breakdown(gold_market_item, quantity):
    """Calculate breakdown for selling gold across multiple price levels."""
    breakdown = []
    total_proceeds = Decimal('0')
    remaining = quantity
    current_progress = int(gold_market_item.progress_within_level)
    current_level = int(gold_market_item.price_level)
    volume_per_level = int(gold_market_item.volume_per_level)

    while remaining > 0:
        # Calculate sell price at this level
        base_rate = Decimal(gold_market_item.initial_exchange_rate) + (Decimal(current_level) * Decimal(gold_market_item.price_adjustment_per_level))
        base_rate = max(gold_market_item.MINIMUM_EXCHANGE_RATE_UNIT, base_rate)
        spread_amount = max(gold_market_item.MINIMUM_EXCHANGE_RATE_UNIT / 10,
                           (base_rate * gold_market_item.MARKET_SPREAD_PERCENT)).quantize(
            gold_market_item.MINIMUM_EXCHANGE_RATE_UNIT / 10, rounding=ROUND_DOWN
        )
        rate_at_level = (base_rate - spread_amount).quantize(gold_market_item.MINIMUM_EXCHANGE_RATE_UNIT, rounding=ROUND_HALF_UP)
        rate_at_level = max(gold_market_item.MINIMUM_EXCHANGE_RATE_UNIT, rate_at_level)

        # How much can we sell at this level? (progress goes down when selling)
        can_sell_at_level = current_progress + 1  # +1 because we can sell down to 0 progress

        if remaining <= can_sell_at_level:
            # Can complete the sale at this level
            breakdown.append([remaining, float(rate_at_level)])
            total_proceeds += rate_at_level * Decimal(str(remaining))
            current_progress -= remaining
            remaining = 0
        else:
            # Sell what we can at this level and move to lower level
            breakdown.append([can_sell_at_level, float(rate_at_level)])
            total_proceeds += rate_at_level * Decimal(str(can_sell_at_level))
            remaining -= can_sell_at_level
            current_level -= 1
            current_progress = volume_per_level - 1

    return {
        'breakdown': breakdown,
        'total_proceeds': float(total_proceeds),
        'final_level': current_level,
        'final_progress': max(0, current_progress)
    }


@bp.route('/currency-market/<slug>/preview-buy', methods=['POST'])
@login_required
def currency_market_preview_buy(slug):
    """Preview gold purchase with multi-level breakdown."""
    from flask import jsonify

    country = db.session.scalar(db.select(Country).filter_by(slug=slug).options(joinedload(Country.gold_market)))
    if not country or not country.gold_market:
        return jsonify({'error': 'Market not found.'}), 404

    gold_market_item = country.gold_market

    try:
        quantity = int(request.form.get('quantity', 0))
        if quantity < 1:
            return jsonify({'error': 'Quantity must be at least 1.'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid quantity.'}), 400

    # Calculate breakdown
    breakdown_data = calculate_gold_buy_breakdown(gold_market_item, quantity)

    # Check if user has enough currency
    user_currency = current_user.get_currency_amount(country.id)
    total_cost = Decimal(str(breakdown_data['total_cost']))

    if user_currency < total_cost:
        return jsonify({
            'error': f'Insufficient {country.currency_code}. Need {format_currency(total_cost)}, have {format_currency(user_currency)}.'
        }), 400

    return jsonify({
        'breakdown': breakdown_data['breakdown'],
        'total_cost': breakdown_data['total_cost'],
        'currency_code': country.currency_code,
        'quantity': quantity,
        'current_price_level': int(gold_market_item.price_level)
    })


@bp.route('/currency-market/<slug>/preview-sell', methods=['POST'])
@login_required
def currency_market_preview_sell(slug):
    """Preview gold sale with multi-level breakdown."""
    from flask import jsonify

    country = db.session.scalar(db.select(Country).filter_by(slug=slug).options(joinedload(Country.gold_market)))
    if not country or not country.gold_market:
        return jsonify({'error': 'Market not found.'}), 404

    gold_market_item = country.gold_market

    try:
        quantity = int(request.form.get('quantity', 0))
        if quantity < 1:
            return jsonify({'error': 'Quantity must be at least 1.'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid quantity.'}), 400

    # Check if user has enough gold
    if current_user.gold < Decimal(str(quantity)):
        return jsonify({
            'error': f'Insufficient Gold. You have {format_currency(current_user.gold)} Gold.'
        }), 400

    # Calculate breakdown
    breakdown_data = calculate_gold_sell_breakdown(gold_market_item, quantity)

    return jsonify({
        'breakdown': breakdown_data['breakdown'],
        'total_proceeds': breakdown_data['total_proceeds'],
        'currency_code': country.currency_code,
        'quantity': quantity,
        'current_price_level': int(gold_market_item.price_level)
    })