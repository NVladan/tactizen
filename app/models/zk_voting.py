"""
ZK Voting Models for Anonymous Elections

This module provides database models for zkSNARK-based anonymous voting.
Voters register commitments to a Merkle tree, then cast votes with ZK proofs
that prove membership without revealing identity.
"""

from datetime import datetime
from app import db


class VoterCommitment(db.Model):
    """
    Stores voter commitments for Merkle tree registration.

    When a voter registers for anonymous voting, they generate:
    - A random secret (stored only in their browser)
    - A random nullifier secret (stored only in their browser)
    - A commitment = Poseidon(secret, nullifierSecret)

    The commitment is stored here and added to the Merkle tree.
    The voter keeps their secrets to later prove membership.
    """
    __tablename__ = 'voter_commitment'

    id = db.Column(db.Integer, primary_key=True)

    # Which user this commitment belongs to (for registration tracking only)
    # This link is NOT used during voting - votes are anonymous
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Election scope
    election_type = db.Column(db.String(50), nullable=False)  # 'presidential', 'congressional', 'party'
    scope_id = db.Column(db.Integer, nullable=False)  # country_id or party_id

    # The commitment hash (Poseidon hash of secrets)
    commitment = db.Column(db.String(66), nullable=False)  # Hex string with 0x prefix

    # Position in the Merkle tree (needed to generate proofs)
    leaf_index = db.Column(db.Integer, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('voter_commitments', lazy='dynamic'))

    __table_args__ = (
        # Each user can only register once per election type/scope
        db.UniqueConstraint('user_id', 'election_type', 'scope_id', name='unique_voter_commitment'),
        db.Index('idx_commitment_scope', 'election_type', 'scope_id'),
    )

    def __repr__(self):
        return f'<VoterCommitment {self.id}: user={self.user_id} type={self.election_type}>'


class MerkleTree(db.Model):
    """
    Stores Merkle tree state for voter registries.

    Each election type + scope has its own Merkle tree of registered voters.
    The tree is rebuilt whenever a new voter registers.
    """
    __tablename__ = 'merkle_tree'

    id = db.Column(db.Integer, primary_key=True)

    # Election scope
    election_type = db.Column(db.String(50), nullable=False)  # 'presidential', 'congressional', 'party'
    scope_id = db.Column(db.Integer, nullable=False)  # country_id or party_id

    # Current Merkle root
    root = db.Column(db.String(66), nullable=False)  # Hex string with 0x prefix

    # Number of registered voters
    num_leaves = db.Column(db.Integer, default=0)

    # Full tree data for generating proofs (JSON serialized)
    # Contains all layer hashes needed to construct proofs
    tree_data = db.Column(db.JSON, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('election_type', 'scope_id', name='unique_merkle_tree'),
    )

    def __repr__(self):
        return f'<MerkleTree {self.election_type}/{self.scope_id}: {self.num_leaves} voters>'


class ZKVote(db.Model):
    """
    Stores anonymous votes verified by ZK proofs.

    IMPORTANT: This table contains NO voter identity information!
    Votes are linked only by nullifier (prevents double-voting) and
    verified by zkVerify blockchain proofs.
    """
    __tablename__ = 'zk_vote'

    id = db.Column(db.Integer, primary_key=True)

    # Election reference
    election_type = db.Column(db.String(50), nullable=False)  # 'presidential', 'congressional', 'party'
    election_id = db.Column(db.Integer, nullable=False)  # GovernmentElection.id or PartyElection.id

    # ========== Public signals from ZK proof (NO voter identity!) ==========

    # Nullifier - unique per voter per election, prevents double voting
    # Even if the same voter votes in different elections, nullifiers are different
    nullifier = db.Column(db.String(66), nullable=False, unique=True)

    # The vote choice
    # For presidential: candidate_id (1-N where N is number of candidates)
    # For congressional: candidate_id
    # For party: candidate_id
    # 0 = abstain/blank vote
    vote_choice = db.Column(db.Integer, nullable=False)

    # Merkle root at time of voting (proves voter was registered)
    merkle_root = db.Column(db.String(66), nullable=False)

    # ========== zkVerify verification data ==========

    # Transaction hash on zkVerify blockchain
    zkverify_tx_hash = db.Column(db.String(128), nullable=True)

    # Block number where proof was included
    zkverify_block = db.Column(db.Integer, nullable=True)

    # Whether the proof has been verified on zkVerify
    proof_verified = db.Column(db.Boolean, default=False)

    # Raw proof data (for audit/replay if needed)
    proof_data = db.Column(db.JSON, nullable=True)

    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_zkvote_election', 'election_type', 'election_id'),
        db.Index('idx_zkvote_verified', 'proof_verified'),
    )

    def __repr__(self):
        return f'<ZKVote {self.id}: {self.election_type}/{self.election_id} choice={self.vote_choice}>'


class ZKElectionConfig(db.Model):
    """
    Configuration for ZK-enabled elections.

    Tracks which elections use anonymous voting and their settings.
    """
    __tablename__ = 'zk_election_config'

    id = db.Column(db.Integer, primary_key=True)

    # Election reference
    election_type = db.Column(db.String(50), nullable=False)  # 'presidential', 'congressional', 'party'
    election_id = db.Column(db.Integer, nullable=False)

    # Whether ZK voting is enabled for this election
    zk_enabled = db.Column(db.Boolean, default=True)

    # Registration period (voters must register before this)
    registration_deadline = db.Column(db.DateTime, nullable=True)

    # Voting period
    voting_start = db.Column(db.DateTime, nullable=True)
    voting_end = db.Column(db.DateTime, nullable=True)

    # Merkle root frozen at voting start (no new registrations during voting)
    frozen_merkle_root = db.Column(db.String(66), nullable=True)

    # Number of candidates
    num_candidates = db.Column(db.Integer, default=0)

    # Results (populated after voting ends)
    results_finalized = db.Column(db.Boolean, default=False)
    results_data = db.Column(db.JSON, nullable=True)  # {candidate_id: vote_count, ...}

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('election_type', 'election_id', name='unique_zk_election'),
    )

    def __repr__(self):
        return f'<ZKElectionConfig {self.election_type}/{self.election_id}>'

    @property
    def is_registration_open(self):
        """Check if voter registration is still open"""
        if not self.registration_deadline:
            return True
        return datetime.utcnow() < self.registration_deadline

    @property
    def is_voting_open(self):
        """Check if voting is currently open"""
        now = datetime.utcnow()
        if self.voting_start and now < self.voting_start:
            return False
        if self.voting_end and now > self.voting_end:
            return False
        return True
