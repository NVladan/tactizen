# app/main/zen_market_routes.py

from flask import render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload
from decimal import Decimal, InvalidOperation, ROUND_DOWN

from app.extensions import db, limiter
from app.models import ZenMarket, ZenTransaction, ZenPriceHistory
from app.main import bp
from app.blockchain import get_zen_balance_raw, transfer_zen_from_treasury, transfer_zen_to_treasury, verify_zen_transfer, get_treasury_balance
from app.utils import update_zen_rate_ohlc
from datetime import datetime, date
import os


@bp.route('/zen-market', methods=['GET'])
@login_required
def zen_market():
    """Display the ZEN/Gold exchange market."""

    # Get the single ZEN market instance
    market = db.session.scalar(db.select(ZenMarket).where(ZenMarket.id == 1))

    if not market:
        flash("ZEN Market is not available.", "danger")
        return redirect(url_for('main.index'))

    # Get user's ZEN balance from blockchain
    # Check base_wallet_address first, fall back to wallet_address (login address)
    zen_balance = Decimal('0.0')
    wallet_to_check = current_user.base_wallet_address or current_user.wallet_address
    if wallet_to_check:
        try:
            zen_balance = Decimal(str(get_zen_balance_raw(wallet_to_check)))
        except Exception as e:
            current_app.logger.error(f"Error fetching ZEN balance for user {current_user.id}: {e}")
            zen_balance = Decimal('0.0')

    # Get price history for chart (last 30 days)
    thirty_days_ago = date.today() - __import__('datetime').timedelta(days=30)
    price_history = db.session.scalars(
        db.select(ZenPriceHistory)
        .where(ZenPriceHistory.market_id == market.id)
        .where(ZenPriceHistory.recorded_date >= thirty_days_ago)
        .order_by(ZenPriceHistory.recorded_date.asc())
    ).all()

    # Format price history for chart (OHLC data)
    chart_labels = [hist.recorded_date.strftime('%m/%d') for hist in price_history]
    candlestick_data = []
    for hist in price_history:
        candlestick_data.append({
            'x': hist.recorded_date.strftime('%m/%d'),
            'o': float(hist.rate_open),
            'h': float(hist.rate_high),
            'l': float(hist.rate_low),
            'c': float(hist.rate_close)
        })

    zen_history_data = {
        'dates': chart_labels,
        'candlestick': candlestick_data
    }

    # Calculate price change: today's last traded price vs yesterday's close
    price_change = None
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

    # Get recent transactions (last 10)
    recent_transactions = db.session.scalars(
        db.select(ZenTransaction)
        .where(ZenTransaction.market_id == market.id)
        .where(ZenTransaction.user_id == current_user.id)
        .order_by(ZenTransaction.created_at.desc())
        .limit(10)
    ).all()

    return render_template(
        'zen_market.html',
        title='ZEN/Gold Exchange',
        market=market,
        zen_balance=zen_balance,
        user_gold=current_user.gold,
        zen_history_data=zen_history_data,
        recent_transactions=recent_transactions,
        price_change=price_change
    )


@bp.route('/zen-market/buy-zen', methods=['POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_ZEN_TRADE", "20 per minute"))
def zen_market_buy_zen():
    """Buy ZEN with Gold."""

    market = db.session.scalar(db.select(ZenMarket).where(ZenMarket.id == 1))
    if not market:
        flash("Market not found.", "danger")
        return redirect(url_for('main.zen_market'))

    # Check if user has wallet address
    if not current_user.base_wallet_address:
        flash("You need to connect your wallet first! Your wallet is automatically linked when you log in.", "warning")
        return redirect(url_for('main.zen_market'))

    try:
        zen_amount = Decimal(str(request.form.get('quantity', '0')))
    except (TypeError, ValueError, InvalidOperation):
        flash("Invalid ZEN amount.", "danger")
        return redirect(url_for('main.zen_market'))

    if zen_amount <= 0:
        flash("ZEN amount must be greater than zero.", "warning")
        return redirect(url_for('main.zen_market'))

    # Calculate total cost in Gold (at buy price)
    buy_price = market.buy_zen_price  # Gold per 1 ZEN
    total_gold_cost = (zen_amount * buy_price).quantize(Decimal('0.01'), rounding=ROUND_DOWN)

    # Check treasury has enough ZEN before proceeding
    treasury_balance = get_treasury_balance()
    if treasury_balance < zen_amount:
        flash(f"Treasury has insufficient ZEN balance ({treasury_balance:.2f} ZEN). Please try a smaller amount.", "danger")
        return redirect(url_for('main.zen_market'))

    # Deduct Gold from user with row-level locking
    from app.services.currency_service import CurrencyService
    success, message, _ = CurrencyService.deduct_gold(
        current_user.id, total_gold_cost, 'ZEN market purchase'
    )
    if not success:
        flash(f"Could not complete purchase: {message}", "warning")
        return redirect(url_for('main.zen_market'))

    # Transfer real ZEN tokens from treasury to user's wallet
    transfer_result = transfer_zen_from_treasury(current_user.base_wallet_address, zen_amount)

    if not transfer_result.get('success'):
        # Refund Gold if blockchain transfer failed
        CurrencyService.add_gold(current_user.id, total_gold_cost, 'ZEN market refund - transfer failed')
        error_msg = transfer_result.get('error', 'Unknown error')
        flash(f"Blockchain transfer failed: {error_msg}. Your Gold has been refunded.", "danger")
        return redirect(url_for('main.zen_market'))

    tx_hash = transfer_result.get('tx_hash', '')

    # Create transaction record
    transaction = ZenTransaction(
        market_id=market.id,
        user_id=current_user.id,
        transaction_type='buy',
        zen_amount=zen_amount,
        gold_amount=total_gold_cost,
        exchange_rate=buy_price,
        blockchain_status='completed',
        blockchain_tx_hash=tx_hash
    )
    db.session.add(transaction)

    # Update market price level
    market.update_price_level(zen_amount, is_buy=True)

    # Update OHLC price history with the buy price
    update_zen_rate_ohlc(market.id, buy_price)

    db.session.commit()

    explorer_url = os.getenv('BLOCK_EXPLORER', 'https://horizen.calderaexplorer.xyz')
    flash(f"Successfully purchased {zen_amount} ZEN for {total_gold_cost:.2f} Gold! ZEN tokens have been sent to your wallet. <a href='{explorer_url}/tx/{tx_hash}' target='_blank'>View transaction</a>", "success")
    return redirect(url_for('main.zen_market'))


@bp.route('/zen-market/sell-zen', methods=['POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_ZEN_TRADE", "20 per minute"))
def zen_market_sell_zen():
    """
    Sell ZEN for Gold - Legacy form route.
    For real blockchain transfers, users should use the JavaScript-based sell
    which calls /api/zen-market/prepare-sell and /api/zen-market/confirm-sell
    to sign transactions with MetaMask.
    """
    flash("To sell ZEN, please use the 'Sell ZEN' button which will prompt you to sign the transaction with MetaMask.", "info")
    return redirect(url_for('main.zen_market'))
