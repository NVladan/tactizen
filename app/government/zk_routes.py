"""
ZK Voting API Routes

Provides endpoints for anonymous voting using zero-knowledge proofs.
Voters register commitments, generate proofs in browser, and submit
anonymous votes verified on zkVerify blockchain.
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime

from app import db
from app.models import (
    VoterCommitment, MerkleTree, ZKVote, ZKElectionConfig,
    GovernmentElection, ElectionCandidate, PartyElection, PartyCandidate,
    User
)
from app.services.merkle_service import (
    merkle_service, get_or_create_tree, add_voter_to_tree, get_merkle_proof
)
from app.services.zkverify_service import zkverify_service, verify_vote_proof


zk_bp = Blueprint('zk_voting', __name__, url_prefix='/api/zk')


# ============================================================
# Poseidon Hash Endpoint (for client-side commitment generation)
# ============================================================

@zk_bp.route('/poseidon', methods=['POST'])
@login_required
def compute_poseidon():
    """
    Compute Poseidon hash on server side.
    Used by client to generate commitment without implementing Poseidon in JS.
    Uses Node.js with circomlibjs for exact circuit compatibility.
    """
    from app.services.merkle_service import poseidon

    data = request.get_json()
    inputs = data.get('inputs', [])

    if not inputs or not isinstance(inputs, list):
        return jsonify({'error': 'inputs must be a non-empty list'}), 400

    if len(inputs) > 16:
        return jsonify({'error': 'Maximum 16 inputs supported'}), 400

    try:
        # Convert hex strings or decimal strings to integers
        int_inputs = []
        for inp in inputs:
            if isinstance(inp, str):
                if inp.startswith('0x'):
                    int_inputs.append(int(inp, 16))
                else:
                    int_inputs.append(int(inp))
            else:
                int_inputs.append(int(inp))

        result = poseidon.hash(int_inputs)
        return jsonify({
            'hash': str(result),
            'hex': '0x' + hex(result)[2:].zfill(64)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


# ============================================================
# Voter Registration Endpoints
# ============================================================

@zk_bp.route('/register', methods=['POST'])
@login_required
def register_voter():
    """
    Register a voter for anonymous voting.

    The client generates:
    - secret: Random 256-bit value (stored in browser)
    - nullifierSecret: Random 256-bit value (stored in browser)
    - commitment: Poseidon(secret, nullifierSecret)

    Only the commitment is sent to server and stored in Merkle tree.
    """
    data = request.get_json()

    election_type = data.get('election_type')  # 'presidential', 'congressional', 'party'
    scope_id = data.get('scope_id')  # country_id or party_id
    commitment = data.get('commitment')  # Hex string

    if not all([election_type, commitment]):
        return jsonify({'error': 'Missing required fields'}), 400

    if election_type not in ['presidential', 'congressional', 'party']:
        return jsonify({'error': 'Invalid election type'}), 400

    # Validate commitment format
    if not commitment.startswith('0x') or len(commitment) != 66:
        return jsonify({'error': 'Invalid commitment format'}), 400

    # Determine scope based on election type
    if election_type in ['presidential', 'congressional']:
        # Must be citizen of a country
        if not current_user.citizenship_id:
            return jsonify({'error': 'You must be a citizen to vote'}), 403
        scope_id = current_user.citizenship_id

    elif election_type == 'party':
        # Must be member of the party
        if not scope_id:
            return jsonify({'error': 'Party ID required'}), 400
        # Check party membership
        from app.models import PartyMembership
        membership = PartyMembership.query.filter_by(
            user_id=current_user.id,
            party_id=scope_id
        ).first()
        if not membership:
            return jsonify({'error': 'You must be a party member to vote'}), 403

    # Check for existing registration
    existing = VoterCommitment.query.filter_by(
        user_id=current_user.id,
        election_type=election_type,
        scope_id=scope_id
    ).first()

    if existing:
        return jsonify({
            'error': 'Already registered',
            'leaf_index': existing.leaf_index,
            'merkle_root': MerkleTree.query.filter_by(
                election_type=election_type,
                scope_id=scope_id
            ).first().root
        }), 400

    # Add commitment to Merkle tree
    leaf_index, merkle_root = add_voter_to_tree(election_type, scope_id, commitment)

    # Store voter commitment record
    voter_commitment = VoterCommitment(
        user_id=current_user.id,
        election_type=election_type,
        scope_id=scope_id,
        commitment=commitment,
        leaf_index=leaf_index
    )
    db.session.add(voter_commitment)
    db.session.commit()

    return jsonify({
        'success': True,
        'leaf_index': leaf_index,
        'merkle_root': merkle_root,
        'message': 'Successfully registered for anonymous voting'
    })


@zk_bp.route('/registration-status', methods=['GET'])
@login_required
def check_registration_status():
    """Check if current user is registered for anonymous voting."""
    election_type = request.args.get('election_type')
    scope_id = request.args.get('scope_id', type=int)

    if election_type in ['presidential', 'congressional']:
        scope_id = current_user.citizenship_id

    commitment = VoterCommitment.query.filter_by(
        user_id=current_user.id,
        election_type=election_type,
        scope_id=scope_id
    ).first()

    if commitment:
        tree = MerkleTree.query.filter_by(
            election_type=election_type,
            scope_id=scope_id
        ).first()

        return jsonify({
            'registered': True,
            'leaf_index': commitment.leaf_index,
            'merkle_root': tree.root if tree else None
        })

    return jsonify({'registered': False})


# ============================================================
# Merkle Proof Endpoints
# ============================================================

@zk_bp.route('/merkle-proof', methods=['POST'])
@login_required
def get_voter_merkle_proof():
    """
    Get Merkle proof for the current user's commitment.

    Required for generating ZK proof of voting eligibility.
    """
    data = request.get_json()

    election_type = data.get('election_type')
    scope_id = data.get('scope_id')

    if election_type in ['presidential', 'congressional']:
        scope_id = current_user.citizenship_id

    # Get user's commitment
    commitment = VoterCommitment.query.filter_by(
        user_id=current_user.id,
        election_type=election_type,
        scope_id=scope_id
    ).first()

    if not commitment:
        return jsonify({'error': 'Not registered for anonymous voting'}), 404

    # Get Merkle proof
    proof = get_merkle_proof(election_type, scope_id, commitment.leaf_index)

    if not proof:
        return jsonify({'error': 'Could not generate Merkle proof'}), 500

    return jsonify({
        'success': True,
        **proof
    })


# ============================================================
# Vote Casting Endpoints
# ============================================================

@zk_bp.route('/vote', methods=['POST'])
@login_required
def cast_anonymous_vote():
    """
    Cast an anonymous vote with ZK proof.

    The proof proves:
    1. Voter is registered (commitment in Merkle tree)
    2. Vote is for a valid candidate
    3. Nullifier is correctly computed (prevents double voting)

    WITHOUT revealing which registered voter is casting the vote.
    """
    data = request.get_json()

    election_type = data.get('election_type')
    election_id = data.get('election_id')
    proof = data.get('proof')  # Groth16 proof from snarkjs
    public_signals = data.get('public_signals')  # Public inputs

    current_app.logger.info(f"ZK Vote request: type={election_type}, id={election_id}")
    current_app.logger.info(f"Public signals: {public_signals}")

    if not all([election_type, election_id, proof, public_signals]):
        current_app.logger.error(f"Missing fields: type={election_type}, id={election_id}, proof={bool(proof)}, signals={bool(public_signals)}")
        return jsonify({'error': 'Missing required fields'}), 400

    # Extract public signals
    merkle_root = public_signals.get('merkle_root')
    candidate_id = public_signals.get('candidate_id')
    num_candidates = public_signals.get('num_candidates')
    nullifier = public_signals.get('nullifier')

    if not all([merkle_root, nullifier]) or candidate_id is None:
        current_app.logger.error(f"Invalid signals: root={merkle_root}, candidate={candidate_id}, nullifier={nullifier}")
        return jsonify({'error': 'Invalid public signals'}), 400

    # Check nullifier hasn't been used (prevents double voting)
    existing_vote = ZKVote.query.filter_by(nullifier=nullifier).first()
    if existing_vote:
        return jsonify({'error': 'Vote already cast (nullifier reused)'}), 400

    # Validate election exists and is active
    if election_type in ['presidential', 'congressional']:
        election = GovernmentElection.query.get(election_id)
        if not election:
            return jsonify({'error': 'Election not found'}), 404

        # Get scope from election
        scope_id = election.country_id

        # Count candidates
        actual_num_candidates = ElectionCandidate.query.filter_by(
            election_id=election_id,
            status='approved'
        ).count()

    elif election_type == 'party':
        election = PartyElection.query.get(election_id)
        if not election:
            return jsonify({'error': 'Election not found'}), 404

        scope_id = election.party_id
        actual_num_candidates = PartyCandidate.query.filter_by(
            election_id=election_id
        ).count()
    else:
        return jsonify({'error': 'Invalid election type'}), 400

    # Verify num_candidates matches
    current_app.logger.info(f"Candidate count check: received={num_candidates}, actual={actual_num_candidates}")
    if int(num_candidates) != actual_num_candidates:
        return jsonify({'error': f'Candidate count mismatch: got {num_candidates}, expected {actual_num_candidates}'}), 400

    # Verify Merkle root matches current tree
    tree = MerkleTree.query.filter_by(
        election_type=election_type,
        scope_id=scope_id
    ).first()

    if not tree:
        current_app.logger.error(f"Voter registry not found for type={election_type}, scope={scope_id}")
        return jsonify({'error': 'Voter registry not found'}), 404

    # Allow voting with current root or frozen root (if election has started)
    config = ZKElectionConfig.query.filter_by(
        election_type=election_type,
        election_id=election_id
    ).first()

    valid_roots = [tree.root]
    if config and config.frozen_merkle_root:
        valid_roots.append(config.frozen_merkle_root)

    current_app.logger.info(f"Merkle root check: received={merkle_root}, valid={valid_roots}")
    if merkle_root not in valid_roots:
        return jsonify({'error': f'Invalid Merkle root. Got {merkle_root}, expected one of {valid_roots}'}), 400

    # Verify candidate_id is valid
    if candidate_id < 0 or candidate_id > actual_num_candidates:
        return jsonify({'error': 'Invalid candidate ID'}), 400

    # Verify ZK proof on zkVerify blockchain
    success, tx_hash, block_number, error = verify_vote_proof(
        proof=proof,
        merkle_root=merkle_root,
        election_id=election_id,
        candidate_id=candidate_id,
        num_candidates=actual_num_candidates,
        nullifier=nullifier
    )

    if not success:
        return jsonify({
            'error': f'Proof verification failed: {error}',
            'zkverify_error': True
        }), 400

    # Store anonymous vote
    zk_vote = ZKVote(
        election_type=election_type,
        election_id=election_id,
        nullifier=nullifier,
        vote_choice=candidate_id,
        merkle_root=merkle_root,
        zkverify_tx_hash=tx_hash,
        zkverify_block=block_number,
        proof_verified=True,
        proof_data=proof
    )
    db.session.add(zk_vote)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Vote cast anonymously and verified on zkVerify',
        'zkverify_tx': tx_hash,
        'zkverify_block': block_number,
        'explorer_url': zkverify_service.get_explorer_url(tx_hash) if tx_hash else None
    })


# ============================================================
# Election Results Endpoints
# ============================================================

@zk_bp.route('/results/<election_type>/<int:election_id>', methods=['GET'])
def get_zk_vote_results(election_type, election_id):
    """
    Get anonymous vote results for an election.

    Returns aggregate vote counts without any voter identity information.
    vote_choice stores the ZK candidate index (1-based), not database ID.
    """
    # Get all verified votes for this election
    votes = ZKVote.query.filter_by(
        election_type=election_type,
        election_id=election_id,
        proof_verified=True
    ).all()

    # Count votes per candidate index (1-based, 0 = abstain)
    from collections import Counter
    vote_counts = Counter(v.vote_choice for v in votes)

    # Get candidate info - map ZK index to actual candidates
    candidates = []
    if election_type in ['presidential', 'congressional']:
        election = GovernmentElection.query.get(election_id)
        if election:
            # Get approved candidates in consistent order
            approved = [c for c in election.candidates if c.status.value == 'approved']
            for idx, candidate in enumerate(approved, start=1):
                candidates.append({
                    'id': candidate.id,
                    'zk_index': idx,
                    'user_id': candidate.user_id,
                    'username': candidate.user.username,
                    'zk_votes': vote_counts.get(idx, 0)
                })
    elif election_type == 'party':
        election = PartyElection.query.get(election_id)
        if election:
            for idx, candidate in enumerate(election.candidates, start=1):
                candidates.append({
                    'id': candidate.id,
                    'zk_index': idx,
                    'user_id': candidate.user_id,
                    'username': candidate.user.username,
                    'zk_votes': vote_counts.get(idx, 0)
                })

    # Get zkVerify proof links
    proof_links = [
        zkverify_service.get_explorer_url(v.zkverify_tx_hash)
        for v in votes if v.zkverify_tx_hash
    ]

    return jsonify({
        'election_type': election_type,
        'election_id': election_id,
        'total_zk_votes': len(votes),
        'abstentions': vote_counts.get(0, 0),  # candidate_id 0 = abstain
        'candidates': candidates,
        'zkverify_proofs': proof_links[:10],  # First 10 proof links
        'all_proofs_verified': all(v.proof_verified for v in votes)
    })


# ============================================================
# Election Configuration Endpoints
# ============================================================

@zk_bp.route('/config/<election_type>/<int:election_id>', methods=['GET'])
def get_election_config(election_type, election_id):
    """Get ZK voting configuration for an election."""
    config = ZKElectionConfig.query.filter_by(
        election_type=election_type,
        election_id=election_id
    ).first()

    if not config:
        return jsonify({
            'zk_enabled': False,
            'message': 'ZK voting not configured for this election'
        })

    return jsonify({
        'zk_enabled': config.zk_enabled,
        'registration_open': config.is_registration_open,
        'voting_open': config.is_voting_open,
        'registration_deadline': config.registration_deadline.isoformat() if config.registration_deadline else None,
        'voting_start': config.voting_start.isoformat() if config.voting_start else None,
        'voting_end': config.voting_end.isoformat() if config.voting_end else None,
        'num_candidates': config.num_candidates,
        'frozen_merkle_root': config.frozen_merkle_root,
        'results_finalized': config.results_finalized
    })


@zk_bp.route('/config/<election_type>/<int:election_id>', methods=['POST'])
@login_required
def setup_election_config(election_type, election_id):
    """
    Set up ZK voting for an election.

    Only admins or election organizers can do this.
    """
    # Check admin or election organizer permission
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403

    data = request.get_json()

    # Get or create config
    config = ZKElectionConfig.query.filter_by(
        election_type=election_type,
        election_id=election_id
    ).first()

    if not config:
        config = ZKElectionConfig(
            election_type=election_type,
            election_id=election_id
        )
        db.session.add(config)

    # Update config
    if 'zk_enabled' in data:
        config.zk_enabled = data['zk_enabled']
    if 'registration_deadline' in data:
        config.registration_deadline = datetime.fromisoformat(data['registration_deadline'])
    if 'voting_start' in data:
        config.voting_start = datetime.fromisoformat(data['voting_start'])
    if 'voting_end' in data:
        config.voting_end = datetime.fromisoformat(data['voting_end'])
    if 'num_candidates' in data:
        config.num_candidates = data['num_candidates']

    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'ZK election configuration updated'
    })


@zk_bp.route('/freeze-registry/<election_type>/<int:election_id>', methods=['POST'])
@login_required
def freeze_voter_registry(election_type, election_id):
    """
    Freeze the voter registry for an election.

    Called when voting period starts. No new registrations allowed after this.
    """
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403

    config = ZKElectionConfig.query.filter_by(
        election_type=election_type,
        election_id=election_id
    ).first()

    if not config:
        return jsonify({'error': 'Election not configured'}), 404

    # Get current Merkle root
    if election_type in ['presidential', 'congressional']:
        election = GovernmentElection.query.get(election_id)
        scope_id = election.country_id if election else None
    elif election_type == 'party':
        election = PartyElection.query.get(election_id)
        scope_id = election.party_id if election else None
    else:
        return jsonify({'error': 'Invalid election type'}), 400

    tree = MerkleTree.query.filter_by(
        election_type=election_type,
        scope_id=scope_id
    ).first()

    if not tree:
        return jsonify({'error': 'Voter registry not found'}), 404

    # Freeze the root
    config.frozen_merkle_root = tree.root
    db.session.commit()

    return jsonify({
        'success': True,
        'frozen_root': tree.root,
        'num_registered_voters': tree.num_leaves
    })


# ============================================================
# Debug/Test Endpoints (remove in production)
# ============================================================

@zk_bp.route('/debug/tree/<election_type>/<int:scope_id>', methods=['GET'])
def debug_merkle_tree(election_type, scope_id):
    """Debug endpoint to view Merkle tree state."""
    if not current_app.debug:
        return jsonify({'error': 'Debug mode only'}), 403

    tree = MerkleTree.query.filter_by(
        election_type=election_type,
        scope_id=scope_id
    ).first()

    if not tree:
        return jsonify({'error': 'Tree not found'}), 404

    return jsonify({
        'election_type': election_type,
        'scope_id': scope_id,
        'root': tree.root,
        'num_leaves': tree.num_leaves,
        'depth': merkle_service.TREE_DEPTH
    })
