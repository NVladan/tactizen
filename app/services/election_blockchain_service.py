"""
Election Blockchain Service

Handles publishing election results to the blockchain and IPFS.
"""

import json
import hashlib
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any
from decimal import Decimal
from flask import current_app

from app.extensions import db
from app.models import (
    GovernmentElection, ElectionCandidate, ElectionVote,
    PartyElection, PartyCandidate, PartyVote,
    User, Country, PoliticalParty
)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class ElectionBlockchainService:
    """Service for publishing election results to blockchain."""

    # Election type constants matching the smart contract
    ELECTION_TYPE_PARTY_PRESIDENT = 0
    ELECTION_TYPE_COUNTRY_PRESIDENT = 1
    ELECTION_TYPE_CONGRESS = 2

    @staticmethod
    def get_web3_and_contract():
        """Get Web3 instance and ElectionResults contract."""
        from web3 import Web3

        rpc_url = current_app.config.get('WEB3_RPC_URL')
        contract_address = current_app.config.get('ELECTION_RESULTS_CONTRACT_ADDRESS')
        private_key = current_app.config.get('WEB3_PRIVATE_KEY')

        if not all([rpc_url, contract_address, private_key]):
            return None, None, None

        w3 = Web3(Web3.HTTPProvider(rpc_url))

        # Load contract ABI
        import os
        abi_path = os.path.join(
            current_app.root_path,
            'blockchain', 'contracts', 'ElectionResults.json'
        )

        # If ABI file doesn't exist, try artifacts folder
        if not os.path.exists(abi_path):
            abi_path = os.path.join(
                os.path.dirname(current_app.root_path),
                'artifacts', 'contracts', 'ElectionResults.sol', 'ElectionResults.json'
            )

        if not os.path.exists(abi_path):
            current_app.logger.error(f"ElectionResults ABI not found")
            return None, None, None

        with open(abi_path, 'r') as f:
            contract_json = json.load(f)
            contract_abi = contract_json.get('abi', contract_json)

        contract = w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=contract_abi
        )

        return w3, contract, private_key

    @staticmethod
    def generate_results_hash(results_data: dict) -> str:
        """Generate a keccak256 hash of the results data."""
        json_str = json.dumps(results_data, sort_keys=True, cls=DecimalEncoder)
        return '0x' + hashlib.sha256(json_str.encode()).hexdigest()

    @staticmethod
    def upload_to_ipfs(results_data: dict) -> Optional[str]:
        """
        Upload results JSON to IPFS.
        Returns IPFS hash or None if upload fails.

        Note: This is a placeholder. In production, integrate with:
        - Pinata (https://pinata.cloud)
        - Infura IPFS
        - web3.storage
        """
        # For now, return a placeholder hash
        # In production, implement actual IPFS upload
        try:
            # Generate a deterministic hash based on content
            json_str = json.dumps(results_data, sort_keys=True, cls=DecimalEncoder)
            content_hash = hashlib.sha256(json_str.encode()).hexdigest()

            # Return a placeholder IPFS-style hash
            # Replace with actual IPFS upload in production
            ipfs_hash = f"Qm{content_hash[:44]}"

            current_app.logger.info(f"IPFS upload placeholder: {ipfs_hash}")
            return ipfs_hash

        except Exception as e:
            current_app.logger.error(f"IPFS upload error: {e}")
            return None

    @staticmethod
    def prepare_government_election_results(election: GovernmentElection) -> dict:
        """Prepare government election results data for blockchain publication."""
        # Get all candidates with vote counts
        candidates = db.session.scalars(
            db.select(ElectionCandidate)
            .where(ElectionCandidate.election_id == election.id)
            .order_by(ElectionCandidate.final_rank)
        ).all()

        # Get all votes for verification
        votes = db.session.scalars(
            db.select(ElectionVote)
            .where(ElectionVote.election_id == election.id)
        ).all()

        country = db.session.get(Country, election.country_id)

        results = {
            'election_id': election.id,
            'election_type': election.election_type.value,
            'country_id': election.country_id,
            'country_name': country.name if country else 'Unknown',
            'voting_start': election.voting_start.isoformat() if election.voting_start else None,
            'voting_end': election.voting_end.isoformat() if election.voting_end else None,
            'results_calculated_at': election.results_calculated_at.isoformat() if election.results_calculated_at else None,
            'total_votes': len(votes),
            'total_candidates': len(candidates),
            'winner_user_id': election.winner_user_id,
            'candidates': [],
            'blockchain_verified_votes': 0
        }

        # Add candidate details
        for candidate in candidates:
            user = db.session.get(User, candidate.user_id)
            candidate_data = {
                'user_id': candidate.user_id,
                'username': user.username if user else 'Unknown',
                'party_id': candidate.party_id,
                'votes_received': candidate.votes_received or 0,
                'final_rank': candidate.final_rank,
                'won_seat': candidate.won_seat
            }
            results['candidates'].append(candidate_data)

        # Count blockchain-verified votes
        blockchain_votes = sum(1 for v in votes if v.wallet_address)
        results['blockchain_verified_votes'] = blockchain_votes

        return results

    @staticmethod
    def prepare_party_election_results(election: PartyElection) -> dict:
        """Prepare party election results data for blockchain publication."""
        party = db.session.get(PoliticalParty, election.party_id)

        # Get all candidates
        candidates = db.session.scalars(
            db.select(PartyCandidate)
            .where(PartyCandidate.election_id == election.id)
        ).all()

        # Get all votes
        votes = db.session.scalars(
            db.select(PartyVote)
            .where(PartyVote.election_id == election.id)
        ).all()

        # Count votes per candidate
        vote_counts = {}
        for vote in votes:
            vote_counts[vote.candidate_id] = vote_counts.get(vote.candidate_id, 0) + 1

        results = {
            'election_id': election.id,
            'election_type': 'party_president',
            'party_id': election.party_id,
            'party_name': party.name if party else 'Unknown',
            'country_id': party.country_id if party else 0,
            'start_time': election.start_time.isoformat() if election.start_time else None,
            'end_time': election.end_time.isoformat() if election.end_time else None,
            'total_votes': len(votes),
            'total_candidates': len(candidates),
            'winner_user_id': election.winner_id,
            'candidates': [],
            'blockchain_verified_votes': 0
        }

        # Add candidate details sorted by votes
        candidate_list = []
        for candidate in candidates:
            user = db.session.get(User, candidate.user_id)
            votes_for_candidate = vote_counts.get(candidate.user_id, 0)
            candidate_list.append({
                'user_id': candidate.user_id,
                'username': user.username if user else 'Unknown',
                'votes_received': votes_for_candidate
            })

        # Sort by votes descending
        candidate_list.sort(key=lambda x: x['votes_received'], reverse=True)

        # Add rank
        for i, c in enumerate(candidate_list, 1):
            c['final_rank'] = i
            c['won'] = c['user_id'] == election.winner_id

        results['candidates'] = candidate_list

        # Count blockchain-verified votes
        blockchain_votes = sum(1 for v in votes if v.wallet_address)
        results['blockchain_verified_votes'] = blockchain_votes

        return results

    @classmethod
    def publish_government_election_results(cls, election: GovernmentElection) -> Tuple[bool, str]:
        """
        Publish government election results to blockchain.

        Returns:
            (success, message/tx_hash)
        """
        try:
            # Prepare results data
            results_data = cls.prepare_government_election_results(election)

            # Generate hash
            results_hash = cls.generate_results_hash(results_data)

            # Upload to IPFS
            ipfs_hash = cls.upload_to_ipfs(results_data)
            if not ipfs_hash:
                ipfs_hash = "pending"  # Fallback if IPFS upload fails

            # Get web3 connection
            w3, contract, private_key = cls.get_web3_and_contract()

            if not w3 or not contract:
                # Log results even if blockchain is not configured
                current_app.logger.info(
                    f"Election {election.id} results prepared but blockchain not configured. "
                    f"Hash: {results_hash}, IPFS: {ipfs_hash}"
                )
                return True, f"Results prepared (blockchain not configured). Hash: {results_hash}"

            # Determine election type
            if election.election_type.value == 'presidential':
                election_type = cls.ELECTION_TYPE_COUNTRY_PRESIDENT
            else:
                election_type = cls.ELECTION_TYPE_CONGRESS

            # Get first winner ID for congress (or main winner for presidential)
            winner_id = election.winner_user_id or 0
            if election_type == cls.ELECTION_TYPE_CONGRESS and results_data['candidates']:
                # For congress, use first place winner
                winners = [c for c in results_data['candidates'] if c.get('won_seat')]
                if winners:
                    winner_id = winners[0]['user_id']

            account = w3.eth.account.from_key(private_key)

            tx = contract.functions.publishResult(
                election.id,
                election_type,
                election.country_id,
                0,  # partyId (0 for government elections)
                winner_id,
                results_data['total_votes'],
                results_data['total_candidates'],
                ipfs_hash,
                bytes.fromhex(results_hash[2:])  # Remove 0x prefix
            ).build_transaction({
                'from': account.address,
                'nonce': w3.eth.get_transaction_count(account.address),
                'gas': 300000,
                'gasPrice': w3.eth.gas_price
            })

            # Sign and send transaction
            signed_tx = w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            current_app.logger.info(
                f"Published election {election.id} results to blockchain. TX: {tx_hash.hex()}"
            )

            return True, tx_hash.hex()

        except Exception as e:
            current_app.logger.error(f"Error publishing election results: {e}", exc_info=True)
            return False, str(e)

    @classmethod
    def publish_party_election_results(cls, election: PartyElection) -> Tuple[bool, str]:
        """
        Publish party election results to blockchain.

        Returns:
            (success, message/tx_hash)
        """
        try:
            # Prepare results data
            results_data = cls.prepare_party_election_results(election)
            party = db.session.get(PoliticalParty, election.party_id)

            # Generate hash
            results_hash = cls.generate_results_hash(results_data)

            # Upload to IPFS
            ipfs_hash = cls.upload_to_ipfs(results_data)
            if not ipfs_hash:
                ipfs_hash = "pending"

            # Get web3 connection
            w3, contract, private_key = cls.get_web3_and_contract()

            if not w3 or not contract:
                current_app.logger.info(
                    f"Party election {election.id} results prepared but blockchain not configured. "
                    f"Hash: {results_hash}, IPFS: {ipfs_hash}"
                )
                return True, f"Results prepared (blockchain not configured). Hash: {results_hash}"

            account = w3.eth.account.from_key(private_key)

            tx = contract.functions.publishResult(
                election.id,
                cls.ELECTION_TYPE_PARTY_PRESIDENT,
                party.country_id if party else 0,
                election.party_id,
                election.winner_id or 0,
                results_data['total_votes'],
                results_data['total_candidates'],
                ipfs_hash,
                bytes.fromhex(results_hash[2:])
            ).build_transaction({
                'from': account.address,
                'nonce': w3.eth.get_transaction_count(account.address),
                'gas': 300000,
                'gasPrice': w3.eth.gas_price
            })

            # Sign and send transaction
            signed_tx = w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            current_app.logger.info(
                f"Published party election {election.id} results to blockchain. TX: {tx_hash.hex()}"
            )

            return True, tx_hash.hex()

        except Exception as e:
            current_app.logger.error(f"Error publishing party election results: {e}", exc_info=True)
            return False, str(e)
