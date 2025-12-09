"""
ZEN Token Blockchain Transfer Functions
Handles actual on-chain token transfers for buying/selling ZEN
"""
import os
from decimal import Decimal
from web3 import Web3
from dotenv import load_dotenv
from .web3_config import get_web3, get_zen_contract

load_dotenv()

# Treasury configuration
TREASURY_ADDRESS = os.getenv('TREASURY_WALLET_ADDRESS')
TREASURY_PRIVATE_KEY = os.getenv('TREASURY_PRIVATE_KEY')
CHAIN_ID = int(os.getenv('HORIZEN_L3_CHAIN_ID', '26514'))


def transfer_zen_to_treasury(from_address, amount_zen):
    """
    Transfer ZEN tokens from user to game treasury (when selling ZEN for Gold).

    Args:
        from_address (str): User's wallet address (seller)
        amount_zen (Decimal): Amount of ZEN to transfer

    Returns:
        tuple: (success: bool, tx_hash: str, error_message: str)
    """
    try:
        w3 = get_web3()
        zen_contract = get_zen_contract()

        # Convert ZEN amount to wei
        amount_wei = w3.to_wei(float(amount_zen), 'ether')

        # Checksum addresses
        from_address_checksum = Web3.to_checksum_address(from_address)
        treasury_checksum = Web3.to_checksum_address(TREASURY_ADDRESS)

        # Build the transfer transaction (from user to treasury)
        transfer_function = zen_contract.functions.transfer(
            treasury_checksum,
            amount_wei
        )

        # Get nonce
        nonce = w3.eth.get_transaction_count(from_address_checksum)

        # Build transaction using build_transaction
        # Let Web3 estimate gas automatically
        transaction = transfer_function.build_transaction({
            'chainId': CHAIN_ID,
            'nonce': nonce,
            'from': from_address_checksum,
        })

        # Return transaction data for user to sign with MetaMask
        tx_data = {
            'to': transaction['to'],
            'from': transaction['from'],
            'data': transaction['data'],
            'gas': hex(transaction['gas']),
            'nonce': hex(transaction['nonce']),
            'chainId': hex(transaction['chainId']),
            'value': '0x0',
        }

        # Handle both legacy (gasPrice) and EIP-1559 (maxFeePerGas/maxPriorityFeePerGas) transactions
        if 'gasPrice' in transaction:
            tx_data['gasPrice'] = hex(transaction['gasPrice'])
        else:
            # EIP-1559 transaction
            tx_data['maxFeePerGas'] = hex(transaction['maxFeePerGas'])
            tx_data['maxPriorityFeePerGas'] = hex(transaction['maxPriorityFeePerGas'])

        return {
            'success': True,
            'requires_user_signature': True,
            'transaction_data': tx_data,
            'message': 'Transaction ready for user signature'
        }

    except Exception as e:
        return {
            'success': False,
            'requires_user_signature': False,
            'error': str(e),
            'message': f'Failed to prepare transfer: {str(e)}'
        }


def transfer_zen_from_treasury(to_address, amount_zen):
    """
    Transfer ZEN tokens from game treasury to user (when buying ZEN with Gold).

    Args:
        to_address (str): User's wallet address (buyer)
        amount_zen (Decimal): Amount of ZEN to transfer

    Returns:
        dict: {'success': bool, 'tx_hash': str, 'error': str}
    """
    try:
        w3 = get_web3()
        zen_contract = get_zen_contract()

        # Convert ZEN amount to wei
        amount_wei = w3.to_wei(float(amount_zen), 'ether')

        # Check treasury balance
        treasury_balance = zen_contract.functions.balanceOf(TREASURY_ADDRESS).call()
        if treasury_balance < amount_wei:
            return {
                'success': False,
                'error': 'Insufficient treasury balance',
                'message': f'Treasury only has {w3.from_wei(treasury_balance, "ether")} ZEN'
            }

        # Build transaction from treasury to user
        nonce = w3.eth.get_transaction_count(TREASURY_ADDRESS)

        transfer_function = zen_contract.functions.transfer(
            Web3.to_checksum_address(to_address),
            amount_wei
        )

        # Estimate gas
        gas_estimate = transfer_function.estimate_gas({'from': TREASURY_ADDRESS})

        # Build transaction
        transaction = transfer_function.build_transaction({
            'chainId': CHAIN_ID,
            'gas': gas_estimate + 50000,  # Add buffer
            'gasPrice': w3.eth.gas_price,
            'nonce': nonce,
            'from': TREASURY_ADDRESS
        })

        # Sign transaction with treasury private key
        signed_txn = w3.eth.account.sign_transaction(transaction, private_key=TREASURY_PRIVATE_KEY)

        # Send transaction
        tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)

        # Wait for confirmation
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if tx_receipt['status'] == 1:
            return {
                'success': True,
                'tx_hash': tx_hash.hex(),
                'message': f'Successfully sent {amount_zen} ZEN to {to_address}',
                'block_number': tx_receipt['blockNumber'],
                'gas_used': tx_receipt['gasUsed']
            }
        else:
            return {
                'success': False,
                'tx_hash': tx_hash.hex(),
                'error': 'Transaction failed',
                'message': 'Blockchain transaction failed'
            }

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'message': f'Failed to transfer ZEN: {str(e)}'
        }


def verify_zen_transfer(tx_hash, expected_from, expected_to, expected_amount_zen):
    """
    Verify a ZEN transfer transaction on the blockchain.

    Args:
        tx_hash (str): Transaction hash to verify
        expected_from (str): Expected sender address
        expected_to (str): Expected recipient address
        expected_amount_zen (Decimal): Expected amount transferred

    Returns:
        dict: {'valid': bool, 'message': str}
    """
    try:
        w3 = get_web3()
        zen_contract = get_zen_contract()

        # Get transaction receipt
        tx_receipt = w3.eth.get_transaction_receipt(tx_hash)

        if not tx_receipt or tx_receipt['status'] != 1:
            return {
                'valid': False,
                'message': 'Transaction not found or failed'
            }

        # Decode transfer event from logs
        transfer_event = zen_contract.events.Transfer()

        for log in tx_receipt['logs']:
            try:
                decoded = transfer_event.process_log(log)

                # Check if this is the transfer we're looking for
                from_addr = decoded['args']['from']
                to_addr = decoded['args']['to']
                amount = decoded['args']['value']

                # Verify addresses (case-insensitive)
                if (from_addr.lower() == expected_from.lower() and
                    to_addr.lower() == expected_to.lower()):

                    # Verify amount
                    expected_wei = w3.to_wei(float(expected_amount_zen), 'ether')

                    if amount == expected_wei:
                        return {
                            'valid': True,
                            'message': 'Transfer verified successfully',
                            'from': from_addr,
                            'to': to_addr,
                            'amount': w3.from_wei(amount, 'ether')
                        }
                    else:
                        return {
                            'valid': False,
                            'message': f'Amount mismatch: expected {expected_amount_zen}, got {w3.from_wei(amount, "ether")}'
                        }
            except:
                continue

        return {
            'valid': False,
            'message': 'No matching transfer event found in transaction'
        }

    except Exception as e:
        return {
            'valid': False,
            'message': f'Verification failed: {str(e)}'
        }


def get_treasury_balance():
    """
    Get the current ZEN balance of the game treasury.

    Returns:
        Decimal: Treasury ZEN balance
    """
    try:
        zen_contract = get_zen_contract()
        balance_wei = zen_contract.functions.balanceOf(TREASURY_ADDRESS).call()
        w3 = get_web3()
        return Decimal(str(w3.from_wei(balance_wei, 'ether')))
    except Exception as e:
        print(f"Error fetching treasury balance: {e}")
        return Decimal('0')
