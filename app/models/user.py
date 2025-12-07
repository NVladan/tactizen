# app/models/user.py

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from flask_login import UserMixin
from sqlalchemy import Numeric, CheckConstraint, Index, select, func

# Assuming db is initialized in extensions and imported in models/__init__
from . import db # Use relative import

# --- Import related models ---
from .location import Region, Country # Import models
from .resource import InventoryItem, Resource # Import models

# Import utilities
from app.utils import get_level_from_xp, get_total_xp_for_level, get_xp_for_next_level_increment
from app.constants import GameConstants
from app.exceptions import (
    InsufficientFundsError,
    InsufficientWellnessError,
    DailyCooldownError,
    InvalidSkillTypeError,
    InvalidLocationError,
    AlreadyAtLocationError,
    InsufficientInventoryError,
    InvalidResourceError,
    InvalidAmountError,
)
from app.mixins import SoftDeleteMixin

logger = logging.getLogger(__name__)

class User(SoftDeleteMixin, UserMixin, db.Model):
    """Represents a player in the game."""
    id = db.Column(db.Integer, primary_key=True)
    wallet_address = db.Column(db.String(42), unique=True, index=True, nullable=False)
    username = db.Column(db.String(30), index=True, unique=True, nullable=True)
    description = db.Column(db.Text, nullable=True)
    avatar = db.Column(db.Boolean, default=False)
    experience = db.Column(db.Integer, default=0, nullable=False, index=True)

    # Military Skills
    skill_infantry = db.Column(db.Float, default=0.0, nullable=False)
    skill_armoured = db.Column(db.Float, default=0.0, nullable=False)
    skill_aviation = db.Column(db.Float, default=0.0, nullable=False)
    last_trained = db.Column(db.DateTime, nullable=True)

    # Military Rank System
    military_rank_id = db.Column(db.Integer, db.ForeignKey('military_ranks.id'), default=1, nullable=False, index=True)
    military_rank_xp = db.Column(Numeric(20, 2), default=Decimal('0.0'), nullable=False)

    # Work Skills
    skill_resource_extraction = db.Column(db.Float, default=0.0, nullable=False)
    skill_manufacture = db.Column(db.Float, default=0.0, nullable=False)
    skill_construction = db.Column(db.Float, default=0.0, nullable=False)
    last_studied = db.Column(db.DateTime, nullable=True)
    last_worked_date = db.Column(db.Date, nullable=True)  # Track when user last worked at any job

    # Other Attributes
    email = db.Column(db.String(120), unique=True, nullable=True) # Kept for potential future use
    birthday = db.Column(db.DateTime, default=datetime.utcnow, nullable=True) # Default to now
    status = db.Column(db.SmallInteger, default=0) # Consider Enum later
    activate = db.Column(db.Boolean, default=True) # Auto-activate on connect
    is_admin = db.Column(db.Boolean, default=False, nullable=False, index=True) # Admin privileges

    # Ban/Timeout System
    is_banned = db.Column(db.Boolean, default=False, nullable=False, index=True) # Is user banned
    ban_reason = db.Column(db.Text, nullable=True) # Reason for ban
    banned_until = db.Column(db.DateTime, nullable=True, index=True) # Temporary ban expiry (null = permanent)
    banned_at = db.Column(db.DateTime, nullable=True) # When ban was applied
    banned_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Admin who banned

    # Location & Economy Foreign Keys
    citizenship_id = db.Column(db.Integer, db.ForeignKey('country.id'), index=True, nullable=True)
    current_region_id = db.Column(db.Integer, db.ForeignKey('region.id'), index=True, nullable=True)

    # Political Party Foreign Key
    party_id = db.Column(db.Integer, db.ForeignKey('political_party.id'), index=True, nullable=True)

    # Referral System
    referral_code = db.Column(db.String(12), unique=True, index=True, nullable=True)  # Unique code for referrals

    # Blockchain Integration (Horizen L3 Testnet)
    base_wallet_address = db.Column(db.String(42), index=True, nullable=True)  # User's wallet for ZEN tokens
    citizenship_nft_token_id = db.Column(db.Integer, nullable=True)  # Citizenship NFT token ID
    government_nft_token_id = db.Column(db.Integer, nullable=True)  # Government position NFT token ID

    # Location & Economy Attributes
    wellness = db.Column(db.Float, default=100.0)
    energy = db.Column(db.Float, default=100.0, nullable=False)  # Energy for actions (work, study, train)
    # Changed to Numeric for precision (no float bugs)
    gold = db.Column(Numeric(20, 8), default=Decimal('0.0'), nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Activity Tracking
    last_login = db.Column(db.DateTime, nullable=True, index=True)  # Last successful login
    last_seen = db.Column(db.DateTime, nullable=True, index=True)  # Last page view/activity
    login_count = db.Column(db.Integer, default=0, nullable=False)  # Total login count
    page_views = db.Column(db.Integer, default=0, nullable=False)  # Total page views

    # Daily Bread/Beer Consumption Tracking (max 10 per day each)
    bread_consumed_today = db.Column(db.Float, default=0.0, nullable=False)  # Number of breads consumed today
    last_bread_reset_date = db.Column(db.Date, nullable=True)  # Last date the bread counter was reset

    # Daily Energy Restoration Tracking
    beer_consumed_today = db.Column(db.Float, default=0.0, nullable=False)  # Number of beers consumed today
    last_beer_reset_date = db.Column(db.Date, nullable=True)  # Last date the beer counter was reset

    # Daily Wine Consumption Tracking (restores both wellness and energy)
    wine_consumed_today = db.Column(db.Float, default=0.0, nullable=False)  # Number of wines consumed today
    last_wine_reset_date = db.Column(db.Date, nullable=True)  # Last date the wine counter was reset

    # Free NFT Mints (earned through tasks/rewards)
    free_nft_mints = db.Column(db.Integer, default=0, nullable=False)  # Available free NFT mints

    # Law proposal cooldown (for congress members after rejected proposal)
    law_proposal_cooldown_until = db.Column(db.DateTime, nullable=True)  # Cannot propose laws until this time

    # Hospital usage cooldown (6 hours between uses during active battles)
    last_hospital_use = db.Column(db.DateTime, nullable=True)  # Last time player used a hospital

    # Resistance War Stats
    resistance_wars_started = db.Column(db.Integer, default=0, nullable=False)  # Number of resistance wars started
    resistance_wars_won = db.Column(db.Integer, default=0, nullable=False)  # Number of resistance wars won (as starter)

    # --- Relationships ---
    citizenship = db.relationship('Country', back_populates='citizens', foreign_keys=[citizenship_id])
    current_region = db.relationship('Region', back_populates='residents', foreign_keys=[current_region_id])
    rank = db.relationship('MilitaryRank', back_populates='users', foreign_keys=[military_rank_id])
    # Use Integer quantity type
    inventory = db.relationship('InventoryItem', back_populates='user', lazy='dynamic', cascade="all, delete-orphan")
    # Active residence/house
    active_residence = db.relationship('ActiveResidence', back_populates='user', uselist=False, cascade="all, delete-orphan")
    # Multi-currency support
    currencies = db.relationship('UserCurrency', back_populates='user', lazy='dynamic', cascade="all, delete-orphan")
    # Ban relationship
    banned_by = db.relationship('User', remote_side='User.id', foreign_keys=[banned_by_id])
    # Party relationship
    party_membership = db.relationship('PartyMembership', back_populates='user', uselist=False)

    # Referral relationships
    referrals_made = db.relationship('Referral', foreign_keys='Referral.referrer_id', back_populates='referrer', lazy='dynamic')
    referred_by_relation = db.relationship('Referral', foreign_keys='Referral.referee_id', back_populates='referee', uselist=False)

    # Company relationships
    companies = db.relationship('Company', back_populates='owner', lazy='dynamic')
    employments = db.relationship('Employment', back_populates='user', lazy='dynamic')

    # --- Table Constraints ---
    __table_args__ = (
        CheckConstraint('gold >= 0', name='gold_non_negative'),
        CheckConstraint('wellness >= 0', name='wellness_min'),
        CheckConstraint('energy >= 0', name='energy_min'),
        CheckConstraint('experience >= 0', name='experience_non_negative'),
        Index('idx_last_trained', 'last_trained'),
        Index('idx_last_studied', 'last_studied'),
    )

    # --- Properties ---
    # (Leveling properties remain the same)
    @property
    def level(self): return get_level_from_xp(self.experience)
    @property
    def xp_start_of_current_level(self): return get_total_xp_for_level(self.level)
    @property
    def xp_needed_for_next_level(self): return get_total_xp_for_level(self.level + 1)
    @property
    def xp_increment_for_current_level(self): return get_xp_for_next_level_increment(self.level)
    @property
    def xp_progress_in_current_level(self): return self.experience - self.xp_start_of_current_level
    @property
    def can_train_today(self):
        if self.last_trained is None: return True
        return datetime.utcnow() >= self.last_trained + timedelta(hours=GameConstants.MILITARY_TRAINING_COOLDOWN_HOURS)
    @property
    def can_study_today(self):
        if self.last_studied is None: return True
        return datetime.utcnow() >= self.last_studied + timedelta(hours=GameConstants.WORK_TRAINING_COOLDOWN_HOURS)

    @property
    def max_wellness(self):
        """Calculate maximum wellness based on active house quality and future NFT bonuses."""
        base_max = 100.0
        house_bonus = 0.0

        # Add house quality bonus: Quality × 10
        if self.active_residence and not self.active_residence.is_expired:
            house_bonus = self.active_residence.quality * 10.0

        # Future: Add NFT bonuses here when implemented
        # nft_bonus = self.get_equipped_nft_wellness_bonus()

        return base_max + house_bonus  # + nft_bonus (when implemented)

    @property
    def max_energy(self):
        """Calculate maximum energy based on active house quality and future NFT bonuses."""
        base_max = 100.0
        house_bonus = 0.0

        # Add house quality bonus: Quality × 10
        if self.active_residence and not self.active_residence.is_expired:
            house_bonus = self.active_residence.quality * 10.0

        # Future: Add NFT bonuses here when implemented
        # nft_bonus = self.get_equipped_nft_energy_bonus()

        return base_max + house_bonus  # + nft_bonus (when implemented)

    @property
    def is_currently_banned(self):
        """Check if user is currently banned (including temporary bans)."""
        if not self.is_banned:
            return False
        # If banned_until is None, it's a permanent ban
        if self.banned_until is None:
            return True
        # Check if temporary ban has expired
        return datetime.utcnow() < self.banned_until

    @property
    def ban_type(self):
        """Get ban type: 'permanent', 'temporary', or None."""
        if not self.is_banned:
            return None
        if self.banned_until is None:
            return 'permanent'
        if datetime.utcnow() < self.banned_until:
            return 'temporary'
        return None  # Ban expired

    @property
    def is_muted(self):
        """Check if user is currently muted (can't post articles/messages)."""
        from app.models.support import UserMute
        active_mute = UserMute.query.filter(
            UserMute.user_id == self.id,
            UserMute.is_active == True,
            UserMute.expires_at > datetime.utcnow(),
            UserMute.lifted_at == None
        ).first()
        return active_mute is not None

    @property
    def active_mute(self):
        """Get the active mute record if user is muted."""
        from app.models.support import UserMute
        return UserMute.query.filter(
            UserMute.user_id == self.id,
            UserMute.is_active == True,
            UserMute.expires_at > datetime.utcnow(),
            UserMute.lifted_at == None
        ).first()

    @property
    def party(self):
        """Get the political party this user belongs to, if any."""
        if not self.party_membership:
            return None
        return self.party_membership.party

    @property
    def military_unit(self):
        """Get the military unit this user belongs to, if any."""
        from app.models.military_unit import MilitaryUnitMember
        membership = MilitaryUnitMember.query.filter_by(
            user_id=self.id,
            is_active=True
        ).first()
        if not membership:
            return None
        return membership.unit

    @property
    def is_party_president(self):
        """Check if this user is politics of their party."""
        if not self.party:
            return False
        return self.party.president_id == self.id

    def can_leave_party(self):
        """Check if user can leave their party (no active elections)."""
        if not self.party:
            return False, "You are not in a party."

        if self.party.has_active_election():
            return False, "Cannot leave party during active elections."

        return True, "OK"

    def can_join_party(self, party):
        """
        Check if user can join a specific party.

        Args:
            party: PoliticalParty instance

        Returns:
            tuple: (can_join: bool, reason: str)
        """
        # Must have citizenship
        if not self.citizenship_id:
            return False, "You must be a citizen of a country to join a party."

        # Must not already be in a party
        if self.party:
            return False, "You are already in a party. Leave your current party first."

        # Citizenship must match party's country
        if self.citizenship_id != party.country_id:
            return False, f"You must be a citizen of {party.country.name} to join this party."

        # Citizens of conquered countries cannot join parties (political rights suspended)
        if self.is_citizen_of_conquered_country():
            return False, "Citizens of conquered countries cannot join parties. Political rights are suspended until liberation."

        # Cannot join during active elections
        if party.has_active_election():
            return False, "Cannot join party during active elections."

        return True, "OK"

    def is_president_of(self, country_id):
        """Check if user is current politics of a specific country."""
        from app.models.government import CountryPresident
        president = db.session.scalar(
            db.select(CountryPresident)
            .where(CountryPresident.country_id == country_id)
            .where(CountryPresident.user_id == self.id)
            .where(CountryPresident.is_current == True)
        )
        return president is not None

    def is_congress_member_of(self, country_id):
        """Check if user is current congress member of a specific country."""
        from app.models.government import CongressMember
        member = db.session.scalar(
            db.select(CongressMember)
            .where(CongressMember.country_id == country_id)
            .where(CongressMember.user_id == self.id)
            .where(CongressMember.is_current == True)
        )
        return member is not None

    def is_minister_of(self, country_id, ministry_type=None):
        """Check if user is current minister of a specific country.

        Args:
            country_id: The country to check
            ministry_type: Optional ministry type (e.g., 'defence', 'finance', 'foreign_affairs')
                          If None, checks if user is any minister of the country.
        """
        from app.models.government import Minister, MinistryType
        query = (
            db.select(Minister)
            .where(Minister.country_id == country_id)
            .where(Minister.user_id == self.id)
            .where(Minister.is_active == True)
        )
        if ministry_type:
            # Convert string to enum if needed
            if isinstance(ministry_type, str):
                ministry_type = MinistryType(ministry_type)
            query = query.where(Minister.ministry_type == ministry_type)
        minister = db.session.scalar(query)
        return minister is not None

    def get_active_minister_position(self):
        """Get user's active minister position if any."""
        from app.models.government import Minister
        return db.session.scalar(
            db.select(Minister)
            .where(Minister.user_id == self.id)
            .where(Minister.is_active == True)
        )

    def can_change_citizenship(self):
        """
        Check if user can change citizenship.
        Ministers cannot change citizenship until they resign.
        Citizens of conquered countries cannot change citizenship.

        Returns:
            tuple: (can_change: bool, reason: str)
        """
        # Check if citizen of conquered country
        if self.is_citizen_of_conquered_country():
            return False, "Citizens of conquered countries cannot change citizenship until liberation."

        minister_position = self.get_active_minister_position()
        if minister_position:
            ministry_names = {
                'FOREIGN_AFFAIRS': 'Minister of Foreign Affairs',
                'DEFENCE': 'Minister of Defence',
                'FINANCE': 'Minister of Finance'
            }
            ministry_name = ministry_names.get(minister_position.ministry_type.name, 'Minister')
            return False, f"You must resign from your position as {ministry_name} before changing citizenship."

        return True, "OK"

    def is_citizen_of_conquered_country(self):
        """Check if user is citizen of a conquered country."""
        if not self.citizenship:
            return False
        return self.citizenship.is_conquered

    def can_vote(self):
        """
        Check if user can vote in elections.

        Returns:
            tuple: (can_vote: bool, reason: str)
        """
        if self.is_citizen_of_conquered_country():
            return False, "Citizens of conquered countries cannot vote."
        return True, "OK"

    def can_run_for_office(self):
        """
        Check if user can run for government office.

        Returns:
            tuple: (can_run: bool, reason: str)
        """
        if self.is_citizen_of_conquered_country():
            return False, "Citizens of conquered countries cannot run for office."
        return True, "OK"

    def can_propose_laws(self):
        """
        Check if user can propose laws.

        Returns:
            tuple: (can_propose: bool, reason: str)
        """
        if self.is_citizen_of_conquered_country():
            return False, "Citizens of conquered countries cannot propose laws."
        return True, "OK"

    # --- Methods ---
    def check_and_clear_expired_ban(self):
        """Clear ban if it has expired. Returns True if ban was cleared."""
        if self.is_banned and self.banned_until:
            if datetime.utcnow() >= self.banned_until:
                self.is_banned = False
                self.ban_reason = None
                self.banned_until = None
                self.banned_at = None
                self.banned_by_id = None
                logger.info(f"Temporary ban expired for user {self.id}")
                return True
        return False
    def add_experience(self, amount):
        """
        Add experience points to the user and award gold if they level up.

        Returns:
            tuple: (leveled_up: bool, new_level: int)
                - leveled_up: True if user leveled up
                - new_level: The new level number (or current level if no level up)
        """
        if amount <= 0:
            return False, self.level

        # Store the old level before adding experience
        old_level = self.level

        # Add experience
        self.experience += amount

        # Check if user leveled up
        new_level = self.level
        leveled_up = new_level > old_level

        if leveled_up:
            # Award 1 Gold for leveling up with row-level locking
            from app.services.currency_service import CurrencyService
            CurrencyService.add_gold(self.id, 1, 'Level up reward')

        # Check if user reached level 10 and award referral bonus
        self.check_and_award_referral_bonus()

        return leveled_up, new_level

    def train_skill(self, skill_type):
        """
        Train a military skill (infantry, armoured, aviation).

        Args:
            skill_type: Type of military skill to train

        Returns:
            tuple: (success: bool, message: str, leveled_up: bool, new_level: int)

        Raises:
            DailyCooldownError: If training cooldown hasn't expired
            InsufficientWellnessError: If user doesn't have enough wellness
            InvalidSkillTypeError: If skill type is not valid
        """
        # Validate skill type
        try:
            GameConstants.validate_skill_type(skill_type, 'military')
        except ValueError as e:
            logger.warning(f"User {self.id} attempted invalid military skill: {skill_type}")
            return False, str(e), False, self.level

        # Check cooldown
        if not self.can_train_today:
            logger.info(f"User {self.id} attempted training on cooldown")
            return False, f"You can only train once per {GameConstants.MILITARY_TRAINING_COOLDOWN_HOURS} hours.", False, self.level

        energy_cost = 10.0
        if self.energy < energy_cost:
            logger.info(f"User {self.id} insufficient energy for training: {self.energy}/{energy_cost}")
            return False, f"Not enough energy (need {energy_cost}).", False, self.level

        # Perform training
        self.energy -= energy_cost
        leveled_up, new_level = self.add_experience(GameConstants.MILITARY_TRAINING_XP_GAIN)
        self.last_trained = datetime.utcnow()

        skill_gain = float(GameConstants.MILITARY_TRAINING_SKILL_GAIN)
        if skill_type == 'infantry':
            self.skill_infantry += skill_gain
        elif skill_type == 'armoured':
            self.skill_armoured += skill_gain
        elif skill_type == 'aviation':
            self.skill_aviation += skill_gain

        logger.info(f"User {self.id} trained {skill_type}, gained {skill_gain} skill and {GameConstants.MILITARY_TRAINING_XP_GAIN} XP")
        return True, f"Successfully trained {skill_type.capitalize()}! Gained {skill_gain} skill and {GameConstants.MILITARY_TRAINING_XP_GAIN} XP.", leveled_up, new_level

    def study_skill(self, skill_type):
        """
        Study a work skill (resource_extraction, manufacture, construction).

        Args:
            skill_type: Type of work skill to study

        Returns:
            tuple: (success: bool, message: str, leveled_up: bool, new_level: int)

        Raises:
            DailyCooldownError: If study cooldown hasn't expired
            InsufficientWellnessError: If user doesn't have enough wellness
            InvalidSkillTypeError: If skill type is not valid
        """
        # Validate skill type
        try:
            GameConstants.validate_skill_type(skill_type, 'work')
        except ValueError as e:
            logger.warning(f"User {self.id} attempted invalid work skill: {skill_type}")
            return False, str(e), False, self.level

        # Check cooldown
        if not self.can_study_today:
            logger.info(f"User {self.id} attempted study on cooldown")
            return False, f"You can only study once per {GameConstants.WORK_TRAINING_COOLDOWN_HOURS} hours.", False, self.level

        energy_cost = 10.0
        if self.energy < energy_cost:
            logger.info(f"User {self.id} insufficient energy for study: {self.energy}/{energy_cost}")
            return False, f"Not enough energy (need {energy_cost}).", False, self.level

        # Perform study
        self.energy -= energy_cost
        leveled_up, new_level = self.add_experience(GameConstants.WORK_TRAINING_XP_GAIN)
        self.last_studied = datetime.utcnow()

        skill_gain = float(GameConstants.WORK_TRAINING_SKILL_GAIN)
        skill_name_display = GameConstants.get_skill_display_name(skill_type)

        if skill_type == 'resource_extraction':
            self.skill_resource_extraction += skill_gain
        elif skill_type == 'manufacture':
            self.skill_manufacture += skill_gain
        elif skill_type == 'construction':
            self.skill_construction += skill_gain

        logger.info(f"User {self.id} studied {skill_type}, gained {skill_gain} skill and {GameConstants.WORK_TRAINING_XP_GAIN} XP")
        return True, f"Successfully studied {skill_name_display}! Gained {skill_gain} skill and {GameConstants.WORK_TRAINING_XP_GAIN} XP.", leveled_up, new_level

    def travel_to(self, destination_region_id, payment_method='gold'):
        """
        Travel to a different region (costs gold OR energy).
        Travel Discount NFT reduces these costs.

        Args:
            destination_region_id: ID of the destination region
            payment_method: 'gold' (costs 1 gold) or 'stats' (costs 50 energy)

        Returns:
            tuple: (success: bool, message: str)
        """
        BASE_TRAVEL_COST_GOLD = 1.0
        BASE_TRAVEL_COST_ENERGY = 50

        # Apply Travel Discount NFT bonus
        from app.services.bonus_calculator import BonusCalculator
        travel_cost_gold, travel_cost_energy = BonusCalculator.get_travel_costs(
            self.id, BASE_TRAVEL_COST_GOLD, BASE_TRAVEL_COST_ENERGY
        )

        # Check if already at destination
        if self.current_region_id == destination_region_id:
            logger.info(f"User {self.id} already at region {destination_region_id}")
            return False, "You are already in this region."

        # Check payment method and requirements
        if payment_method == 'gold':
            if travel_cost_gold > 0 and float(self.gold) < travel_cost_gold:
                logger.info(f"User {self.id} insufficient gold for travel: {self.gold}/{travel_cost_gold}")
                return False, f"Not enough Gold to travel (need {travel_cost_gold} Gold)."
        elif payment_method == 'stats':
            if travel_cost_energy > 0 and self.energy < travel_cost_energy:
                logger.info(f"User {self.id} insufficient energy for travel: energy={self.energy}/{travel_cost_energy}")
                return False, f"Not enough Energy to travel (need {travel_cost_energy} Energy)."
        else:
            return False, "Invalid payment method."

        # More robust region lookup
        try:
            destination_region = db.session.get(Region, destination_region_id)
            if not destination_region:
                logger.error(f"Destination region {destination_region_id} not found for user {self.id}")
                return False, "Invalid destination region."

            # Verify the region is associated with a country
            if not destination_region.current_owner:
                logger.error(f"Destination region {destination_region_id} has no current owner for user {self.id}")
                return False, "Invalid destination region - no owning country."

            # Deduct travel cost based on payment method and update location
            if payment_method == 'gold':
                if travel_cost_gold > 0:
                    # Use safe gold deduction with row-level locking
                    from app.services.currency_service import CurrencyService
                    success, message, _ = CurrencyService.deduct_gold(
                        self.id, Decimal(str(travel_cost_gold)), 'Travel cost'
                    )
                    if not success:
                        return False, f"Could not deduct gold: {message}"
                    logger.info(f"User {self.id} paid {travel_cost_gold} gold for travel")
                else:
                    logger.info(f"User {self.id} traveled free (Travel Discount NFT)")
            elif payment_method == 'stats':
                if travel_cost_energy > 0:
                    self.energy -= travel_cost_energy
                    logger.info(f"User {self.id} paid {travel_cost_energy} energy for travel")
                else:
                    logger.info(f"User {self.id} traveled free (Travel Discount NFT)")

            self.current_region_id = destination_region_id

            logger.info(f"User {self.id} traveled to region {destination_region_id} ({destination_region.name})")
            return True, f"Successfully traveled to {destination_region.name}."

        except Exception as e:
            logger.exception(f"Error during travel for user {self.id}: {e}")
            return False, "An error occurred during travel. Please try again."

    # --- Inventory Methods (INTEGER LOGIC) ---
    # Storage limit constant
    USER_STORAGE_LIMIT = 1000  # Maximum total quantity of items users can hold

    def get_total_inventory_count(self):
        """Get total quantity of all items in user's inventory."""
        from app.services.inventory_service import InventoryService
        return InventoryService.get_total_count(self)

    def get_available_storage_space(self):
        """Get remaining storage space available."""
        from app.services.inventory_service import InventoryService
        return InventoryService.get_available_storage(self)

    def get_inventory_item(self, resource_id, quality=0):
        """Gets a specific inventory item for this user."""
        from app.services.inventory_service import InventoryService
        return InventoryService.get_item(self, resource_id, quality)

    def get_resource_quantity(self, resource_id, quality=0):
        """Gets the quantity (Integer) of a specific resource with specific quality."""
        from app.services.inventory_service import InventoryService
        return InventoryService.get_resource_quantity(self, resource_id, quality)

    def add_to_inventory(self, resource_id, quantity, quality=0):
        """
        Adds an INTEGER quantity of a resource to the user's inventory.
        Respects USER_STORAGE_LIMIT and will add partial quantity if limit is reached.

        Args:
            resource_id: ID of the resource to add
            quantity: Integer quantity to add
            quality: Quality level (0 for raw materials, 1-5 for manufactured goods)

        Returns:
            tuple: (quantity_added: int, remaining: int)
                - quantity_added: Amount actually added to inventory
                - remaining: Amount that couldn't be added due to storage limit
        """
        from app.services.inventory_service import InventoryService
        return InventoryService.add_item(self, resource_id, quantity, quality)

    def remove_from_inventory(self, resource_id, quantity, quality=0):
        """
        Removes an INTEGER quantity of a resource from the user's inventory.

        Args:
            resource_id: ID of the resource to remove
            quantity: Integer quantity to remove
            quality: Quality level (0 for raw materials, 1-5 for manufactured goods)

        Returns:
            bool: True if successful, False otherwise
        """
        from app.services.inventory_service import InventoryService
        return InventoryService.remove_item(self, resource_id, quantity, quality)

    def eat_bread(self, quantity='max', quality=1):
        """
        Eat bread from inventory to restore wellness.
        Quality determines restoration amount: Q1=2, Q2=4, Q3=6, Q4=8, Q5=10

        Args:
            quantity: Either 'max' or an integer number of bread to eat
            quality: Quality level (1-5)

        Returns:
            tuple: (success: bool, message: str, bread_eaten: int, wellness_restored: float)
        """
        from app.services.wellness_service import WellnessService
        return WellnessService.eat_bread(self, quantity, quality)

    def drink_beer(self, quantity='max', quality=1):
        """
        Drink beer from inventory to restore energy.
        Quality determines restoration amount: Q1=2, Q2=4, Q3=6, Q4=8, Q5=10

        Args:
            quantity: Either 'max' or an integer number of beer to drink
            quality: Quality level (1-5)

        Returns:
            tuple: (success: bool, message: str, beer_drunk: int, energy_restored: float)
        """
        from app.services.wellness_service import WellnessService
        return WellnessService.drink_beer(self, quantity, quality)

    def process_residence_restoration(self):
        """
        Process automatic wellness and energy restoration from active residence.
        Quality determines restoration amount: Q1=2+2, Q2=4+4, Q3=6+6, Q4=8+8, Q5=10+10
        Restores every 15 minutes.

        Returns:
            tuple: (restored: bool, wellness_restored: float, energy_restored: float)
        """
        from app.services.wellness_service import WellnessService
        return WellnessService.process_residence_restoration(self)

    # --- Messaging Properties ---
    @property
    def unread_message_count(self):
        """Get count of unread messages for this user."""
        from .messaging import Message  # Import here to avoid circular import
        return db.session.scalar(
            select(func.count(Message.id)).where(
                Message.recipient_id == self.id,
                Message.is_read == False,
                Message.recipient_deleted == False
            )
        ) or 0

    @property
    def unread_alert_count(self):
        """Get count of unread alerts for this user."""
        from .messaging import Alert  # Import here to avoid circular import
        return db.session.scalar(
            select(func.count(Alert.id)).where(
                Alert.user_id == self.id,
                Alert.is_read == False,
                Alert.is_deleted == False
            )
        ) or 0

    def get_recent_messages(self, limit=5):
        """Get recent messages for navbar dropdown."""
        from .messaging import Message
        from sqlalchemy import or_, and_

        # Get all unique conversation partners
        sent_to = db.session.scalars(
            select(Message.recipient_id)
            .where(
                Message.sender_id == self.id,
                Message.sender_deleted == False
            )
            .distinct()
        ).all()

        received_from = db.session.scalars(
            select(Message.sender_id)
            .where(
                Message.recipient_id == self.id,
                Message.recipient_deleted == False
            )
            .distinct()
        ).all()

        # Combine and get unique user IDs
        partner_ids = list(set(sent_to + received_from))

        # Get latest message for each conversation
        conversations = []
        for partner_id in partner_ids:
            partner = db.session.get(User, partner_id)
            if not partner:
                continue

            # Get latest message in this conversation
            latest_msg = db.session.scalar(
                select(Message)
                .where(
                    or_(
                        and_(Message.sender_id == self.id, Message.recipient_id == partner_id, Message.sender_deleted == False),
                        and_(Message.sender_id == partner_id, Message.recipient_id == self.id, Message.recipient_deleted == False)
                    )
                )
                .order_by(Message.created_at.desc())
            )

            if latest_msg:
                conversations.append({
                    'partner': partner,
                    'message': latest_msg
                })

        # Sort by latest message date and limit
        conversations.sort(key=lambda x: x['message'].created_at, reverse=True)
        return conversations[:limit]

    def get_recent_alerts(self, limit=5):
        """Get recent alerts for navbar dropdown."""
        from .messaging import Alert

        alerts = db.session.scalars(
            select(Alert)
            .where(Alert.user_id == self.id, Alert.is_deleted == False)
            .order_by(Alert.created_at.desc())
            .limit(limit)
        ).all()

        return alerts

    # --- Time Allocation Methods (New System) ---
    def get_today_allocation(self):
        """Get or create today's time allocation record."""
        from .time_allocation import TimeAllocation
        from app.time_helpers import get_allocation_date

        today = get_allocation_date()

        allocation = db.session.scalar(
            select(TimeAllocation).where(
                TimeAllocation.user_id == self.id,
                TimeAllocation.allocation_date == today
            )
        )

        if not allocation:
            allocation = TimeAllocation(
                user_id=self.id,
                allocation_date=today,
                hours_training=0,
                hours_studying=0,
                hours_working=0
            )
            db.session.add(allocation)
            db.session.flush()

        return allocation

    def get_remaining_hours_today(self):
        """Get remaining hours available for allocation today."""
        allocation = self.get_today_allocation()
        return allocation.remaining_hours

    def can_allocate_hours(self, activity_type, hours):
        """
        Check if user can allocate specified hours to an activity.

        Args:
            activity_type: 'training', 'studying', or 'working'
            hours: Number of hours to allocate

        Returns:
            tuple: (can_allocate: bool, reason: str or None)
        """
        if hours <= 0:
            return False, "Hours must be greater than 0"

        allocation = self.get_today_allocation()

        # Check if total hours for this specific activity would exceed 12
        if activity_type == 'training':
            current_activity_hours = allocation.hours_training
            activity_name = "training"
        elif activity_type == 'studying':
            current_activity_hours = allocation.hours_studying
            activity_name = "studying"
        elif activity_type == 'working':
            current_activity_hours = allocation.hours_working
            activity_name = "working"
        else:
            return False, "Invalid activity type"

        if current_activity_hours + hours > 12:
            remaining_for_activity = 12 - current_activity_hours
            return False, f"Cannot allocate more than 12 hours to {activity_name} per day. You have {remaining_for_activity} hours remaining for {activity_name}."

        # Check if total hours would exceed 24
        current_total = allocation.total_hours_allocated
        if current_total + hours > 24:
            return False, f"Only {allocation.remaining_hours} hours remaining today"

        return True, None

    def get_skill_for_company_type(self, company_type):
        """Get user's skill level for a specific company type."""
        from .company import CompanyType

        skill_mapping = {
            # Resource extraction
            CompanyType.MINING: self.skill_resource_extraction,
            CompanyType.RESOURCE_EXTRACTION: self.skill_resource_extraction,
            CompanyType.FARMING: self.skill_resource_extraction,
            # Weapon manufacturing (split)
            CompanyType.RIFLE_MANUFACTURING: self.skill_manufacture,
            CompanyType.TANK_MANUFACTURING: self.skill_manufacture,
            CompanyType.HELICOPTER_MANUFACTURING: self.skill_manufacture,
            # Consumer goods (split)
            CompanyType.BREAD_MANUFACTURING: self.skill_manufacture,
            CompanyType.BEER_MANUFACTURING: self.skill_manufacture,
            CompanyType.WINE_MANUFACTURING: self.skill_manufacture,
            # Semi-products
            CompanyType.SEMI_PRODUCT: self.skill_manufacture,
            # Construction
            CompanyType.CONSTRUCTION: self.skill_construction,
        }
        return skill_mapping.get(company_type, 0.0)

    def allocate_training_hours(self, skill_type, hours):
        """
        Allocate hours to training a military skill.

        Args:
            skill_type: 'infantry', 'armoured', or 'aviation'
            hours: Number of hours to train (1-12)

        Returns:
            tuple: (success: bool, message: str, skill_gain: float, energy_cost: int, leveled_up: bool, new_level: int)
        """
        # Validate hours
        can_allocate, reason = self.can_allocate_hours('training', hours)
        if not can_allocate:
            return False, reason, 0.0, 0, False, self.level

        # Validate skill type
        if skill_type not in ['infantry', 'armoured', 'aviation']:
            return False, "Invalid skill type", 0.0, 0, False, self.level

        # Calculate costs
        energy_cost = hours * 2  # 2 energy per hour

        # Check energy
        if self.energy < energy_cost:
            return False, f"Insufficient energy. Need {energy_cost}, have {self.energy:.1f}", 0.0, 0, False, self.level

        # Calculate skill gain (0.01 per hour)
        skill_gain = hours * 0.01

        # Apply skill gain
        if skill_type == 'infantry':
            self.skill_infantry += skill_gain
        elif skill_type == 'armoured':
            self.skill_armoured += skill_gain
        elif skill_type == 'aviation':
            self.skill_aviation += skill_gain

        # Deduct energy
        self.energy = max(0, self.energy - energy_cost)

        # Update time allocation
        allocation = self.get_today_allocation()
        allocation.hours_training += hours
        allocation.training_skill = skill_type

        # Add experience and check for level up
        xp_gain = GameConstants.MILITARY_TRAINING_XP_GAIN * hours
        leveled_up, new_level = self.add_experience(xp_gain)

        # Track training streak for achievements
        from app.services.achievement_service import AchievementService
        try:
            AchievementService.track_training_streak(self)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error tracking training achievement for user {self.id}: {e}")

        message = f"Trained {skill_type} for {hours} hours. Gained {skill_gain:.2f} skill and {xp_gain} XP. Energy: -{energy_cost}"

        return True, message, skill_gain, energy_cost, leveled_up, new_level

    def allocate_studying_hours(self, skill_type, hours):
        """
        Allocate hours to studying a work skill.

        Args:
            skill_type: 'resource_extraction', 'manufacture', or 'construction'
            hours: Number of hours to study (1-12)

        Returns:
            tuple: (success: bool, message: str, skill_gain: float, energy_cost: int, leveled_up: bool, new_level: int)
        """
        # Validate hours
        can_allocate, reason = self.can_allocate_hours('studying', hours)
        if not can_allocate:
            return False, reason, 0.0, 0, False, self.level

        # Validate skill type
        if skill_type not in ['resource_extraction', 'manufacture', 'construction']:
            return False, "Invalid skill type", 0.0, 0, False, self.level

        # Calculate costs
        energy_cost = hours * 2  # 2 energy per hour

        # Check energy
        if self.energy < energy_cost:
            return False, f"Insufficient energy. Need {energy_cost}, have {self.energy:.1f}", 0.0, 0, False, self.level

        # Calculate skill gain (0.01 per hour)
        skill_gain = hours * 0.01

        # Apply skill gain
        if skill_type == 'resource_extraction':
            self.skill_resource_extraction += skill_gain
        elif skill_type == 'manufacture':
            self.skill_manufacture += skill_gain
        elif skill_type == 'construction':
            self.skill_construction += skill_gain

        # Deduct energy
        self.energy = max(0, self.energy - energy_cost)

        # Update time allocation
        allocation = self.get_today_allocation()
        allocation.hours_studying += hours
        allocation.studying_skill = skill_type

        # Add experience and check for level up
        xp_gain = GameConstants.WORK_TRAINING_XP_GAIN * hours
        leveled_up, new_level = self.add_experience(xp_gain)

        # Track study streak for achievements
        from app.services.achievement_service import AchievementService
        try:
            AchievementService.track_study_streak(self)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error tracking study achievement for user {self.id}: {e}")

        message = f"Studied {skill_type.replace('_', ' ')} for {hours} hours. Gained {skill_gain:.2f} skill and {xp_gain} XP. Energy: -{energy_cost}"

        return True, message, skill_gain, energy_cost, leveled_up, new_level

    def allocate_work_hours(self, employment_id, hours):
        """
        Allocate hours to work at a company.
        Delegates to EmploymentService for the actual implementation.

        Args:
            employment_id: ID of the employment relationship
            hours: Number of hours to work (1-12)

        Returns:
            tuple: (success: bool, message: str, production_points: float, payment: Decimal, energy_cost: int, wellness_cost: int)
        """
        from app.services.employment_service import EmploymentService
        return EmploymentService.allocate_work_hours(self, employment_id, hours)

    def get_or_create_currency(self, country_id):
        """Get or create user's currency for a specific country."""
        from .currency import UserCurrency

        user_currency = db.session.scalar(
            select(UserCurrency).where(
                UserCurrency.user_id == self.id,
                UserCurrency.country_id == country_id
            )
        )

        if not user_currency:
            user_currency = UserCurrency(
                user_id=self.id,
                country_id=country_id,
                amount=Decimal('0')
            )
            db.session.add(user_currency)
            db.session.flush()

        return user_currency

    # --- Currency Methods (Multi-Currency Support) ---
    def get_currency_amount(self, country_id):
        """Get amount of specific country's currency user owns."""
        from app.services.currency_service import CurrencyService
        return CurrencyService.get_amount(self, country_id)

    @property
    def local_currency(self):
        """Get currency amount for the country user is currently in (for dashboard display)."""
        from app.services.currency_service import CurrencyService
        return CurrencyService.get_local_currency(self)

    @property
    def local_currency_code(self):
        """Get currency code for the country user is currently in."""
        from app.services.currency_service import CurrencyService
        return CurrencyService.get_local_currency_code(self)

    @property
    def all_currencies(self):
        """Get all currencies owned by user with amount > 0."""
        from app.services.currency_service import CurrencyService
        return CurrencyService.get_all_currencies(self)

    def add_currency(self, country_id, amount):
        """Add currency to user's wallet."""
        from app.services.currency_service import CurrencyService
        return CurrencyService.add_currency(self, country_id, amount)

    def remove_currency(self, country_id, amount):
        """Remove currency from user's wallet. Returns False if insufficient funds."""
        from app.services.currency_service import CurrencyService
        return CurrencyService.remove_currency(self, country_id, amount)

    def has_sufficient_currency(self, country_id, amount):
        """Check if user has enough of a specific currency."""
        from app.services.currency_service import CurrencyService
        return CurrencyService.has_sufficient(self, country_id, amount)

    def validate_currency_transaction(self, country_id, amount, action='deduct'):
        """
        Validate currency transaction before attempting.

        Args:
            country_id: Country ID for the currency
            amount: Amount to validate
            action: 'deduct' or 'add'

        Returns:
            bool: True if valid

        Raises:
            InvalidAmountError: If amount is invalid
            InsufficientFundsError: If user doesn't have enough currency
        """
        from app.services.currency_service import CurrencyService
        return CurrencyService.validate_transaction(self, country_id, amount, action)

    def safe_remove_currency(self, country_id, amount):
        """
        Safe currency removal with validation.

        Args:
            country_id: Country ID for the currency
            amount: Amount to remove

        Returns:
            bool: True if successful

        Raises:
            InvalidAmountError: If amount is invalid
            InsufficientFundsError: If user doesn't have enough currency
        """
        from app.services.currency_service import CurrencyService
        return CurrencyService.safe_remove(self, country_id, amount)

    # --- Referral System Methods ---
    def generate_referral_code(self):
        """Generate a unique referral code for the user."""
        import secrets
        import string

        if self.referral_code:
            return self.referral_code  # Already has a code

        # Generate a random 8-character alphanumeric code
        alphabet = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(secrets.choice(alphabet) for _ in range(8))
            # Check if code is unique
            existing = db.session.scalar(select(User).where(User.referral_code == code))
            if not existing:
                self.referral_code = code
                return code

    def check_and_award_referral_bonus(self):
        """
        Check if user has reached level 10 and award referral bonus to referrer.
        Should be called when user gains experience.

        Returns:
            bool: True if bonus was awarded
        """
        # Only award at level 10
        if self.level != 10:
            return False

        # Check if user was referred
        if not self.referred_by_relation:
            return False

        referral = self.referred_by_relation

        # Check if referral is still pending
        if not referral.is_pending:
            return False  # Already completed or cancelled

        # Award gold to referrer with row-level locking
        referrer = referral.referrer
        gold_amount = Decimal('5.0')
        from app.services.currency_service import CurrencyService
        success, message, _ = CurrencyService.add_gold(
            referrer.id, gold_amount, f'Referral bonus for user {self.id}'
        )
        if not success:
            logger.error(f"Failed to add referral gold to user {referrer.id}: {message}")
            return False

        # Mark referral as completed
        referral.complete_referral(gold_amount)

        logger.info(f"Referral bonus awarded: User {referrer.id} received {gold_amount} gold for referring user {self.id}")
        return True

    @property
    def referrer(self):
        """Get the user who referred this user, if any."""
        if self.referred_by_relation:
            return self.referred_by_relation.referrer
        return None

    @property
    def referral_stats(self):
        """Get referral statistics for this user."""
        from .referral import ReferralStatus

        total = self.referrals_made.count()
        pending = self.referrals_made.filter_by(status=ReferralStatus.PENDING).count()
        completed = self.referrals_made.filter_by(status=ReferralStatus.COMPLETED).count()

        return {
            'total': total,
            'pending': pending,
            'completed': completed,
            'gold_earned': sum(r.gold_awarded for r in self.referrals_made.filter_by(status=ReferralStatus.COMPLETED))
        }

    # --- Friendship Methods ---
    def get_friendship_status(self, other_user_id):
        """
        Get friendship status with another user.

        Returns:
            str: 'friends', 'request_sent', 'request_received', 'none'
        """
        from .friendship import Friendship, FriendshipStatus

        # Check if we sent a request to them
        sent_request = db.session.scalar(
            select(Friendship).where(
                Friendship.requester_id == self.id,
                Friendship.receiver_id == other_user_id
            )
        )

        if sent_request:
            if sent_request.status == FriendshipStatus.ACCEPTED:
                return 'friends'
            else:
                return 'request_sent'

        # Check if they sent a request to us
        received_request = db.session.scalar(
            select(Friendship).where(
                Friendship.requester_id == other_user_id,
                Friendship.receiver_id == self.id
            )
        )

        if received_request:
            if received_request.status == FriendshipStatus.ACCEPTED:
                return 'friends'
            else:
                return 'request_received'

        return 'none'

    def are_friends(self, other_user_id):
        """Quick check if users are friends (accepted friendship)."""
        return self.get_friendship_status(other_user_id) == 'friends'

    def get_friends(self):
        """
        Get list of all accepted friends.

        Returns:
            list: List of User objects who are friends
        """
        from .friendship import Friendship, FriendshipStatus

        # Get friendships where this user is the requester
        friends_as_requester = db.session.scalars(
            select(User).join(
                Friendship, Friendship.receiver_id == User.id
            ).where(
                Friendship.requester_id == self.id,
                Friendship.status == FriendshipStatus.ACCEPTED
            )
        ).all()

        # Get friendships where this user is the receiver
        friends_as_receiver = db.session.scalars(
            select(User).join(
                Friendship, Friendship.requester_id == User.id
            ).where(
                Friendship.receiver_id == self.id,
                Friendship.status == FriendshipStatus.ACCEPTED
            )
        ).all()

        # Combine and return unique friends
        return list(set(friends_as_requester + friends_as_receiver))

    def get_pending_friend_requests(self):
        """
        Get list of pending friend requests received by this user.

        Returns:
            list: List of Friendship objects with pending requests
        """
        from .friendship import Friendship, FriendshipStatus

        return db.session.scalars(
            select(Friendship).where(
                Friendship.receiver_id == self.id,
                Friendship.status == FriendshipStatus.PENDING
            )
        ).all()

    # ==================== Military Rank Methods ====================

    def add_rank_xp(self, xp_amount):
        """
        Add XP to military rank and check for rank ups

        Args:
            xp_amount: Amount of XP to add (from battle damage * 0.1)

        Returns:
            bool: True if ranked up, False otherwise
        """
        self.military_rank_xp += Decimal(str(xp_amount))
        ranked_up = False

        # Check for rank ups
        while self.military_rank_id < 60:  # Max rank is 60 (Field Marshal)
            from app.models.military_rank import MilitaryRank
            next_rank = MilitaryRank.get_next_rank(self.military_rank_id)

            if next_rank and self.military_rank_xp >= next_rank.xp_required:
                self.military_rank_id = next_rank.id
                ranked_up = True
                logger.info(f"User {self.username} ranked up to {next_rank.name}")
            else:
                break

        return ranked_up

    def get_rank_progress(self):
        """
        Get current rank progress information

        Returns:
            dict: Contains current_rank, next_rank, current_xp, xp_needed, progress_percent
        """
        from app.models.military_rank import MilitaryRank

        current_rank = self.rank
        next_rank = MilitaryRank.get_next_rank(self.military_rank_id) if self.military_rank_id < 60 else None

        if not next_rank:
            # Max rank reached
            return {
                'current_rank': current_rank,
                'next_rank': None,
                'current_xp': float(self.military_rank_xp),
                'xp_needed': 0,
                'progress_percent': 100.0
            }

        # Calculate progress to next rank
        current_xp = float(self.military_rank_xp)
        xp_needed = next_rank.xp_required
        current_rank_xp_start = current_rank.xp_required if current_rank else 0

        # XP in current rank level
        xp_in_current_level = current_xp - current_rank_xp_start
        xp_for_next_level = xp_needed - current_rank_xp_start

        progress_percent = (xp_in_current_level / xp_for_next_level * 100) if xp_for_next_level > 0 else 0

        return {
            'current_rank': current_rank,
            'next_rank': next_rank,
            'current_xp': xp_in_current_level,
            'xp_needed': xp_for_next_level,
            'progress_percent': min(progress_percent, 100.0)
        }

    def get_rank_damage_bonus(self):
        """
        Get damage bonus percentage from current military rank

        Returns:
            int: Damage bonus percentage (e.g., 20 for +20%)
        """
        if self.rank:
            return self.rank.damage_bonus
        return 2  # Default to Recruit bonus

    def __repr__(self):
        """String representation of the User object."""
        display_name = self.username if self.username else self.wallet_address
        return f'<User {display_name} (Lvl {self.level})>'