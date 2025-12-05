"""
Vote signature verification for blockchain-verified elections.
"""

from eth_account.messages import encode_defunct
from web3 import Web3
import re


def verify_vote_signature(wallet_address: str, message: str, signature: str) -> bool:
    """
    Verify that a vote signature was signed by the claimed wallet address.

    Args:
        wallet_address: The Ethereum address that supposedly signed the message
        message: The vote message that was signed
        signature: The hex signature

    Returns:
        True if signature is valid and matches the wallet address
    """
    try:
        # Normalize addresses
        wallet_address = Web3.to_checksum_address(wallet_address)

        # Encode the message as it was signed by MetaMask (personal_sign)
        message_encoded = encode_defunct(text=message)

        # Recover the address that signed the message
        w3 = Web3()
        recovered_address = w3.eth.account.recover_message(message_encoded, signature=signature)

        # Compare addresses (case-insensitive)
        return recovered_address.lower() == wallet_address.lower()

    except Exception as e:
        print(f"Signature verification error: {e}")
        return False


def parse_vote_message(message: str) -> dict:
    """
    Parse a vote message into its components.

    Supports two formats:
    1. Legacy: TACTIZEN_VOTE|{election_type}|{election_id}|{candidate_id}|{timestamp}
    2. Human-readable:
       TACTIZEN ELECTION VOTE

       Election Type: {election_type}
       Election ID: {election_id}
       Candidate ID: {candidate_id}
       Voter Wallet: {wallet}
       Timestamp: {timestamp}

       By signing this message, I confirm my vote...

    Returns:
        dict with keys: election_type, election_id, candidate_id, timestamp
        or None if parsing fails
    """
    try:
        # Try legacy format first
        if message.startswith('TACTIZEN_VOTE|'):
            parts = message.split('|')
            if len(parts) != 5:
                return None

            return {
                'election_type': parts[1],
                'election_id': int(parts[2]),
                'candidate_id': int(parts[3]),
                'timestamp': int(parts[4])
            }

        # Try human-readable format
        if message.startswith('TACTIZEN ELECTION VOTE'):
            result = {}

            # Extract Election Type
            match = re.search(r'Election Type:\s*(\w+)', message)
            if match:
                result['election_type'] = match.group(1)

            # Extract Election ID
            match = re.search(r'Election ID:\s*(\d+)', message)
            if match:
                result['election_id'] = int(match.group(1))

            # Extract Candidate ID
            match = re.search(r'Candidate ID:\s*(\d+)', message)
            if match:
                result['candidate_id'] = int(match.group(1))

            # Extract Timestamp
            match = re.search(r'Timestamp:\s*(\d+)', message)
            if match:
                result['timestamp'] = int(match.group(1))

            # Validate all required fields are present
            if all(key in result for key in ['election_type', 'election_id', 'candidate_id', 'timestamp']):
                return result

        return None
    except (ValueError, IndexError):
        return None


def validate_vote_data(
    wallet_address: str,
    vote_message: str,
    vote_signature: str,
    expected_election_type: str,
    expected_election_id: int,
    expected_candidate_id: int,
    user_wallet: str = None,
    max_age_seconds: int = 300
) -> tuple[bool, str]:
    """
    Validate all aspects of a signed vote.

    Args:
        wallet_address: Claimed wallet address
        vote_message: The signed message
        vote_signature: The signature
        expected_election_type: Expected election type in message
        expected_election_id: Expected election ID in message
        expected_candidate_id: Expected candidate ID in message
        user_wallet: User's registered wallet (optional, for extra validation)
        max_age_seconds: Maximum age of signature in seconds (default 5 minutes)

    Returns:
        (is_valid, error_message)
    """
    import time

    # Validate wallet address format
    if not wallet_address or not re.match(r'^0x[a-fA-F0-9]{40}$', wallet_address):
        return False, "Invalid wallet address format"

    # Validate signature format
    if not vote_signature or not re.match(r'^0x[a-fA-F0-9]{130}$', vote_signature):
        return False, "Invalid signature format"

    # Parse the vote message
    parsed = parse_vote_message(vote_message)
    if not parsed:
        return False, "Invalid vote message format"

    # Verify message contents match expected values
    if parsed['election_type'] != expected_election_type:
        return False, "Election type mismatch"

    if parsed['election_id'] != expected_election_id:
        return False, "Election ID mismatch"

    if parsed['candidate_id'] != expected_candidate_id:
        return False, "Candidate ID mismatch"

    # Check signature age
    current_time = int(time.time())
    if current_time - parsed['timestamp'] > max_age_seconds:
        return False, "Vote signature has expired. Please try again."

    # Check signature isn't from the future (with 60 second tolerance)
    if parsed['timestamp'] > current_time + 60:
        return False, "Invalid timestamp in vote"

    # Verify the cryptographic signature
    if not verify_vote_signature(wallet_address, vote_message, vote_signature):
        return False, "Invalid signature - verification failed"

    # If user has a registered wallet, verify it matches
    if user_wallet:
        try:
            user_wallet_checksum = Web3.to_checksum_address(user_wallet)
            vote_wallet_checksum = Web3.to_checksum_address(wallet_address)
            if user_wallet_checksum.lower() != vote_wallet_checksum.lower():
                return False, "Vote must be signed with your registered wallet"
        except Exception:
            pass  # Skip this check if conversion fails

    return True, "Valid"
