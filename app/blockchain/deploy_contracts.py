"""
Smart Contract Deployment Script for Horizen L3
"""
import os
import sys
import json
from web3 import Web3
from solcx import compile_standard, install_solc
from dotenv import load_dotenv
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

# Configuration
RPC_URL = os.getenv('BLOCKCHAIN_RPC_URL')
CHAIN_ID = int(os.getenv('HORIZEN_L3_CHAIN_ID', '26514'))
PRIVATE_KEY = os.getenv('DEPLOYER_PRIVATE_KEY')
DEPLOYER_ADDRESS = os.getenv('DEPLOYER_ADDRESS')

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Check connection
if not w3.is_connected():
    raise Exception("Failed to connect to Horizen L3 RPC")

print(f"✅ Connected to Horizen L3")
print(f"📍 Chain ID: {w3.eth.chain_id}")
print(f"🔑 Deployer Address: {DEPLOYER_ADDRESS}")
print(f"💰 Balance: {w3.from_wei(w3.eth.get_balance(DEPLOYER_ADDRESS), 'ether')} ETH")

def compile_contract(contract_name, source_file=None):
    """Compile a Solidity contract"""
    print(f"\n📝 Compiling {contract_name}...")

    if source_file is None:
        source_file = contract_name

    contract_path = Path(__file__).parent / 'contracts' / f'{source_file}.sol'

    with open(contract_path, 'r') as file:
        contract_source = file.read()

    # Install Solidity compiler version
    install_solc('0.8.20')

    # Compile contract
    compiled_sol = compile_standard(
        {
            "language": "Solidity",
            "sources": {f"{source_file}.sol": {"content": contract_source}},
            "settings": {
                "outputSelection": {
                    "*": {
                        "*": ["abi", "metadata", "evm.bytecode", "evm.sourceMap"]
                    }
                },
                "optimizer": {
                    "enabled": True,
                    "runs": 200
                }
            },
        },
        solc_version="0.8.20",
    )

    # Extract ABI and bytecode
    contract_interface = compiled_sol['contracts'][f'{source_file}.sol'][contract_name]
    abi = contract_interface['abi']
    bytecode = contract_interface['evm']['bytecode']['object']

    # Save ABI to file
    abi_path = Path(__file__).parent / 'contracts' / f'{contract_name}.json'
    with open(abi_path, 'w') as f:
        json.dump(abi, f, indent=2)

    print(f"✅ {contract_name} compiled successfully")
    print(f"💾 ABI saved to {abi_path}")

    return abi, bytecode

def deploy_contract(contract_name, abi, bytecode, *constructor_args):
    """Deploy a contract to BASE Sepolia"""
    print(f"\n🚀 Deploying {contract_name}...")

    # Create contract object
    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)

    # Build transaction
    nonce = w3.eth.get_transaction_count(DEPLOYER_ADDRESS)

    # Estimate gas
    gas_estimate = Contract.constructor(*constructor_args).estimate_gas({
        'from': DEPLOYER_ADDRESS
    })

    # Build deployment transaction
    transaction = Contract.constructor(*constructor_args).build_transaction({
        'chainId': CHAIN_ID,
        'gas': gas_estimate + 50000,  # Add buffer
        'gasPrice': w3.eth.gas_price,
        'nonce': nonce,
        'from': DEPLOYER_ADDRESS
    })

    # Sign transaction
    signed_txn = w3.eth.account.sign_transaction(transaction, private_key=PRIVATE_KEY)

    # Send transaction
    print(f"📤 Sending transaction...")
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    print(f"⏳ Transaction hash: {tx_hash.hex()}")

    # Wait for receipt
    print(f"⏳ Waiting for confirmation...")
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    contract_address = tx_receipt['contractAddress']

    print(f"✅ {contract_name} deployed successfully!")
    print(f"📍 Contract Address: {contract_address}")
    print(f"⛽ Gas Used: {tx_receipt['gasUsed']}")
    print(f"🔗 View on Explorer: {os.getenv('BASE_SEPOLIA_EXPLORER')}/address/{contract_address}")

    return contract_address

def update_env_file(contract_name, address):
    """Update .env file with deployed contract address"""
    env_path = Path(__file__).parent.parent.parent / '.env'

    with open(env_path, 'r') as f:
        lines = f.readlines()

    # Update the appropriate line
    env_var_name = f"{contract_name.upper().replace('TEST', 'TESTZEN_TOKEN' if 'ZEN' in contract_name else '')}_ADDRESS"
    if 'ZEN' in contract_name:
        env_var_name = 'TESTZEN_TOKEN_ADDRESS'
    elif 'Citizenship' in contract_name:
        env_var_name = 'CITIZENSHIP_NFT_ADDRESS'

    updated = False
    for i, line in enumerate(lines):
        if line.startswith(env_var_name):
            lines[i] = f"{env_var_name}={address}\n"
            updated = True
            break

    with open(env_path, 'w') as f:
        f.writelines(lines)

    print(f"✅ Updated .env file: {env_var_name}={address}")

def main():
    """Deploy all contracts"""
    print("=" * 80)
    print("🌐 BASE Sepolia Smart Contract Deployment")
    print("=" * 80)

    # Deploy TestZEN
    print("\n" + "=" * 80)
    print("1️⃣  DEPLOYING TESTZEN TOKEN")
    print("=" * 80)

    zen_abi, zen_bytecode = compile_contract('TestZEN', 'TestZEN_Simple')
    zen_address = deploy_contract('TestZEN', zen_abi, zen_bytecode)
    update_env_file('TestZEN', zen_address)

    # Deploy CitizenshipNFT
    print("\n" + "=" * 80)
    print("2️⃣  DEPLOYING CITIZENSHIP NFT")
    print("=" * 80)

    nft_abi, nft_bytecode = compile_contract('CitizenshipNFT', 'CitizenshipNFT_Simple')
    nft_address = deploy_contract('CitizenshipNFT', nft_abi, nft_bytecode)
    update_env_file('CitizenshipNFT', nft_address)

    # Summary
    print("\n" + "=" * 80)
    print("🎉 DEPLOYMENT COMPLETE!")
    print("=" * 80)
    print(f"\n📋 Contract Addresses:")
    print(f"   • TestZEN Token: {zen_address}")
    print(f"   • CitizenshipNFT: {nft_address}")
    print(f"\n🔗 View on BASE Sepolia Explorer:")
    print(f"   • {os.getenv('BASE_SEPOLIA_EXPLORER')}/address/{zen_address}")
    print(f"   • {os.getenv('BASE_SEPOLIA_EXPLORER')}/address/{nft_address}")
    print("\n✅ Contract addresses have been saved to .env file")
    print("=" * 80)

if __name__ == '__main__':
    main()
