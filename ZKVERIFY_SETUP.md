# zkVerify Anonymous Voting Setup

This document explains how to set up the zkVerify anonymous voting system for Tactizen.

## Overview

The anonymous voting system uses zero-knowledge proofs (zkSNARKs) to allow players to vote in elections without revealing their identity. Proofs are verified on the zkVerify blockchain (Volta testnet).

**Elections with anonymous voting:**
- Presidential elections
- Congressional elections
- Party president elections

**Elections with transparent voting (for accountability):**
- Law voting in Congress

**Configuration:**
- Merkle tree depth: 14 (supports up to 16,384 voters per election)
- Max candidates per election: 50

## Production Server Setup

### Prerequisites

1. **Python 3.10+** with Flask and dependencies
2. **Node.js 18+**
3. **MySQL/MariaDB** database

### Installation Steps

#### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

#### 2. Install Node.js dependencies

```bash
npm install
```

This installs:
- `zkverifyjs` - SDK for submitting proofs to zkVerify blockchain
- `snarkjs` - Zero-knowledge proof library

#### 3. Configure environment variables

Add to your `.env` file:

```env
# zkVerify Configuration (Anonymous Voting)
ZKVERIFY_RPC_WS=wss://zkverify-volta-rpc.zkverify.io
ZKVERIFY_EXPLORER=https://zkverify-testnet.subscan.io/
ZKVERIFY_SEED_PHRASE=your twelve word seed phrase here
```

**Getting a seed phrase:**
1. Install [Talisman wallet](https://www.talisman.xyz/) or [Polkadot.js extension](https://polkadot.js.org/extension/)
2. Create a new Polkadot account
3. Copy the 12-word seed phrase
4. Get testnet tokens from [zkVerify faucet](https://www.faucy.com/zkverify-volta)

#### 4. Run database migrations

```bash
flask db upgrade
```

This creates the ZK voting tables:
- `voter_commitment` - Stores voter commitments
- `merkle_tree` - Stores Merkle tree state
- `zk_vote` - Stores anonymous votes
- `zk_election_config` - Election configuration

#### 5. Verify circuit files exist

Check that these files exist in `app/static/circuits/`:
- `anonymous_vote.wasm`
- `anonymous_vote.zkey`
- `anonymous_vote_verification_key.json`
- `voter_commitment.wasm`
- `voter_commitment.zkey`
- `voter_commitment_verification_key.json`
- `nullifier.wasm`
- `nullifier.zkey`
- `nullifier_verification_key.json`

These files are pre-compiled and included in the repository.

## Development Setup (Recompiling Circuits)

Only needed if you modify the Circom circuits.

### Prerequisites (WSL on Windows or Linux)

1. **Rust** - `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
2. **Circom** - Build from source:
   ```bash
   git clone https://github.com/iden3/circom.git
   cd circom
   cargo build --release
   cargo install --path circom
   ```
3. **Node.js** - `sudo apt install nodejs npm`
4. **Build tools** - `sudo apt install build-essential`

### Compile Circuits

```bash
cd circuits
npm install circomlib snarkjs
./compile_circuits.sh
```

This will:
1. Compile Circom circuits to R1CS format
2. Download Powers of Tau ceremony file
3. Generate proving keys (.zkey)
4. Generate verification keys (.json)
5. Copy artifacts to `app/static/circuits/`

## How It Works

### Voter Registration
1. User clicks "Register for Anonymous Voting"
2. Browser generates random secrets (stored in localStorage)
3. Browser computes commitment = Poseidon(secret, nullifierSecret)
4. Commitment is sent to server and added to Merkle tree
5. User receives their leaf index

### Casting a Vote
1. User selects a candidate and clicks "Cast Anonymous Vote"
2. Browser retrieves Merkle proof from server
3. Browser generates ZK proof proving:
   - Voter is in the Merkle tree (registered)
   - Vote is for a valid candidate
   - Nullifier is correctly computed
4. Proof is sent to server
5. Server submits proof to zkVerify blockchain
6. If verified, vote is recorded (only nullifier + choice, NO identity)

### Privacy Guarantees
- Server never sees voter's secrets
- Nullifier prevents double-voting without revealing identity
- Merkle proof proves registration without revealing which leaf
- All proofs publicly verifiable on zkVerify blockchain

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/zk/register` | POST | Register voter commitment |
| `/api/zk/registration-status` | GET | Check if registered |
| `/api/zk/merkle-proof` | POST | Get Merkle proof for voting |
| `/api/zk/vote` | POST | Cast anonymous vote |
| `/api/zk/results/<type>/<id>` | GET | Get election results |
| `/api/zk/config/<type>/<id>` | GET/POST | Election configuration |

## Troubleshooting

### "Node not found" error
Install Node.js: `sudo apt install nodejs npm`

### Proof verification timeout
- Check zkVerify testnet status
- Ensure seed phrase has testnet tokens
- Check network connectivity to `wss://zkverify-volta-rpc.zkverify.io`

### "Not registered" error when voting
User must register before voting. Registration creates the cryptographic commitment.

### Browser localStorage cleared
If user clears browser data, they lose their voting secrets. They would need to re-register for future elections.

## zkVerify Resources

- [zkVerify Documentation](https://docs.zkverify.io/)
- [zkVerify Testnet Explorer](https://zkverify-testnet.subscan.io/)
- [zkVerify Faucet](https://www.faucy.com/zkverify-volta)
- [zkVerifyJS NPM](https://www.npmjs.com/package/zkverifyjs)
