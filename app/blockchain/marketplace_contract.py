"""
NFT Marketplace Smart Contract Integration
Handles blockchain interactions for listing, buying, and canceling NFT marketplace listings
"""
import os
import logging
from decimal import Decimal
from typing import Optional, Tuple, Dict, List
from web3 import Web3
from web3.contract import Contract

logger = logging.getLogger(__name__)

# Load environment variables
BLOCKCHAIN_RPC_URL = os.getenv('BLOCKCHAIN_RPC_URL', 'https://horizen-testnet.rpc.caldera.xyz/http')
MARKETPLACE_CONTRACT_ADDRESS = os.getenv('MARKETPLACE_CONTRACT_ADDRESS', None)
TREASURY_PRIVATE_KEY = os.getenv('TREASURY_PRIVATE_KEY', None)
TREASURY_ADDRESS = os.getenv('TREASURY_ADDRESS', None)
ZEN_TOKEN_ADDRESS = os.getenv('ZEN_TOKEN_ADDRESS', None)
NFT_CONTRACT_ADDRESS = os.getenv('NFT_CONTRACT_ADDRESS', '0x6A20E1a6730683C1aE932d17557Df81AbB9442c6')

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(BLOCKCHAIN_RPC_URL))

# Marketplace Contract ABI
MARKETPLACE_ABI = [
    {
        "inputs": [
            {"name": "tokenId", "type": "uint256"},
            {"name": "price", "type": "uint256"}
        ],
        "name": "listNFT",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "buyNFT",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "cancelListing",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "getListing",
        "outputs": [
            {"name": "seller", "type": "address"},
            {"name": "price", "type": "uint256"},
            {"name": "active", "type": "bool"},
            {"name": "listedAt", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getActiveListings",
        "outputs": [{"name": "", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getActiveListingCount",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "marketplaceFee",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "tokenId", "type": "uint256"},
            {"indexed": True, "name": "seller", "type": "address"},
            {"indexed": False, "name": "price", "type": "uint256"},
            {"indexed": False, "name": "timestamp", "type": "uint256"}
        ],
        "name": "NFTListed",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "tokenId", "type": "uint256"},
            {"indexed": True, "name": "seller", "type": "address"},
            {"indexed": True, "name": "buyer", "type": "address"},
            {"indexed": False, "name": "price", "type": "uint256"},
            {"indexed": False, "name": "fee", "type": "uint256"},
            {"indexed": False, "name": "timestamp", "type": "uint256"}
        ],
        "name": "NFTSold",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "tokenId", "type": "uint256"},
            {"indexed": True, "name": "seller", "type": "address"},
            {"indexed": False, "name": "timestamp", "type": "uint256"}
        ],
        "name": "ListingCancelled",
        "type": "event"
    }
]

# ERC721 ABI (for NFT approval)
ERC721_ABI = [
    {
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "tokenId", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "operator", "type": "address"}
        ],
        "name": "isApprovedForAll",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "operator", "type": "address"},
            {"name": "approved", "type": "bool"}
        ],
        "name": "setApprovalForAll",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "ownerOf",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    }
]


def get_marketplace_contract() -> Optional[Contract]:
    """Get NFT Marketplace contract instance"""
    if not MARKETPLACE_CONTRACT_ADDRESS:
        return None

    return w3.eth.contract(
        address=Web3.to_checksum_address(MARKETPLACE_CONTRACT_ADDRESS),
        abi=MARKETPLACE_ABI
    )


def get_nft_contract() -> Optional[Contract]:
    """Get GameNFT contract instance"""
    if not NFT_CONTRACT_ADDRESS:
        return None

    return w3.eth.contract(
        address=Web3.to_checksum_address(NFT_CONTRACT_ADDRESS),
        abi=ERC721_ABI
    )


def get_marketplace_fee() -> int:
    """
    Get current marketplace fee in basis points

    Returns:
        Fee in basis points (e.g., 500 = 5%)
    """
    marketplace_contract = get_marketplace_contract()
    if not marketplace_contract:
        return 500  # Default 5%

    try:
        fee = marketplace_contract.functions.marketplaceFee().call()
        return fee
    except Exception as e:
        logger.error(f"Error getting marketplace fee: {e}")
        return 500


def calculate_marketplace_fee(price_zen: Decimal) -> Tuple[Decimal, Decimal]:
    """
    Calculate marketplace fee and seller amount

    Args:
        price_zen: Price in ZEN tokens

    Returns:
        (fee_amount, seller_amount) tuple
    """
    fee_bps = get_marketplace_fee()
    fee_amount = price_zen * Decimal(fee_bps) / Decimal(10000)
    seller_amount = price_zen - fee_amount

    return fee_amount, seller_amount


def verify_listing_transaction(
    tx_hash: str,
    expected_seller: str,
    expected_token_id: int,
    expected_price: Decimal
) -> bool:
    """
    Verify that a listing transaction succeeded

    Args:
        tx_hash: Transaction hash
        expected_seller: Expected seller address
        expected_token_id: Expected token ID
        expected_price: Expected price in ZEN

    Returns:
        True if listing successful
    """
    import time

    try:
        logger.info(f"[Listing Verification] Starting verification for tx: {tx_hash}")

        # Wait for transaction to be mined
        receipt = None
        for attempt in range(15):
            try:
                receipt = w3.eth.get_transaction_receipt(tx_hash)
                logger.info(f"[Listing Verification] Transaction found")
                break
            except Exception as e:
                if attempt < 14:
                    logger.info(f"[Listing Verification] Waiting... (attempt {attempt + 1}/15)")
                    time.sleep(2)
                else:
                    raise

        if not receipt or receipt['status'] != 1:
            logger.error(f"[Listing Verification] FAILED: Transaction failed")
            return False

        # Parse NFTListed event
        nft_listed_signature = w3.keccak(text="NFTListed(uint256,address,uint256,uint256)").hex()

        for log in receipt['logs']:
            if not log.get('topics') or len(log['topics']) < 3:
                continue
            if log['topics'][0].hex() == nft_listed_signature:
                token_id = int(log['topics'][1].hex(), 16)
                seller = '0x' + log['topics'][2].hex()[-40:]

                # Decode data (price and timestamp)
                data = log['data'].hex()[2:]  # Remove '0x'
                price_wei = int(data[:64], 16)  # First 64 hex chars = 32 bytes = price
                price_zen = Decimal(price_wei) / Decimal(10**18)

                logger.info(f"[Listing Verification] Found NFTListed: tokenId={token_id}, seller={seller}, price={price_zen}")
                logger.info(f"[Listing Verification] Comparing: tokenId {token_id} == {expected_token_id}, seller {seller.lower()} == {expected_seller.lower()}, price {price_zen} ~= {expected_price}")

                # Verify token ID and seller match (don't verify price as it's authoritative on blockchain)
                if (token_id == expected_token_id and
                    seller.lower() == expected_seller.lower()):
                    logger.info(f"[Listing Verification] SUCCESS (actual price on blockchain: {price_zen} ZEN)")
                    return True
                else:
                    logger.warning(f"[Listing Verification] Mismatch in event - TokenID: {token_id == expected_token_id}, Seller: {seller.lower() == expected_seller.lower()}")

        # If no matching event found, check the actual contract state as fallback
        logger.warning(f"[Listing Verification] No matching event in logs, checking contract state...")
        try:
            marketplace_contract = get_marketplace_contract()
            if marketplace_contract:
                listing = marketplace_contract.functions.getListing(expected_token_id).call()
                onchain_seller = listing[0]
                onchain_price_wei = listing[1]
                onchain_active = listing[2]
                onchain_price_zen = Decimal(onchain_price_wei) / Decimal(10**18)

                logger.info(f"[Listing Verification] Contract state: active={onchain_active}, price={onchain_price_zen}, seller={onchain_seller}")

                # Check if listing exists and matches
                price_tolerance = max(Decimal("0.001"), expected_price * Decimal("0.1"))
                if (onchain_active and
                    onchain_seller.lower() == expected_seller.lower() and
                    abs(onchain_price_zen - expected_price) <= price_tolerance):
                    logger.info(f"[Listing Verification] SUCCESS via contract state check")
                    return True
        except Exception as e:
            logger.error(f"[Listing Verification] Error checking contract state: {e}")

        logger.error(f"[Listing Verification] FAILED: No matching event or contract state")
        return False

    except Exception as e:
        logger.error(f"[Listing Verification] ERROR: {str(e)}")
        return False


def verify_purchase_transaction(
    tx_hash: str,
    expected_buyer: str,
    expected_token_id: int
) -> Optional[Dict]:
    """
    Verify that a purchase transaction succeeded

    Args:
        tx_hash: Transaction hash
        expected_buyer: Expected buyer address
        expected_token_id: Expected token ID

    Returns:
        Dict with purchase details if successful, None otherwise
    """
    import time

    try:
        logger.info(f"[Purchase Verification] Starting verification for tx: {tx_hash}")

        # Wait for transaction to be mined
        receipt = None
        for attempt in range(15):
            try:
                receipt = w3.eth.get_transaction_receipt(tx_hash)
                logger.info(f"[Purchase Verification] Transaction found")
                break
            except Exception as e:
                if attempt < 14:
                    logger.info(f"[Purchase Verification] Waiting... (attempt {attempt + 1}/15)")
                    time.sleep(2)
                else:
                    raise

        if not receipt or receipt['status'] != 1:
            logger.error(f"[Purchase Verification] FAILED: Transaction failed")
            return None

        # Parse NFTSold event
        nft_sold_signature = w3.keccak(text="NFTSold(uint256,address,address,uint256,uint256,uint256)").hex()

        for log in receipt['logs']:
            if not log.get('topics') or len(log['topics']) < 4:
                continue
            if log['topics'][0].hex() == nft_sold_signature:
                token_id = int(log['topics'][1].hex(), 16)
                seller = '0x' + log['topics'][2].hex()[-40:]
                buyer = '0x' + log['topics'][3].hex()[-40:]

                # Decode data (price and fee)
                data = log['data'].hex()[2:]  # Remove '0x'
                price_wei = int(data[:64], 16)
                fee_wei = int(data[64:128], 16)

                price_zen = Decimal(price_wei) / Decimal(10**18)
                fee_zen = Decimal(fee_wei) / Decimal(10**18)

                logger.info(f"[Purchase Verification] Found NFTSold: tokenId={token_id}, buyer={buyer}, price={price_zen}, fee={fee_zen}")

                # Verify details
                if (token_id == expected_token_id and
                    buyer.lower() == expected_buyer.lower()):
                    logger.info(f"[Purchase Verification] SUCCESS")
                    return {
                        'token_id': token_id,
                        'seller': seller,
                        'buyer': buyer,
                        'price': price_zen,
                        'fee': fee_zen
                    }

        logger.error(f"[Purchase Verification] FAILED: No matching event found")
        return None

    except Exception as e:
        logger.error(f"[Purchase Verification] ERROR: {str(e)}")
        return None


def verify_cancel_transaction(
    tx_hash: str,
    expected_seller: str,
    expected_token_id: int
) -> bool:
    """
    Verify that a cancel listing transaction succeeded

    Args:
        tx_hash: Transaction hash
        expected_seller: Expected seller address
        expected_token_id: Expected token ID

    Returns:
        True if cancellation successful
    """
    import time

    try:
        logger.info(f"[Cancel Verification] Starting verification for tx: {tx_hash}")

        # Wait for transaction to be mined
        receipt = None
        for attempt in range(15):
            try:
                receipt = w3.eth.get_transaction_receipt(tx_hash)
                logger.info(f"[Cancel Verification] Transaction found")
                break
            except Exception as e:
                if attempt < 14:
                    logger.info(f"[Cancel Verification] Waiting... (attempt {attempt + 1}/15)")
                    time.sleep(2)
                else:
                    raise

        if not receipt or receipt['status'] != 1:
            logger.error(f"[Cancel Verification] FAILED: Transaction failed")
            return False

        # Parse ListingCancelled event
        listing_cancelled_signature = w3.keccak(text="ListingCancelled(uint256,address,uint256)").hex()

        for log in receipt['logs']:
            if not log.get('topics') or len(log['topics']) < 3:
                continue
            if log['topics'][0].hex() == listing_cancelled_signature:
                token_id = int(log['topics'][1].hex(), 16)
                seller = '0x' + log['topics'][2].hex()[-40:]

                logger.info(f"[Cancel Verification] Found ListingCancelled: tokenId={token_id}, seller={seller}")

                # Verify details
                if (token_id == expected_token_id and
                    seller.lower() == expected_seller.lower()):
                    logger.info(f"[Cancel Verification] SUCCESS")
                    return True

        logger.error(f"[Cancel Verification] FAILED: No matching event found")
        return False

    except Exception as e:
        logger.error(f"[Cancel Verification] ERROR: {str(e)}")
        return False


def get_active_listings_onchain() -> List[int]:
    """
    Get all active listing token IDs from blockchain

    Returns:
        List of token IDs currently listed
    """
    marketplace_contract = get_marketplace_contract()
    if not marketplace_contract:
        return []

    try:
        token_ids = marketplace_contract.functions.getActiveListings().call()
        return list(token_ids)
    except Exception as e:
        logger.error(f"Error getting active listings: {e}")
        return []


def get_listing_details_onchain(token_id: int) -> Optional[Dict]:
    """
    Get listing details from blockchain

    Args:
        token_id: NFT token ID

    Returns:
        Dict with listing details or None
    """
    marketplace_contract = get_marketplace_contract()
    if not marketplace_contract:
        return None

    try:
        listing = marketplace_contract.functions.getListing(token_id).call()

        return {
            'seller': listing[0],
            'price': Decimal(listing[1]) / Decimal(10**18),
            'active': listing[2],
            'listed_at': listing[3]
        }
    except Exception as e:
        logger.error(f"Error getting listing details for token {token_id}: {e}")
        return None
