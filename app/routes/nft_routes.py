"""
NFT Routes
API endpoints for NFT management
"""
import os
from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required, current_user

from app.services.nft_service import NFTService
from app.services.bonus_calculator import BonusCalculator
from app.models.nft import NFTInventory, PlayerNFTSlots, CompanyNFTSlots, NFTMarketplace

nft_bp = Blueprint('nft', __name__, url_prefix='/api/nft')


@nft_bp.route('/inventory/page', methods=['GET'])
@login_required
def inventory_page():
    """Render the NFT inventory UI page"""
    from app.blockchain.nft_config import NFT_METADATA_URIS
    import json

    # Pass blockchain configuration and metadata URIs to template
    return render_template(
        'nft/inventory.html',
        ZEN_TOKEN_ADDRESS=os.getenv('ZEN_TOKEN_ADDRESS'),
        TREASURY_ADDRESS=os.getenv('TREASURY_ADDRESS'),
        NFT_CONTRACT_ADDRESS=os.getenv('NFT_CONTRACT_ADDRESS'),
        HORIZEN_L3_CHAIN_ID='0x28751c',  # 2651420 in hex
        NFT_METADATA_URIS=json.dumps(NFT_METADATA_URIS)
    )


@nft_bp.route('/inventory', methods=['GET'])
@login_required
def get_inventory():
    """Get user's NFT inventory"""
    nft_type = request.args.get('type')  # Optional: 'player' or 'company'
    equipped_only = request.args.get('equipped', 'false').lower() == 'true'

    nfts = NFTService.get_user_nfts(
        user_id=current_user.id,
        nft_type=nft_type,
        equipped_only=equipped_only
    )

    # Get IDs of NFTs currently listed on marketplace
    listed_nft_ids = set(
        listing.nft_id for listing in NFTMarketplace.query.filter_by(is_active=True).all()
    )

    # Add marketplace listing status to each NFT
    nft_list = []
    for nft in nfts:
        nft_dict = nft.to_dict()
        nft_dict['is_listed'] = nft.id in listed_nft_ids
        nft_list.append(nft_dict)

    return jsonify({
        'success': True,
        'nfts': nft_list,
        'count': len(nfts)
    })


@nft_bp.route('/available/company', methods=['GET'])
@login_required
def get_available_company_nfts():
    """Get user's available company NFTs (not equipped or available to equip)"""
    from app.blockchain.nft_config import get_nft_name, get_nft_description, get_nft_bonus_value

    # Get all company NFTs owned by user
    nfts = NFTInventory.query.filter_by(
        user_id=current_user.id,
        nft_type='company'
    ).all()

    # Format NFT data with enriched information
    nft_list = []
    for nft in nfts:
        nft_dict = nft.to_dict()
        nft_dict['bonus_percentage'] = nft.bonus_value
        nft_list.append(nft_dict)

    return jsonify({
        'success': True,
        'nfts': nft_list,
        'count': len(nft_list)
    })


@nft_bp.route('/purchase', methods=['POST'])
@login_required
def purchase_nft():
    """Purchase an NFT with ZEN tokens (Q1 only) - BLOCKCHAIN INTEGRATED"""
    data = request.get_json()

    tier = data.get('tier', 1)  # Default to Q1
    nft_type = data.get('type')  # 'player' or 'company' - if empty, will be random
    category = data.get('category')  # Always random (ignored)
    tx_hash = data.get('tx_hash')  # Transaction hash from MetaMask payment

    # Validate only Q1 can be purchased
    if tier != 1:
        return jsonify({
            'success': False,
            'error': 'Only Q1 NFTs can be purchased. Higher tiers must be crafted via upgrading.'
        }), 400

    # If nft_type is empty or None, set to None so backend randomly selects
    if not nft_type:
        nft_type = None

    # Check wallet connection
    if not current_user.wallet_address:
        return jsonify({
            'success': False,
            'error': 'Please connect your wallet first',
            'action': 'connect_wallet'
        }), 400

    # Validate transaction hash provided
    if not tx_hash:
        return jsonify({
            'success': False,
            'error': 'Missing transaction hash. Please complete payment first.'
        }), 400

    # Purchase NFT using blockchain integration
    nft, error = NFTService.purchase_nft_blockchain(
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        tier=1,  # Force Q1
        nft_type=nft_type,
        category=None,  # Force random category
        tx_hash=tx_hash  # Verify payment transaction
    )

    if error:
        return jsonify({
            'success': False,
            'error': error
        }), 400

    return jsonify({
        'success': True,
        'nft': nft.to_dict(),
        'message': f'Successfully purchased {nft.nft_type} NFT!',
        'token_id': nft.token_id
    })


@nft_bp.route('/free-mints', methods=['GET'])
@login_required
def get_free_mints():
    """Get user's available free NFT mints"""
    return jsonify({
        'success': True,
        'free_mints': current_user.free_nft_mints
    })


@nft_bp.route('/claim-free', methods=['POST'])
@login_required
def claim_free_nft():
    """Claim a free NFT using available free mints - SERVER-SIDE ADMIN MINT (no gas cost for user)"""
    from app import db
    from app.blockchain.nft_contract import admin_mint_nft
    from app.blockchain.nft_config import (
        PLAYER_CATEGORIES, COMPANY_CATEGORIES, get_nft_bonus_value,
        get_nft_name, get_nft_description, get_nft_metadata_uri
    )
    from app.models.nft import NFTInventory
    import random
    import os

    # Check if user has free mints available
    if current_user.free_nft_mints <= 0:
        return jsonify({
            'success': False,
            'error': 'You have no free NFT mints available. Complete tasks to earn free mints!'
        }), 400

    # Check wallet connection
    if not current_user.wallet_address:
        return jsonify({
            'success': False,
            'error': 'Please connect your wallet first',
            'action': 'connect_wallet'
        }), 400

    # Random type and category
    nft_type = random.choice(['player', 'company'])
    if nft_type == 'player':
        category = random.choice(PLAYER_CATEGORIES)
    else:
        category = random.choice(COMPANY_CATEGORIES)

    tier = 1  # Free mints are always Q1
    bonus_value = get_nft_bonus_value(nft_type, category, tier)
    metadata_uri = get_nft_metadata_uri(nft_type, category, tier)

    try:
        # Mint NFT on blockchain via admin mint (server-side, no cost to user)
        token_id, tx_hash = admin_mint_nft(
            to_address=current_user.wallet_address,
            nft_type=nft_type,
            category=category,
            tier=tier,
            bonus_value=bonus_value,
            metadata_uri=metadata_uri
        )

        # Create NFT in database
        nft = NFTInventory(
            user_id=current_user.id,
            nft_type=nft_type,
            category=category,
            tier=tier,
            bonus_value=bonus_value,
            token_id=token_id,
            contract_address=os.getenv('NFT_CONTRACT_ADDRESS'),
            acquired_via='free_mint',
            metadata_uri=metadata_uri
        )
        db.session.add(nft)

        # Decrement free mints counter
        current_user.free_nft_mints -= 1

        db.session.commit()

        return jsonify({
            'success': True,
            'nft': nft.to_dict(),
            'message': f'Successfully claimed free {nft_type} NFT!',
            'token_id': token_id,
            'remaining_free_mints': current_user.free_nft_mints
        })

    except Exception as e:
        import logging
        logging.error(f"Error claiming free NFT: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to mint free NFT: {str(e)}'
        }), 500


@nft_bp.route('/upgrade', methods=['POST'])
@login_required
def upgrade_nft():
    """Upgrade 3 NFTs to create 1 higher tier NFT - BLOCKCHAIN INTEGRATED"""
    data = request.get_json()

    nft_ids = data.get('nft_ids')  # List of 3 NFT IDs
    tx_hash = data.get('tx_hash')  # Transaction hash from MetaMask upgrade

    if not nft_ids or len(nft_ids) != 3:
        return jsonify({
            'success': False,
            'error': 'Must provide exactly 3 NFT IDs'
        }), 400

    # Check wallet connection
    if not current_user.wallet_address:
        return jsonify({
            'success': False,
            'error': 'Please connect your wallet first',
            'action': 'connect_wallet'
        }), 400

    # Validate transaction hash provided
    if not tx_hash:
        return jsonify({
            'success': False,
            'error': 'Missing transaction hash. Please complete upgrade on blockchain first.'
        }), 400

    # Upgrade NFT using blockchain integration
    new_nft, error = NFTService.upgrade_nft_blockchain(
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        nft_ids=nft_ids,
        tx_hash=tx_hash
    )

    if error:
        return jsonify({
            'success': False,
            'error': error
        }), 400

    return jsonify({
        'success': True,
        'nft': new_nft.to_dict(),
        'message': f'Successfully upgraded to Q{new_nft.tier} NFT!',
        'token_id': new_nft.token_id
    })


@nft_bp.route('/equip/profile', methods=['POST'])
@login_required
def equip_to_profile():
    """Equip NFT to player profile"""
    data = request.get_json()

    nft_id = data.get('nft_id')
    slot = data.get('slot')  # 1-3

    if not nft_id or not slot:
        return jsonify({
            'success': False,
            'error': 'Missing required fields: nft_id and slot'
        }), 400

    success, error = NFTService.equip_nft_to_profile(
        user_id=current_user.id,
        nft_id=nft_id,
        slot=slot
    )

    if not success:
        return jsonify({
            'success': False,
            'error': error
        }), 400

    return jsonify({
        'success': True,
        'message': f'NFT equipped to slot {slot}!'
    })


@nft_bp.route('/unequip/profile', methods=['POST'])
@login_required
def unequip_from_profile():
    """Unequip NFT from player profile"""
    data = request.get_json()

    slot = data.get('slot')  # 1-3

    if not slot:
        return jsonify({
            'success': False,
            'error': 'Missing required field: slot'
        }), 400

    success, error = NFTService.unequip_nft_from_profile(
        user_id=current_user.id,
        slot=slot
    )

    if not success:
        return jsonify({
            'success': False,
            'error': error
        }), 400

    return jsonify({
        'success': True,
        'message': f'NFT unequipped from slot {slot}!'
    })


@nft_bp.route('/equip/company', methods=['POST'])
@login_required
def equip_to_company():
    """Equip NFT to company"""
    data = request.get_json()

    company_id = data.get('company_id')
    nft_id = data.get('nft_id')
    slot = data.get('slot')  # 1-3

    if not company_id or not nft_id or not slot:
        return jsonify({
            'success': False,
            'error': 'Missing required fields: company_id, nft_id, and slot'
        }), 400

    success, error = NFTService.equip_nft_to_company(
        user_id=current_user.id,
        company_id=company_id,
        nft_id=nft_id,
        slot=slot
    )

    if not success:
        return jsonify({
            'success': False,
            'error': error
        }), 400

    return jsonify({
        'success': True,
        'message': f'NFT equipped to company slot {slot}!'
    })


@nft_bp.route('/unequip/company', methods=['POST'])
@login_required
def unequip_from_company():
    """Unequip NFT from company"""
    data = request.get_json()

    company_id = data.get('company_id')
    slot = data.get('slot')  # 1-3

    if not company_id or not slot:
        return jsonify({
            'success': False,
            'error': 'Missing required fields: company_id and slot'
        }), 400

    success, error = NFTService.unequip_nft_from_company(
        user_id=current_user.id,
        company_id=company_id,
        slot=slot
    )

    if not success:
        return jsonify({
            'success': False,
            'error': error
        }), 400

    return jsonify({
        'success': True,
        'message': f'NFT unequipped from company slot {slot}!'
    })


@nft_bp.route('/slots/profile', methods=['GET'])
@login_required
def get_profile_slots():
    """Get player's equipped NFT slots"""
    slots = PlayerNFTSlots.query.get(current_user.id)

    if not slots:
        return jsonify({
            'success': True,
            'slots': {
                'slot_1': None,
                'slot_2': None,
                'slot_3': None
            }
        })

    return jsonify({
        'success': True,
        'slots': slots.to_dict()
    })


@nft_bp.route('/slots/company/<int:company_id>', methods=['GET'])
@login_required
def get_company_slots(company_id):
    """Get company's equipped NFT slots"""
    from app.models.company import Company

    # Verify ownership
    company = Company.query.get(company_id)
    if not company or company.owner_id != current_user.id:
        return jsonify({
            'success': False,
            'error': 'Company not found or not owned by user'
        }), 404

    slots = CompanyNFTSlots.query.get(company_id)

    if not slots:
        return jsonify({
            'success': True,
            'slots': {
                'slot_1': None,
                'slot_2': None,
                'slot_3': None
            }
        })

    return jsonify({
        'success': True,
        'slots': slots.to_dict()
    })


@nft_bp.route('/bonuses/profile', methods=['GET'])
@login_required
def get_profile_bonuses():
    """Get player's total bonuses from equipped NFTs"""
    bonuses = BonusCalculator.get_player_bonus_summary(current_user.id)

    return jsonify({
        'success': True,
        'bonuses': bonuses
    })


@nft_bp.route('/bonuses/company/<int:company_id>', methods=['GET'])
@login_required
def get_company_bonuses(company_id):
    """Get company's total bonuses from equipped NFTs"""
    from app.models.company import Company

    # Verify ownership
    company = Company.query.get(company_id)
    if not company or company.owner_id != current_user.id:
        return jsonify({
            'success': False,
            'error': 'Company not found or not owned by user'
        }), 404

    bonuses = BonusCalculator.get_company_bonus_summary(company_id)

    return jsonify({
        'success': True,
        'bonuses': bonuses
    })


@nft_bp.route('/transfer', methods=['POST'])
@login_required
def transfer_nft():
    """Transfer NFT to another user"""
    data = request.get_json()

    nft_id = data.get('nft_id')
    to_user_id = data.get('to_user_id')
    price_zen = data.get('price_zen')
    price_gold = data.get('price_gold')
    trade_type = data.get('trade_type', 'transfer')  # 'sale', 'gift', 'transfer'

    if not nft_id or not to_user_id:
        return jsonify({
            'success': False,
            'error': 'Missing required fields: nft_id and to_user_id'
        }), 400

    success, error = NFTService.transfer_nft(
        from_user_id=current_user.id,
        to_user_id=to_user_id,
        nft_id=nft_id,
        price_zen=price_zen,
        price_gold=price_gold,
        trade_type=trade_type
    )

    if not success:
        return jsonify({
            'success': False,
            'error': error
        }), 400

    return jsonify({
        'success': True,
        'message': 'NFT transferred successfully!'
    })


@nft_bp.route('/detail/<int:nft_id>', methods=['GET'])
@login_required
def get_nft_detail(nft_id):
    """Get detailed information about a specific NFT"""
    nft = NFTInventory.query.get(nft_id)

    if not nft:
        return jsonify({
            'success': False,
            'error': 'NFT not found'
        }), 404

    # Allow viewing if owner or if listed on marketplace
    if nft.user_id != current_user.id:
        # TODO: Check if listed on marketplace
        return jsonify({
            'success': False,
            'error': 'You do not own this NFT'
        }), 403

    return jsonify({
        'success': True,
        'nft': nft.to_dict()
    })


@nft_bp.route('/stats', methods=['GET'])
@login_required
def get_nft_stats():
    """Get user's NFT statistics"""
    nfts = NFTService.get_user_nfts(current_user.id)

    stats = {
        'total_nfts': len(nfts),
        'by_type': {
            'player': len([n for n in nfts if n.nft_type == 'player']),
            'company': len([n for n in nfts if n.nft_type == 'company'])
        },
        'by_tier': {
            f'Q{i}': len([n for n in nfts if n.tier == i])
            for i in range(1, 6)
        },
        'equipped': len([n for n in nfts if n.is_equipped])
    }

    return jsonify({
        'success': True,
        'stats': stats
    })


@nft_bp.route('/image/<ipfs_cid>', methods=['GET'])
def get_nft_image(ipfs_cid):
    """Proxy endpoint to serve NFT images from IPFS through our domain"""
    import requests
    from flask import Response

    try:
        # Fetch image from Pinata gateway
        image_url = f'https://gateway.pinata.cloud/ipfs/{ipfs_cid}'
        response = requests.get(image_url, timeout=10)

        if response.status_code == 200:
            # Return image with proper headers
            return Response(
                response.content,
                mimetype=response.headers.get('Content-Type', 'image/png'),
                headers={
                    'Cache-Control': 'public, max-age=31536000',  # Cache for 1 year
                    'Access-Control-Allow-Origin': '*'
                }
            )
        else:
            return jsonify({'error': 'Image not found'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500
