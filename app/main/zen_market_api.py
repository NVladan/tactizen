# app/main/zen_market_api.py

"""
API endpoints for ZEN market blockchain transactions
These handle the actual on-chain token transfers
"""

import os
from flask import jsonify, request, current_app
from flask_login import current_user, login_required
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from sqlalchemy.orm import joinedload

from app.extensions import db, limiter
from app.models import ZenMarket, ZenTransaction
from app.main import bp
from app.blockchain import (
    transfer_zen_to_treasury,
    transfer_zen_from_treasury,
    verify_zen_transfer,
    get_zen_balance_raw
)


@bp.route('/api/zen-market/prepare-sell', methods=['POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_ZEN_TRADE", "20 per minute"))
def api_zen_market_prepare_sell():
    """
    Prepare a sell transaction (user selling ZEN for Gold).
    Returns transaction data for user to sign with MetaMask.
    """
    try:
        data = request.get_json()
        zen_amount = Decimal(str(data.get('zen_amount', '0')))
    except (TypeError, ValueError, InvalidOperation):
        return jsonify({'success': False, 'error': 'Invalid ZEN amount'}), 400

    if zen_amount <= 0:
        return jsonify({'success': False, 'error': 'ZEN amount must be greater than zero'}), 400

    # Check if amount is a whole number
    if zen_amount % 1 != 0:
        return jsonify({'success': False, 'error': 'ZEN amount must be a whole number (no decimals)'}), 400

    # Check if user has wallet (check base_wallet_address OR wallet_address)
    user_wallet = current_user.base_wallet_address or current_user.wallet_address
    if not user_wallet:
        return jsonify({'success': False, 'error': 'No wallet connected'}), 400

    # Get market
    market = db.session.scalar(db.select(ZenMarket).where(ZenMarket.id == 1))
    if not market:
        return jsonify({'success': False, 'error': 'Market not found'}), 404

    # Verify user has enough ZEN
    zen_balance = Decimal(str(get_zen_balance_raw(user_wallet)))
    if zen_balance < zen_amount:
        return jsonify({
            'success': False,
            'error': f'Insufficient ZEN. You have {zen_balance:.2f} ZEN'
        }), 400

    # Calculate Gold amount
    sell_price = market.sell_zen_price
    gold_amount = (zen_amount * sell_price).quantize(Decimal('0.01'), rounding=ROUND_DOWN)

    # Prepare blockchain transaction
    result = transfer_zen_to_treasury(user_wallet, zen_amount)

    if not result['success']:
        return jsonify({'success': False, 'error': result.get('message', 'Failed to prepare transaction')}), 500

    # Store pending transaction in session for verification later
    from flask import session
    session['pending_zen_sell'] = {
        'zen_amount': str(zen_amount),
        'gold_amount': str(gold_amount),
        'sell_price': str(sell_price),
        'user_address': user_wallet
    }

    return jsonify({
        'success': True,
        'transaction_data': result['transaction_data'],
        'zen_amount': float(zen_amount),
        'gold_amount': float(gold_amount),
        'sell_price': float(sell_price)
    })


@bp.route('/api/zen-market/confirm-sell', methods=['POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_ZEN_TRADE", "20 per minute"))
def api_zen_market_confirm_sell():
    """
    Confirm sell transaction after user has signed it.
    Verifies the blockchain transaction and credits Gold.
    """
    from flask import session

    # Get pending transaction from session
    pending = session.get('pending_zen_sell')
    if not pending:
        current_app.logger.error(f"No pending transaction in session for user {current_user.id}")
        return jsonify({'success': False, 'error': 'No pending transaction found'}), 400

    try:
        data = request.get_json()
        tx_hash = data.get('tx_hash')

        current_app.logger.info(f"Confirming sell for user {current_user.id}, tx_hash: {tx_hash}")

        if not tx_hash:
            return jsonify({'success': False, 'error': 'Transaction hash required'}), 400

        zen_amount = Decimal(pending['zen_amount'])
        gold_amount = Decimal(pending['gold_amount'])
        sell_price = Decimal(pending['sell_price'])

        # Verify the blockchain transaction
        import os
        treasury_address = os.getenv('TREASURY_WALLET_ADDRESS')

        # Get user's wallet address (base_wallet_address OR wallet_address)
        user_wallet = current_user.base_wallet_address or current_user.wallet_address

        verification = verify_zen_transfer(
            tx_hash,
            user_wallet,
            treasury_address,
            zen_amount
        )

        if not verification['valid']:
            return jsonify({
                'success': False,
                'error': f'Transaction verification failed: {verification["message"]}'
            }), 400

        # Transaction verified! Credit Gold to user with row-level locking
        market = db.session.scalar(db.select(ZenMarket).where(ZenMarket.id == 1))

        from app.services.currency_service import CurrencyService
        success, message, _ = CurrencyService.add_gold(
            current_user.id, gold_amount, 'ZEN blockchain sale'
        )
        if not success:
            return jsonify({
                'success': False,
                'error': f'Could not credit gold: {message}'
            }), 400

        # Create transaction record
        transaction = ZenTransaction(
            market_id=market.id,
            user_id=current_user.id,
            transaction_type='sell',
            zen_amount=zen_amount,
            gold_amount=gold_amount,
            exchange_rate=sell_price,
            blockchain_tx_hash=tx_hash,
            blockchain_status='confirmed'
        )
        db.session.add(transaction)

        # Update market price level
        market.update_price_level(zen_amount, is_buy=False)

        db.session.commit()

        # Clear pending transaction
        session.pop('pending_zen_sell', None)

        return jsonify({
            'success': True,
            'message': f'Successfully sold {zen_amount} ZEN for {gold_amount:.2f} Gold!',
            'zen_amount': float(zen_amount),
            'gold_amount': float(gold_amount),
            'tx_hash': tx_hash,
            'new_gold_balance': float(current_user.gold)
        })

    except Exception as e:
        current_app.logger.error(f"Error confirming sell transaction: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/zen-market/buy-zen', methods=['POST'])
@login_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_ZEN_TRADE", "20 per minute"))
def api_zen_market_buy_zen():
    """
    Buy ZEN with Gold - sends actual ZEN tokens from treasury to user's wallet.
    """
    try:
        data = request.get_json()
        zen_amount = Decimal(str(data.get('zen_amount', '0')))
    except (TypeError, ValueError, InvalidOperation):
        return jsonify({'success': False, 'error': 'Invalid ZEN amount'}), 400

    if zen_amount <= 0:
        return jsonify({'success': False, 'error': 'ZEN amount must be greater than zero'}), 400

    # Check if amount is a whole number
    if zen_amount % 1 != 0:
        return jsonify({'success': False, 'error': 'ZEN amount must be a whole number (no decimals)'}), 400

    # Check if user has wallet (check base_wallet_address OR wallet_address)
    user_wallet = current_user.base_wallet_address or current_user.wallet_address
    if not user_wallet:
        return jsonify({'success': False, 'error': 'No wallet connected'}), 400

    # Get market
    market = db.session.scalar(db.select(ZenMarket).where(ZenMarket.id == 1))
    if not market:
        return jsonify({'success': False, 'error': 'Market not found'}), 404

    # Calculate Gold cost
    buy_price = market.buy_zen_price
    gold_cost = (zen_amount * buy_price).quantize(Decimal('0.01'), rounding=ROUND_DOWN)

    # Transfer ZEN from treasury to user (on blockchain) FIRST
    # We do blockchain transfer first because we can't reverse it if gold deduction fails
    transfer_result = transfer_zen_from_treasury(user_wallet, zen_amount)

    if not transfer_result['success']:
        return jsonify({
            'success': False,
            'error': f'Blockchain transfer failed: {transfer_result.get("message", "Unknown error")}'
        }), 500

    # Blockchain transfer successful! Deduct Gold from user with row-level locking
    from app.services.currency_service import CurrencyService
    success, message, _ = CurrencyService.deduct_gold(
        current_user.id, gold_cost, 'ZEN blockchain purchase'
    )
    if not success:
        # Note: ZEN was already transferred on blockchain, log this critical error
        current_app.logger.critical(
            f"ZEN transferred to user {current_user.id} but gold deduction failed: {message}. "
            f"TX: {transfer_result['tx_hash']}, Amount: {zen_amount} ZEN, Gold: {gold_cost}"
        )
        return jsonify({
            'success': False,
            'error': f'Gold deduction failed after blockchain transfer. Please contact support with TX: {transfer_result["tx_hash"]}'
        }), 500

    # Create transaction record
    transaction = ZenTransaction(
        market_id=market.id,
        user_id=current_user.id,
        transaction_type='buy',
        zen_amount=zen_amount,
        gold_amount=gold_cost,
        exchange_rate=buy_price,
        blockchain_tx_hash=transfer_result['tx_hash'],
        blockchain_status='confirmed'
    )
    db.session.add(transaction)

    # Update market price level
    market.update_price_level(zen_amount, is_buy=True)

    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Successfully bought {zen_amount} ZEN for {gold_cost:.2f} Gold!',
        'zen_amount': float(zen_amount),
        'gold_amount': float(gold_cost),
        'tx_hash': transfer_result['tx_hash'],
        'explorer_url': f"{os.getenv('BLOCK_EXPLORER', 'https://horizen.calderaexplorer.xyz')}/tx/{transfer_result['tx_hash']}",
        'new_gold_balance': float(current_user.gold)
    })
