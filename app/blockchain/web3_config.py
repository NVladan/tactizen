"""
Web3 Configuration for Horizen L3 Testnet
"""
import os
import json
from web3 import Web3
from pathlib import Path

# Configuration - these will be loaded from environment at runtime
_w3 = None
_zen_contract = None
_citizenship_nft_contract = None

def get_web3():
    """Get Web3 instance (singleton)"""
    global _w3
    if _w3 is None:
        # Load RPC_URL from environment at runtime (after Flask has loaded .env)
        RPC_URL = os.getenv('BLOCKCHAIN_RPC_URL', 'https://horizen-testnet.rpc.caldera.xyz/http')
        _w3 = Web3(Web3.HTTPProvider(RPC_URL))
        if not _w3.is_connected():
            raise Exception(f"Failed to connect to Horizen L3 Testnet RPC at {RPC_URL}")
    return _w3

def load_contract_abi(contract_name):
    """Load contract ABI from JSON file"""
    abi_path = Path(__file__).parent / 'contracts' / f'{contract_name}.json'
    with open(abi_path, 'r') as f:
        return json.load(f)

def get_zen_contract():
    """Get TestZEN token contract instance"""
    global _zen_contract
    if _zen_contract is None:
        # Load address from environment at runtime
        TESTZEN_ADDRESS = os.getenv('ZEN_TOKEN_ADDRESS')
        if not TESTZEN_ADDRESS:
            raise ValueError("ZEN_TOKEN_ADDRESS not found in environment variables")
        w3 = get_web3()
        abi = load_contract_abi('TestZEN')
        _zen_contract = w3.eth.contract(
            address=Web3.to_checksum_address(TESTZEN_ADDRESS),
            abi=abi
        )
    return _zen_contract

def get_citizenship_nft_contract():
    """Get CitizenshipNFT contract instance"""
    global _citizenship_nft_contract
    if _citizenship_nft_contract is None:
        # Load address from environment at runtime
        CITIZENSHIP_NFT_ADDRESS = os.getenv('CITIZENSHIP_NFT_ADDRESS')
        if not CITIZENSHIP_NFT_ADDRESS:
            raise ValueError("CITIZENSHIP_NFT_ADDRESS not found in environment variables")
        w3 = get_web3()
        abi = load_contract_abi('CitizenshipNFT')
        _citizenship_nft_contract = w3.eth.contract(
            address=Web3.to_checksum_address(CITIZENSHIP_NFT_ADDRESS),
            abi=abi
        )
    return _citizenship_nft_contract

def is_valid_address(address):
    """Check if an Ethereum address is valid"""
    if not address:
        return False
    return Web3.is_address(address)

def to_checksum_address(address):
    """Convert address to checksum format"""
    if not is_valid_address(address):
        return None
    return Web3.to_checksum_address(address)
