"""
Blockchain integration module for Tactizen
Handles interaction with Horizen L3 Testnet
"""
from .web3_config import get_web3, get_zen_contract, get_citizenship_nft_contract, is_valid_address
from .zen_integration import (
    get_zen_balance,
    get_zen_balance_formatted,
    get_zen_balance_raw,
    can_claim_from_faucet,
    get_faucet_cooldown_remaining
)
from .zen_transfers import (
    transfer_zen_to_treasury,
    transfer_zen_from_treasury,
    verify_zen_transfer,
    get_treasury_balance
)

__all__ = [
    'get_web3',
    'get_zen_contract',
    'get_citizenship_nft_contract',
    'is_valid_address',
    'get_zen_balance',
    'get_zen_balance_formatted',
    'get_zen_balance_raw',
    'can_claim_from_faucet',
    'get_faucet_cooldown_remaining',
    'transfer_zen_to_treasury',
    'transfer_zen_from_treasury',
    'verify_zen_transfer',
    'get_treasury_balance'
]
