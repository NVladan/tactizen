"""
Wallet Management Routes
Handle wallet connection, verification, and blockchain interactions
"""
from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required, current_user
from web3 import Web3
from eth_account.messages import encode_defunct
from decimal import Decimal
import os

from app import db
from app.models.user import User

wallet_bp = Blueprint('wallet', __name__, url_prefix='/api/wallet')

# Web3 setup
BLOCKCHAIN_RPC_URL = os.getenv('BLOCKCHAIN_RPC_URL', 'https://horizen-testnet.rpc.caldera.xyz/http')
ZEN_TOKEN_ADDRESS = os.getenv('ZEN_TOKEN_ADDRESS', None)

try:
    w3 = Web3(Web3.HTTPProvider(BLOCKCHAIN_RPC_URL))
except Exception as e:
    print(f"Warning: Web3 initialization failed: {e}")
    w3 = None

# ERC20 ABI for balanceOf
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }
]


@wallet_bp.route('/connect-page', methods=['GET'])
@login_required
def connect_page():
    """Render wallet connection page"""
    return render_template('wallet/connect.html')


@wallet_bp.route('/zen-balance', methods=['GET'])
@login_required
def get_zen_balance():
    """Get ZEN token balance for a wallet address"""
    address = request.args.get('address')

    if not address:
        return jsonify({'success': False, 'error': 'Missing address'}), 400

    # Reload env vars in case they weren't loaded at module init
    rpc_url = os.getenv('BLOCKCHAIN_RPC_URL', 'https://horizen-testnet.rpc.caldera.xyz/http')
    zen_token_addr = os.getenv('ZEN_TOKEN_ADDRESS')

    if not zen_token_addr:
        # Return mock balance for development
        return jsonify({
            'success': True,
            'balance': '100.0',
            'mock': True,
            'message': 'ZEN token address not configured - showing mock balance'
        })

    try:
        # Create Web3 connection
        web3 = Web3(Web3.HTTPProvider(rpc_url))

        if not web3.is_connected():
            return jsonify({
                'success': False,
                'error': 'Cannot connect to blockchain'
            }), 500

        # Validate address
        if not Web3.is_address(address):
            return jsonify({'success': False, 'error': 'Invalid address'}), 400

        # Get ZEN token contract
        zen_contract = web3.eth.contract(
            address=Web3.to_checksum_address(zen_token_addr),
            abi=ERC20_ABI
        )

        # Get balance
        balance_wei = zen_contract.functions.balanceOf(
            Web3.to_checksum_address(address)
        ).call()

        # Convert from wei (18 decimals) to tokens
        balance = Decimal(balance_wei) / Decimal(10**18)

        return jsonify({
            'success': True,
            'balance': str(balance),
            'balance_wei': str(balance_wei)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error fetching balance: {str(e)}'
        }), 500


@wallet_bp.route('/check-verified', methods=['GET'])
@login_required
def check_verified():
    """Check if wallet is verified for current user"""
    address = request.args.get('address')

    if not address:
        return jsonify({'success': False, 'error': 'Missing address'}), 400

    # Check if this wallet is linked to current user
    # User is considered verified if wallet_address matches (login wallet) or base_wallet_address matches
    is_verified = False
    if current_user.wallet_address and current_user.wallet_address.lower() == address.lower():
        is_verified = True
    elif current_user.base_wallet_address and current_user.base_wallet_address.lower() == address.lower():
        is_verified = True

    return jsonify({
        'success': True,
        'verified': is_verified
    })


@wallet_bp.route('/get-verification-message', methods=['POST'])
@login_required
def get_verification_message():
    """Get message to sign for wallet verification"""
    data = request.get_json()
    address = data.get('address')

    if not address:
        return jsonify({'success': False, 'error': 'Missing address'}), 400

    # Generate unique message
    message = f"Sign this message to verify wallet ownership for Tactizen account #{current_user.id}\n\nWallet: {address}\nTimestamp: {int(__import__('time').time())}"

    return jsonify({
        'success': True,
        'message': message
    })


@wallet_bp.route('/verify-signature', methods=['POST'])
@login_required
def verify_signature():
    """Verify signed message and link wallet to user account"""
    data = request.get_json()

    address = data.get('address')
    signature = data.get('signature')
    message = data.get('message')

    if not all([address, signature, message]):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    if not w3:
        # Development mode - skip actual verification
        current_user.wallet_address = address
        current_user.wallet_verified = True
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Wallet linked (development mode - signature verification skipped)'
        })

    try:
        # Recover address from signature
        message_hash = encode_defunct(text=message)
        recovered_address = w3.eth.account.recover_message(message_hash, signature=signature)

        # Verify recovered address matches provided address
        if recovered_address.lower() != address.lower():
            return jsonify({
                'success': False,
                'error': 'Signature verification failed'
            }), 400

        # Check if wallet is already linked to another account
        existing_user = User.query.filter(
            User.wallet_address.ilike(address),
            User.id != current_user.id
        ).first()

        if existing_user:
            return jsonify({
                'success': False,
                'error': 'This wallet is already linked to another account'
            }), 400

        # Link wallet to current user
        current_user.wallet_address = address
        current_user.wallet_verified = True
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Wallet verified and linked successfully'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Verification error: {str(e)}'
        }), 500


@wallet_bp.route('/unlink', methods=['POST'])
@login_required
def unlink_wallet():
    """Unlink wallet from user account"""
    current_user.wallet_address = None
    current_user.wallet_verified = False
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Wallet unlinked successfully'
    })


@wallet_bp.route('/info', methods=['GET'])
@login_required
def wallet_info():
    """Get current user's wallet info"""
    return jsonify({
        'success': True,
        'wallet_address': current_user.wallet_address,
        'wallet_verified': current_user.wallet_verified
    })
