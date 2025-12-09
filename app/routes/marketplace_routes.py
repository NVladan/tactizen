"""
NFT Marketplace Routes
Handles P2P NFT trading marketplace
"""
from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user
from app.services.nft_service import NFTService
from app.blockchain.marketplace_contract import get_marketplace_fee, calculate_marketplace_fee
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

marketplace_bp = Blueprint('marketplace', __name__, url_prefix='/nft-marketplace')


@marketplace_bp.route('/')
@login_required
def marketplace_page():
    """NFT Marketplace main page"""
    return render_template('marketplace/marketplace.html')


@marketplace_bp.route('/api/listings', methods=['GET'])
@login_required
def get_listings():
    """
    Get marketplace listings with filters

    Query params:
        - nft_type: 'player' or 'company'
        - category: NFT category
        - min_tier: Minimum tier (1-5)
        - max_tier: Maximum tier (1-5)
        - min_price: Minimum price in ZEN
        - max_price: Maximum price in ZEN
        - sort_by: 'listed_at', 'price_zen', 'tier'
        - sort_order: 'asc' or 'desc'
    """
    try:
        # Get filters from query params
        nft_type = request.args.get('nft_type')
        category = request.args.get('category')
        min_tier = request.args.get('min_tier', type=int)
        max_tier = request.args.get('max_tier', type=int)
        min_price = request.args.get('min_price', type=float)
        max_price = request.args.get('max_price', type=float)
        sort_by = request.args.get('sort_by', 'listed_at')
        sort_order = request.args.get('sort_order', 'desc')

        # Get listings
        listings = NFTService.get_marketplace_listings(
            nft_type=nft_type,
            category=category,
            min_tier=min_tier,
            max_tier=max_tier,
            min_price=min_price,
            max_price=max_price,
            sort_by=sort_by,
            sort_order=sort_order
        )

        # Convert to dict
        listings_data = [listing.to_dict() for listing in listings]

        return jsonify({
            'success': True,
            'listings': listings_data,
            'count': len(listings_data),
            'current_user_id': current_user.id
        })

    except Exception as e:
        logger.error(f"Error getting marketplace listings: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to load marketplace listings'
        }), 500


@marketplace_bp.route('/api/my-listings', methods=['GET'])
@login_required
def get_my_listings():
    """Get current user's marketplace listings"""
    try:
        active_only = request.args.get('active_only', 'true').lower() == 'true'

        listings = NFTService.get_user_marketplace_listings(
            user_id=current_user.id,
            active_only=active_only
        )

        listings_data = [listing.to_dict() for listing in listings]

        return jsonify({
            'success': True,
            'listings': listings_data,
            'count': len(listings_data)
        })

    except Exception as e:
        logger.error(f"Error getting user's listings: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to load your listings'
        }), 500


@marketplace_bp.route('/api/list', methods=['POST'])
@login_required
def list_nft():
    """
    List an NFT on the marketplace

    Body:
        - nft_id: Database NFT ID
        - price_zen: Price in ZEN tokens
        - tx_hash: Transaction hash from blockchain
    """
    try:
        data = request.get_json()

        nft_id = data.get('nft_id')
        price_zen = data.get('price_zen')
        tx_hash = data.get('tx_hash')

        # Validate inputs
        if not nft_id or not price_zen or not tx_hash:
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400

        # Validate price is positive and within reasonable bounds
        try:
            price_zen_decimal = Decimal(str(price_zen))
            if price_zen_decimal <= 0:
                return jsonify({
                    'success': False,
                    'error': 'Price must be greater than 0'
                }), 400
            if price_zen_decimal > Decimal('999999999.99'):
                return jsonify({
                    'success': False,
                    'error': 'Price exceeds maximum allowed value'
                }), 400
        except Exception:
            return jsonify({
                'success': False,
                'error': 'Invalid price format'
            }), 400

        # Validate wallet
        if not current_user.wallet_address:
            return jsonify({
                'success': False,
                'error': 'Please connect your wallet first'
            }), 400

        # List NFT
        listing, error = NFTService.list_nft_on_marketplace(
            user_id=current_user.id,
            wallet_address=current_user.wallet_address,
            nft_id=nft_id,
            price_zen=price_zen,
            tx_hash=tx_hash
        )

        if error:
            return jsonify({
                'success': False,
                'error': error
            }), 400

        return jsonify({
            'success': True,
            'message': 'NFT listed successfully',
            'listing': listing.to_dict()
        })

    except Exception as e:
        logger.error(f"Error listing NFT: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to list NFT'
        }), 500


@marketplace_bp.route('/api/buy', methods=['POST'])
@login_required
def buy_nft():
    """
    Purchase an NFT from the marketplace

    Body:
        - listing_id: Database listing ID
        - tx_hash: Transaction hash from blockchain
    """
    try:
        data = request.get_json()

        listing_id = data.get('listing_id')
        tx_hash = data.get('tx_hash')

        # Validate inputs
        if not listing_id or not tx_hash:
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400

        # Validate wallet
        if not current_user.wallet_address:
            return jsonify({
                'success': False,
                'error': 'Please connect your wallet first'
            }), 400

        # Purchase NFT
        success, error = NFTService.buy_nft_from_marketplace(
            buyer_id=current_user.id,
            buyer_wallet=current_user.wallet_address,
            listing_id=listing_id,
            tx_hash=tx_hash
        )

        if not success:
            return jsonify({
                'success': False,
                'error': error
            }), 400

        return jsonify({
            'success': True,
            'message': 'NFT purchased successfully!'
        })

    except Exception as e:
        logger.error(f"Error purchasing NFT: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to purchase NFT'
        }), 500


@marketplace_bp.route('/api/cancel', methods=['POST'])
@login_required
def cancel_listing():
    """
    Cancel a marketplace listing

    Body:
        - listing_id: Database listing ID
        - tx_hash: Transaction hash from blockchain
    """
    try:
        data = request.get_json()

        listing_id = data.get('listing_id')
        tx_hash = data.get('tx_hash')

        # Validate inputs
        if not listing_id or not tx_hash:
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400

        # Validate wallet
        if not current_user.wallet_address:
            return jsonify({
                'success': False,
                'error': 'Please connect your wallet first'
            }), 400

        # Cancel listing
        success, error = NFTService.cancel_marketplace_listing(
            user_id=current_user.id,
            wallet_address=current_user.wallet_address,
            listing_id=listing_id,
            tx_hash=tx_hash
        )

        if not success:
            return jsonify({
                'success': False,
                'error': error
            }), 400

        return jsonify({
            'success': True,
            'message': 'Listing cancelled successfully'
        })

    except Exception as e:
        logger.error(f"Error cancelling listing: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to cancel listing'
        }), 500


@marketplace_bp.route('/api/marketplace-info', methods=['GET'])
@login_required
def marketplace_info():
    """Get marketplace configuration info"""
    try:
        fee_bps = get_marketplace_fee()
        fee_percent = fee_bps / 100  # Convert basis points to percent

        return jsonify({
            'success': True,
            'marketplace_fee_percent': fee_percent,
            'marketplace_fee_bps': fee_bps
        })

    except Exception as e:
        logger.error(f"Error getting marketplace info: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to load marketplace info'
        }), 500


@marketplace_bp.route('/api/calculate-fee', methods=['POST'])
@login_required
def calculate_fee():
    """
    Calculate marketplace fee for a given price

    Body:
        - price_zen: Price in ZEN tokens
    """
    try:
        data = request.get_json()
        price_zen = data.get('price_zen')

        if not price_zen:
            return jsonify({
                'success': False,
                'error': 'Price is required'
            }), 400

        # Validate price is positive and within reasonable bounds
        try:
            price_zen_decimal = Decimal(str(price_zen))
            if price_zen_decimal <= 0:
                return jsonify({
                    'success': False,
                    'error': 'Price must be greater than 0'
                }), 400
            if price_zen_decimal > Decimal('999999999.99'):
                return jsonify({
                    'success': False,
                    'error': 'Price exceeds maximum allowed value'
                }), 400
        except Exception:
            return jsonify({
                'success': False,
                'error': 'Invalid price format'
            }), 400

        fee, seller_amount = calculate_marketplace_fee(price_zen_decimal)

        return jsonify({
            'success': True,
            'price_zen': float(price_zen),
            'fee_zen': float(fee),
            'seller_receives_zen': float(seller_amount)
        })

    except Exception as e:
        logger.error(f"Error calculating fee: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to calculate fee'
        }), 500


@marketplace_bp.route('/api/listing/<int:listing_id>', methods=['GET'])
@login_required
def get_listing_details(listing_id):
    """Get detailed information about a specific listing"""
    try:
        from app.models.nft import NFTMarketplace

        listing = NFTMarketplace.query.get(listing_id)

        if not listing:
            return jsonify({
                'success': False,
                'error': 'Listing not found'
            }), 404

        return jsonify({
            'success': True,
            'listing': listing.to_dict()
        })

    except Exception as e:
        logger.error(f"Error getting listing details: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to load listing details'
        }), 500
