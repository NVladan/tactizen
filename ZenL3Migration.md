# Horizen L3 Mainnet Migration

## Overview
Migration from Horizen L3 Testnet to Horizen L3 Mainnet (launched December 9, 2025).

## Network Details

| Setting | Testnet (Old) | Mainnet (New) |
|---------|---------------|---------------|
| RPC URL | https://horizen-testnet.rpc.caldera.xyz/http | https://horizen.calderachain.xyz/http |
| WebSocket | wss://horizen-testnet.rpc.caldera.xyz/ws | wss://horizen.calderachain.xyz/ws |
| Chain ID | 2651420 (0x28751c) | 26514 (0x6792) |
| Explorer | https://horizen-testnet.explorer.caldera.xyz | https://horizen.calderaexplorer.xyz |
| L1 (Settlement) | Base Sepolia | Base Mainnet (8453) |

## Completed Tasks

### 1. Environment Configuration
- [x] Updated `.env` with mainnet RPC, WebSocket, Chain ID, and Explorer URLs
- [x] Updated `.env.example` with mainnet defaults

### 2. Backend Code Updates
- [x] `app/blockchain/deploy_contracts.py` - Updated default chain ID to 26514
- [x] `app/blockchain/nft_contract.py` - Updated default RPC URL
- [x] `app/blockchain/marketplace_contract.py` - Updated default RPC URL
- [x] `app/blockchain/web3_config.py` - Updated default RPC URL and error messages
- [x] `app/blockchain/zen_transfers.py` - Updated default chain ID
- [x] `app/routes/wallet_routes.py` - Updated default RPC URLs
- [x] `app/routes/nft_routes.py` - Updated chain ID hex value (0x6792)
- [x] `app/main/zen_market_routes.py` - Updated default explorer URL
- [x] `app/main/zen_market_api.py` - Updated default explorer URL

### 3. Frontend/Template Updates
- [x] `app/templates/wallet/connect.html` - Updated network info, chain ID, RPC, explorer
- [x] `app/templates/index.html` - Updated MetaMask network configuration
- [x] `app/templates/zen_market.html` - Updated chain ID and network error messages
- [x] `app/templates/nft/inventory.html` - Updated chain ID and explorer links
- [x] `app/templates/company/view_company.html` - Updated explorer links
- [x] `app/static/js/marketplace.js` - Updated contract addresses

### 4. Hardhat Configuration
- [x] `hardhat.config.js` - Updated horizenL3 network with mainnet RPC, chain ID, and explorer URLs

### 5. Infrastructure
- [x] Bridged 0.005 ETH from Base to Horizen L3 mainnet for gas
- [x] Deployer wallet funded: `0xe928a273C83c80445adF89a880D0c7cc8Ee089b0`

### 6. Contract Deployment (Completed Dec 9, 2025)
- [x] Deployed custom ZEN token (Horizen, 21M max supply)
- [x] Deployed GameNFT contract
- [x] Deployed NFTMarketplace contract (5% fee)
- [x] Verified all contracts on explorer

## Contract Addresses (Mainnet - LIVE)

```env
# Horizen L3 Mainnet Contracts
ZEN_TOKEN_ADDRESS=0x070040A826B586b58569750ED43cb5979b171e8d
NFT_CONTRACT_ADDRESS=0x57e277b2d887C3C749757e36F0B6CFad32E00e8A
CITIZENSHIP_NFT_ADDRESS=0x57e277b2d887C3C749757e36F0B6CFad32E00e8A
MARKETPLACE_CONTRACT_ADDRESS=0x82F89212432Ae4675C8B84Cb2bE992E9B1dC0E3b
```

## ZEN Token Details

- **Name:** Horizen
- **Symbol:** ZEN
- **Total Supply:** 21,000,000 (fixed max, no minting)
- **Decimals:** 18
- **Contract:** [View on Explorer](https://horizen.calderaexplorer.xyz/address/0x070040A826B586b58569750ED43cb5979b171e8d#code)

## Bridge Information

**Horizen L3 Bridge:** https://horizen.hub.caldera.xyz/bridge
- Bridges ETH from Base Mainnet to Horizen L3 Mainnet
- Uses native Optimism bridge (OptimismPortalProxy)
- Estimated time: ~3 minutes

## Deployment Commands

```bash
# Compile contracts
npx hardhat compile

# Deploy ZEN Token
npx hardhat run scripts/deploy-zen.js --network horizenL3

# Deploy GameNFT
npx hardhat run scripts/deploy-nft.js --network horizenL3

# Deploy Marketplace
npx hardhat run scripts/deploy-marketplace.js --network horizenL3

# Verify contract (example)
npx hardhat verify --network horizenL3 <CONTRACT_ADDRESS> <CONSTRUCTOR_ARGS>
```

## Notes

- Horizen L3 is an OP Stack rollup settling on Base Mainnet
- Gas fees are very low on L3 (~0.001 gwei)
- 0.005 ETH should be sufficient for multiple contract deployments and transactions
- ZEN token has fixed supply - no additional minting possible
