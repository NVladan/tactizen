"""
ZEN Token Integration
Functions for interacting with testZEN ERC-20 token
"""
import os
import logging
from decimal import Decimal
from typing import Tuple, Optional
from web3 import Web3
from eth_account import Account
from .web3_config import get_web3, get_zen_contract, is_valid_address, to_checksum_address

logger = logging.getLogger(__name__)

# Treasury configuration
TREASURY_PRIVATE_KEY = os.getenv('TREASURY_PRIVATE_KEY')
TREASURY_ADDRESS = os.getenv('TREASURY_ADDRESS')

def get_zen_balance(wallet_address):
    """
    Get ZEN token balance for a wallet address

    Args:
        wallet_address (str): Ethereum wallet address

    Returns:
        int: Balance in wei (smallest unit)
        None: If address is invalid or error occurs
    """
    if not is_valid_address(wallet_address):
        return None

    try:
        zen_contract = get_zen_contract()
        checksum_address = to_checksum_address(wallet_address)
        balance_wei = zen_contract.functions.balanceOf(checksum_address).call()
        return balance_wei
    except Exception as e:
        logger.error(f"Error fetching ZEN balance for {wallet_address}: {e}", exc_info=True)
        return None

def get_zen_balance_formatted(wallet_address, decimals=2):
    """
    Get ZEN token balance formatted in human-readable form

    Args:
        wallet_address (str): Ethereum wallet address
        decimals (int): Number of decimal places to show (default: 2)

    Returns:
        str: Formatted balance (e.g., "1,234.56 ZEN")
        str: "0.00 ZEN" if address is invalid or balance is 0
    """
    balance_wei = get_zen_balance(wallet_address)

    if balance_wei is None:
        return "0.00 ZEN"

    # Convert from wei to ZEN (18 decimals)
    w3 = get_web3()
    balance_zen = w3.from_wei(balance_wei, 'ether')

    # Format with commas and specified decimal places
    balance_float = float(balance_zen)
    formatted = f"{balance_float:,.{decimals}f} ZEN"

    return formatted

def get_zen_balance_raw(wallet_address):
    """
    Get ZEN balance as a float

    Args:
        wallet_address (str): Ethereum wallet address

    Returns:
        float: Balance in ZEN tokens
        float: 0.0 if error
    """
    balance_wei = get_zen_balance(wallet_address)

    if balance_wei is None:
        return 0.0

    w3 = get_web3()
    return float(w3.from_wei(balance_wei, 'ether'))

def can_claim_from_faucet(wallet_address):
    """
    Check if a wallet can claim from the testZEN faucet

    Args:
        wallet_address (str): Ethereum wallet address

    Returns:
        bool: True if can claim, False otherwise
    """
    if not is_valid_address(wallet_address):
        return False

    try:
        zen_contract = get_zen_contract()
        w3 = get_web3()
        checksum_address = to_checksum_address(wallet_address)

        last_claim = zen_contract.functions.lastClaim(checksum_address).call()
        current_time = w3.eth.get_block('latest')['timestamp']
        cooldown = 86400  # 1 day in seconds

        return current_time >= last_claim + cooldown
    except Exception as e:
        print(f"Error checking faucet eligibility: {e}")
        return False

def get_faucet_cooldown_remaining(wallet_address):
    """
    Get remaining cooldown time for faucet claim

    Args:
        wallet_address (str): Ethereum wallet address

    Returns:
        int: Seconds remaining until next claim (0 if can claim now)
    """
    if not is_valid_address(wallet_address):
        return 0

    try:
        zen_contract = get_zen_contract()
        w3 = get_web3()
        checksum_address = to_checksum_address(wallet_address)

        last_claim = zen_contract.functions.lastClaim(checksum_address).call()
        current_time = w3.eth.get_block('latest')['timestamp']
        cooldown = 86400  # 1 day in seconds

        next_claim_time = last_claim + cooldown

        if current_time >= next_claim_time:
            return 0
        else:
            return next_claim_time - current_time
    except Exception as e:
        print(f"Error getting cooldown: {e}")
        return 0


def transfer_zen_from_treasury(to_address: str, amount: Decimal) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Transfer ZEN tokens from treasury to a user wallet.
    Used when user buys ZEN with Gold.

    Args:
        to_address: Recipient's wallet address
        amount: Amount of ZEN to transfer (in tokens, not wei)

    Returns:
        Tuple of (success: bool, tx_hash: str or None, error_message: str or None)
    """
    # Reload env vars in case they weren't loaded at module init
    treasury_private_key = os.getenv('TREASURY_PRIVATE_KEY')
    treasury_address = os.getenv('TREASURY_ADDRESS')

    if not treasury_private_key:
        logger.error("[ZEN Transfer] Treasury private key not configured")
        return False, None, "Treasury private key not configured"

    if not is_valid_address(to_address):
        logger.error(f"[ZEN Transfer] Invalid recipient address: {to_address}")
        return False, None, "Invalid recipient address"

    try:
        w3 = get_web3()
        zen_contract = get_zen_contract()

        # Create treasury account
        treasury_account = Account.from_key(treasury_private_key)
        logger.info(f"[ZEN Transfer] Treasury account: {treasury_account.address}")

        # Convert amount to wei (18 decimals)
        amount_wei = int(amount * Decimal(10**18))
        logger.info(f"[ZEN Transfer] Transferring {amount} ZEN ({amount_wei} wei) to {to_address}")

        # Check treasury ZEN balance
        treasury_balance = zen_contract.functions.balanceOf(treasury_account.address).call()
        if treasury_balance < amount_wei:
            logger.error(f"[ZEN Transfer] Insufficient treasury balance: {treasury_balance} < {amount_wei}")
            return False, None, "Treasury has insufficient ZEN balance"

        # Build transfer transaction
        transfer_tx = zen_contract.functions.transfer(
            Web3.to_checksum_address(to_address),
            amount_wei
        ).build_transaction({
            'from': treasury_account.address,
            'nonce': w3.eth.get_transaction_count(treasury_account.address),
            'gas': 100000,
            'gasPrice': w3.eth.gas_price
        })

        # Sign transaction
        signed_tx = w3.eth.account.sign_transaction(transfer_tx, treasury_private_key)

        # Send transaction
        raw_tx = getattr(signed_tx, 'raw_transaction', None) or getattr(signed_tx, 'rawTransaction', None)
        tx_hash = w3.eth.send_raw_transaction(raw_tx)
        tx_hash_hex = tx_hash.hex()

        logger.info(f"[ZEN Transfer] Transaction sent: {tx_hash_hex}")

        # Wait for receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt['status'] != 1:
            logger.error(f"[ZEN Transfer] Transaction failed on blockchain")
            return False, tx_hash_hex, "Transaction failed on blockchain"

        logger.info(f"[ZEN Transfer] SUCCESS! {amount} ZEN transferred to {to_address}")
        return True, tx_hash_hex, None

    except Exception as e:
        logger.error(f"[ZEN Transfer] Error: {str(e)}", exc_info=True)
        return False, None, str(e)


def prepare_zen_transfer_to_treasury(from_address: str, amount: Decimal) -> Tuple[Optional[dict], Optional[str]]:
    """
    Prepare a ZEN transfer transaction for user to sign (transfer to treasury).
    Used when user sells ZEN for Gold.

    Args:
        from_address: User's wallet address
        amount: Amount of ZEN to transfer (in tokens, not wei)

    Returns:
        Tuple of (transaction_data: dict or None, error_message: str or None)
    """
    treasury_address = os.getenv('TREASURY_ADDRESS')

    if not treasury_address:
        return None, "Treasury address not configured"

    if not is_valid_address(from_address):
        return None, "Invalid sender address"

    try:
        w3 = get_web3()
        zen_contract = get_zen_contract()

        # Convert amount to wei (18 decimals)
        amount_wei = int(amount * Decimal(10**18))

        # Get user's ZEN balance
        user_balance = zen_contract.functions.balanceOf(
            Web3.to_checksum_address(from_address)
        ).call()

        if user_balance < amount_wei:
            return None, f"Insufficient ZEN balance. You have {user_balance / 10**18:.2f} ZEN"

        # Build transfer transaction data for user to sign
        transfer_data = zen_contract.functions.transfer(
            Web3.to_checksum_address(treasury_address),
            amount_wei
        ).build_transaction({
            'from': Web3.to_checksum_address(from_address),
            'nonce': w3.eth.get_transaction_count(Web3.to_checksum_address(from_address)),
            'gas': 100000,
            'gasPrice': w3.eth.gas_price
        })

        return transfer_data, None

    except Exception as e:
        logger.error(f"[ZEN Sell Prepare] Error: {str(e)}", exc_info=True)
        return None, str(e)


def verify_zen_transfer_to_treasury(tx_hash: str, from_address: str, expected_amount: Decimal) -> Tuple[bool, Optional[str]]:
    """
    Verify that a ZEN transfer to treasury was successful.

    Args:
        tx_hash: Transaction hash to verify
        from_address: Expected sender address
        expected_amount: Expected ZEN amount

    Returns:
        Tuple of (success: bool, error_message: str or None)
    """
    import time

    treasury_address = os.getenv('TREASURY_ADDRESS')

    try:
        w3 = get_web3()
        zen_contract = get_zen_contract()

        logger.info(f"[ZEN Verify] Verifying tx: {tx_hash}")

        # Wait for transaction receipt
        receipt = None
        for attempt in range(15):
            try:
                receipt = w3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    break
            except Exception:
                pass
            if attempt < 14:
                time.sleep(2)

        if not receipt:
            return False, "Transaction not found"

        if receipt['status'] != 1:
            return False, "Transaction failed on blockchain"

        # Parse Transfer event
        transfer_event_signature = w3.keccak(text="Transfer(address,address,uint256)").hex()

        for log in receipt['logs']:
            if log['topics'][0].hex() == transfer_event_signature:
                from_addr = '0x' + log['topics'][1].hex()[-40:]
                to_addr = '0x' + log['topics'][2].hex()[-40:]
                amount_wei = int(log['data'].hex(), 16)
                amount_zen = Decimal(amount_wei) / Decimal(10**18)

                # Verify addresses and amount
                if (from_addr.lower() == from_address.lower() and
                    to_addr.lower() == treasury_address.lower()):

                    # Allow small tolerance for rounding
                    if abs(amount_zen - expected_amount) <= Decimal('0.001'):
                        logger.info(f"[ZEN Verify] SUCCESS! {amount_zen} ZEN transferred to treasury")
                        return True, None
                    else:
                        return False, f"Amount mismatch: expected {expected_amount}, got {amount_zen}"

        return False, "No matching Transfer event found"

    except Exception as e:
        logger.error(f"[ZEN Verify] Error: {str(e)}", exc_info=True)
        return False, str(e)
