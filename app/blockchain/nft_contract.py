"""
NFT Smart Contract Integration
Handles blockchain interactions for minting, burning, and upgrading NFTs
"""
import os
import logging
from decimal import Decimal
from typing import Optional, Tuple, Dict
from web3 import Web3
from web3.contract import Contract
from eth_account import Account

logger = logging.getLogger(__name__)

# Load environment variables
BLOCKCHAIN_RPC_URL = os.getenv('BLOCKCHAIN_RPC_URL', 'https://horizen-testnet.rpc.caldera.xyz/http')
NFT_CONTRACT_ADDRESS = os.getenv('NFT_CONTRACT_ADDRESS')  # Tactizen GameNFT
TREASURY_PRIVATE_KEY = os.getenv('TREASURY_PRIVATE_KEY', None)
TREASURY_ADDRESS = os.getenv('TREASURY_ADDRESS', None)
ZEN_TOKEN_ADDRESS = os.getenv('ZEN_TOKEN_ADDRESS', None)

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(BLOCKCHAIN_RPC_URL))

# GameNFT Contract ABI (simplified - add full ABI from compiled contract)
GAME_NFT_ABI = [
    {
        "inputs": [
            {"name": "nftType", "type": "string"},
            {"name": "category", "type": "string"},
            {"name": "tier", "type": "uint8"},
            {"name": "bonusValue", "type": "uint16"},
            {"name": "tokenURI", "type": "string"}
        ],
        "name": "mintNFT",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "nftType", "type": "string"},
            {"name": "category", "type": "string"},
            {"name": "tier", "type": "uint8"},
            {"name": "bonusValue", "type": "uint16"},
            {"name": "tokenURI", "type": "string"}
        ],
        "name": "adminMintNFT",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "burnNFT",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "burnTokenIds", "type": "uint256[]"},
            {"name": "newNftType", "type": "string"},
            {"name": "newCategory", "type": "string"},
            {"name": "newBonusValue", "type": "uint16"},
            {"name": "newTokenURI", "type": "string"}
        ],
        "name": "upgradeNFT",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "getNFTMetadata",
        "outputs": [
            {"name": "nftType", "type": "string"},
            {"name": "category", "type": "string"},
            {"name": "tier", "type": "uint8"},
            {"name": "bonusValue", "type": "uint16"},
            {"name": "exists", "type": "bool"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"name": "owner", "type": "address"}],
        "name": "getNFTsByOwner",
        "outputs": [{"name": "", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": True, "name": "tokenId", "type": "uint256"},
            {"indexed": False, "name": "nftType", "type": "string"},
            {"indexed": False, "name": "category", "type": "string"},
            {"indexed": False, "name": "tier", "type": "uint8"},
            {"indexed": False, "name": "pricePaid", "type": "uint256"}
        ],
        "name": "NFTMinted",
        "type": "event"
    }
]

# ERC20 ABI for ZEN token (simplified)
ERC20_ABI = [
    {
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "from", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "transferFrom",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]


def get_nft_contract() -> Optional[Contract]:
    """Get GameNFT contract instance"""
    if not NFT_CONTRACT_ADDRESS:
        return None

    return w3.eth.contract(
        address=Web3.to_checksum_address(NFT_CONTRACT_ADDRESS),
        abi=GAME_NFT_ABI
    )


def get_zen_contract() -> Optional[Contract]:
    """Get ZEN token contract instance"""
    if not ZEN_TOKEN_ADDRESS:
        return None

    return w3.eth.contract(
        address=Web3.to_checksum_address(ZEN_TOKEN_ADDRESS),
        abi=ERC20_ABI
    )


def check_zen_balance(wallet_address: str) -> Decimal:
    """
    Check user's ZEN token balance

    Args:
        wallet_address: User's Ethereum wallet address

    Returns:
        ZEN balance in tokens (18 decimals)
    """
    zen_contract = get_zen_contract()
    if not zen_contract:
        raise Exception("ZEN token contract not configured")

    balance_wei = zen_contract.functions.balanceOf(
        Web3.to_checksum_address(wallet_address)
    ).call()

    # Convert from wei (18 decimals) to tokens
    balance = Decimal(balance_wei) / Decimal(10**18)
    return balance


def verify_zen_payment(tx_hash: str, from_address: str, to_address: str, expected_amount: Decimal) -> bool:
    """
    Verify that a ZEN payment transaction is valid

    Args:
        tx_hash: Transaction hash to verify
        from_address: Expected sender address
        to_address: Expected recipient address (treasury)
        expected_amount: Expected ZEN amount transferred

    Returns:
        True if payment is valid, False otherwise
    """
    import time

    try:
        logger.info(f"[Payment Verification] Starting verification for tx: {tx_hash}")
        logger.info(f"[Payment Verification] From: {from_address}, To: {to_address}, Amount: {expected_amount} ZEN")

        # Wait for transaction to be mined (retry up to 30 seconds)
        receipt = None
        for attempt in range(15):  # 15 attempts * 2 seconds = 30 seconds max
            try:
                receipt = w3.eth.get_transaction_receipt(tx_hash)
                logger.info(f"[Payment Verification] Transaction found after {attempt * 2} seconds")
                break
            except Exception as e:
                if attempt < 14:  # Don't sleep on last attempt
                    logger.info(f"[Payment Verification] Transaction not found yet, waiting... (attempt {attempt + 1}/15)")
                    time.sleep(2)
                else:
                    raise  # Re-raise on last attempt

        if not receipt:
            logger.info(f"[Payment Verification] FAILED: Transaction not found after 30 seconds")
            return False

        logger.info(f"[Payment Verification] Receipt status: {receipt['status']}")

        if receipt['status'] != 1:
            logger.info(f"[Payment Verification] FAILED: Transaction failed on blockchain")
            return False  # Transaction failed

        # Get transaction details
        tx = w3.eth.get_transaction(tx_hash)
        logger.info(f"[Payment Verification] TX from: {tx['from']}, to: {tx['to']}")

        # Verify sender
        if tx['from'].lower() != from_address.lower():
            logger.info(f"[Payment Verification] FAILED: Sender mismatch. Expected {from_address}, got {tx['from']}")
            return False

        # Verify recipient (must be ZEN token contract for transfer)
        zen_contract = get_zen_contract()
        if tx['to'].lower() != ZEN_TOKEN_ADDRESS.lower():
            logger.info(f"[Payment Verification] FAILED: Recipient mismatch. Expected {ZEN_TOKEN_ADDRESS}, got {tx['to']}")
            return False

        # Parse transfer event from receipt
        # ERC20 Transfer event signature
        transfer_event_signature = w3.keccak(text="Transfer(address,address,uint256)").hex()
        logger.info(f"[Payment Verification] Looking for Transfer events...")

        for log in receipt['logs']:
            if log['topics'][0].hex() == transfer_event_signature:
                # Decode transfer event
                from_addr = '0x' + log['topics'][1].hex()[-40:]
                to_addr = '0x' + log['topics'][2].hex()[-40:]
                amount_wei = int(log['data'].hex(), 16)
                amount_zen = Decimal(amount_wei) / Decimal(10**18)

                logger.info(f"[Payment Verification] Found Transfer: {from_addr} -> {to_addr}, Amount: {amount_zen} ZEN")

                # Verify addresses and amount
                if (from_addr.lower() == from_address.lower() and
                    to_addr.lower() == to_address.lower()):

                    # Convert expected amount to wei
                    expected_wei = int(expected_amount * Decimal(10**18))

                    # Allow small rounding difference (0.001 ZEN)
                    tolerance = int(0.001 * 10**18)

                    logger.info(f"[Payment Verification] Amount check: {amount_wei} vs {expected_wei} (tolerance: {tolerance})")

                    if abs(amount_wei - expected_wei) <= tolerance:
                        logger.info(f"[Payment Verification] SUCCESS: Payment verified!")
                        return True
                    else:
                        logger.info(f"[Payment Verification] FAILED: Amount mismatch")

        logger.info(f"[Payment Verification] FAILED: No matching Transfer event found")
        return False

    except Exception as e:
        logger.info(f"[Payment Verification] ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def prepare_nft_purchase_transaction(
    user_wallet: str,
    nft_type: str,
    category: str,
    tier: int,
    bonus_value: int,
    price_zen: Decimal
) -> Dict:
    """
    Prepare NFT purchase transaction for user to sign

    This creates the transaction data that the frontend will send to MetaMask

    Args:
        user_wallet: User's Ethereum wallet address
        nft_type: 'player' or 'company'
        category: NFT category
        tier: NFT tier (1-5)
        bonus_value: Bonus percentage
        price_zen: Price in ZEN tokens

    Returns:
        Transaction data dict for MetaMask signing
    """
    if not NFT_CONTRACT_ADDRESS or not TREASURY_ADDRESS or not ZEN_TOKEN_ADDRESS:
        raise Exception("Blockchain configuration incomplete. Set NFT_CONTRACT_ADDRESS, TREASURY_ADDRESS, and ZEN_TOKEN_ADDRESS in .env")

    zen_contract = get_zen_contract()

    # Convert ZEN amount to wei (18 decimals)
    amount_wei = int(price_zen * Decimal(10**18))

    # Build transaction to transfer ZEN from user to treasury
    transaction = zen_contract.functions.transferFrom(
        Web3.to_checksum_address(user_wallet),
        Web3.to_checksum_address(TREASURY_ADDRESS),
        amount_wei
    ).build_transaction({
        'from': Web3.to_checksum_address(user_wallet),
        'nonce': w3.eth.get_transaction_count(Web3.to_checksum_address(user_wallet)),
        'gas': 100000,
        'gasPrice': w3.eth.gas_price
    })

    return {
        'transaction': transaction,
        'nft_metadata': {
            'nft_type': nft_type,
            'category': category,
            'tier': tier,
            'bonus_value': bonus_value
        }
    }


def mint_nft_onchain(
    user_wallet: str,
    nft_type: str,
    category: str,
    tier: int,
    bonus_value: int,
    metadata_uri: str = ""
) -> Tuple[Optional[int], Optional[str]]:
    """
    Mint NFT on blockchain (called after payment confirmed)

    This function is called by the backend after ZEN payment is confirmed

    Args:
        user_wallet: User's Ethereum wallet address
        nft_type: 'player' or 'company'
        category: NFT category
        tier: NFT tier (1-5)
        bonus_value: Bonus percentage
        metadata_uri: IPFS URI for NFT metadata

    Returns:
        (token_id, tx_hash) tuple on success, raises Exception on failure
    """
    logger.info(f"[NFT Minting] Starting on-chain minting for user {user_wallet}")
    logger.info(f"[NFT Minting] Type: {nft_type}, Category: {category}, Tier: {tier}, Bonus: {bonus_value}")

    if not TREASURY_PRIVATE_KEY:
        logger.info(f"[NFT Minting] ERROR: Treasury private key not configured")
        raise Exception("Treasury private key not configured")

    nft_contract = get_nft_contract()
    if not nft_contract:
        logger.info(f"[NFT Minting] ERROR: NFT contract not deployed")
        raise Exception("NFT contract not deployed")

    logger.info(f"[NFT Minting] NFT contract loaded: {NFT_CONTRACT_ADDRESS}")

    # Create treasury account from private key
    treasury_account = Account.from_key(TREASURY_PRIVATE_KEY)
    logger.info(f"[NFT Minting] Treasury account: {treasury_account.address}")

    # Check treasury balance
    treasury_balance = w3.eth.get_balance(treasury_account.address)
    treasury_balance_eth = treasury_balance / 10**18
    logger.info(f"[NFT Minting] Treasury ETH balance: {treasury_balance_eth} ETH")

    # Build mint transaction
    logger.info(f"[NFT Minting] Building mint transaction...")
    try:
        mint_tx = nft_contract.functions.mintNFT(
            Web3.to_checksum_address(user_wallet),
            nft_type,
            category,
            tier,
            bonus_value,
            metadata_uri or f"ipfs://placeholder/{nft_type}_{category}_q{tier}.json"
        ).build_transaction({
            'from': treasury_account.address,
            'nonce': w3.eth.get_transaction_count(treasury_account.address),
            'gas': 500000,  # Increased from 200000 to handle contract execution
            'gasPrice': w3.eth.gas_price
        })
        logger.info(f"[NFT Minting] Transaction built. Gas: {mint_tx['gas']}, Gas Price: {mint_tx['gasPrice']}")
    except Exception as e:
        logger.info(f"[NFT Minting] ERROR building transaction: {str(e)}")
        raise

    # Sign transaction
    logger.info(f"[NFT Minting] Signing transaction...")
    try:
        signed_tx = w3.eth.account.sign_transaction(mint_tx, TREASURY_PRIVATE_KEY)
        logger.info(f"[NFT Minting] Transaction signed successfully")
    except Exception as e:
        logger.info(f"[NFT Minting] ERROR signing transaction: {str(e)}")
        raise

    # Send transaction (handle both old and new web3.py versions)
    raw_tx = getattr(signed_tx, 'raw_transaction', None) or getattr(signed_tx, 'rawTransaction', None)
    if raw_tx is None:
        logger.info(f"[NFT Minting] ERROR: Could not get raw transaction")
        raise Exception("Could not get raw transaction from signed transaction")

    logger.info(f"[NFT Minting] Sending transaction to blockchain...")
    try:
        tx_hash = w3.eth.send_raw_transaction(raw_tx)
        tx_hash_hex = tx_hash.hex()
        logger.info(f"[NFT Minting] Transaction sent! Hash: {tx_hash_hex}")
    except Exception as e:
        logger.info(f"[NFT Minting] ERROR sending transaction: {str(e)}")
        raise

    # Wait for receipt
    logger.info(f"[NFT Minting] Waiting for transaction confirmation (max 120s)...")
    try:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        logger.info(f"[NFT Minting] Transaction confirmed! Status: {receipt['status']}")
    except Exception as e:
        logger.info(f"[NFT Minting] ERROR waiting for receipt: {str(e)}")
        raise

    if receipt['status'] != 1:
        raise Exception("Transaction failed on blockchain")

    # Parse NFTMinted event to get token ID
    logs = nft_contract.events.NFTMinted().process_receipt(receipt)
    if not logs:
        raise Exception("NFT minted but token ID not found in logs")

    token_id = logs[0]['args']['tokenId']
    return token_id, tx_hash_hex


def admin_mint_nft(
    to_address: str,
    nft_type: str,
    category: str,
    tier: int,
    bonus_value: int,
    metadata_uri: str = ""
) -> Tuple[Optional[int], Optional[str]]:
    """
    Admin mint NFT on blockchain (free mint - no ZEN payment required)

    Uses the adminMintNFT function which can only be called by the contract owner (treasury).
    Used for free mints, rewards, airdrops, etc.

    Args:
        to_address: Recipient's Ethereum wallet address
        nft_type: 'player' or 'company'
        category: NFT category
        tier: NFT tier (1-5)
        bonus_value: Bonus percentage
        metadata_uri: IPFS URI for NFT metadata

    Returns:
        (token_id, tx_hash) tuple on success, raises Exception on failure
    """
    logger.info(f"[Admin Mint] Starting free mint for user {to_address}")
    logger.info(f"[Admin Mint] Type: {nft_type}, Category: {category}, Tier: {tier}, Bonus: {bonus_value}")

    if not TREASURY_PRIVATE_KEY:
        logger.error(f"[Admin Mint] ERROR: Treasury private key not configured")
        raise Exception("Treasury private key not configured")

    nft_contract = get_nft_contract()
    if not nft_contract:
        logger.error(f"[Admin Mint] ERROR: NFT contract not deployed")
        raise Exception("NFT contract not deployed")

    # Create treasury account from private key
    treasury_account = Account.from_key(TREASURY_PRIVATE_KEY)
    logger.info(f"[Admin Mint] Treasury account: {treasury_account.address}")

    # Check treasury balance for gas
    treasury_balance = w3.eth.get_balance(treasury_account.address)
    treasury_balance_eth = treasury_balance / 10**18
    logger.info(f"[Admin Mint] Treasury ETH balance: {treasury_balance_eth} ETH")

    if treasury_balance_eth < 0.001:
        raise Exception("Treasury has insufficient ETH for gas")

    # Build admin mint transaction
    logger.info(f"[Admin Mint] Building adminMintNFT transaction...")
    try:
        # ABI for adminMintNFT
        admin_mint_abi = [{
            "inputs": [
                {"name": "to", "type": "address"},
                {"name": "nftType", "type": "string"},
                {"name": "category", "type": "string"},
                {"name": "tier", "type": "uint8"},
                {"name": "bonusValue", "type": "uint16"},
                {"name": "tokenURI", "type": "string"}
            ],
            "name": "adminMintNFT",
            "outputs": [{"name": "", "type": "uint256"}],
            "stateMutability": "nonpayable",
            "type": "function"
        }]

        # Create contract instance with admin mint ABI
        contract_with_admin = w3.eth.contract(
            address=Web3.to_checksum_address(NFT_CONTRACT_ADDRESS),
            abi=admin_mint_abi
        )

        mint_tx = contract_with_admin.functions.adminMintNFT(
            Web3.to_checksum_address(to_address),
            nft_type,
            category,
            tier,
            bonus_value,
            metadata_uri or f"ipfs://tactizen/{nft_type}_{category}_q{tier}.json"
        ).build_transaction({
            'from': treasury_account.address,
            'nonce': w3.eth.get_transaction_count(treasury_account.address),
            'gas': 500000,
            'gasPrice': w3.eth.gas_price
        })
        logger.info(f"[Admin Mint] Transaction built. Gas: {mint_tx['gas']}")
    except Exception as e:
        logger.error(f"[Admin Mint] ERROR building transaction: {str(e)}")
        raise

    # Sign transaction
    logger.info(f"[Admin Mint] Signing transaction...")
    try:
        signed_tx = w3.eth.account.sign_transaction(mint_tx, TREASURY_PRIVATE_KEY)
        logger.info(f"[Admin Mint] Transaction signed successfully")
    except Exception as e:
        logger.error(f"[Admin Mint] ERROR signing transaction: {str(e)}")
        raise

    # Send transaction
    raw_tx = getattr(signed_tx, 'raw_transaction', None) or getattr(signed_tx, 'rawTransaction', None)
    if raw_tx is None:
        raise Exception("Could not get raw transaction from signed transaction")

    logger.info(f"[Admin Mint] Sending transaction to blockchain...")
    try:
        tx_hash = w3.eth.send_raw_transaction(raw_tx)
        tx_hash_hex = tx_hash.hex()
        logger.info(f"[Admin Mint] Transaction sent! Hash: {tx_hash_hex}")
    except Exception as e:
        logger.error(f"[Admin Mint] ERROR sending transaction: {str(e)}")
        raise

    # Wait for receipt
    logger.info(f"[Admin Mint] Waiting for transaction confirmation...")
    try:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        logger.info(f"[Admin Mint] Transaction confirmed! Status: {receipt['status']}")
    except Exception as e:
        logger.error(f"[Admin Mint] ERROR waiting for receipt: {str(e)}")
        raise

    if receipt['status'] != 1:
        raise Exception("Admin mint transaction failed on blockchain")

    # Parse NFTMinted event to get token ID
    logs = nft_contract.events.NFTMinted().process_receipt(receipt)
    if not logs:
        raise Exception("NFT minted but token ID not found in logs")

    token_id = logs[0]['args']['tokenId']
    logger.info(f"[Admin Mint] SUCCESS! Token ID: {token_id}")
    return token_id, tx_hash_hex


def burn_nfts_and_upgrade(
    user_wallet: str,
    burn_token_ids: list,
    new_nft_type: str,
    new_category: str,
    new_tier: int,
    new_bonus_value: int
) -> Tuple[Optional[int], Optional[str]]:
    """
    Burn 3 NFTs and mint 1 upgraded NFT (called by user via MetaMask)

    Args:
        user_wallet: User's wallet address
        burn_token_ids: List of 3 token IDs to burn
        new_nft_type: Type of new NFT
        new_category: Category of new NFT
        new_tier: Tier of new NFT
        new_bonus_value: Bonus value of new NFT

    Returns:
        (new_token_id, error_message)
    """
    nft_contract = get_nft_contract()
    if not nft_contract:
        return None, "NFT contract not deployed"

    try:
        # This transaction must be signed by the user (not treasury)
        # Return transaction data for MetaMask
        upgrade_tx = nft_contract.functions.upgradeNFT(
            burn_token_ids,
            new_nft_type,
            new_category,
            new_bonus_value,
            f"ipfs://placeholder/{new_nft_type}_{new_category}_q{new_tier}.json"
        ).build_transaction({
            'from': Web3.to_checksum_address(user_wallet),
            'nonce': w3.eth.get_transaction_count(Web3.to_checksum_address(user_wallet)),
            'gas': 300000,
            'gasPrice': w3.eth.gas_price
        })

        return upgrade_tx, None

    except Exception as e:
        return None, f"Error preparing upgrade transaction: {str(e)}"


def verify_nft_ownership(wallet_address: str, token_id: int) -> bool:
    """
    Verify that a wallet owns a specific NFT

    Args:
        wallet_address: Wallet to check
        token_id: NFT token ID

    Returns:
        True if wallet owns the NFT
    """
    nft_contract = get_nft_contract()
    if not nft_contract:
        return False

    try:
        owner = nft_contract.functions.ownerOf(token_id).call()
        return owner.lower() == wallet_address.lower()
    except:
        return False


def get_nft_metadata_from_chain(token_id: int) -> Optional[Dict]:
    """
    Get NFT metadata from blockchain

    Args:
        token_id: NFT token ID

    Returns:
        Dict with NFT metadata or None
    """
    nft_contract = get_nft_contract()
    if not nft_contract:
        return None

    try:
        metadata = nft_contract.functions.getNFTMetadata(token_id).call()
        return {
            'nft_type': metadata[0],
            'category': metadata[1],
            'tier': metadata[2],
            'bonus_value': metadata[3],
            'exists': metadata[4]
        }
    except Exception as e:
        logger.info(f"Error fetching NFT metadata: {e}")
        return None


def verify_nft_mint_transaction(tx_hash: str, expected_minter: str) -> Optional[Dict]:
    """
    Verify that an NFT mint transaction succeeded and extract NFT details

    This is for V2 contract where users call mintNFT() directly with payment

    Args:
        tx_hash: Transaction hash of the mintNFT() call
        expected_minter: Expected minter address (user wallet)

    Returns:
        Dict with NFT details if successful, None if failed
    """
    import time

    try:
        logger.info(f"[NFT Mint Verification] Starting verification for tx: {tx_hash}")
        logger.info(f"[NFT Mint Verification] Expected minter: {expected_minter}")

        # Wait for transaction to be mined (retry up to 30 seconds)
        receipt = None
        for attempt in range(15):  # 15 attempts * 2 seconds = 30 seconds max
            try:
                receipt = w3.eth.get_transaction_receipt(tx_hash)
                logger.info(f"[NFT Mint Verification] Transaction found after {attempt * 2} seconds")
                break
            except Exception as e:
                if attempt < 14:  # Don't sleep on last attempt
                    logger.info(f"[NFT Mint Verification] Transaction not found yet, waiting... (attempt {attempt + 1}/15)")
                    time.sleep(2)
                else:
                    raise  # Re-raise on last attempt

        if not receipt:
            logger.error(f"[NFT Mint Verification] FAILED: Transaction not found after 30 seconds")
            return None

        logger.info(f"[NFT Mint Verification] Receipt status: {receipt['status']}")

        if receipt['status'] != 1:
            logger.error(f"[NFT Mint Verification] FAILED: Transaction failed on blockchain")
            return None  # Transaction failed

        # Get transaction details
        tx = w3.eth.get_transaction(tx_hash)
        logger.info(f"[NFT Mint Verification] TX from: {tx['from']}, to: {tx['to']}")

        # Verify sender (minter)
        if tx['from'].lower() != expected_minter.lower():
            logger.error(f"[NFT Mint Verification] FAILED: Minter mismatch. Expected {expected_minter}, got {tx['from']}")
            return None

        # Verify recipient is NFT contract
        if tx['to'].lower() != NFT_CONTRACT_ADDRESS.lower():
            logger.error(f"[NFT Mint Verification] FAILED: Contract mismatch. Expected {NFT_CONTRACT_ADDRESS}, got {tx['to']}")
            return None

        # Parse NFTMinted event from receipt
        # NFTMinted(address indexed to, uint256 indexed tokenId, string nftType, string category, uint8 tier, uint256 pricePaid)
        nft_minted_event_signature = w3.keccak(text="NFTMinted(address,uint256,string,string,uint8,uint256)").hex()
        logger.info(f"[NFT Mint Verification] Looking for NFTMinted events...")

        for log in receipt['logs']:
            if log['topics'][0].hex() == nft_minted_event_signature:
                # Decode NFTMinted event
                to_addr = '0x' + log['topics'][1].hex()[-40:]
                token_id = int(log['topics'][2].hex(), 16)

                # Decode non-indexed parameters (nftType, category, tier, pricePaid)
                # This is more complex - need to decode ABI-encoded data
                nft_contract = get_nft_contract()
                event_abi = next((x for x in GAME_NFT_ABI if x.get('name') == 'NFTMinted'), None)

                if event_abi:
                    # Use Web3's event processing
                    from web3._utils.events import get_event_data
                    from eth_utils import event_abi_to_log_topic

                    try:
                        event_data = get_event_data(w3.codec, event_abi, log)
                        nft_type = event_data['args']['nftType']
                        category = event_data['args']['category']
                        tier = event_data['args']['tier']
                        price_paid = event_data['args']['pricePaid']

                        logger.info(f"[NFT Mint Verification] Found NFTMinted: to={to_addr}, tokenId={token_id}")
                        logger.info(f"[NFT Mint Verification] NFT details: type={nft_type}, category={category}, tier={tier}, price={price_paid}")

                        # Verify the minter matches expected
                        if to_addr.lower() == expected_minter.lower():
                            # Get full metadata from contract to get bonus_value
                            contract = get_nft_contract()
                            nft_metadata = contract.functions.getNFTMetadata(token_id).call()

                            bonus_value = nft_metadata[3]  # bonusValue is at index 3

                            logger.info(f"[NFT Mint Verification] SUCCESS: Mint verified!")
                            return {
                                'token_id': token_id,
                                'nft_type': nft_type,
                                'category': category,
                                'tier': tier,
                                'bonus_value': bonus_value,
                                'price_paid': price_paid
                            }
                    except Exception as e:
                        logger.error(f"[NFT Mint Verification] Error decoding event: {e}")

        logger.error(f"[NFT Mint Verification] FAILED: No matching NFTMinted event found")
        return None

    except Exception as e:
        logger.error(f"[NFT Mint Verification] ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def verify_nft_upgrade_transaction(tx_hash: str, expected_upgrader: str, expected_burn_token_ids: list) -> Optional[Dict]:
    """
    Verify that an NFT upgrade transaction succeeded and extract new NFT details

    CRITICAL: This function MUST verify that the blockchain transaction actually succeeded
    before returning data. The database should ONLY be updated after this returns successfully.

    Args:
        tx_hash: Transaction hash of the upgradeNFT() call
        expected_upgrader: Expected upgrader address (user wallet)
        expected_burn_token_ids: List of 3 token IDs that should have been burned

    Returns:
        Dict with new NFT details if successful, None if failed
    """
    import time

    try:
        logger.info(f"[NFT Upgrade Verification] Starting verification for tx: {tx_hash}")
        logger.info(f"[NFT Upgrade Verification] Expected upgrader: {expected_upgrader}")
        logger.info(f"[NFT Upgrade Verification] Expected burn token IDs: {expected_burn_token_ids}")

        # Wait for transaction to be mined (retry up to 60 seconds for better reliability)
        receipt = None
        for attempt in range(30):  # 30 attempts * 2 seconds = 60 seconds max
            try:
                receipt = w3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    logger.info(f"[NFT Upgrade Verification] Transaction found after {attempt * 2} seconds")
                    break
            except Exception as e:
                logger.debug(f"[NFT Upgrade Verification] Receipt not available yet: {e}")

            if attempt < 29:  # Don't sleep on last attempt
                logger.info(f"[NFT Upgrade Verification] Transaction not found yet, waiting... (attempt {attempt + 1}/30)")
                time.sleep(2)

        if not receipt:
            logger.error(f"[NFT Upgrade Verification] FAILED: Transaction not found after 60 seconds")
            return None

        # CRITICAL: Explicitly check transaction status
        # Status 1 = success, Status 0 = failed/reverted
        tx_status = receipt.get('status')
        logger.info(f"[NFT Upgrade Verification] Receipt status: {tx_status} (1=success, 0=failed)")

        if tx_status != 1:
            logger.error(f"[NFT Upgrade Verification] FAILED: Transaction REVERTED on blockchain (status={tx_status})")
            logger.error(f"[NFT Upgrade Verification] Block: {receipt.get('blockNumber')}, Gas used: {receipt.get('gasUsed')}")
            return None

        # Additional safety: verify transaction has at least 1 confirmation
        try:
            current_block = w3.eth.block_number
            tx_block = receipt.get('blockNumber')
            confirmations = current_block - tx_block if tx_block else 0
            logger.info(f"[NFT Upgrade Verification] Transaction has {confirmations} confirmations")

            # Wait for at least 1 confirmation
            if confirmations < 1:
                logger.info(f"[NFT Upgrade Verification] Waiting for confirmation...")
                time.sleep(3)  # Wait a bit more for confirmation
        except Exception as conf_err:
            logger.warning(f"[NFT Upgrade Verification] Could not check confirmations: {conf_err}")

        # Re-check status after waiting (in case of reorg)
        try:
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            if receipt.get('status') != 1:
                logger.error(f"[NFT Upgrade Verification] FAILED: Transaction status changed to failed after recheck")
                return None
        except Exception as recheck_err:
            logger.warning(f"[NFT Upgrade Verification] Could not recheck status: {recheck_err}")

        # Get transaction details
        tx = w3.eth.get_transaction(tx_hash)
        logger.info(f"[NFT Upgrade Verification] TX from: {tx['from']}, to: {tx['to']}")

        # Verify sender (upgrader)
        if tx['from'].lower() != expected_upgrader.lower():
            logger.error(f"[NFT Upgrade Verification] FAILED: Upgrader mismatch. Expected {expected_upgrader}, got {tx['from']}")
            return None

        # Verify recipient is NFT contract
        if tx['to'].lower() != NFT_CONTRACT_ADDRESS.lower():
            logger.error(f"[NFT Upgrade Verification] FAILED: Contract mismatch. Expected {NFT_CONTRACT_ADDRESS}, got {tx['to']}")
            return None

        # Parse NFTUpgraded event from receipt
        # NFTUpgraded(address indexed upgrader, uint256[] burnedTokenIds, uint256 newTokenId, uint8 newTier)
        nft_upgraded_event_signature = w3.keccak(text="NFTUpgraded(address,uint256[],uint256,uint8)").hex()
        logger.info(f"[NFT Upgrade Verification] Looking for NFTUpgraded events...")

        for log in receipt['logs']:
            if log['topics'][0].hex() == nft_upgraded_event_signature:
                # Decode NFTUpgraded event
                upgrader_addr = '0x' + log['topics'][1].hex()[-40:]

                # The non-indexed parameters need to be decoded from data
                nft_contract = get_nft_contract()

                # Add NFTUpgraded event to ABI if not present
                event_abi = {
                    "anonymous": False,
                    "inputs": [
                        {"indexed": True, "name": "upgrader", "type": "address"},
                        {"indexed": False, "name": "burnedTokenIds", "type": "uint256[]"},
                        {"indexed": False, "name": "newTokenId", "type": "uint256"},
                        {"indexed": False, "name": "newTier", "type": "uint8"}
                    ],
                    "name": "NFTUpgraded",
                    "type": "event"
                }

                try:
                    from web3._utils.events import get_event_data

                    event_data = get_event_data(w3.codec, event_abi, log)
                    burned_token_ids = event_data['args']['burnedTokenIds']
                    new_token_id = event_data['args']['newTokenId']
                    new_tier = event_data['args']['newTier']

                    logger.info(f"[NFT Upgrade Verification] Found NFTUpgraded: upgrader={upgrader_addr}")
                    logger.info(f"[NFT Upgrade Verification] Burned tokens: {burned_token_ids}, New token: {new_token_id}, New tier: {new_tier}")

                    # Verify the upgrader matches expected
                    if upgrader_addr.lower() != expected_upgrader.lower():
                        logger.error(f"[NFT Upgrade Verification] FAILED: Upgrader mismatch in event")
                        continue

                    # Verify burned token IDs match (order doesn't matter)
                    if set(burned_token_ids) != set(expected_burn_token_ids):
                        logger.error(f"[NFT Upgrade Verification] FAILED: Burned token IDs don't match. Expected {expected_burn_token_ids}, got {burned_token_ids}")
                        continue

                    # Get full metadata from contract for the new NFT
                    nft_metadata = nft_contract.functions.getNFTMetadata(new_token_id).call()

                    nft_type = nft_metadata[0]
                    category = nft_metadata[1]
                    tier = nft_metadata[2]
                    bonus_value = nft_metadata[3]

                    logger.info(f"[NFT Upgrade Verification] SUCCESS: Upgrade verified!")
                    logger.info(f"[NFT Upgrade Verification] New NFT: type={nft_type}, category={category}, tier=Q{tier}, bonus={bonus_value}%")

                    return {
                        'new_token_id': new_token_id,
                        'burned_token_ids': burned_token_ids,
                        'nft_type': nft_type,
                        'category': category,
                        'tier': tier,
                        'bonus_value': bonus_value
                    }

                except Exception as e:
                    logger.error(f"[NFT Upgrade Verification] Error decoding event: {e}")

        logger.error(f"[NFT Upgrade Verification] FAILED: No matching NFTUpgraded event found")
        return None

    except Exception as e:
        logger.error(f"[NFT Upgrade Verification] ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
