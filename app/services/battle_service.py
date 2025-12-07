# app/services/battle_service.py
"""
Battle Service

Handles all battle-related logic including:
- Damage calculation
- Fighting (dealing damage)
- Battle/round creation and management
- Initiative tracking
- Region capture
- Battle hero awards
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from flask import current_app

from app.extensions import db
from app.models import (
    User, War, Battle, BattleRound, BattleParticipation, BattleDamage, BattleHero,
    Alliance, Region, Country, Resource, InventoryItem, Employment,
    MilitaryRank, WarStatus, Alert, AlertType, AlertPriority
)
from app.models.battle import BattleStatus, RoundStatus, WallType
from app.services.nft_service import NFTService
from app.services.inventory_service import InventoryService


# Weapon quality bonuses (percentage added to base damage)
WEAPON_QUALITY_BONUS = {
    1: 30,   # Q1: +30%
    2: 60,   # Q2: +60%
    3: 90,   # Q3: +90%
    4: 120,  # Q4: +120%
    5: 150,  # Q5: +150%
}

# Weapon slugs for each wall type
WALL_WEAPON_SLUGS = {
    WallType.INFANTRY: 'rifle',
    WallType.ARMOURED: 'tank',
    WallType.AVIATION: 'helicopter',
}

# Skill attributes for each wall type
WALL_SKILL_ATTRS = {
    WallType.INFANTRY: 'infantry_skill',
    WallType.ARMOURED: 'armoured_skill',
    WallType.AVIATION: 'aviation_skill',
}

# Fight costs
FIGHT_ENERGY_COST = 10
FIGHT_WELLNESS_COST = 10
FIGHT_COOLDOWN_SECONDS = 1.5

# Battle initiation cost (gold from country treasury)
BATTLE_START_COST_GOLD = Decimal('10.0')

# Battle timing
BATTLE_DURATION_HOURS = 24
ROUND_DURATION_HOURS = 8
NUM_ROUNDS = 3


class BattleService:
    """Service for battle-related operations."""

    # =========================================================================
    # DAMAGE CALCULATION
    # =========================================================================

    @staticmethod
    def calculate_base_damage(user: User, wall_type: WallType) -> float:
        """
        Calculate base damage for a user.

        Formula: base_damage = (level * 2) + (skill * 10)

        Args:
            user: The user fighting
            wall_type: Which wall they're fighting at

        Returns:
            Base damage value
        """
        level = user.level or 1
        skill_attr = WALL_SKILL_ATTRS.get(wall_type, 'infantry_skill')
        skill = getattr(user, skill_attr, 0) or 0

        base_damage = (level * 2) + (skill * 10)
        return base_damage

    @staticmethod
    def get_rank_damage_bonus(user: User) -> int:
        """
        Get military rank damage bonus percentage.

        Args:
            user: The user

        Returns:
            Damage bonus percentage (e.g., 2 for +2%)
        """
        if user.rank:
            return user.rank.damage_bonus or 0
        return 0

    @staticmethod
    def get_nft_damage_bonus(user_id: int) -> int:
        """
        Get NFT combat boost percentage.

        Args:
            user_id: User's ID

        Returns:
            Damage bonus percentage from NFTs
        """
        bonuses = NFTService.get_player_bonuses(user_id)
        return bonuses.get('combat_boost', 0)

    @staticmethod
    def get_weapon_bonus(quality: Optional[int]) -> int:
        """
        Get weapon quality damage bonus percentage.

        Args:
            quality: Weapon quality (1-5) or None if barehanded

        Returns:
            Damage bonus percentage
        """
        if quality is None:
            return 0
        return WEAPON_QUALITY_BONUS.get(quality, 0)

    @staticmethod
    def calculate_final_damage(
        user: User,
        wall_type: WallType,
        weapon_quality: Optional[int] = None
    ) -> Tuple[int, Dict]:
        """
        Calculate final damage with all bonuses.

        Formula: final = base * (1 + rank_bonus% + weapon_bonus% + nft_bonus%)

        Args:
            user: The user fighting
            wall_type: Which wall they're fighting at
            weapon_quality: Quality of weapon used (None if barehanded)

        Returns:
            Tuple of (final_damage, breakdown_dict)
        """
        base_damage = BattleService.calculate_base_damage(user, wall_type)
        rank_bonus = BattleService.get_rank_damage_bonus(user)
        nft_bonus = BattleService.get_nft_damage_bonus(user.id)
        weapon_bonus = BattleService.get_weapon_bonus(weapon_quality)

        # Total multiplier
        total_bonus_percent = rank_bonus + weapon_bonus + nft_bonus
        multiplier = 1 + (total_bonus_percent / 100)

        final_damage = round(base_damage * multiplier)

        breakdown = {
            'base_damage': base_damage,
            'rank_bonus_percent': rank_bonus,
            'weapon_bonus_percent': weapon_bonus,
            'nft_bonus_percent': nft_bonus,
            'total_bonus_percent': total_bonus_percent,
            'multiplier': multiplier,
            'final_damage': final_damage,
        }

        return final_damage, breakdown

    # =========================================================================
    # FIGHTING
    # =========================================================================

    @staticmethod
    def can_user_fight(user: User, battle: Battle) -> Tuple[bool, str]:
        """
        Check if a user can fight in a battle.

        Args:
            user: The user wanting to fight
            battle: The battle to fight in

        Returns:
            Tuple of (can_fight, error_message)
        """
        # Check battle is active
        if not battle.is_active:
            return False, "This battle is no longer active."

        # Get current round
        current_round = battle.get_current_round()
        if not current_round or not current_round.is_active:
            return False, "No active round in this battle."

        # Check user has enough energy
        if user.energy < FIGHT_ENERGY_COST:
            return False, f"Not enough energy. You need {FIGHT_ENERGY_COST} energy to fight."

        # Check user has enough wellness
        if user.wellness < FIGHT_WELLNESS_COST:
            return False, f"Not enough wellness. You need {FIGHT_WELLNESS_COST} wellness to fight."

        # Check cooldown
        participation = BattleParticipation.query.filter_by(
            battle_id=battle.id,
            round_number=current_round.round_number,
            user_id=user.id
        ).first()

        if participation and not participation.can_fight:
            remaining = participation.cooldown_remaining
            return False, f"You must wait {remaining:.1f} seconds before fighting again."

        return True, ""

    @staticmethod
    def determine_user_side(user: User, battle: Battle, chosen_side: Optional[bool] = None) -> Tuple[bool, Optional[bool], str]:
        """
        Determine which side a user fights for based on their location and MPPs.

        For resistance wars: Anyone in the occupying country can choose their side.

        Args:
            user: The user
            battle: The battle
            chosen_side: For resistance wars, the side chosen by the user (True=resistance/attacker, False=occupier/defender)

        Returns:
            Tuple of (can_fight, is_attacker, error_message)
            is_attacker is True for attacker side, False for defender side, None if can't fight
        """
        war = battle.war
        if not war:
            return False, None, "Battle is in invalid state (no associated war)."

        attacker_id = war.attacker_country_id
        defender_id = war.defender_country_id

        # Get user's current region and its owner
        if not user.current_region:
            return False, None, "You must be in a region to fight."

        region_owner = user.current_region.current_owner
        if not region_owner:
            return False, None, "Your current region has no owner."

        user_location_country_id = region_owner.id

        # Special handling for resistance wars
        if war.is_resistance_war:
            # In resistance wars, anyone in the occupying country (defender) can fight for either side
            # Attacker = resistance (original country)
            # Defender = occupying country
            if user_location_country_id == defender_id:
                # User is in the occupying country - they can choose their side
                # Check if they already have participation in this battle to determine their side
                existing_participation = BattleParticipation.query.filter_by(
                    battle_id=battle.id,
                    user_id=user.id
                ).first()

                if existing_participation:
                    # User already chose a side - stick with it
                    return True, existing_participation.is_attacker, ""
                elif chosen_side is not None:
                    # User is choosing a side now
                    return True, chosen_side, ""
                else:
                    # User needs to choose a side (return special message)
                    return True, None, "CHOOSE_SIDE"

            # User is not in the occupying country - can't participate
            defender_name = war.defender_country.name if war.defender_country else "the defending country"
            return False, None, f"You must be located in {defender_name} to participate in this resistance war."

        # Regular war logic
        # Check if user is in attacker's territory
        if user_location_country_id == attacker_id:
            return True, True, ""

        # Check if user is in defender's territory
        if user_location_country_id == defender_id:
            return True, False, ""

        # Check alliance with attacker
        attacker_allies = Alliance.get_all_allies(attacker_id)
        if user_location_country_id in attacker_allies:
            # Check if user's country also has alliance with defender (can't fight)
            defender_allies = Alliance.get_all_allies(defender_id)
            if user_location_country_id in defender_allies:
                return False, None, "Your country is allied with both sides and cannot participate."
            return True, True, ""

        # Check alliance with defender
        defender_allies = Alliance.get_all_allies(defender_id)
        if user_location_country_id in defender_allies:
            return True, False, ""

        return False, None, "You must be located in a participating country's territory to fight."

    @staticmethod
    def get_best_weapon(user: User, wall_type: WallType) -> Tuple[Optional[int], Optional[int]]:
        """
        Get the best weapon for this wall type from user's inventory.

        Args:
            user: The user
            wall_type: The wall type to find weapon for

        Returns:
            Tuple of (resource_id, quality) or (None, None) if no weapons
        """
        weapon_slug = WALL_WEAPON_SLUGS.get(wall_type)
        if not weapon_slug:
            return None, None

        # Find the resource
        weapon_resource = Resource.query.filter_by(slug=weapon_slug).first()
        if not weapon_resource:
            return None, None

        # Find user's inventory of this weapon, ordered by quality descending
        inventory_items = InventoryItem.query.filter_by(
            user_id=user.id,
            resource_id=weapon_resource.id
        ).filter(
            InventoryItem.quantity > 0,
            InventoryItem.quality > 0
        ).order_by(
            InventoryItem.quality.desc()
        ).all()

        if inventory_items:
            best = inventory_items[0]
            return best.resource_id, best.quality

        return None, None

    @staticmethod
    def get_available_weapons(user: User, wall_type: WallType) -> List[Dict]:
        """
        Get all available weapons for this wall type from user's inventory.

        Args:
            user: The user
            wall_type: The wall type to find weapons for

        Returns:
            List of dicts with quality and quantity info
        """
        weapon_slug = WALL_WEAPON_SLUGS.get(wall_type)
        if not weapon_slug:
            return []

        # Find the resource
        weapon_resource = Resource.query.filter_by(slug=weapon_slug).first()
        if not weapon_resource:
            return []

        # Find user's inventory of this weapon, ordered by quality descending
        inventory_items = InventoryItem.query.filter_by(
            user_id=user.id,
            resource_id=weapon_resource.id
        ).filter(
            InventoryItem.quantity > 0,
            InventoryItem.quality > 0
        ).order_by(
            InventoryItem.quality.desc()
        ).all()

        return [
            {'quality': item.quality, 'quantity': item.quantity, 'resource_id': item.resource_id}
            for item in inventory_items
        ]

    @staticmethod
    def consume_weapon(user: User, resource_id: int, quality: int) -> bool:
        """
        Consume one weapon from user's inventory.

        Args:
            user: The user
            resource_id: Resource ID of the weapon
            quality: Quality of the weapon

        Returns:
            True if weapon was consumed, False otherwise
        """
        # Lock row to prevent race conditions on weapon consumption
        inventory_item = db.session.scalar(
            db.select(InventoryItem)
            .where(InventoryItem.user_id == user.id)
            .where(InventoryItem.resource_id == resource_id)
            .where(InventoryItem.quality == quality)
            .with_for_update()
        )

        if not inventory_item or inventory_item.quantity < 1:
            return False

        inventory_item.quantity -= 1
        return True

    @staticmethod
    def fight(
        user: User,
        battle: Battle,
        wall_type: WallType,
        use_weapon: bool = True,
        preferred_quality: Optional[int] = None,
        chosen_side: Optional[bool] = None
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Execute a fight action.

        Args:
            user: The user fighting
            battle: The battle
            wall_type: Which wall to fight at
            use_weapon: Whether to use a weapon (True) or fight barehanded (False)
            preferred_quality: Preferred weapon quality (None = use best available)
            chosen_side: For resistance wars, the side chosen by user (True=resistance, False=occupier)

        Returns:
            Tuple of (success, message, damage_info)
        """
        # Validate user can fight
        can_fight, error = BattleService.can_user_fight(user, battle)
        if not can_fight:
            return False, error, None

        # Determine which side user fights for (pass chosen_side for resistance wars)
        can_participate, is_attacker, error = BattleService.determine_user_side(user, battle, chosen_side)
        if not can_participate:
            return False, error, None

        # For resistance wars, if user hasn't chosen a side yet
        if error == "CHOOSE_SIDE":
            return False, "Please choose a side before fighting in this resistance war.", None

        current_round = battle.get_current_round()

        # Get or create participation record
        participation = BattleParticipation.query.filter_by(
            battle_id=battle.id,
            round_number=current_round.round_number,
            user_id=user.id
        ).first()

        if not participation:
            participation = BattleParticipation(
                battle_id=battle.id,
                round_number=current_round.round_number,
                user_id=user.id,
                is_attacker=is_attacker,
                wall_type=wall_type,
                joined_at=datetime.utcnow()
            )
            db.session.add(participation)
        else:
            # Update wall type if changed
            participation.wall_type = wall_type

        # Check cooldown again (in case of race condition)
        if not participation.can_fight:
            return False, "Please wait for cooldown.", None

        # Get weapon if using one
        weapon_resource_id = None
        weapon_quality = None

        if use_weapon:
            if preferred_quality:
                # Use the preferred quality weapon if available
                weapon_slug = WALL_WEAPON_SLUGS.get(wall_type)
                if weapon_slug:
                    weapon_resource = Resource.query.filter_by(slug=weapon_slug).first()
                    if weapon_resource:
                        inventory_item = InventoryItem.query.filter_by(
                            user_id=user.id,
                            resource_id=weapon_resource.id,
                            quality=preferred_quality
                        ).filter(InventoryItem.quantity > 0).first()
                        if inventory_item:
                            weapon_resource_id = weapon_resource.id
                            weapon_quality = preferred_quality

            # Fall back to best weapon if preferred not available
            if not weapon_resource_id:
                weapon_resource_id, weapon_quality = BattleService.get_best_weapon(user, wall_type)

            if weapon_resource_id and weapon_quality:
                # Consume the weapon
                if not BattleService.consume_weapon(user, weapon_resource_id, weapon_quality):
                    weapon_resource_id = None
                    weapon_quality = None

        # Calculate damage
        final_damage, breakdown = BattleService.calculate_final_damage(
            user, wall_type, weapon_quality
        )

        # Apply fortress damage reduction for attackers (disabled in resistance wars)
        fortress_reduction_percent = 0
        war = battle.war
        if is_attacker and not war.is_resistance_war:
            from app.models import RegionalConstruction
            fortress = RegionalConstruction.get_region_fortress(battle.region_id)
            if fortress:
                # Fortress reduces attacker damage: Q1=5%, Q2=10%, Q3=15%, Q4=20%, Q5=25%
                fortress_reduction_percent = fortress.quality * 5
                damage_before_fortress = final_damage
                final_damage = round(final_damage * (1 - fortress_reduction_percent / 100))
                breakdown['fortress_reduction_percent'] = fortress_reduction_percent
                breakdown['damage_before_fortress'] = damage_before_fortress
                breakdown['final_damage'] = final_damage

        # Deduct energy and wellness
        user.energy -= FIGHT_ENERGY_COST
        user.wellness -= FIGHT_WELLNESS_COST

        # Add military XP (100% of damage dealt, modified by Military Tutor NFT)
        from app.services.bonus_calculator import BonusCalculator
        military_xp_multiplier = BonusCalculator.get_military_xp_multiplier(user.id)
        military_xp_gain = int(final_damage * military_xp_multiplier)
        user.add_rank_xp(military_xp_gain)

        # Add player experience (2 XP per successful fight)
        leveled_up, new_level = user.add_experience(2)

        # Create level up alert if player leveled up
        if leveled_up:
            from app.alert_helpers import create_alert
            create_alert(
                user_id=user.id,
                alert_type=AlertType.LEVEL_UP,
                title="Level Up!",
                content=f"Congratulations! You reached Level {new_level}! You received 1 Gold as a reward.",
                priority=AlertPriority.IMPORTANT
            )

        # Record the damage
        damage_record = BattleDamage(
            battle_id=battle.id,
            round_number=current_round.round_number,
            user_id=user.id,
            is_attacker=is_attacker,
            wall_type=wall_type,
            damage=final_damage,
            weapon_resource_id=weapon_resource_id,
            weapon_quality=weapon_quality,
            player_level=user.level or 1,
            player_skill=getattr(user, WALL_SKILL_ATTRS.get(wall_type), 0) or 0,
            military_rank_id=user.military_rank_id or 1,
            rank_damage_bonus=breakdown['rank_bonus_percent'],
            nft_damage_bonus=breakdown['nft_bonus_percent'],
            dealt_at=datetime.utcnow()
        )
        db.session.add(damage_record)

        # Update participation
        participation.total_damage += final_damage
        participation.fight_count += 1
        participation.last_fight_at = datetime.utcnow()

        # Update round damage totals
        current_round.add_damage(wall_type, final_damage, is_attacker)

        # Update bounty contract damage if user's military unit has an active bounty for this battle
        BattleService._update_bounty_damage(user, battle, final_damage, is_attacker)

        # Track mission progress for fighting
        from app.services.mission_service import MissionService
        MissionService.track_progress(user, 'fight', 1)

        db.session.commit()

        damage_info = {
            'damage': final_damage,
            'wall_type': wall_type.value,
            'is_attacker': is_attacker,
            'weapon_used': weapon_quality is not None,
            'weapon_quality': weapon_quality,
            'military_xp_gained': military_xp_gain,
            'breakdown': breakdown,
            'leveled_up': leveled_up,
            'new_level': new_level if leveled_up else None,
            'fortress_reduction_percent': fortress_reduction_percent,
        }

        message = f"You dealt {final_damage} damage!"
        if fortress_reduction_percent > 0:
            message += f" (Fortress reduced by {fortress_reduction_percent}%)"

        return True, message, damage_info

    @staticmethod
    def _check_rank_up(user: User):
        """Check if user should rank up based on military XP."""
        if not user.military_rank_id:
            user.military_rank_id = 1

        current_rank = MilitaryRank.get_rank_by_id(user.military_rank_id)
        if not current_rank:
            return

        next_rank = MilitaryRank.get_next_rank(user.military_rank_id)
        if not next_rank:
            return  # Already at max rank

        if (user.military_experience or 0) >= next_rank.xp_required:
            user.military_rank_id = next_rank.id

    @staticmethod
    def _update_bounty_damage(user: User, battle: Battle, damage: int, is_attacker: bool):
        """
        Update bounty contract damage for user's military unit if applicable.

        Args:
            user: The user who dealt damage
            battle: The battle where damage was dealt
            damage: Amount of damage dealt
            is_attacker: Whether user fought on attacker side
        """
        from app.models import (
            MilitaryUnitMember, BountyContract, BountyContractApplication,
            BountyContractStatus, MilitaryUnit
        )

        # Get user's military unit membership
        membership = MilitaryUnitMember.query.filter_by(
            user_id=user.id,
            is_active=True
        ).first()

        if not membership:
            return  # User not in a military unit

        unit = membership.unit
        if not unit:
            return

        # Find active approved bounty application for this battle (lock rows to prevent race conditions)
        application = db.session.query(BountyContractApplication).join(
            BountyContract,
            BountyContractApplication.contract_id == BountyContract.id
        ).filter(
            BountyContractApplication.unit_id == unit.id,
            BountyContractApplication.status == BountyContractStatus.APPROVED,
            BountyContract.battle_id == battle.id,
            BountyContract.is_active == True
        ).with_for_update().first()

        if not application:
            return  # No active bounty for this battle

        contract = application.contract

        # Check if user is fighting on the correct side for the bounty
        if contract.fight_for_attacker != is_attacker:
            return  # Fighting on wrong side, damage doesn't count

        # Update damage dealt (row is locked)
        application.damage_dealt += damage

        # Check if bounty is now completed
        if application.damage_dealt >= contract.damage_required:
            # Complete the bounty and pay the unit
            payment = contract.payment_amount
            application.complete(payment)

            # Lock unit row before updating treasury and stats
            locked_unit = db.session.scalar(
                db.select(MilitaryUnit).where(MilitaryUnit.id == unit.id).with_for_update()
            )
            # Add payment to unit treasury
            locked_unit.treasury += payment

            # Update unit stats (on locked row)
            locked_unit.contracts_completed += 1
            locked_unit.total_damage += application.damage_dealt

            # Mark contract as no longer active
            contract.is_active = False

    # =========================================================================
    # BATTLE MANAGEMENT
    # =========================================================================

    @staticmethod
    def can_start_battle(
        war: War,
        attacking_country_id: int,
        target_region: Region,
        user: User
    ) -> Tuple[bool, str]:
        """
        Check if a battle can be started.

        Args:
            war: The war
            attacking_country_id: Country starting the battle
            target_region: Region being attacked
            user: User starting the battle

        Returns:
            Tuple of (can_start, error_message)
        """
        # Check war is active
        if not war.is_active():
            return False, "This war is not active."

        # Check no active battle in this war
        if war.has_active_battle():
            return False, "There is already an active battle in this war."

        # Check no active battle on the target region (from ANY war - region lock)
        existing_battle = Battle.query.filter(
            Battle.region_id == target_region.id,
            Battle.status == BattleStatus.ACTIVE
        ).first()
        if existing_battle:
            return False, f"There is already an active battle for {target_region.name}. Wait for it to end."

        # Check initiative
        if not war.can_country_attack(attacking_country_id):
            if war.initiative_holder_id and war.initiative_holder_id != attacking_country_id:
                holder = Country.query.get(war.initiative_holder_id)
                holder_name = holder.name if holder else "the other country"
                return False, f"Initiative belongs to {holder_name}. You cannot attack yet."
            return False, "You cannot start a battle at this time."

        # Check user is president or minister of defence
        user_country_id = user.citizenship_id
        if user_country_id != attacking_country_id:
            return False, "You can only start battles for your own country."

        is_president = user.is_president_of(attacking_country_id)
        is_defence_minister = user.is_minister_of(attacking_country_id, 'defence')

        if not is_president and not is_defence_minister:
            return False, "Only the President or Minister of Defence can start battles."

        # Check target region belongs to enemy
        defending_country_id = war.get_opponent_country_id(attacking_country_id)
        region_owner = target_region.current_owner
        if not region_owner or region_owner.id != defending_country_id:
            return False, "This region does not belong to the enemy."

        # Check if defending country has Starter Protection (only 1 region left)
        defending_country = Country.query.get(defending_country_id)
        if defending_country and defending_country.has_starter_protection:
            return False, f"{defending_country.name} has Starter Protection. Countries with only 1 region cannot be attacked until protection is removed."

        # Check target region is adjacent to attacking country's territory
        attacking_country = Country.query.get(attacking_country_id)
        if not attacking_country:
            return False, "Invalid attacking country."

        # Get all regions owned by attacker
        attacker_regions = attacking_country.current_regions.all()
        attacker_region_ids = [r.id for r in attacker_regions]

        # Check if target region is neighbor to any attacker region
        is_adjacent = False
        for neighbor in target_region.neighbors.all():
            if neighbor.id in attacker_region_ids:
                is_adjacent = True
                break
        for neighbor in target_region.neighbor_of.all():
            if neighbor.id in attacker_region_ids:
                is_adjacent = True
                break

        if not is_adjacent:
            return False, "You can only attack regions adjacent to your territory."

        # Check country has enough gold in treasury
        available_gold = attacking_country.treasury_gold - attacking_country.reserved_gold
        if available_gold < BATTLE_START_COST_GOLD:
            return False, f"Insufficient treasury gold. Starting a battle costs {BATTLE_START_COST_GOLD} gold."

        return True, ""

    @staticmethod
    def start_battle(
        war: War,
        attacking_country_id: int,
        target_region: Region,
        user: User
    ) -> Tuple[Optional[Battle], str]:
        """
        Start a new battle.

        Args:
            war: The war
            attacking_country_id: Country starting the battle
            target_region: Region being attacked
            user: User starting the battle

        Returns:
            Tuple of (battle, message)
        """
        can_start, error = BattleService.can_start_battle(
            war, attacking_country_id, target_region, user
        )
        if not can_start:
            return None, error

        # Deduct gold from country treasury with row-level locking
        attacking_country = db.session.scalar(
            db.select(Country)
            .where(Country.id == attacking_country_id)
            .with_for_update()
        )
        if attacking_country.treasury_gold < BATTLE_START_COST_GOLD:
            return None, f"Insufficient treasury gold. Need {BATTLE_START_COST_GOLD} Gold."
        attacking_country.treasury_gold -= BATTLE_START_COST_GOLD

        now = datetime.utcnow()
        battle_end = now + timedelta(hours=BATTLE_DURATION_HOURS)

        # Create battle
        battle = Battle(
            war_id=war.id,
            region_id=target_region.id,
            started_by_country_id=attacking_country_id,
            started_by_user_id=user.id,
            status=BattleStatus.ACTIVE,
            started_at=now,
            ends_at=battle_end,
            current_round=1
        )
        db.session.add(battle)
        db.session.flush()  # Get battle ID

        # Create first round (active)
        # Only create round 1 initially - subsequent rounds will be created when needed
        # This avoids confusion with pre-created "completed" rounds
        first_round = BattleRound(
            battle_id=battle.id,
            round_number=1,
            status=RoundStatus.ACTIVE,
            started_at=now,
            ends_at=now + timedelta(hours=ROUND_DURATION_HOURS)
        )
        db.session.add(first_round)

        db.session.commit()

        return battle, f"Battle started for {target_region.name}!"

    @staticmethod
    def complete_round(battle: Battle, battle_round: BattleRound) -> Dict:
        """
        Complete a round and calculate winners.

        Args:
            battle: The battle (needed for creating next round)
            battle_round: The round to complete

        Returns:
            Dictionary with round results
        """
        battle_round.status = RoundStatus.COMPLETED
        battle_round.ended_at = datetime.utcnow()

        # Calculate winners
        battle_round.calculate_round_winner()

        # Update battle round wins
        if battle_round.winner_is_attacker:
            battle.attacker_rounds_won += 1
        else:
            battle.defender_rounds_won += 1

        # Check if battle should end (all 3 rounds complete)
        if battle_round.round_number == NUM_ROUNDS:
            BattleService.complete_battle(battle)
        else:
            # Move to next round - create it if it doesn't exist
            next_round_num = battle_round.round_number + 1
            battle.current_round = next_round_num

            # Calculate next round timing based on when previous round was SUPPOSED to end
            # This ensures correct timing even if server was offline
            now = datetime.utcnow()

            # The next round should start when the previous round was scheduled to end
            # and end 8 hours after that (not 8 hours from now)
            scheduled_start = battle_round.ends_at if battle_round.ends_at else now
            scheduled_end = scheduled_start + timedelta(hours=ROUND_DURATION_HOURS)

            # If the scheduled times are in the past (server was offline), cap to battle end time
            # but don't extend beyond what was originally scheduled
            if battle.ends_at and scheduled_end > battle.ends_at:
                scheduled_end = battle.ends_at

            # Check if next round already exists
            next_round = battle.get_round(next_round_num)
            if not next_round:
                # Create the next round
                next_round = BattleRound(
                    battle_id=battle.id,
                    round_number=next_round_num,
                    status=RoundStatus.ACTIVE,
                    started_at=scheduled_start,
                    ends_at=scheduled_end
                )
                db.session.add(next_round)
            else:
                # Activate existing round with correct timing
                next_round.status = RoundStatus.ACTIVE
                next_round.started_at = scheduled_start
                next_round.ends_at = scheduled_end

        db.session.commit()

        return {
            'round_number': battle_round.round_number,
            'winner_is_attacker': battle_round.winner_is_attacker,
            'infantry_winner_is_attacker': battle_round.infantry_winner_is_attacker,
            'armoured_winner_is_attacker': battle_round.armoured_winner_is_attacker,
            'aviation_winner_is_attacker': battle_round.aviation_winner_is_attacker,
        }

    @staticmethod
    def complete_battle(battle: Battle) -> Dict:
        """
        Complete a battle and determine winner.

        Args:
            battle: The battle to complete

        Returns:
            Dictionary with battle results
        """
        battle.ended_at = datetime.utcnow()
        war = battle.war

        # Determine winner (2/3 rounds)
        if battle.attacker_rounds_won >= 2:
            battle.status = BattleStatus.ATTACKER_WON
            winner_is_attacker = True
        else:
            battle.status = BattleStatus.DEFENDER_WON
            winner_is_attacker = False

        # Award battle heroes
        BattleService.award_battle_heroes(battle)

        # Handle resistance war completion
        if war.is_resistance_war:
            BattleService.handle_resistance_war_result(battle, winner_is_attacker)
        else:
            # Handle region capture if attacker won (normal war)
            if winner_is_attacker:
                BattleService.capture_region(battle)

            # Update initiative
            if winner_is_attacker:
                # Attacker keeps/gets initiative
                war.set_initiative(war.attacker_country_id)
            else:
                # Defender gets initiative
                war.set_initiative(war.defender_country_id)

        db.session.commit()

        return {
            'winner_is_attacker': winner_is_attacker,
            'attacker_rounds_won': battle.attacker_rounds_won,
            'defender_rounds_won': battle.defender_rounds_won,
        }

    @staticmethod
    def handle_resistance_war_result(battle: Battle, resistance_won: bool):
        """
        Handle the result of a resistance war battle.

        For resistance wars:
        - Attacker = Resistance (original country)
        - Defender = Occupier (conquering country)

        If resistance wins: Region is liberated back to original owner
        If occupier wins: War ends, region stays with occupier

        Args:
            battle: The completed battle
            resistance_won: True if resistance won, False if occupier won
        """
        from app.alert_helpers import create_alert
        from app.services.achievement_service import AchievementService

        war = battle.war
        region = battle.region
        resistance_country = war.resistance_country
        occupier_country = war.defender_country
        starter = war.resistance_started_by

        if resistance_won:
            # RESISTANCE WON - Liberate the region
            BattleService.capture_region(battle)  # This transfers the region

            # Check if this liberates a conquered country
            # If resistance_country was conquered and now has regions, it's being liberated
            from app.services.conquest_service import ConquestService
            if resistance_country and resistance_country.is_conquered:
                # Country is being liberated! Pass the starter user ID for president assignment
                starter_id = starter.id if starter else None
                ConquestService.liberate_country(resistance_country.id, starter_id)

            # Update the war starter's stats
            if starter:
                starter.resistance_wars_won += 1

                # Check for achievements
                AchievementService._check_and_unlock(
                    starter, 'resistance_hero_10', starter.resistance_wars_won
                )
                AchievementService._check_and_unlock(
                    starter, 'resistance_hero_100', starter.resistance_wars_won
                )

                # Alert the starter
                create_alert(
                    user_id=starter.id,
                    alert_type=AlertType.BATTLE,
                    title="Resistance War Victory!",
                    content=f"Your resistance war has succeeded! {region.name} has been liberated for {resistance_country.name}!",
                    priority=AlertPriority.IMPORTANT
                )

            # End the resistance war
            war.status = WarStatus.ENDED_PEACE
            war.ended_at = datetime.utcnow()

        else:
            # OCCUPIER WON - Region stays with occupier
            if starter:
                # Alert the starter
                create_alert(
                    user_id=starter.id,
                    alert_type=AlertType.BATTLE,
                    title="Resistance War Failed",
                    content=f"Your resistance war has failed. {region.name} remains under {occupier_country.name}'s control.",
                    priority=AlertPriority.NORMAL
                )

            # End the resistance war
            war.status = WarStatus.ENDED_EXPIRED
            war.ended_at = datetime.utcnow()

    # =========================================================================
    # BATTLE HEROES
    # =========================================================================

    @staticmethod
    def award_battle_heroes(battle: Battle):
        """
        Award Battle Hero achievements to top damage dealers.

        6 awards total: 3 walls x 2 sides
        Each award gives 5 Gold.

        Args:
            battle: The completed battle
        """
        from app.alert_helpers import create_alert

        for wall_type in WallType:
            for is_attacker in [True, False]:
                # Get top damage dealer for this wall/side combination
                top_damage = db.session.query(
                    BattleDamage.user_id,
                    db.func.sum(BattleDamage.damage).label('total_damage')
                ).filter(
                    BattleDamage.battle_id == battle.id,
                    BattleDamage.wall_type == wall_type,
                    BattleDamage.is_attacker == is_attacker
                ).group_by(
                    BattleDamage.user_id
                ).order_by(
                    db.desc('total_damage')
                ).first()

                if not top_damage or top_damage.total_damage == 0:
                    continue

                user_id = top_damage.user_id
                total_damage = top_damage.total_damage

                # Create hero record
                hero = BattleHero(
                    battle_id=battle.id,
                    user_id=user_id,
                    wall_type=wall_type,
                    is_attacker=is_attacker,
                    total_damage=total_damage,
                    gold_reward=5,
                    awarded_at=datetime.utcnow()
                )
                db.session.add(hero)

                # Award gold
                user = User.query.get(user_id)
                if user:
                    user.gold = (user.gold or Decimal('0')) + Decimal('5')

                    # Create alert
                    side_name = "Attacker" if is_attacker else "Defender"
                    wall_name = wall_type.value.title()
                    create_alert(
                        user_id=user_id,
                        alert_type=AlertType.LEVEL_UP,
                        title="Battle Hero!",
                        content=f"You are the Battle Hero for {wall_name} ({side_name} side) with {total_damage} total damage! You received 5 Gold.",
                        priority=AlertPriority.IMPORTANT
                    )

                    # Check for Battle Hero achievements
                    from app.services.achievement_service import AchievementService
                    AchievementService.check_battle_hero(user)

    # =========================================================================
    # REGION CAPTURE
    # =========================================================================

    @staticmethod
    def capture_region(battle: Battle):
        """
        Transfer region ownership after battle victory.

        Fires all workers living in the captured region.

        Args:
            battle: The completed battle (attacker won)
        """
        region = battle.region
        war = battle.war
        attacker_country = war.attacker_country
        defender_country = war.defender_country

        # Remove region from defender
        if defender_country in region.current_owners.all():
            region.current_owners.remove(defender_country)

        # Add region to attacker
        if attacker_country not in region.current_owners.all():
            region.current_owners.append(attacker_country)

        # Fire all workers living in this region
        # Workers who live in this region now live in attacker's territory
        # They can no longer work for defender's companies
        residents = User.query.filter_by(current_region_id=region.id).all()

        for resident in residents:
            # Get their employments in defender country's companies
            employments = Employment.query.join(
                Employment.company
            ).filter(
                Employment.user_id == resident.id,
                Employment.company.has(country_id=defender_country.id)
            ).all()

            for employment in employments:
                db.session.delete(employment)

                # Alert the user
                from app.alert_helpers import create_alert
                create_alert(
                    user_id=resident.id,
                    alert_type=AlertType.EMPLOYMENT,
                    title="Employment Terminated",
                    content=f"Your employment has been terminated because {region.name} was captured by {attacker_country.name}.",
                    priority=AlertPriority.IMPORTANT
                )

        # Destroy regional constructions (hospitals and fortresses) when region is conquered
        from app.models import RegionalConstruction
        constructions = RegionalConstruction.query.filter_by(region_id=region.id).all()
        for construction in constructions:
            db.session.delete(construction)

        if constructions:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Destroyed {len(constructions)} construction(s) in {region.name} after capture by {attacker_country.name}")

        # Check if defender has lost ALL regions (full conquest)
        from app.services.conquest_service import ConquestService
        if ConquestService.check_full_conquest(defender_country.id):
            ConquestService.conquer_country(defender_country.id, attacker_country.id, war)

    # =========================================================================
    # QUERIES
    # =========================================================================

    @staticmethod
    def get_active_battles() -> List[Battle]:
        """Get all currently active battles."""
        return Battle.query.filter_by(status=BattleStatus.ACTIVE).all()

    @staticmethod
    def get_battle_leaderboard(battle_id: int, wall_type: WallType, is_attacker: bool, limit: int = 10) -> List[Dict]:
        """
        Get leaderboard for a specific wall/side in a battle.

        Args:
            battle_id: Battle ID
            wall_type: Wall type
            is_attacker: True for attacker side, False for defender
            limit: Max results

        Returns:
            List of {user_id, username, total_damage, avatar_url}
        """
        results = db.session.query(
            BattleDamage.user_id,
            User.username,
            User.avatar,
            db.func.sum(BattleDamage.damage).label('total_damage')
        ).join(
            User, BattleDamage.user_id == User.id
        ).filter(
            BattleDamage.battle_id == battle_id,
            BattleDamage.wall_type == wall_type,
            BattleDamage.is_attacker == is_attacker
        ).group_by(
            BattleDamage.user_id, User.username, User.avatar
        ).order_by(
            db.desc('total_damage')
        ).limit(limit).all()

        return [
            {
                'user_id': r.user_id,
                'username': r.username,
                'total_damage': r.total_damage,
                'avatar_url': f'/static/uploads/avatars/{r.user_id}.png' if r.avatar else None
            }
            for r in results
        ]

    @staticmethod
    def get_recent_damage(battle_id: int, limit: int = 20) -> List[Dict]:
        """
        Get recent damage records for live display.

        Args:
            battle_id: Battle ID
            limit: Max results

        Returns:
            List of recent damage records
        """
        records = BattleDamage.query.filter_by(
            battle_id=battle_id
        ).order_by(
            BattleDamage.dealt_at.desc()
        ).limit(limit).all()

        return [
            {
                'user_id': r.user_id,
                'username': r.user.username if r.user else 'Unknown',
                'avatar_url': f'/static/uploads/avatars/{r.user_id}.png' if r.user and r.user.avatar else None,
                'damage': r.damage,
                'wall_type': r.wall_type.value,
                'is_attacker': r.is_attacker,
                'dealt_at': r.dealt_at.isoformat() + 'Z',
            }
            for r in records
        ]

    @staticmethod
    def get_attackable_regions(war: War, attacking_country_id: int) -> List[Region]:
        """
        Get regions that can be attacked by a country.

        Args:
            war: The war
            attacking_country_id: The attacking country

        Returns:
            List of regions that can be attacked
        """
        defending_country_id = war.get_opponent_country_id(attacking_country_id)
        if not defending_country_id:
            return []

        defending_country = Country.query.get(defending_country_id)
        if not defending_country:
            return []

        attacking_country = Country.query.get(attacking_country_id)
        if not attacking_country:
            return []

        # Get all attacker regions
        attacker_region_ids = [r.id for r in attacking_country.current_regions.all()]

        # Get all defender regions
        defender_regions = defending_country.current_regions.all()

        # Filter to only adjacent regions
        attackable = []
        for region in defender_regions:
            # Check if region is neighbor to any attacker region
            for neighbor in region.neighbors.all():
                if neighbor.id in attacker_region_ids:
                    attackable.append(region)
                    break
            else:
                for neighbor in region.neighbor_of.all():
                    if neighbor.id in attacker_region_ids:
                        attackable.append(region)
                        break

        return attackable
