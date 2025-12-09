# Tactizen Privacy-Preserving Voting System

## Overview

Tactizen implements a cutting-edge anonymous voting system using **zkSNARKs** (Zero-Knowledge Succinct Non-Interactive Arguments of Knowledge) with blockchain verification on **zkVerify**. This system ensures that votes are:

- **Anonymous**: No one can link a vote to a voter
- **Verifiable**: Anyone can verify that all votes are valid
- **Tamper-proof**: Votes are recorded on the blockchain and cannot be altered
- **Double-vote resistant**: Each voter can only vote once per election

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Cryptographic Primitives](#cryptographic-primitives)
3. [Voter Registration Process](#voter-registration-process)
4. [Vote Casting Process](#vote-casting-process)
5. [Blockchain Verification](#blockchain-verification)
6. [Vote Counting & Results](#vote-counting--results)
7. [Security Properties](#security-properties)
8. [Technical Implementation](#technical-implementation)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TACTIZEN VOTING SYSTEM                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌───────────┐ │
│  │   VOTER     │     │   SERVER    │     │  zkVERIFY   │     │ BLOCKCHAIN│ │
│  │  (Browser)  │────▶│   (Flask)   │────▶│  (Testnet)  │────▶│  (Record) │ │
│  └─────────────┘     └─────────────┘     └─────────────┘     └───────────┘ │
│        │                   │                   │                   │       │
│        │  1. Generate      │  2. Store         │  3. Verify       │       │
│        │     Secrets       │     Commitment    │     ZK Proof     │       │
│        │                   │                   │                   │       │
│        │  4. Generate      │  5. Validate      │  6. Record       │       │
│        │     ZK Proof      │     & Submit      │     Proof Hash   │       │
│        │                   │                   │                   │       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Description | Key Files |
|-----------|-------------|-----------|
| **Circom Circuits** | Define the mathematical constraints for valid votes | `circuits/anonymous_vote.circom` |
| **Merkle Tree Service** | Manages voter registrations in a cryptographic tree | `app/services/merkle_service.py` |
| **ZK Routes** | API endpoints for registration and voting | `app/government/zk_routes.py` |
| **zkVerify Service** | Submits proofs to zkVerify blockchain | `app/services/zkverify_service.py` |
| **Client-Side JS** | Generates proofs in the browser | `app/static/js/zk_voting.js` |

---

## Cryptographic Primitives

### Poseidon Hash Function

We use **Poseidon**, a zkSNARK-friendly hash function optimized for arithmetic circuits. Unlike SHA-256, Poseidon operates natively over prime fields, making it extremely efficient inside zero-knowledge proofs.

```
commitment = Poseidon(secret, nullifierSecret)
nullifier = Poseidon(secret, nullifierSecret, electionId)
```

### Merkle Trees

A **Merkle tree** is a binary tree where:
- Each leaf is a voter's commitment
- Each internal node is the hash of its two children
- The **root** represents all registered voters

**Properties:**
- Tree depth: 14 levels (supports up to 16,384 voters per election)
- Proving membership requires only 14 hash values (the "Merkle path")
- Adding a voter updates only O(log n) nodes

```
                    ROOT
                   /    \
                 H01     H23
                /   \   /   \
              H0    H1 H2    H3
              |     |  |     |
            Leaf0 Leaf1 Leaf2 Leaf3
            (C1)  (C2)  (C3)  (C4)    ← Voter Commitments
```

### zkSNARKs (Groth16)

We use the **Groth16** proving system:
- **Proving time**: ~2-3 seconds in browser (WebAssembly)
- **Proof size**: ~200 bytes
- **Verification time**: ~10ms
- **Trusted setup**: Powers of Tau ceremony (Hermez)

---

## Voter Registration Process

### Step 1: Generate Secrets (Client-Side)

When a voter decides to participate in an election, their browser generates two cryptographic secrets:

```javascript
// In browser (app/static/js/zk_voting.js)
const secret = generateRandomFieldElement();         // 256-bit random
const nullifierSecret = generateRandomFieldElement(); // 256-bit random
```

**Important**: These secrets are stored ONLY in the voter's browser (`localStorage`). The server NEVER sees them.

### Step 2: Compute Commitment

The browser computes a **commitment** - a hash that "commits" to the secrets without revealing them:

```javascript
// Commitment = Poseidon(secret, nullifierSecret)
const commitment = await poseidonHash([secret, nullifierSecret]);
```

### Step 3: Register Commitment

The browser sends ONLY the commitment to the server:

```http
POST /api/zk/register
{
    "election_type": "presidential",
    "scope_id": 1,
    "commitment": "0x1a2b3c4d..."
}
```

### Step 4: Add to Merkle Tree

The server adds the commitment to the Merkle tree:

```python
# In app/services/merkle_service.py
def add_voter_to_tree(election_type, scope_id, commitment):
    tree = get_or_create_tree(election_type, scope_id)
    tree_data = MerkleTree.deserialize(tree.tree_data)
    leaf_index = service.add_leaf(tree_data, commitment)
    tree.root = service.compute_root(tree_data['leaves'])
    tree.num_leaves = len(tree_data['leaves'])
    return leaf_index
```

### Step 5: Store Voter Record

```python
# Database record (NO secrets stored)
VoterCommitment:
    user_id: 123          # Only for preventing duplicate registrations
    election_type: "presidential"
    scope_id: 1
    commitment: "0x1a2b3c4d..."
    leaf_index: 42        # Position in Merkle tree
```

### What the Server Knows vs. Doesn't Know

| Server Knows | Server Does NOT Know |
|--------------|---------------------|
| User registered for election | User's secret values |
| User's commitment hash | How to generate valid proofs |
| User's leaf index in tree | Which vote belongs to which user |

---

## Vote Casting Process

### Step 1: Get Merkle Proof

The voter requests their Merkle proof (path from their leaf to the root):

```http
POST /api/zk/merkle-proof
{
    "election_type": "presidential",
    "scope_id": 1
}

Response:
{
    "pathElements": ["0xabc...", "0xdef...", ...],  // 14 sibling hashes
    "pathIndices": [0, 1, 1, 0, ...],               // 14 left/right flags
    "merkleRoot": "0x123...",
    "leafIndex": 42
}
```

### Step 2: Compute Nullifier

The nullifier is unique per voter per election - it prevents double voting without revealing identity:

```javascript
// Nullifier = Poseidon(secret, nullifierSecret, electionId)
const nullifier = await poseidonHash([secret, nullifierSecret, electionId]);
```

### Step 3: Generate ZK Proof

The browser generates a zero-knowledge proof using snarkjs:

```javascript
// Load circuit files
const wasmPath = '/static/circuits/anonymous_vote.wasm';
const zkeyPath = '/static/circuits/anonymous_vote.zkey';

// Prepare witness (circuit inputs)
const witness = {
    // Private inputs (known only to voter)
    secret: voterData.secret,
    nullifierSecret: voterData.nullifierSecret,
    pathElements: merkleProof.pathElements,
    pathIndices: merkleProof.pathIndices,

    // Public inputs (visible to everyone)
    merkleRoot: merkleProof.merkleRoot,
    electionId: electionId,
    candidateId: selectedCandidate,
    numCandidates: totalCandidates
};

// Generate proof (takes ~2-3 seconds)
const { proof, publicSignals } = await snarkjs.groth16.fullProve(
    witness, wasmPath, zkeyPath
);
```

### Step 4: Submit Vote

The browser sends the proof and public signals to the server:

```http
POST /api/zk/vote
{
    "election_type": "presidential",
    "election_id": 5,
    "proof": {
        "pi_a": [...],
        "pi_b": [...],
        "pi_c": [...],
        "protocol": "groth16",
        "curve": "bn128"
    },
    "public_signals": [
        "0x123...",  // merkleRoot
        "5",         // electionId
        "3",         // candidateId (vote choice)
        "7",         // numCandidates
        "0xabc..."   // nullifier
    ]
}
```

### Step 5: Server Validation

The server performs these checks:

```python
# In app/government/zk_routes.py

# 1. Check nullifier hasn't been used (prevents double voting)
existing = ZKVote.query.filter_by(nullifier=nullifier).first()
if existing:
    return error("Vote already cast")

# 2. Verify election exists and is active
config = ZKElectionConfig.query.filter_by(
    election_type=election_type,
    election_id=election_id
).first()
if not config.is_voting_open:
    return error("Voting is not open")

# 3. Verify Merkle root matches (current or frozen)
if merkle_root != config.frozen_merkle_root:
    if merkle_root != current_tree.root:
        return error("Invalid Merkle root")

# 4. Verify candidate ID is valid
if candidate_id < 0 or candidate_id > num_candidates:
    return error("Invalid candidate")
```

### Step 6: Blockchain Verification

The proof is submitted to zkVerify for on-chain verification:

```python
# In app/services/zkverify_service.py

async def verify_proof(proof, public_signals, verification_key):
    # Create zkVerify session
    session = await zkVerifySession.start() \
        .Custom('wss://zkverify-volta-rpc.zkverify.io') \
        .withAccount(seed_phrase)

    # Submit proof
    result = await session.verify() \
        .groth16() \
        .waitForPublishedAttestation() \
        .execute({
            vk: verification_key,
            proof: proof,
            publicSignals: public_signals
        })

    return {
        'success': True,
        'tx_hash': result.txHash,
        'block_number': result.blockNumber
    }
```

### Step 7: Record Vote

Once verified on zkVerify, the vote is stored:

```python
# Database record (NO voter identity)
ZKVote:
    election_type: "presidential"
    election_id: 5
    nullifier: "0xabc..."      # Unique per voter per election
    vote_choice: 3             # Candidate ID
    merkle_root: "0x123..."    # Voter registry snapshot
    zkverify_tx_hash: "0xdef..." # Blockchain proof
    zkverify_block: 12345
    proof_verified: True
    proof_data: {...}          # Raw proof for transparency
```

---

## Blockchain Verification

### zkVerify Network

**zkVerify** is a specialized blockchain for verifying zero-knowledge proofs:

- **Network**: Volta Testnet
- **RPC**: `wss://zkverify-volta-rpc.zkverify.io`
- **Explorer**: `https://zkverify-testnet.subscan.io`

### What Gets Recorded

Each vote proof is recorded on-chain:

| Field | Description |
|-------|-------------|
| `tx_hash` | Unique transaction identifier |
| `block_number` | Block containing the proof |
| `proof_hash` | Hash of the ZK proof |
| `public_signals` | Merkle root, election ID, candidate ID, nullifier |
| `verification_result` | True if proof is valid |

### Verification Process

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Tactizen  │────▶│   zkVerify  │────▶│  Permanent  │
│   Server    │     │   Network   │     │   Record    │
└─────────────┘     └─────────────┘     └─────────────┘
      │                    │                   │
      │ 1. Submit proof    │                   │
      │    + pub signals   │                   │
      │                    │                   │
      │ 2. Verify proof    │                   │
      │    against VK      │                   │
      │                    │                   │
      │ 3. Return tx_hash  │                   │
      │    + block_num     │                   │
      │                    │                   │
      └────────────────────┴───────────────────┘
```

### Explorer Link

Each vote has a verifiable link:
```
https://zkverify-testnet.subscan.io/extrinsic/{tx_hash}
```

---

## Vote Counting & Results

### How Votes Are Counted

```python
# In app/government/zk_routes.py - /api/zk/results endpoint

def get_results(election_type, election_id):
    # Query all verified votes for this election
    votes = ZKVote.query.filter_by(
        election_type=election_type,
        election_id=election_id,
        proof_verified=True
    ).all()

    # Count votes per candidate
    vote_counts = {}
    abstentions = 0

    for vote in votes:
        if vote.vote_choice == 0:
            abstentions += 1
        else:
            candidate_id = vote.vote_choice
            vote_counts[candidate_id] = vote_counts.get(candidate_id, 0) + 1

    return {
        'total_votes': len(votes),
        'abstentions': abstentions,
        'results': vote_counts,
        'zkverify_proofs': [v.zkverify_tx_hash for v in votes]
    }
```

### What Results Show

```json
{
    "election_type": "presidential",
    "election_id": 5,
    "total_votes": 150,
    "abstentions": 5,
    "results": {
        "candidate_1": {"name": "Alice", "votes": 75, "percentage": 51.7},
        "candidate_2": {"name": "Bob", "votes": 45, "percentage": 31.0},
        "candidate_3": {"name": "Charlie", "votes": 25, "percentage": 17.2}
    },
    "winner": "Alice",
    "zkverify_proofs": [
        "https://zkverify-testnet.subscan.io/extrinsic/0x123...",
        "https://zkverify-testnet.subscan.io/extrinsic/0x456...",
        // ... one link per vote
    ]
}
```

### Verification by Anyone

Anyone can verify the election:

1. **Count votes**: Query all ZKVote records for the election
2. **Verify proofs**: Each vote has a zkVerify transaction
3. **Check uniqueness**: Each nullifier appears exactly once
4. **Audit Merkle root**: Compare against frozen registry

---

## Security Properties

### 1. Vote Anonymity

**Why votes can't be linked to voters:**

- The voter's `secret` and `nullifierSecret` never leave the browser
- The `commitment` is a one-way hash - you can't reverse it
- The `nullifier` is derived using the election ID, so it's different each election
- The Merkle proof reveals which tree the voter is in, but not which leaf

```
Voter → secret + nullifierSecret → commitment → Merkle Tree
                    ↓
                 (hidden)
                    ↓
Vote  → nullifier (unique per election) → ZKVote record
```

### 2. Double-Vote Prevention

**Why voters can only vote once:**

- The `nullifier` is deterministically computed from secrets + election ID
- The same voter ALWAYS produces the same nullifier for the same election
- The database enforces unique nullifiers
- If you try to vote twice, your nullifier is already recorded

```python
# Check in vote submission
existing = ZKVote.query.filter_by(nullifier=nullifier).first()
if existing:
    return error("You have already voted in this election")
```

### 3. Eligibility Verification

**Why only registered voters can vote:**

- Only registered commitments are in the Merkle tree
- The ZK proof verifies: "I know a secret that hashes to a commitment in this tree"
- Without a valid Merkle proof, you can't create a valid ZK proof
- The Merkle root is frozen when voting starts

### 4. Vote Integrity

**Why votes can't be modified:**

- Each vote is verified on zkVerify blockchain
- The proof includes the exact candidate ID
- Changing the vote would require a new valid proof
- Blockchain records are immutable

### 5. Censorship Resistance

**Why the server can't reject valid votes:**

- Valid proofs MUST be accepted (cryptographically enforced)
- All votes are recorded on public blockchain
- Anyone can audit the full vote set
- Missing votes would be detectable

---

## Technical Implementation

### Circuit: anonymous_vote.circom

```circom
pragma circom 2.0.0;

include "poseidon.circom";
include "mux1.circom";

template AnonymousVote(levels) {
    // Private inputs (known only to voter)
    signal input secret;
    signal input nullifierSecret;
    signal input pathElements[levels];
    signal input pathIndices[levels];

    // Public inputs (visible to all)
    signal input merkleRoot;
    signal input electionId;
    signal input candidateId;
    signal input numCandidates;

    // Public output
    signal output nullifier;

    // 1. Verify candidate is valid (0 = abstain, 1-N = candidates)
    signal validCandidate;
    validCandidate <== candidateId * (numCandidates + 1 - candidateId);
    // This is >= 0 for valid candidates (0 to numCandidates)

    // 2. Compute commitment from secrets
    component commitmentHasher = Poseidon(2);
    commitmentHasher.inputs[0] <== secret;
    commitmentHasher.inputs[1] <== nullifierSecret;
    signal commitment <== commitmentHasher.out;

    // 3. Verify Merkle proof (commitment is in the tree)
    component merkleProof = MerkleTreeChecker(levels);
    merkleProof.leaf <== commitment;
    merkleProof.root <== merkleRoot;
    for (var i = 0; i < levels; i++) {
        merkleProof.pathElements[i] <== pathElements[i];
        merkleProof.pathIndices[i] <== pathIndices[i];
    }

    // 4. Compute nullifier (unique per voter per election)
    component nullifierHasher = Poseidon(3);
    nullifierHasher.inputs[0] <== secret;
    nullifierHasher.inputs[1] <== nullifierSecret;
    nullifierHasher.inputs[2] <== electionId;
    nullifier <== nullifierHasher.out;
}

component main {public [merkleRoot, electionId, candidateId, numCandidates]}
    = AnonymousVote(14);
```

### Key Files Reference

| File | Purpose |
|------|---------|
| `circuits/anonymous_vote.circom` | Main voting proof circuit |
| `circuits/voter_commitment.circom` | Commitment generation circuit |
| `circuits/nullifier.circom` | Nullifier computation circuit |
| `app/static/circuits/*.wasm` | Compiled WebAssembly for browser |
| `app/static/circuits/*.zkey` | Proving keys (Groth16) |
| `app/models/zk_voting.py` | Database models for ZK voting |
| `app/services/merkle_service.py` | Merkle tree operations |
| `app/services/zkverify_service.py` | zkVerify blockchain integration |
| `app/government/zk_routes.py` | API endpoints for voting |
| `app/static/js/zk_voting.js` | Client-side proof generation |

---

## Election Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                      ELECTION TIMELINE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ SETUP    │───▶│ REGISTER │───▶│  VOTING  │───▶│ RESULTS  │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│       │               │               │               │         │
│   Admin sets     Voters gen      Registry is     Votes are     │
│   dates and      secrets &       FROZEN and      counted &     │
│   candidates     register        voting opens    published     │
│                  commitments                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 1: Setup
- Admin creates election with dates
- Admin sets candidates
- ZK configuration created

### Phase 2: Registration
- Voters generate secrets in browser
- Voters register commitments
- Merkle tree built incrementally

### Phase 3: Voting
- Registry is FROZEN (new registrations blocked)
- Merkle root is locked
- Voters generate proofs and cast votes
- Proofs verified on zkVerify

### Phase 4: Results
- Voting period ends
- Votes counted by candidate
- Results published with proof links
- Winner declared

---

## Summary

The Tactizen voting system achieves **true ballot secrecy** through:

1. **Client-side secrets**: Voters' private keys never leave their browser
2. **Merkle tree membership**: Prove you're registered without revealing which voter
3. **zkSNARK proofs**: Prove vote validity without revealing vote-voter link
4. **Nullifiers**: Prevent double voting without identifying voters
5. **Blockchain verification**: Permanent, tamper-proof proof records

This system provides the same privacy guarantees as a physical ballot box while adding the transparency and auditability of blockchain technology.

---

*Last updated: December 2025*
*Tactizen Recreation - Privacy-First Gaming*
