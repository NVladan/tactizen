# zkVerify Mainnet Migration

## Overview
Migration from zkVerify Volta Testnet to zkVerify Mainnet for anonymous voting proof verification.

## Network Details

| Setting | Testnet (Volta) | Mainnet |
|---------|-----------------|---------|
| RPC WebSocket | wss://zkverify-volta-rpc.zkverify.io | wss://zkverify-rpc.zkverify.io |
| Explorer | https://zkverify-testnet.subscan.io/ | https://zkverify.subscan.io/ |
| Session Method | `.Volta()` | `.zkVerify()` |
| Token | tVFY (testnet) | VFY (mainnet) |

## Completed Tasks

### 1. Environment Configuration
- [x] Updated `.env` with mainnet RPC and explorer URLs
- [x] Added `ZKVERIFY_MAINNET` toggle flag (true/false)
- [x] Updated `.env.example` with mainnet defaults

### 2. Backend Code Updates
- [x] `app/services/zkverify_service.py`:
  - Updated default RPC URL to mainnet
  - Updated default explorer URL to mainnet
  - Added `use_mainnet` flag from environment
  - Changed session initialization from `.Testnet()` to conditional `.zkVerify()` / `.Volta()`
  - Updated groth16 verification to use new API: `groth16({ library: Library.snarkjs, curve: CurveType.bn128 })`

### 3. zkverifyjs Package
- [x] Updated zkverifyjs to latest version (2.1.0)
  - Now supports `.zkVerify()` method for mainnet
  - New groth16 API requires object parameter with `library` and `curve` properties

## Pending Tasks

### 1. Fund zkVerify Wallet
- [ ] **BLOCKER:** Need VFY tokens on zkVerify mainnet (Substrate chain)
- [ ] Current VFY location: Base network (EVM) - WRONG NETWORK
- [ ] VFY needed on: zkVerify mainnet (Substrate) - CORRECT NETWORK

### 2. Get VFY on zkVerify Mainnet
- [ ] **Option A (Recommended):** Withdraw from Gate.io to zkVerify mainnet
  - Gate.io supports zkVerify mainnet withdrawal
  - 24-hour hold for new deposits (waiting period active)
  - Withdraw to Talisman Substrate address (not ETH address)

- [ ] **Option B:** Bridge from Base to zkVerify
  - Complex multi-step process
  - Base → VFlow (LayerZero) → zkVerify mainnet (XCM teleport)
  - No simple UI available yet

### 3. Post-Funding Tasks
- [ ] Change `.env` to `ZKVERIFY_MAINNET=true`
- [ ] Test anonymous voting with mainnet VFY
- [ ] Verify proof submissions on zkVerify mainnet explorer

## Wallet Addresses

**Talisman Wallets:**
- Substrate (zkVerify): Use "Tactizen" account for zkVerify mainnet VFY
- Ethereum/Base: `0x85A0b8417E0aE13972e390875a8a90f0793E174F` (where VFY on Base is)

**Important:** These are DIFFERENT addresses on DIFFERENT networks!

## VFY Token Information

- **VFY on Base:** `0xa749dE6c28262B7ffbc5De27dC845DD7eCD2b358` (ERC-20, LayerZero OFT)
- **VFY on zkVerify:** Native Substrate token (not EVM)

## Current Configuration (Testnet - Active)

```env
# zkVerify Configuration (Anonymous Voting) - TESTNET
ZKVERIFY_RPC_WS=wss://zkverify-volta-rpc.zkverify.io
ZKVERIFY_EXPLORER=https://zkverify-testnet.subscan.io/
ZKVERIFY_MAINNET=false
ZKVERIFY_SEED_PHRASE=<your-seed-phrase>
```

## Mainnet Configuration (Ready - Needs Funding)

```env
# zkVerify Configuration (Anonymous Voting) - MAINNET
ZKVERIFY_RPC_WS=wss://zkverify-rpc.zkverify.io
ZKVERIFY_EXPLORER=https://zkverify.subscan.io/
ZKVERIFY_MAINNET=true
ZKVERIFY_SEED_PHRASE=<your-seed-phrase>
```

## Supported Wallets for zkVerify

1. **Talisman** (currently using)
   - Supports both Polkadot/Substrate and Ethereum
   - Enable zkVerify network in Settings → Networks & Tokens → Networks

2. **SubWallet**
   - Alternative option
   - Good mobile support

## Anonymous Voting Flow

1. User generates ZK proof in browser (snarkjs)
2. Proof submitted to backend
3. Backend uses zkverifyjs to submit proof to zkVerify network
4. zkVerify verifies the groth16 proof on-chain
5. Backend receives verification result and records vote

## Code Reference

**zkverify_service.py** - Key changes for mainnet:
```python
# Session initialization
session = await zkVerifySession.start()
    .zkVerify()  # mainnet (was .Volta() for testnet)
    .withAccount(seed_phrase);

# Proof verification
const { events, transactionResult } = await session.verify()
    .groth16({
        library: Library.snarkjs,
        curve: CurveType.bn128
    })
    .execute({
        proofData: {
            vk: verification_key,
            proof: proof,
            publicSignals: public_signals
        }
    });
```

## Timeline

- **Gate.io withdrawal available:** ~24 hours from deposit (December 10, 2025)
- **Mainnet switch:** After VFY funded on zkVerify mainnet

## Notes

- zkVerify is a Substrate-based blockchain (Polkadot ecosystem)
- VFY on Base (EVM) cannot be used directly - needs bridging
- Each proof verification costs a small amount of VFY
- Testnet (Volta) works identically for development/testing
