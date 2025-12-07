# zkVerify Anonymous Voting Implementation Plan

## Executive Summary

This plan outlines the implementation of zero-knowledge proof (zkSNARK) based anonymous voting for Tactizen using zkVerify as the verification layer. The system will allow players to cast votes that are:
- **Anonymous**: No one can link a vote to a specific voter
- **Verifiable**: Anyone can verify votes are valid without knowing who cast them
- **Non-duplicable**: Each eligible voter can only vote once
- **Transparent**: Vote tallies are publicly auditable

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TACTIZEN VOTING SYSTEM                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │   VOTER      │    │   BROWSER    │    │   BACKEND    │                  │
│  │   (Player)   │───>│   (SnarkJS)  │───>│   (Flask)    │                  │
│  └──────────────┘    └──────────────┘    └──────────────┘                  │
│         │                   │                   │                          │
│         │ 1. Get commitment │                   │                          │
│         │    (secret+null)  │                   │                          │
│         ▼                   │                   │                          │
│  ┌──────────────┐           │                   │                          │
│  │  REGISTRATION│           │                   │                          │
│  │  Merkle Tree │<──────────┘                   │                          │
│  └──────────────┘                               │                          │
│         │                                       │                          │
│         │ 2. Generate ZK Proof                  │                          │
│         │    (in browser)                       │                          │
│         ▼                                       ▼                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │   ZK PROOF   │───>│  zkVerify    │<───│  zkVerifyJS  │                  │
│  │   + Vote     │    │  Testnet     │    │  (Backend)   │                  │
│  └──────────────┘    └──────────────┘    └──────────────┘                  │
│                             │                                              │
│                             │ 3. Proof verified on-chain                   │
│                             ▼                                              │
│                      ┌──────────────┐                                      │
│                      │  Tactizen DB │                                      │
│                      │  (Vote Tally)│                                      │
│                      └──────────────┘                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Voting Types to Implement (Priority Order)

### Phase 1: Law Voting (Congressional)
- **Privacy Need**: HIGH - Current system shows exactly how each politician voted
- **Voter Pool**: Small (20 congress members + 1 president per country)
- **Complexity**: LOW - Binary vote (For/Against)
- **Impact**: Removes political retaliation risk

### Phase 2: Presidential Elections
- **Privacy Need**: MEDIUM - Vote counts shown but not individual votes
- **Voter Pool**: Large (all citizens)
- **Complexity**: MEDIUM - Multiple candidates
- **Impact**: True secret ballot democracy

### Phase 3: Party Elections
- **Privacy Need**: MEDIUM
- **Voter Pool**: Medium (party members)
- **Complexity**: MEDIUM
- **Impact**: Internal party democracy

### Phase 4: Peace Treaty Voting
- **Privacy Need**: HIGH - Sensitive wartime decisions
- **Voter Pool**: Small (congress of both countries)
- **Complexity**: LOW - Binary vote
- **Impact**: Prevents pressure/intimidation during wars

---

## Technical Implementation

### 1. Circom Circuit Design

#### 1.1 Voter Registration Circuit
```circom
pragma circom 2.0.0;

include "circomlib/poseidon.circom";

// Generates a commitment from voter's secret and nullifier
template VoterCommitment() {
    signal input secret;           // Voter's private secret (random 256-bit)
    signal input nullifierSecret;  // Used to derive nullifier per election
    signal output commitment;      // Public commitment stored in Merkle tree

    component hasher = Poseidon(2);
    hasher.inputs[0] <== secret;
    hasher.inputs[1] <== nullifierSecret;
    commitment <== hasher.out;
}

component main = VoterCommitment();
```

#### 1.2 Anonymous Vote Circuit (Binary - For Laws/Peace)
```circom
pragma circom 2.0.0;

include "circomlib/poseidon.circom";
include "circomlib/mux1.circom";
include "circomlib/comparators.circom";

// Merkle tree inclusion proof
template MerkleProof(levels) {
    signal input leaf;
    signal input pathElements[levels];
    signal input pathIndices[levels];
    signal output root;

    component hashers[levels];
    component mux[levels];

    signal levelHashes[levels + 1];
    levelHashes[0] <== leaf;

    for (var i = 0; i < levels; i++) {
        hashers[i] = Poseidon(2);
        mux[i] = Mux1();

        mux[i].c[0] <== levelHashes[i];
        mux[i].c[1] <== pathElements[i];
        mux[i].s <== pathIndices[i];

        hashers[i].inputs[0] <== mux[i].out;
        hashers[i].inputs[1] <== pathElements[i] - mux[i].out + levelHashes[i];

        levelHashes[i + 1] <== hashers[i].out;
    }

    root <== levelHashes[levels];
}

// Main anonymous voting circuit
template AnonymousVote(merkleDepth) {
    // Private inputs
    signal input secret;              // Voter's secret
    signal input nullifierSecret;     // Nullifier derivation secret
    signal input pathElements[merkleDepth];
    signal input pathIndices[merkleDepth];

    // Public inputs
    signal input merkleRoot;          // Current voter registry root
    signal input electionId;          // Unique election identifier
    signal input vote;                // 0 = Against, 1 = For
    signal input nullifier;           // Prevents double voting

    // Verify vote is binary (0 or 1)
    signal voteBinary;
    voteBinary <== vote * (1 - vote);
    voteBinary === 0;

    // Compute commitment
    component commitmentHasher = Poseidon(2);
    commitmentHasher.inputs[0] <== secret;
    commitmentHasher.inputs[1] <== nullifierSecret;

    // Verify Merkle proof
    component merkleProof = MerkleProof(merkleDepth);
    merkleProof.leaf <== commitmentHasher.out;
    for (var i = 0; i < merkleDepth; i++) {
        merkleProof.pathElements[i] <== pathElements[i];
        merkleProof.pathIndices[i] <== pathIndices[i];
    }
    merkleRoot === merkleProof.root;

    // Compute nullifier (unique per election, prevents double voting)
    component nullifierHasher = Poseidon(3);
    nullifierHasher.inputs[0] <== secret;
    nullifierHasher.inputs[1] <== nullifierSecret;
    nullifierHasher.inputs[2] <== electionId;
    nullifier === nullifierHasher.out;
}

component main {public [merkleRoot, electionId, vote, nullifier]} = AnonymousVote(20);
```

#### 1.3 Multi-Candidate Vote Circuit (For Elections)
```circom
pragma circom 2.0.0;

include "circomlib/poseidon.circom";
include "circomlib/comparators.circom";

// Anonymous multi-candidate vote
template AnonymousElectionVote(merkleDepth, maxCandidates) {
    // Private inputs
    signal input secret;
    signal input nullifierSecret;
    signal input pathElements[merkleDepth];
    signal input pathIndices[merkleDepth];

    // Public inputs
    signal input merkleRoot;
    signal input electionId;
    signal input candidateId;         // Which candidate (1 to maxCandidates)
    signal input numCandidates;       // Total candidates in this election
    signal input nullifier;

    // Verify candidateId is valid (1 <= candidateId <= numCandidates)
    component gtZero = GreaterThan(8);
    gtZero.in[0] <== candidateId;
    gtZero.in[1] <== 0;
    gtZero.out === 1;

    component lteMax = LessEqThan(8);
    lteMax.in[0] <== candidateId;
    lteMax.in[1] <== numCandidates;
    lteMax.out === 1;

    // Compute commitment (same as binary vote)
    component commitmentHasher = Poseidon(2);
    commitmentHasher.inputs[0] <== secret;
    commitmentHasher.inputs[1] <== nullifierSecret;

    // Verify Merkle proof (same as binary vote)
    component merkleProof = MerkleProof(merkleDepth);
    merkleProof.leaf <== commitmentHasher.out;
    for (var i = 0; i < merkleDepth; i++) {
        merkleProof.pathElements[i] <== pathElements[i];
        merkleProof.pathIndices[i] <== pathIndices[i];
    }
    merkleRoot === merkleProof.root;

    // Compute nullifier
    component nullifierHasher = Poseidon(3);
    nullifierHasher.inputs[0] <== secret;
    nullifierHasher.inputs[1] <== nullifierSecret;
    nullifierHasher.inputs[2] <== electionId;
    nullifier === nullifierHasher.out;
}

component main {public [merkleRoot, electionId, candidateId, numCandidates, nullifier]} = AnonymousElectionVote(20, 50);
```

---

### 2. Backend Implementation

#### 2.1 New Database Models

```python
# app/models/zk_voting.py

from app import db
from datetime import datetime

class VoterCommitment(db.Model):
    """Stores voter commitments for Merkle tree"""
    __tablename__ = 'voter_commitment'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    election_type = db.Column(db.String(50), nullable=False)  # 'law', 'presidential', 'party', 'peace'
    scope_id = db.Column(db.Integer, nullable=False)  # country_id, party_id, or war_id
    commitment = db.Column(db.String(66), nullable=False)  # Poseidon hash (hex)
    leaf_index = db.Column(db.Integer, nullable=False)  # Position in Merkle tree
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'election_type', 'scope_id', name='unique_voter_commitment'),
    )


class ZKVote(db.Model):
    """Stores anonymous votes with ZK proofs"""
    __tablename__ = 'zk_vote'

    id = db.Column(db.Integer, primary_key=True)
    election_type = db.Column(db.String(50), nullable=False)
    election_id = db.Column(db.Integer, nullable=False)  # law_id, election_id, etc.

    # Public signals (no voter identity!)
    nullifier = db.Column(db.String(66), nullable=False, unique=True)  # Prevents double voting
    vote_choice = db.Column(db.Integer, nullable=False)  # 0/1 for binary, candidateId for elections
    merkle_root = db.Column(db.String(66), nullable=False)  # Root at time of vote

    # zkVerify verification
    zkverify_tx_hash = db.Column(db.String(66), nullable=True)  # Transaction on zkVerify
    zkverify_block = db.Column(db.Integer, nullable=True)
    proof_verified = db.Column(db.Boolean, default=False)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_zkvote_election', 'election_type', 'election_id'),
    )


class MerkleTree(db.Model):
    """Stores Merkle tree roots for voter registries"""
    __tablename__ = 'merkle_tree'

    id = db.Column(db.Integer, primary_key=True)
    election_type = db.Column(db.String(50), nullable=False)
    scope_id = db.Column(db.Integer, nullable=False)
    root = db.Column(db.String(66), nullable=False)
    num_leaves = db.Column(db.Integer, default=0)
    tree_data = db.Column(db.JSON, nullable=True)  # Full tree for proof generation
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('election_type', 'scope_id', name='unique_merkle_tree'),
    )
```

#### 2.2 zkVerify Integration Service

```python
# app/services/zkverify_service.py

import os
import json
import asyncio
from typing import Dict, Any, Optional, Tuple

class ZKVerifyService:
    """Service for verifying ZK proofs via zkVerify testnet"""

    ZKVERIFY_RPC = "wss://testnet-rpc.zkverify.io"

    def __init__(self):
        self.seed_phrase = os.getenv('ZKVERIFY_SEED_PHRASE')
        self.verification_key = None
        self.vk_registered = False

    async def verify_vote_proof(
        self,
        proof: Dict[str, Any],
        public_signals: list,
        verification_key: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Verify a Groth16 proof on zkVerify

        Returns:
            (success, tx_hash, error_message)
        """
        # This will use zkverifyjs via subprocess or Node.js bridge
        # For production, consider using a dedicated Node.js microservice

        verification_script = f"""
        const {{ zkVerifySession, Library, CurveType }} = require('zkverifyjs');

        async function verify() {{
            const session = await zkVerifySession.start()
                .Testnet()
                .withAccount('{self.seed_phrase}');

            try {{
                const {{ events, transactionResult }} = await session.verify()
                    .groth16({{ library: Library.snarkjs, curve: CurveType.bn128 }})
                    .execute({{
                        proofData: {{
                            vk: {json.dumps(verification_key)},
                            proof: {json.dumps(proof)},
                            publicSignals: {json.dumps(public_signals)}
                        }}
                    }});

                // Wait for block inclusion
                return new Promise((resolve) => {{
                    events.on('includedInBlock', (data) => {{
                        resolve({{ success: true, txHash: data.txHash }});
                    }});
                    events.on('error', (err) => {{
                        resolve({{ success: false, error: err.message }});
                    }});
                }});
            }} finally {{
                await session.close();
            }}
        }}

        verify().then(console.log).catch(console.error);
        """

        # Execute via Node.js
        result = await self._run_node_script(verification_script)
        return result

    async def _run_node_script(self, script: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Execute Node.js script and parse result"""
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(script)
            script_path = f.name

        try:
            result = subprocess.run(
                ['node', script_path],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                output = json.loads(result.stdout.strip())
                if output.get('success'):
                    return (True, output.get('txHash'), None)
                else:
                    return (False, None, output.get('error'))
            else:
                return (False, None, result.stderr)
        finally:
            os.unlink(script_path)


# Singleton instance
zkverify_service = ZKVerifyService()
```

#### 2.3 Merkle Tree Service

```python
# app/services/merkle_service.py

import hashlib
from typing import List, Dict, Tuple, Optional
from py_poseidon_hash import poseidon_hash  # Need to install

class MerkleTreeService:
    """Manages Merkle trees for voter registries"""

    TREE_DEPTH = 20  # Supports up to 2^20 = 1,048,576 voters

    def __init__(self):
        self.zero_values = self._compute_zero_values()

    def _compute_zero_values(self) -> List[int]:
        """Precompute zero values for empty tree levels"""
        zeros = [0]
        for i in range(self.TREE_DEPTH):
            zeros.append(poseidon_hash([zeros[i], zeros[i]]))
        return zeros

    def _hash_pair(self, left: int, right: int) -> int:
        """Hash two nodes using Poseidon"""
        return poseidon_hash([left, right])

    def build_tree(self, commitments: List[int]) -> Dict:
        """
        Build a Merkle tree from voter commitments

        Returns:
            {
                'root': int,
                'leaves': List[int],
                'layers': List[List[int]]
            }
        """
        # Pad to power of 2
        num_leaves = 2 ** self.TREE_DEPTH
        leaves = commitments + [self.zero_values[0]] * (num_leaves - len(commitments))

        layers = [leaves]
        current_layer = leaves

        for depth in range(self.TREE_DEPTH):
            next_layer = []
            for i in range(0, len(current_layer), 2):
                left = current_layer[i]
                right = current_layer[i + 1] if i + 1 < len(current_layer) else self.zero_values[depth]
                next_layer.append(self._hash_pair(left, right))
            layers.append(next_layer)
            current_layer = next_layer

        return {
            'root': layers[-1][0],
            'leaves': commitments,
            'layers': layers
        }

    def get_proof(self, tree_data: Dict, leaf_index: int) -> Tuple[List[int], List[int]]:
        """
        Generate Merkle proof for a leaf

        Returns:
            (pathElements, pathIndices)
        """
        layers = tree_data['layers']
        path_elements = []
        path_indices = []

        current_index = leaf_index

        for depth in range(self.TREE_DEPTH):
            is_right = current_index % 2
            sibling_index = current_index - 1 if is_right else current_index + 1

            if sibling_index < len(layers[depth]):
                path_elements.append(layers[depth][sibling_index])
            else:
                path_elements.append(self.zero_values[depth])

            path_indices.append(is_right)
            current_index //= 2

        return path_elements, path_indices

    def verify_proof(
        self,
        leaf: int,
        root: int,
        path_elements: List[int],
        path_indices: List[int]
    ) -> bool:
        """Verify a Merkle proof"""
        current = leaf

        for i in range(len(path_elements)):
            if path_indices[i]:
                current = self._hash_pair(path_elements[i], current)
            else:
                current = self._hash_pair(current, path_elements[i])

        return current == root


merkle_service = MerkleTreeService()
```

#### 2.4 Anonymous Voting Routes

```python
# app/government/zk_routes.py

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.models import Law, ZKVote, VoterCommitment, MerkleTree
from app.services.zkverify_service import zkverify_service
from app.services.merkle_service import merkle_service
from app import db
import secrets
import asyncio

zk_bp = Blueprint('zk_voting', __name__, url_prefix='/api/zk')


@zk_bp.route('/register-voter', methods=['POST'])
@login_required
def register_voter():
    """
    Register voter for anonymous voting
    Client generates commitment = Poseidon(secret, nullifierSecret)
    """
    data = request.json
    election_type = data.get('election_type')  # 'law', 'presidential', etc.
    scope_id = data.get('scope_id')  # country_id, party_id
    commitment = data.get('commitment')  # Hex string

    # Validate eligibility
    if election_type == 'law':
        # Must be president or congress member
        if not current_user.is_president() and not current_user.is_congress_member():
            return jsonify({'error': 'Not eligible to vote on laws'}), 403
        scope_id = current_user.citizenship_country_id

    # Check if already registered
    existing = VoterCommitment.query.filter_by(
        user_id=current_user.id,
        election_type=election_type,
        scope_id=scope_id
    ).first()

    if existing:
        return jsonify({'error': 'Already registered', 'leaf_index': existing.leaf_index}), 400

    # Add to Merkle tree
    tree = MerkleTree.query.filter_by(
        election_type=election_type,
        scope_id=scope_id
    ).first()

    if not tree:
        tree = MerkleTree(
            election_type=election_type,
            scope_id=scope_id,
            root='0x0',
            num_leaves=0,
            tree_data={'leaves': [], 'layers': []}
        )
        db.session.add(tree)

    # Assign leaf index
    leaf_index = tree.num_leaves
    tree.num_leaves += 1

    # Store commitment
    voter_commitment = VoterCommitment(
        user_id=current_user.id,
        election_type=election_type,
        scope_id=scope_id,
        commitment=commitment,
        leaf_index=leaf_index
    )
    db.session.add(voter_commitment)

    # Rebuild Merkle tree
    all_commitments = VoterCommitment.query.filter_by(
        election_type=election_type,
        scope_id=scope_id
    ).order_by(VoterCommitment.leaf_index).all()

    commitment_values = [int(c.commitment, 16) for c in all_commitments]
    tree_data = merkle_service.build_tree(commitment_values)

    tree.root = hex(tree_data['root'])
    tree.tree_data = {
        'leaves': [hex(l) for l in tree_data['leaves']],
        'layers': [[hex(n) for n in layer] for layer in tree_data['layers']]
    }

    db.session.commit()

    return jsonify({
        'success': True,
        'leaf_index': leaf_index,
        'merkle_root': tree.root
    })


@zk_bp.route('/get-merkle-proof', methods=['POST'])
@login_required
def get_merkle_proof():
    """Get Merkle proof for voter's commitment"""
    data = request.json
    election_type = data.get('election_type')
    scope_id = data.get('scope_id')

    # Get voter's commitment
    commitment = VoterCommitment.query.filter_by(
        user_id=current_user.id,
        election_type=election_type,
        scope_id=scope_id
    ).first()

    if not commitment:
        return jsonify({'error': 'Not registered'}), 404

    # Get Merkle tree
    tree = MerkleTree.query.filter_by(
        election_type=election_type,
        scope_id=scope_id
    ).first()

    if not tree:
        return jsonify({'error': 'Tree not found'}), 404

    # Convert tree data back to integers
    tree_data = {
        'leaves': [int(l, 16) for l in tree.tree_data['leaves']],
        'layers': [[int(n, 16) for n in layer] for layer in tree.tree_data['layers']]
    }

    # Generate proof
    path_elements, path_indices = merkle_service.get_proof(tree_data, commitment.leaf_index)

    return jsonify({
        'success': True,
        'leaf_index': commitment.leaf_index,
        'merkle_root': tree.root,
        'path_elements': [hex(e) for e in path_elements],
        'path_indices': path_indices
    })


@zk_bp.route('/cast-vote', methods=['POST'])
@login_required
def cast_anonymous_vote():
    """
    Cast an anonymous vote with ZK proof

    Expected data:
    {
        'election_type': 'law',
        'election_id': 123,
        'proof': {...},  // Groth16 proof
        'public_signals': {
            'merkle_root': '0x...',
            'election_id': 123,
            'vote': 1,
            'nullifier': '0x...'
        }
    }
    """
    data = request.json
    election_type = data.get('election_type')
    election_id = data.get('election_id')
    proof = data.get('proof')
    public_signals = data.get('public_signals')

    # Extract public signals
    merkle_root = public_signals.get('merkle_root')
    vote_choice = public_signals.get('vote')
    nullifier = public_signals.get('nullifier')

    # Check nullifier hasn't been used (prevents double voting)
    existing_vote = ZKVote.query.filter_by(nullifier=nullifier).first()
    if existing_vote:
        return jsonify({'error': 'Vote already cast (nullifier reused)'}), 400

    # Verify Merkle root matches current tree
    if election_type == 'law':
        law = Law.query.get(election_id)
        if not law:
            return jsonify({'error': 'Law not found'}), 404
        scope_id = law.country_id

    tree = MerkleTree.query.filter_by(
        election_type=election_type,
        scope_id=scope_id
    ).first()

    if not tree or tree.root != merkle_root:
        return jsonify({'error': 'Invalid Merkle root'}), 400

    # Load verification key
    with open('circuits/vote_verification_key.json', 'r') as f:
        verification_key = json.load(f)

    # Verify proof on zkVerify
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    success, tx_hash, error = loop.run_until_complete(
        zkverify_service.verify_vote_proof(
            proof,
            [merkle_root, election_id, vote_choice, nullifier],
            verification_key
        )
    )

    if not success:
        return jsonify({'error': f'Proof verification failed: {error}'}), 400

    # Store anonymous vote
    zk_vote = ZKVote(
        election_type=election_type,
        election_id=election_id,
        nullifier=nullifier,
        vote_choice=vote_choice,
        merkle_root=merkle_root,
        zkverify_tx_hash=tx_hash,
        proof_verified=True
    )
    db.session.add(zk_vote)

    # Update vote tallies (denormalized for efficiency)
    if election_type == 'law':
        law = Law.query.get(election_id)
        if vote_choice == 1:
            law.zk_votes_for = (law.zk_votes_for or 0) + 1
        else:
            law.zk_votes_against = (law.zk_votes_against or 0) + 1
        law.zk_total_votes = (law.zk_total_votes or 0) + 1

    db.session.commit()

    return jsonify({
        'success': True,
        'zkverify_tx': tx_hash,
        'message': 'Vote cast anonymously and verified on zkVerify'
    })


@zk_bp.route('/vote-results/<election_type>/<int:election_id>', methods=['GET'])
def get_vote_results(election_type, election_id):
    """Get anonymized vote results"""
    votes = ZKVote.query.filter_by(
        election_type=election_type,
        election_id=election_id,
        proof_verified=True
    ).all()

    if election_type == 'law':
        votes_for = sum(1 for v in votes if v.vote_choice == 1)
        votes_against = sum(1 for v in votes if v.vote_choice == 0)

        return jsonify({
            'election_type': election_type,
            'election_id': election_id,
            'total_votes': len(votes),
            'votes_for': votes_for,
            'votes_against': votes_against,
            'zkverify_proofs': [v.zkverify_tx_hash for v in votes if v.zkverify_tx_hash]
        })
    else:
        # Multi-candidate election
        from collections import Counter
        vote_counts = Counter(v.vote_choice for v in votes)

        return jsonify({
            'election_type': election_type,
            'election_id': election_id,
            'total_votes': len(votes),
            'candidate_votes': dict(vote_counts),
            'zkverify_proofs': [v.zkverify_tx_hash for v in votes if v.zkverify_tx_hash]
        })
```

---

### 3. Frontend Implementation

#### 3.1 Voter Registration (Browser)

```javascript
// static/js/zk_voting.js

import { groth16 } from 'snarkjs';

// Generate random secrets for voter
function generateVoterSecrets() {
    const secret = BigInt('0x' + crypto.getRandomValues(new Uint8Array(32))
        .reduce((s, b) => s + b.toString(16).padStart(2, '0'), ''));
    const nullifierSecret = BigInt('0x' + crypto.getRandomValues(new Uint8Array(32))
        .reduce((s, b) => s + b.toString(16).padStart(2, '0'), ''));

    // Store securely in localStorage (encrypted in production)
    localStorage.setItem('zkVoteSecret', secret.toString());
    localStorage.setItem('zkVoteNullifierSecret', nullifierSecret.toString());

    return { secret, nullifierSecret };
}

// Compute commitment using Poseidon hash (via WASM)
async function computeCommitment(secret, nullifierSecret) {
    // Load circuit artifacts
    const wasmPath = '/static/circuits/commitment.wasm';
    const zkeyPath = '/static/circuits/commitment.zkey';

    const input = {
        secret: secret.toString(),
        nullifierSecret: nullifierSecret.toString()
    };

    const { proof, publicSignals } = await groth16.fullProve(input, wasmPath, zkeyPath);

    // publicSignals[0] is the commitment
    return '0x' + BigInt(publicSignals[0]).toString(16).padStart(64, '0');
}

// Register as voter
async function registerVoter(electionType, scopeId) {
    const { secret, nullifierSecret } = generateVoterSecrets();
    const commitment = await computeCommitment(secret, nullifierSecret);

    const response = await fetch('/api/zk/register-voter', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            election_type: electionType,
            scope_id: scopeId,
            commitment: commitment
        })
    });

    const result = await response.json();
    if (result.success) {
        localStorage.setItem(`zkLeafIndex_${electionType}_${scopeId}`, result.leaf_index);
        alert('Successfully registered for anonymous voting!');
    } else {
        alert('Registration failed: ' + result.error);
    }

    return result;
}
```

#### 3.2 Anonymous Vote Casting (Browser)

```javascript
// Cast anonymous vote with ZK proof
async function castAnonymousVote(electionType, electionId, voteChoice) {
    // Retrieve stored secrets
    const secret = BigInt(localStorage.getItem('zkVoteSecret'));
    const nullifierSecret = BigInt(localStorage.getItem('zkVoteNullifierSecret'));

    if (!secret || !nullifierSecret) {
        alert('Please register for anonymous voting first');
        return;
    }

    // Get Merkle proof from server
    const proofResponse = await fetch('/api/zk/get-merkle-proof', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            election_type: electionType,
            scope_id: getScopeId(electionType, electionId)
        })
    });

    const merkleData = await proofResponse.json();
    if (!merkleData.success) {
        alert('Failed to get Merkle proof: ' + merkleData.error);
        return;
    }

    // Compute nullifier
    const nullifier = await computeNullifier(secret, nullifierSecret, electionId);

    // Generate ZK proof in browser
    const wasmPath = '/static/circuits/anonymous_vote.wasm';
    const zkeyPath = '/static/circuits/anonymous_vote.zkey';

    const input = {
        // Private inputs
        secret: secret.toString(),
        nullifierSecret: nullifierSecret.toString(),
        pathElements: merkleData.path_elements.map(e => BigInt(e).toString()),
        pathIndices: merkleData.path_indices,

        // Public inputs
        merkleRoot: BigInt(merkleData.merkle_root).toString(),
        electionId: electionId.toString(),
        vote: voteChoice.toString(),
        nullifier: nullifier.toString()
    };

    console.log('Generating ZK proof...');
    const startTime = Date.now();

    const { proof, publicSignals } = await groth16.fullProve(input, wasmPath, zkeyPath);

    console.log(`Proof generated in ${Date.now() - startTime}ms`);

    // Submit vote to server
    const voteResponse = await fetch('/api/zk/cast-vote', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            election_type: electionType,
            election_id: electionId,
            proof: proof,
            public_signals: {
                merkle_root: merkleData.merkle_root,
                election_id: electionId,
                vote: voteChoice,
                nullifier: '0x' + BigInt(nullifier).toString(16).padStart(64, '0')
            }
        })
    });

    const result = await voteResponse.json();
    if (result.success) {
        alert(`Vote cast anonymously!\n\nzkVerify TX: ${result.zkverify_tx}\n\nYour vote is verified on-chain but cannot be linked to your identity.`);
    } else {
        alert('Vote failed: ' + result.error);
    }

    return result;
}

// Helper: compute nullifier
async function computeNullifier(secret, nullifierSecret, electionId) {
    // Use Poseidon hash via WASM
    // nullifier = Poseidon(secret, nullifierSecret, electionId)
    const wasmPath = '/static/circuits/nullifier.wasm';
    const zkeyPath = '/static/circuits/nullifier.zkey';

    const { publicSignals } = await groth16.fullProve({
        secret: secret.toString(),
        nullifierSecret: nullifierSecret.toString(),
        electionId: electionId.toString()
    }, wasmPath, zkeyPath);

    return BigInt(publicSignals[0]);
}
```

#### 3.3 Updated Law Voting UI

```html
<!-- templates/government/view_law_zk.html -->

{% extends "layouts/base.html" %}

{% block content %}
<div class="law-detail-card">
    <h2>{{ law.title }}</h2>
    <p>{{ law.description }}</p>

    {% if can_vote and not has_voted %}
    <div class="zk-voting-section">
        <h4><i class="fas fa-shield-alt me-2"></i>Anonymous Voting (Zero-Knowledge)</h4>
        <p class="text-muted">Your vote will be cryptographically verified without revealing your identity.</p>

        {% if not is_registered %}
        <button class="btn btn-outline-primary" onclick="registerForZKVoting('law', {{ law.country_id }})">
            <i class="fas fa-user-secret me-2"></i>Register for Anonymous Voting
        </button>
        <p class="small text-muted mt-2">One-time setup required. Your voting credentials are stored locally.</p>
        {% else %}
        <div class="vote-buttons">
            <button class="btn btn-success btn-lg me-3" onclick="castAnonymousVote('law', {{ law.id }}, 1)">
                <i class="fas fa-check me-2"></i>Vote FOR
            </button>
            <button class="btn btn-danger btn-lg" onclick="castAnonymousVote('law', {{ law.id }}, 0)">
                <i class="fas fa-times me-2"></i>Vote AGAINST
            </button>
        </div>
        <p class="small text-muted mt-3">
            <i class="fas fa-info-circle me-1"></i>
            Proof generation takes 5-15 seconds in your browser.
        </p>
        {% endif %}
    </div>
    {% endif %}

    <!-- Vote Results (Anonymous) -->
    <div class="vote-results mt-4">
        <h5>Current Results</h5>
        <div class="progress" style="height: 30px;">
            <div class="progress-bar bg-success" style="width: {{ votes_for_pct }}%">
                FOR: {{ law.zk_votes_for or 0 }}
            </div>
            <div class="progress-bar bg-danger" style="width: {{ votes_against_pct }}%">
                AGAINST: {{ law.zk_votes_against or 0 }}
            </div>
        </div>
        <p class="text-muted mt-2">
            Total votes: {{ law.zk_total_votes or 0 }}
            <span class="ms-3">
                <i class="fas fa-shield-alt text-success me-1"></i>
                All votes verified on <a href="https://testnet-explorer.zkverify.io/" target="_blank">zkVerify</a>
            </span>
        </p>

        <!-- No individual voter names displayed! -->
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/snarkjs@0.7.0/build/snarkjs.min.js"></script>
<script src="{{ url_for('static', filename='js/zk_voting.js') }}"></script>
{% endblock %}
```

---

### 4. zkVerify Integration Setup

#### 4.1 Environment Configuration

```env
# .env additions for zkVerify

# zkVerify Testnet
ZKVERIFY_RPC_HTTP=https://testnet-rpc.zkverify.io
ZKVERIFY_RPC_WS=wss://testnet-rpc.zkverify.io
ZKVERIFY_EXPLORER=https://testnet-explorer.zkverify.io/

# zkVerify account (get tokens from faucet: https://www.zkay.io/faucet)
ZKVERIFY_SEED_PHRASE="your twelve word seed phrase here"

# Circuit paths
ZK_CIRCUITS_PATH=circuits/
ZK_VOTE_WASM=circuits/anonymous_vote.wasm
ZK_VOTE_ZKEY=circuits/anonymous_vote.zkey
ZK_VOTE_VKEY=circuits/anonymous_vote_verification_key.json
```

#### 4.2 Node.js Dependencies

```json
// package.json additions
{
  "dependencies": {
    "zkverifyjs": "^0.7.0",
    "snarkjs": "^0.7.0",
    "circomlib": "^2.0.5"
  }
}
```

#### 4.3 Circuit Compilation Script

```bash
#!/bin/bash
# scripts/compile_circuits.sh

# Install circom if needed
if ! command -v circom &> /dev/null; then
    cargo install --git https://github.com/iden3/circom.git
fi

# Create circuits directory
mkdir -p circuits

# Compile anonymous vote circuit
circom circuits/anonymous_vote.circom --r1cs --wasm --sym -o circuits/

# Generate trusted setup (use existing powers of tau for production)
snarkjs powersoftau new bn128 14 circuits/pot14_0000.ptau
snarkjs powersoftau contribute circuits/pot14_0000.ptau circuits/pot14_0001.ptau --name="First contribution"
snarkjs powersoftau prepare phase2 circuits/pot14_0001.ptau circuits/pot14_final.ptau

# Generate zkey
snarkjs groth16 setup circuits/anonymous_vote.r1cs circuits/pot14_final.ptau circuits/anonymous_vote_0000.zkey
snarkjs zkey contribute circuits/anonymous_vote_0000.zkey circuits/anonymous_vote.zkey --name="Contribution"
snarkjs zkey export verificationkey circuits/anonymous_vote.zkey circuits/anonymous_vote_verification_key.json

echo "Circuits compiled successfully!"
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
- [ ] Set up zkVerify testnet account and get test tokens
- [ ] Install Circom and snarkjs toolchain
- [ ] Design and implement Circom circuits
- [ ] Compile circuits and generate verification keys
- [ ] Create database migrations for ZK voting tables

### Phase 2: Backend Integration (Week 3-4)
- [ ] Implement MerkleTreeService
- [ ] Implement ZKVerifyService
- [ ] Create voter registration API
- [ ] Create anonymous vote casting API
- [ ] Add vote result aggregation

### Phase 3: Frontend Integration (Week 5-6)
- [ ] Bundle snarkjs for browser
- [ ] Implement voter registration UI
- [ ] Implement proof generation in browser
- [ ] Create anonymous voting UI components
- [ ] Add loading states for proof generation

### Phase 4: Law Voting Migration (Week 7-8)
- [ ] Update law voting UI to use ZK proofs
- [ ] Migrate existing vote display (remove voter names)
- [ ] Add zkVerify proof links to UI
- [ ] Test with congress members

### Phase 5: Presidential Elections (Week 9-10)
- [ ] Extend circuit for multi-candidate voting
- [ ] Create election-specific Merkle trees
- [ ] Update election UI for anonymous voting
- [ ] Large-scale testing with citizens

### Phase 6: Polish & Security (Week 11-12)
- [ ] Security audit of circuits
- [ ] Performance optimization
- [ ] Error handling improvements
- [ ] Documentation
- [ ] Mainnet migration planning

---

## Security Considerations

### 1. Secret Storage
- Voter secrets stored in browser localStorage
- Consider: IndexedDB encryption, hardware wallet integration
- Backup/recovery mechanism needed

### 2. Merkle Tree Integrity
- Tree updates must be atomic
- Consider: Append-only trees, signed roots
- Snapshot mechanism for large elections

### 3. Proof Verification
- All proofs verified on zkVerify blockchain
- Consider: Local verification fallback
- Monitor for proof replay attacks

### 4. Nullifier Management
- Nullifiers prevent double voting
- Must be election-specific
- Consider: Nullifier expiration for repeated elections

### 5. Frontend Security
- Circuit files must be integrity-checked
- WASM loaded from trusted source
- Consider: Subresource integrity (SRI)

---

## Resources

- [zkVerify Documentation](https://docs.zkverify.io/)
- [zkVerify Testnet Explorer](https://testnet-explorer.zkverify.io/)
- [zkVerify Faucet](https://www.zkay.io/faucet)
- [zkVerifyJS NPM](https://www.npmjs.com/package/zkverifyjs)
- [Circom Documentation](https://docs.circom.io/)
- [snarkjs GitHub](https://github.com/iden3/snarkjs)
- [Poseidon Hash](https://www.poseidon-hash.info/)

---

## Estimated Costs

### zkVerify Testnet
- Proof verification: ~Free (testnet tokens from faucet)
- Transaction fees: Minimal

### Production (Mainnet)
- Proof verification: TBD (significantly cheaper than Ethereum)
- Expected: <$0.01 per vote verification

### Infrastructure
- Node.js service for zkVerifyJS: Minimal
- Circuit artifacts hosting: Static files (~10MB)
- Database: Minimal additional storage

---

## Success Metrics

1. **Privacy**: No vote can be linked to voter identity
2. **Verifiability**: All proofs verifiable on zkVerify explorer
3. **Performance**: Proof generation <15s in browser
4. **Reliability**: >99.9% successful vote submissions
5. **Adoption**: >80% of eligible voters using ZK voting

---

## Open Questions

1. Should we support both anonymous and transparent voting modes?
2. How to handle lost voter secrets (recovery mechanism)?
3. Should we implement vote delegation with ZK proofs?
4. Timeline for mainnet deployment?
5. Audit requirements before production use?
