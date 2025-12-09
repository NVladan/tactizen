"""
NFT Service Layer
Handles all NFT-related business logic
"""
import random
import logging
from datetime import datetime
from typing import Optional, List, Dict, Tuple

logger = logging.getLogger(__name__)

from app import db
from app.models.nft import (
    NFTInventory, PlayerNFTSlots, CompanyNFTSlots,
    NFTBurnHistory, NFTDropHistory, NFTMarketplace, NFTTradeHistory
)
from app.blockchain.nft_config import (
    NFTType, PlayerNFTCategory, CompanyNFTCategory,
    get_nft_bonus_value, get_nft_name, get_nft_description,
    get_all_player_categories, get_all_company_categories,
    get_purchase_price, get_company_slot_count,
    can_upgrade_tier, get_upgrade_tier,
    NFT_DROP_WEIGHTS, NFT_DROP_CHANCES, PLAYER_NFT_SLOTS,
    get_nft_metadata_uri
)


class NFTService:
    """Service class for NFT operations"""

    @staticmethod
    def mint_nft_direct(user_id: int, tier: int, nft_type: str,
                        category: Optional[str] = None) -> Tuple[Optional[NFTInventory], Optional[str]]:
        """
        Directly mint an NFT for a user (admin/testing purposes)

        Args:
            user_id: ID of the user to receive NFT
            tier: Tier of NFT (1-5)
            nft_type: 'player' or 'company'
            category: Optional specific category, otherwise random

        Returns:
            (NFTInventory object, error_message) - error_message is None on success
        """
        from app.models.user import User

        # Validate tier
        if tier < 1 or tier > 5:
            return None, "Invalid tier. Must be 1-5."

        # Validate NFT type
        if nft_type not in [NFTType.PLAYER, NFTType.COMPANY]:
            return None, "Invalid NFT type. Must be 'player' or 'company'."

        # Get user
        user = User.query.get(user_id)
        if not user:
            return None, "User not found."

        # Random category if not specified
        if not category:
            if nft_type == NFTType.PLAYER:
                category = random.choice(get_all_player_categories())
            else:
                category = random.choice(get_all_company_categories())

        # Get bonus value
        bonus_value = get_nft_bonus_value(nft_type, category, tier)

        # Create NFT
        nft = NFTInventory(
            user_id=user_id,
            nft_type=nft_type,
            category=category,
            tier=tier,
            bonus_value=bonus_value,
            token_id=random.randint(1000000, 9999999),
            contract_address="0x0000000000000000000000000000000000000000",
            acquired_via='admin_mint',
            metadata_uri=get_nft_metadata_uri(nft_type, category, tier)
        )

        db.session.add(nft)
        db.session.commit()

        return nft, None

    @staticmethod
    def purchase_nft(user_id: int, tier: int, nft_type: str,
                     category: Optional[str] = None, contract_address: str = None,
                     token_id: int = None) -> Tuple[Optional[NFTInventory], Optional[str]]:
        """
        Purchase an NFT with ZEN tokens

        Args:
            user_id: ID of the user purchasing
            tier: Tier of NFT (1-5)
            nft_type: 'player' or 'company'
            category: Optional specific category, otherwise random
            contract_address: Smart contract address
            token_id: On-chain token ID

        Returns:
            (NFTInventory object, error_message) - error_message is None on success
        """
        from app.models.user import User

        # Validate tier
        if tier < 1 or tier > 5:
            return None, "Invalid tier. Must be 1-5."

        # Validate NFT type
        if nft_type not in [NFTType.PLAYER, NFTType.COMPANY]:
            return None, "Invalid NFT type. Must be 'player' or 'company'."

        # Get user
        user = User.query.get(user_id)
        if not user:
            return None, "User not found."

        # Check ZEN balance (TODO: implement ZEN balance checking)
        price = get_purchase_price(tier)
        # if user.zen_balance < price:
        #     return None, f"Insufficient ZEN balance. Need {price} ZEN."

        # Random category if not specified
        if not category:
            if nft_type == NFTType.PLAYER:
                category = random.choice(get_all_player_categories())
            else:
                category = random.choice(get_all_company_categories())

        # Get bonus value
        bonus_value = get_nft_bonus_value(nft_type, category, tier)

        # Create NFT
        nft = NFTInventory(
            user_id=user_id,
            nft_type=nft_type,
            category=category,
            tier=tier,
            bonus_value=bonus_value,
            token_id=token_id or random.randint(1000000, 9999999),  # Temporary until on-chain
            contract_address=contract_address or "0x0000000000000000000000000000000000000000",
            acquired_via='purchase',
            metadata_uri=get_nft_metadata_uri(nft_type, category, tier)
        )

        db.session.add(nft)

        # Deduct ZEN (TODO: implement ZEN deduction)
        # user.zen_balance -= price

        db.session.commit()

        return nft, None

    @staticmethod
    def purchase_nft_blockchain(user_id: int, wallet_address: str, tier: int, nft_type: str,
                                category: Optional[str] = None, tx_hash: str = None) -> Tuple[Optional[NFTInventory], Optional[str]]:
        """
        Purchase an NFT with ZEN tokens via blockchain (V2 with on-chain payment verification)

        Flow (New V2):
        1. Frontend approves ZEN spending via MetaMask
        2. Frontend calls mintNFT() on contract with payment
        3. Contract verifies payment and mints NFT atomically
        4. Frontend sends mint tx_hash to this endpoint
        5. Backend verifies mint transaction succeeded
        6. Backend saves NFT to database

        Args:
            user_id: ID of the user purchasing
            wallet_address: User's verified wallet address
            tier: Tier of NFT (1-5)
            nft_type: 'player' or 'company'
            category: Optional specific category, otherwise random
            tx_hash: Transaction hash of the mintNFT() call

        Returns:
            (NFTInventory object, error_message) - error_message is None on success
        """
        from app.models.user import User
        from app.blockchain.nft_contract import verify_nft_mint_transaction
        import os

        # Validate tier
        if tier < 1 or tier > 5:
            return None, "Invalid tier. Must be 1-5."

        # Validate NFT type
        if nft_type not in [NFTType.PLAYER, NFTType.COMPANY]:
            return None, "Invalid NFT type. Must be 'player' or 'company'."

        # Get user
        user = User.query.get(user_id)
        if not user:
            return None, "User not found."

        # Validate wallet address matches user's verified wallet
        if user.wallet_address.lower() != wallet_address.lower():
            return None, "Wallet address mismatch."

        # Verify the mint transaction on blockchain
        # This checks that the transaction succeeded and extracts the token ID and NFT details
        try:
            mint_data = verify_nft_mint_transaction(
                tx_hash=tx_hash,
                expected_minter=wallet_address
            )

            if not mint_data:
                return None, "Mint transaction verification failed. Transaction not found or failed."

            token_id = mint_data['token_id']
            contract_nft_type = mint_data['nft_type']
            contract_category = mint_data['category']
            contract_tier = mint_data['tier']
            contract_bonus_value = mint_data['bonus_value']
            contract_address = os.getenv('NFT_CONTRACT_ADDRESS')

            logger.info(f"[NFT Purchase] Verified mint transaction: token_id={token_id}, type={contract_nft_type}, category={contract_category}, tier={contract_tier}")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[NFT Purchase] Mint verification failed: {error_msg}")
            return None, f"Failed to verify NFT mint: {error_msg}"

        # Create NFT in database with data from blockchain
        nft = NFTInventory(
            user_id=user_id,
            nft_type=contract_nft_type,
            category=contract_category,
            tier=contract_tier,
            bonus_value=contract_bonus_value,
            token_id=token_id,
            contract_address=contract_address,
            acquired_via='purchase',
            metadata_uri=get_nft_metadata_uri(contract_nft_type, contract_category, contract_tier)
        )

        db.session.add(nft)
        db.session.commit()

        return nft, None

    @staticmethod
    def drop_nft(user_id: int, source: str) -> Tuple[Optional[NFTInventory], Optional[str]]:
        """
        Attempt to drop an NFT from gameplay activity

        Args:
            user_id: ID of the user
            source: Source of drop ('work', 'training', 'study', 'battle_win', 'daily_login')

        Returns:
            (NFTInventory object or None, error_message)
        """
        # Get drop chance for this source
        drop_chance = NFT_DROP_CHANCES.get(source, 0)

        # Roll for drop
        if random.random() * 100 > drop_chance:
            return None, None  # No drop, not an error

        # Determine tier (weighted random Q1-Q3 only)
        tier_choices = list(NFT_DROP_WEIGHTS.keys())
        tier_weights = list(NFT_DROP_WEIGHTS.values())
        tier = random.choices(tier_choices, weights=tier_weights, k=1)[0]

        # Random type and category
        nft_type = random.choice([NFTType.PLAYER, NFTType.COMPANY])

        if nft_type == NFTType.PLAYER:
            category = random.choice(get_all_player_categories())
        else:
            category = random.choice(get_all_company_categories())

        # Get bonus value
        bonus_value = get_nft_bonus_value(nft_type, category, tier)

        # Create NFT
        nft = NFTInventory(
            user_id=user_id,
            nft_type=nft_type,
            category=category,
            tier=tier,
            bonus_value=bonus_value,
            token_id=random.randint(1000000, 9999999),  # Temporary
            contract_address="0x0000000000000000000000000000000000000000",
            acquired_via='drop',
            metadata_uri=get_nft_metadata_uri(nft_type, category, tier)
        )

        db.session.add(nft)

        # Record drop history
        drop_record = NFTDropHistory(
            user_id=user_id,
            nft_id=nft.id,
            drop_source=source,
            tier=tier,
            category=category
        )
        db.session.add(drop_record)

        db.session.commit()

        return nft, None

    @staticmethod
    def upgrade_nft_blockchain(
        user_id: int,
        wallet_address: str,
        nft_ids: List[int],
        tx_hash: str
    ) -> Tuple[Optional[NFTInventory], Optional[str]]:
        """
        Upgrade 3 NFTs via blockchain transaction verification

        Flow:
        1. Frontend calls upgradeNFT() on smart contract (burns 3, mints 1 new NFT)
        2. Frontend sends upgrade tx_hash to this endpoint
        3. Backend verifies upgrade transaction succeeded
        4. Backend updates database (removes burned NFTs, adds new NFT)

        IDEMPOTENT: If tx_hash was already processed, returns the existing NFT.
        RECOVERY: If blockchain succeeded but DB failed, can be retried safely.

        Args:
            user_id: ID of the user
            wallet_address: User's wallet address
            nft_ids: List of 3 database NFT IDs to burn
            tx_hash: Transaction hash of the upgradeNFT() call

        Returns:
            (New NFT object, error_message)
        """
        from app.blockchain.nft_contract import verify_nft_upgrade_transaction

        # Validate transaction hash
        if not tx_hash:
            return None, "Missing upgrade transaction hash."

        # IDEMPOTENCY CHECK: See if this tx_hash was already processed
        existing_burn = NFTBurnHistory.query.filter_by(transaction_hash=tx_hash).first()
        if existing_burn:
            # Transaction already processed - return the minted NFT
            existing_nft = NFTInventory.query.filter_by(
                token_id=existing_burn.minted_nft_id,
                user_id=user_id
            ).first()
            if existing_nft:
                logger.info(f"[NFT Upgrade] Transaction {tx_hash} already processed, returning existing NFT #{existing_nft.token_id}")
                return existing_nft, None
            else:
                # Burn record exists but NFT doesn't - unusual state, log and continue
                logger.warning(f"[NFT Upgrade] Burn record exists for tx {tx_hash} but NFT {existing_burn.minted_nft_id} not found")

        # Validate input
        if len(nft_ids) != 3:
            return None, "Must select exactly 3 NFTs to upgrade."

        # Get NFTs from database
        nfts = NFTInventory.query.filter(
            NFTInventory.id.in_(nft_ids),
            NFTInventory.user_id == user_id
        ).all()

        # RECOVERY MODE: If NFTs already burned (not in DB), verify on blockchain and recover
        if len(nfts) < 3:
            logger.info(f"[NFT Upgrade] Only found {len(nfts)}/3 NFTs in database - checking blockchain for recovery")
            return NFTService._recover_upgrade_from_blockchain(user_id, wallet_address, tx_hash)

        # Check all same tier
        tiers = [nft.tier for nft in nfts]
        if len(set(tiers)) != 1:
            return None, "All NFTs must be the same tier."

        current_tier = tiers[0]

        # Check if upgradeable
        if not can_upgrade_tier(current_tier):
            return None, "Q5 NFTs cannot be upgraded further."

        # Check none are equipped
        for nft in nfts:
            if nft.is_equipped:
                return None, f"NFT #{nft.id} is equipped. Please unequip first."

        # Check none are listed on marketplace
        for nft in nfts:
            active_listing = NFTMarketplace.query.filter_by(nft_id=nft.id, is_active=True).first()
            if active_listing:
                return None, f"NFT #{nft.id} is listed on marketplace. Please cancel the listing first."

        # Get token IDs for blockchain verification
        burn_token_ids = [nft.token_id for nft in nfts]

        # Verify the upgrade transaction on blockchain
        # CRITICAL: This must succeed before we modify the database
        logger.info(f"[NFT Upgrade] Verifying blockchain transaction {tx_hash}")
        upgrade_data = verify_nft_upgrade_transaction(
            tx_hash=tx_hash,
            expected_upgrader=wallet_address,
            expected_burn_token_ids=burn_token_ids
        )

        if not upgrade_data:
            logger.error(f"[NFT Upgrade] Blockchain verification FAILED for tx {tx_hash}")
            return None, "Upgrade transaction verification failed. The blockchain transaction may have failed or reverted. Your NFTs have NOT been burned - please check your wallet and try again."

        # Extract verified data from blockchain
        new_token_id = upgrade_data['new_token_id']
        verified_burned_ids = upgrade_data['burned_token_ids']
        nft_type = upgrade_data['nft_type']
        category = upgrade_data['category']
        tier = upgrade_data['tier']
        bonus_value = upgrade_data['bonus_value']

        # If blockchain returns 0 bonus, use config-based bonus value
        if bonus_value == 0:
            from app.blockchain.nft_config import get_nft_bonus_value
            bonus_value = get_nft_bonus_value(nft_type, category, tier)
            logger.info(f"[NFT Upgrade] Using config bonus value: {bonus_value}%")

        # Double-check burned IDs match
        if set(verified_burned_ids) != set(burn_token_ids):
            return None, "Burned token IDs mismatch between database and blockchain."

        # Get contract address before we start deleting
        contract_address = nfts[0].contract_address if nfts else None

        # DATABASE UPDATE - wrapped in try/except for safety
        # At this point, blockchain transaction is CONFIRMED successful
        # We MUST update the database, and if it fails, we have recovery mechanisms
        try:
            # Create new NFT in database with blockchain data
            new_nft = NFTInventory(
                user_id=user_id,
                nft_type=nft_type,
                category=category,
                tier=tier,
                bonus_value=bonus_value,
                token_id=new_token_id,
                contract_address=contract_address,
                acquired_via='upgrade',
                metadata_uri=get_nft_metadata_uri(nft_type, category, tier)
            )

            db.session.add(new_nft)
            db.session.flush()  # Get new_nft.id

            # Record burn history with transaction hash for audit trail
            # This is CRITICAL for idempotency - allows us to detect already-processed tx
            burn_record = NFTBurnHistory(
                user_id=user_id,
                burned_nft_ids=burn_token_ids,
                minted_nft_id=new_token_id,
                tier_from=current_tier,
                tier_to=tier,
                transaction_hash=tx_hash  # Store verified tx hash for audit
            )
            db.session.add(burn_record)

            # Delete old NFTs from database (already burned on blockchain)
            # First, delete any dependent records that reference these NFTs
            for nft in nfts:
                # Delete marketplace listings for this NFT
                NFTMarketplace.query.filter_by(nft_id=nft.id).delete()
                # Delete trade history for this NFT
                NFTTradeHistory.query.filter_by(nft_id=nft.id).delete()
                db.session.delete(nft)

            db.session.commit()

            logger.info(f"[NFT Upgrade] SUCCESS: User {user_id} upgraded tokens {burn_token_ids} to token {new_token_id} (Q{tier})")
            return new_nft, None

        except Exception as db_error:
            db.session.rollback()
            logger.error(f"[NFT Upgrade] DATABASE ERROR after blockchain success: {db_error}")
            logger.error(f"[NFT Upgrade] TX {tx_hash} succeeded on blockchain but DB update failed!")
            logger.error(f"[NFT Upgrade] Recovery data: user={user_id}, new_token={new_token_id}, burned={burn_token_ids}")

            # Return error but include recovery instructions
            return None, f"Blockchain upgrade succeeded but database update failed. Please click 'Verify Ownership' to sync your inventory, or retry the upgrade with the same transaction. Error: {str(db_error)}"

    @staticmethod
    def _recover_upgrade_from_blockchain(
        user_id: int,
        wallet_address: str,
        tx_hash: str
    ) -> Tuple[Optional[NFTInventory], Optional[str]]:
        """
        Recover an upgrade when blockchain succeeded but DB update failed.

        This happens when:
        1. User burned NFTs on blockchain
        2. Backend verification succeeded
        3. But database update failed (network error, timeout, etc.)

        This function re-verifies the blockchain transaction and creates
        the missing database records.
        """
        from app.blockchain.nft_contract import verify_nft_upgrade_transaction
        import os

        logger.info(f"[NFT Upgrade Recovery] Starting recovery for user {user_id}, tx {tx_hash}")

        # We don't know the expected burn token IDs since they're gone from DB
        # So we verify the transaction with empty expected list and trust blockchain data
        try:
            # Get transaction receipt to extract data
            from app.blockchain.web3_config import get_web3
            w3 = get_web3()

            receipt = w3.eth.get_transaction_receipt(tx_hash)
            if not receipt or receipt.get('status') != 1:
                return None, "Recovery failed: Transaction not found or failed on blockchain."

            tx = w3.eth.get_transaction(tx_hash)
            if tx['from'].lower() != wallet_address.lower():
                return None, "Recovery failed: Transaction was not sent by your wallet."

            # Parse the upgrade event from logs to get new token ID
            # Look for Transfer events (NFT minting)
            nft_contract_address = os.environ.get('NFT_CONTRACT_ADDRESS', '').lower()

            new_token_id = None
            burned_token_ids = []

            # Parse logs for Transfer events
            # Transfer to 0x0 = burn, Transfer from 0x0 = mint
            TRANSFER_TOPIC = w3.keccak(text='Transfer(address,address,uint256)').hex()
            ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'

            for log in receipt['logs']:
                if log['address'].lower() == nft_contract_address:
                    if log['topics'][0].hex() == TRANSFER_TOPIC:
                        from_addr = '0x' + log['topics'][1].hex()[-40:]
                        to_addr = '0x' + log['topics'][2].hex()[-40:]
                        token_id = int(log['topics'][3].hex(), 16)

                        if to_addr.lower() == ZERO_ADDRESS.lower():
                            # Burn event
                            burned_token_ids.append(token_id)
                        elif from_addr.lower() == ZERO_ADDRESS.lower():
                            # Mint event
                            new_token_id = token_id

            if not new_token_id:
                return None, "Recovery failed: Could not find minted token in transaction."

            if len(burned_token_ids) != 3:
                return None, f"Recovery failed: Expected 3 burned tokens, found {len(burned_token_ids)}."

            logger.info(f"[NFT Upgrade Recovery] Found: burned={burned_token_ids}, minted={new_token_id}")

            # Check if the new token is already in DB
            existing_nft = NFTInventory.query.filter_by(token_id=new_token_id, user_id=user_id).first()
            if existing_nft:
                logger.info(f"[NFT Upgrade Recovery] NFT #{new_token_id} already exists in database")
                # Clean up any burned NFTs still in DB
                for burned_id in burned_token_ids:
                    burned_nft = NFTInventory.query.filter_by(token_id=burned_id, user_id=user_id).first()
                    if burned_nft:
                        NFTMarketplace.query.filter_by(nft_id=burned_nft.id).delete()
                        NFTTradeHistory.query.filter_by(nft_id=burned_nft.id).delete()
                        db.session.delete(burned_nft)
                db.session.commit()
                return existing_nft, None

            # Get NFT metadata from blockchain
            from app.blockchain.nft_contract import get_nft_metadata_from_chain
            metadata = get_nft_metadata_from_chain(new_token_id)

            if not metadata:
                return None, "Recovery failed: Could not fetch NFT metadata from blockchain."

            # Determine tier from burned NFTs (new tier = old tier + 1)
            # Since we burned 3 of same tier, new tier is next level
            # We'll infer from the metadata or default based on typical upgrade pattern
            new_tier = metadata.get('tier', 2)  # Default to Q2 if unknown
            nft_type = metadata.get('nft_type', 'player')
            category = metadata.get('category', 'combat_boost')

            # Get bonus value from config if blockchain returns 0
            bonus_value = metadata.get('bonus_value', 0)
            if bonus_value == 0:
                from app.blockchain.nft_config import get_nft_bonus_value
                bonus_value = get_nft_bonus_value(nft_type, category, new_tier)
                logger.info(f"[NFT Upgrade Recovery] Using config bonus value: {bonus_value}%")

            # Create the new NFT
            new_nft = NFTInventory(
                user_id=user_id,
                nft_type=nft_type,
                category=category,
                tier=new_tier,
                bonus_value=bonus_value,
                token_id=new_token_id,
                contract_address=nft_contract_address,
                acquired_via='upgrade',
                metadata_uri=metadata.get('metadata_uri', '')
            )

            db.session.add(new_nft)

            # Record burn history
            burn_record = NFTBurnHistory(
                user_id=user_id,
                burned_nft_ids=burned_token_ids,
                minted_nft_id=new_token_id,
                tier_from=new_tier - 1,
                tier_to=new_tier,
                transaction_hash=tx_hash
            )
            db.session.add(burn_record)

            # Remove any burned NFTs still in database
            for burned_id in burned_token_ids:
                burned_nft = NFTInventory.query.filter_by(token_id=burned_id, user_id=user_id).first()
                if burned_nft:
                    NFTMarketplace.query.filter_by(nft_id=burned_nft.id).delete()
                    NFTTradeHistory.query.filter_by(nft_id=burned_nft.id).delete()
                    db.session.delete(burned_nft)

            db.session.commit()

            logger.info(f"[NFT Upgrade Recovery] SUCCESS: Recovered NFT #{new_token_id} for user {user_id}")
            return new_nft, None

        except Exception as e:
            db.session.rollback()
            logger.error(f"[NFT Upgrade Recovery] FAILED: {e}")
            return None, f"Recovery failed: {str(e)}"

    @staticmethod
    def equip_nft_to_profile(user_id: int, nft_id: int, slot: int) -> Tuple[bool, Optional[str]]:
        """
        Equip an NFT to player profile with 24-hour cooldown per slot

        Args:
            user_id: ID of the user
            nft_id: ID of the NFT to equip
            slot: Slot number (1-3)

        Returns:
            (success, error_message)
        """
        from datetime import timedelta

        # Validate slot
        if slot < 1 or slot > PLAYER_NFT_SLOTS:
            return False, f"Invalid slot. Must be 1-{PLAYER_NFT_SLOTS}."

        # Get NFT
        nft = NFTInventory.query.filter_by(id=nft_id, user_id=user_id).first()
        if not nft:
            return False, "NFT not found or not owned by user."

        # Check NFT type
        if nft.nft_type != NFTType.PLAYER:
            return False, "Only player NFTs can be equipped to profiles."

        # Check if NFT is already equipped in ANY slot
        if nft.is_equipped:
            return False, "This NFT is already equipped in another slot."

        # Get or create player slots
        player_slots = PlayerNFTSlots.query.get(user_id)
        if not player_slots:
            player_slots = PlayerNFTSlots(user_id=user_id)
            db.session.add(player_slots)

        # Check if slot is occupied
        slot_attr = f'slot_{slot}_nft_id'
        slot_timestamp_attr = f'slot_{slot}_last_modified'
        current_nft_id = getattr(player_slots, slot_attr, None)

        if current_nft_id:
            return False, f"Slot {slot} is already occupied. Unequip it first."

        # Check 24-hour cooldown for this slot
        last_modified = getattr(player_slots, slot_timestamp_attr, None)
        if last_modified:
            time_since_last_change = datetime.utcnow() - last_modified
            if time_since_last_change < timedelta(hours=24):
                hours_remaining = 24 - (time_since_last_change.total_seconds() / 3600)
                return False, f"Slot {slot} is on cooldown. You can change it in {hours_remaining:.1f} hours."

        # Equip NFT
        setattr(player_slots, slot_attr, nft_id)
        setattr(player_slots, slot_timestamp_attr, datetime.utcnow())
        nft.is_equipped = True
        nft.equipped_to_profile = True

        db.session.commit()

        logger.info(f"User {user_id} equipped NFT {nft_id} to profile slot {slot}")
        return True, None

    @staticmethod
    def unequip_nft_from_profile(user_id: int, slot: int) -> Tuple[bool, Optional[str]]:
        """
        Unequip an NFT from player profile with 24-hour cooldown per slot

        Args:
            user_id: ID of the user
            slot: Slot number (1-3)

        Returns:
            (success, error_message)
        """
        from datetime import timedelta

        # Validate slot
        if slot < 1 or slot > PLAYER_NFT_SLOTS:
            return False, f"Invalid slot. Must be 1-{PLAYER_NFT_SLOTS}."

        # Get player slots
        player_slots = PlayerNFTSlots.query.get(user_id)
        if not player_slots:
            return False, "No equipped NFTs found."

        # Get slot NFT
        slot_attr = f'slot_{slot}_nft_id'
        slot_timestamp_attr = f'slot_{slot}_last_modified'
        nft_id = getattr(player_slots, slot_attr, None)

        if not nft_id:
            return False, f"Slot {slot} is already empty."

        # Check 24-hour cooldown for this slot
        last_modified = getattr(player_slots, slot_timestamp_attr, None)
        if last_modified:
            time_since_last_change = datetime.utcnow() - last_modified
            if time_since_last_change < timedelta(hours=24):
                hours_remaining = 24 - (time_since_last_change.total_seconds() / 3600)
                return False, f"Slot {slot} is on cooldown. You can change it in {hours_remaining:.1f} hours."

        # Get NFT and unequip
        nft = NFTInventory.query.get(nft_id)
        if nft:
            nft.is_equipped = False
            nft.equipped_to_profile = False

        setattr(player_slots, slot_attr, None)
        setattr(player_slots, slot_timestamp_attr, datetime.utcnow())

        db.session.commit()

        logger.info(f"User {user_id} unequipped NFT {nft_id} from profile slot {slot}")
        return True, None

    @staticmethod
    def equip_nft_to_company(user_id: int, company_id: int, nft_id: int, slot: int) -> Tuple[bool, Optional[str]]:
        """
        Equip an NFT to a company with 24-hour cooldown per slot and quality-based slot limits

        Args:
            user_id: ID of the user
            company_id: ID of the company
            nft_id: ID of the NFT to equip
            slot: Slot number (1-3)

        Returns:
            (success, error_message)
        """
        from app.models.company import Company
        from datetime import timedelta

        # Get company
        company = Company.query.get(company_id)
        if not company:
            return False, "Company not found."

        # Check ownership
        if company.owner_id != user_id:
            return False, "You don't own this company."

        # Check slot availability based on company quality_level
        max_slots = get_company_slot_count(company.quality_level)
        if slot < 1 or slot > max_slots:
            return False, f"Invalid slot. Q{company.quality_level} companies have {max_slots} slot(s)."

        # Get NFT
        nft = NFTInventory.query.filter_by(id=nft_id, user_id=user_id).first()
        if not nft:
            return False, "NFT not found or not owned by user."

        # Check NFT type
        if nft.nft_type != NFTType.COMPANY:
            return False, "Only company NFTs can be equipped to companies."

        # Check if NFT is already equipped in ANY slot
        if nft.is_equipped:
            return False, "This NFT is already equipped in another slot."

        # Get or create company slots
        company_slots = CompanyNFTSlots.query.get(company_id)
        if not company_slots:
            company_slots = CompanyNFTSlots(company_id=company_id)
            db.session.add(company_slots)

        # Check if slot is occupied
        slot_attr = f'slot_{slot}_nft_id'
        slot_timestamp_attr = f'slot_{slot}_last_modified'
        current_nft_id = getattr(company_slots, slot_attr, None)

        if current_nft_id:
            return False, f"Slot {slot} is already occupied. Unequip it first."

        # Check 24-hour cooldown for this slot
        last_modified = getattr(company_slots, slot_timestamp_attr, None)
        if last_modified:
            time_since_last_change = datetime.utcnow() - last_modified
            if time_since_last_change < timedelta(hours=24):
                hours_remaining = 24 - (time_since_last_change.total_seconds() / 3600)
                return False, f"Slot {slot} is on cooldown. You can change it in {hours_remaining:.1f} hours."

        # Equip NFT
        setattr(company_slots, slot_attr, nft_id)
        setattr(company_slots, slot_timestamp_attr, datetime.utcnow())
        nft.is_equipped = True
        nft.equipped_to_company_id = company_id

        db.session.commit()

        logger.info(f"User {user_id} equipped NFT {nft_id} to company {company_id} slot {slot}")
        return True, None

    @staticmethod
    def unequip_nft_from_company(user_id: int, company_id: int, slot: int) -> Tuple[bool, Optional[str]]:
        """
        Unequip an NFT from a company with 24-hour cooldown per slot

        Args:
            user_id: ID of the user
            company_id: ID of the company
            slot: Slot number (1-3)

        Returns:
            (success, error_message)
        """
        from app.models.company import Company
        from datetime import timedelta

        # Get company
        company = Company.query.get(company_id)
        if not company:
            return False, "Company not found."

        # Check ownership
        if company.owner_id != user_id:
            return False, "You don't own this company."

        # Validate slot
        max_slots = get_company_slot_count(company.quality_level)
        if slot < 1 or slot > max_slots:
            return False, f"Invalid slot. Must be 1-{max_slots}."

        # Get company slots
        company_slots = CompanyNFTSlots.query.get(company_id)
        if not company_slots:
            return False, "No equipped NFTs found."

        # Get slot NFT
        slot_attr = f'slot_{slot}_nft_id'
        slot_timestamp_attr = f'slot_{slot}_last_modified'
        nft_id = getattr(company_slots, slot_attr, None)

        if not nft_id:
            return False, f"Slot {slot} is already empty."

        # Check 24-hour cooldown for this slot
        last_modified = getattr(company_slots, slot_timestamp_attr, None)
        if last_modified:
            time_since_last_change = datetime.utcnow() - last_modified
            if time_since_last_change < timedelta(hours=24):
                hours_remaining = 24 - (time_since_last_change.total_seconds() / 3600)
                return False, f"Slot {slot} is on cooldown. You can change it in {hours_remaining:.1f} hours."

        # Get NFT and unequip
        nft = NFTInventory.query.get(nft_id)
        if nft:
            nft.is_equipped = False
            nft.equipped_to_company_id = None

        setattr(company_slots, slot_attr, None)
        setattr(company_slots, slot_timestamp_attr, datetime.utcnow())

        db.session.commit()

        logger.info(f"User {user_id} unequipped NFT {nft_id} from company {company_id} slot {slot}")
        return True, None

    @staticmethod
    def get_player_bonuses(user_id: int) -> Dict[str, int]:
        """
        Calculate total bonuses from equipped player NFTs

        Args:
            user_id: ID of the user

        Returns:
            Dictionary of bonuses by category
        """
        bonuses = {
            'combat_boost': 0,
            'energy_regen': 0,
            'wellness_regen': 0,
            'military_tutor': 0,      # XP bonus for military rank
            'travel_discount': 0,     # Travel cost discount percentage
            'storage_increase': 0     # Extra storage capacity
        }

        # Get player slots
        player_slots = PlayerNFTSlots.query.get(user_id)
        if not player_slots:
            return bonuses

        # Sum bonuses from equipped NFTs
        for nft in player_slots.get_equipped_nfts():
            if nft and nft.category in bonuses:
                bonuses[nft.category] += nft.bonus_value

        return bonuses

    @staticmethod
    def get_company_bonuses(company_id: int) -> Dict[str, int]:
        """
        Calculate total bonuses from equipped company NFTs

        Args:
            company_id: ID of the company

        Returns:
            Dictionary of bonuses by category
        """
        bonuses = {
            'production_boost': 0,
            'material_efficiency': 0,
            'upgrade_discount': 0,
            'speed_boost': 0,
            'android_worker': 0,    # Android worker skill level
            'tax_breaks': 0         # Tax reduction percentage
        }

        # Get company slots
        company_slots = CompanyNFTSlots.query.get(company_id)
        if not company_slots:
            return bonuses

        # Sum bonuses from equipped NFTs
        for nft in company_slots.get_equipped_nfts():
            if nft and nft.category in bonuses:
                bonuses[nft.category] += nft.bonus_value

        return bonuses

    @staticmethod
    def get_user_nfts(user_id: int, nft_type: Optional[str] = None,
                      equipped_only: bool = False) -> List[NFTInventory]:
        """
        Get all NFTs owned by a user

        Args:
            user_id: ID of the user
            nft_type: Optional filter by type ('player' or 'company')
            equipped_only: Only return equipped NFTs

        Returns:
            List of NFTInventory objects
        """
        query = NFTInventory.query.filter_by(user_id=user_id)

        if nft_type:
            query = query.filter_by(nft_type=nft_type)

        if equipped_only:
            query = query.filter_by(is_equipped=True)

        return query.order_by(NFTInventory.tier.desc(), NFTInventory.acquired_at.desc()).all()

    @staticmethod
    def transfer_nft(from_user_id: int, to_user_id: int, nft_id: int,
                     price_zen: Optional[float] = None, price_gold: Optional[float] = None,
                     trade_type: str = 'transfer') -> Tuple[bool, Optional[str]]:
        """
        Transfer NFT from one user to another

        Args:
            from_user_id: ID of sender
            to_user_id: ID of receiver
            nft_id: ID of NFT to transfer
            price_zen: Optional ZEN price (for sales)
            price_gold: Optional gold price (for sales)
            trade_type: Type of trade ('sale', 'gift', 'transfer')

        Returns:
            (success, error_message)
        """
        from app.models.user import User

        # Get users
        from_user = User.query.get(from_user_id)
        to_user = User.query.get(to_user_id)

        if not from_user or not to_user:
            return False, "User not found."

        # Get NFT
        nft = NFTInventory.query.filter_by(id=nft_id, user_id=from_user_id).first()
        if not nft:
            return False, "NFT not found or not owned by sender."

        # Check if equipped
        if nft.is_equipped:
            return False, "Cannot transfer equipped NFT. Unequip first."

        # Handle payment if sale
        if trade_type == 'sale':
            if price_zen:
                # ZEN payment is handled on-chain via smart contract
                # The transaction should already be verified before this point
                pass
            if price_gold and price_gold > 0:
                # Gold payment - deduct from buyer, add to seller
                from app.services.currency_service import CurrencyService
                from decimal import Decimal

                buyer = User.query.get(to_user_id)
                seller = User.query.get(from_user_id)

                if not buyer or not seller:
                    return False, "Invalid buyer or seller."

                gold_amount = Decimal(str(price_gold))

                # Check buyer has enough gold
                if buyer.gold < gold_amount:
                    return False, f"Insufficient gold. Need {price_gold} Gold."

                # Deduct from buyer
                success, message, _ = CurrencyService.deduct_gold(
                    to_user_id, gold_amount, f'NFT purchase (ID: {nft_id})'
                )
                if not success:
                    return False, f"Payment failed: {message}"

                # Add to seller
                success, message, _ = CurrencyService.add_gold(
                    from_user_id, gold_amount, f'NFT sale (ID: {nft_id})'
                )
                if not success:
                    # Rollback buyer deduction would be complex - log error
                    logger.error(f"Failed to credit seller {from_user_id} for NFT sale: {message}")

        # Transfer ownership
        nft.user_id = to_user_id

        # Record trade
        trade = NFTTradeHistory(
            nft_id=nft_id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            price_zen=price_zen,
            price_gold=price_gold,
            trade_type=trade_type
        )
        db.session.add(trade)

        db.session.commit()

        return True, None

    @staticmethod
    def list_nft_on_marketplace(
        user_id: int,
        wallet_address: str,
        nft_id: int,
        price_zen: float,
        tx_hash: str
    ) -> Tuple[Optional[NFTMarketplace], Optional[str]]:
        """
        List an NFT on the marketplace (verifies blockchain transaction)

        Args:
            user_id: ID of the user listing
            wallet_address: User's wallet address
            nft_id: Database NFT ID to list
            price_zen: Price in ZEN tokens
            tx_hash: Transaction hash of the listNFT() call

        Returns:
            (NFTMarketplace object, error_message)
        """
        from app.blockchain.marketplace_contract import verify_listing_transaction
        from decimal import Decimal

        # Get NFT
        nft = NFTInventory.query.filter_by(id=nft_id, user_id=user_id).first()
        if not nft:
            return None, "NFT not found or not owned by you."

        # Check if equipped
        if nft.is_equipped:
            return None, "Cannot list equipped NFT. Please unequip it first."

        # Check if already listed
        existing_listing = NFTMarketplace.query.filter_by(
            nft_id=nft_id,
            is_active=True
        ).first()

        if existing_listing:
            return None, "NFT is already listed on marketplace."

        # Verify blockchain transaction
        verified = verify_listing_transaction(
            tx_hash=tx_hash,
            expected_seller=wallet_address,
            expected_token_id=nft.token_id,
            expected_price=Decimal(str(price_zen))
        )

        if not verified:
            return None, "Failed to verify listing transaction on blockchain."

        # Create marketplace listing
        listing = NFTMarketplace(
            nft_id=nft_id,
            seller_id=user_id,
            price_zen=price_zen,
            is_active=True
        )

        db.session.add(listing)
        db.session.commit()

        logger.info(f"User {user_id} listed NFT {nft_id} for {price_zen} ZEN")
        return listing, None

    @staticmethod
    def buy_nft_from_marketplace(
        buyer_id: int,
        buyer_wallet: str,
        listing_id: int,
        tx_hash: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Purchase an NFT from the marketplace (verifies blockchain transaction)

        Args:
            buyer_id: ID of the buyer
            buyer_wallet: Buyer's wallet address
            listing_id: Database listing ID
            tx_hash: Transaction hash of the buyNFT() call

        Returns:
            (success, error_message)
        """
        from app.blockchain.marketplace_contract import verify_purchase_transaction

        # Get listing
        listing = NFTMarketplace.query.get(listing_id)
        if not listing:
            return False, "Listing not found."

        if not listing.is_active:
            return False, "Listing is no longer active."

        # Check if buyer is seller
        if listing.seller_id == buyer_id:
            return False, "Cannot buy your own NFT."

        # Get NFT
        nft = listing.nft
        if not nft:
            return False, "NFT not found."

        # Verify blockchain transaction
        purchase_data = verify_purchase_transaction(
            tx_hash=tx_hash,
            expected_buyer=buyer_wallet,
            expected_token_id=nft.token_id
        )

        if not purchase_data:
            return False, "Failed to verify purchase transaction on blockchain."

        # Transfer ownership
        nft.user_id = buyer_id

        # Update listing
        listing.is_active = False
        listing.sold_at = datetime.utcnow()
        listing.buyer_id = buyer_id

        # Record trade history
        trade = NFTTradeHistory(
            nft_id=nft.id,
            from_user_id=listing.seller_id,
            to_user_id=buyer_id,
            price_zen=listing.price_zen,
            trade_type='sale',
            transaction_hash=tx_hash
        )
        db.session.add(trade)

        db.session.commit()

        logger.info(f"User {buyer_id} purchased NFT {nft.id} from user {listing.seller_id} for {listing.price_zen} ZEN")
        return True, None

    @staticmethod
    def cancel_marketplace_listing(
        user_id: int,
        wallet_address: str,
        listing_id: int,
        tx_hash: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Cancel a marketplace listing (verifies blockchain transaction)

        Args:
            user_id: ID of the user canceling
            wallet_address: User's wallet address
            listing_id: Database listing ID
            tx_hash: Transaction hash of the cancelListing() call

        Returns:
            (success, error_message)
        """
        from app.blockchain.marketplace_contract import verify_cancel_transaction

        # Get listing
        listing = NFTMarketplace.query.get(listing_id)
        if not listing:
            return False, "Listing not found."

        # Check ownership
        if listing.seller_id != user_id:
            return False, "You don't own this listing."

        if not listing.is_active:
            return False, "Listing is already inactive."

        # Get NFT
        nft = listing.nft
        if not nft:
            return False, "NFT not found."

        # Verify blockchain transaction
        verified = verify_cancel_transaction(
            tx_hash=tx_hash,
            expected_seller=wallet_address,
            expected_token_id=nft.token_id
        )

        if not verified:
            return False, "Failed to verify cancel transaction on blockchain."

        # Mark as inactive
        listing.is_active = False

        db.session.commit()

        logger.info(f"User {user_id} cancelled listing {listing_id}")
        return True, None

    @staticmethod
    def get_marketplace_listings(
        nft_type: Optional[str] = None,
        category: Optional[str] = None,
        min_tier: Optional[int] = None,
        max_tier: Optional[int] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        sort_by: str = 'listed_at',
        sort_order: str = 'desc'
    ) -> List[NFTMarketplace]:
        """
        Get marketplace listings with filters

        Args:
            nft_type: Filter by NFT type ('player' or 'company')
            category: Filter by category
            min_tier: Minimum tier (1-5)
            max_tier: Maximum tier (1-5)
            min_price: Minimum price in ZEN
            max_price: Maximum price in ZEN
            sort_by: Sort field ('listed_at', 'price_zen', 'tier')
            sort_order: Sort order ('asc' or 'desc')

        Returns:
            List of NFTMarketplace objects
        """
        query = NFTMarketplace.query.filter_by(is_active=True)

        # Join with NFTInventory for filtering
        query = query.join(NFTInventory, NFTMarketplace.nft_id == NFTInventory.id)

        # Apply filters
        if nft_type:
            query = query.filter(NFTInventory.nft_type == nft_type)

        if category:
            query = query.filter(NFTInventory.category == category)

        if min_tier:
            query = query.filter(NFTInventory.tier >= min_tier)

        if max_tier:
            query = query.filter(NFTInventory.tier <= max_tier)

        if min_price:
            query = query.filter(NFTMarketplace.price_zen >= min_price)

        if max_price:
            query = query.filter(NFTMarketplace.price_zen <= max_price)

        # Apply sorting
        if sort_by == 'price_zen':
            sort_col = NFTMarketplace.price_zen
        elif sort_by == 'tier':
            sort_col = NFTInventory.tier
        else:
            sort_col = NFTMarketplace.listed_at

        if sort_order == 'asc':
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())

        return query.all()

    @staticmethod
    def get_user_marketplace_listings(user_id: int, active_only: bool = True) -> List[NFTMarketplace]:
        """
        Get user's marketplace listings

        Args:
            user_id: ID of the user
            active_only: Only return active listings

        Returns:
            List of NFTMarketplace objects
        """
        query = NFTMarketplace.query.filter_by(seller_id=user_id)

        if active_only:
            query = query.filter_by(is_active=True)

        return query.order_by(NFTMarketplace.listed_at.desc()).all()
