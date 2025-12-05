# app/models/military_unit.py
"""
Military Unit Models

Models for military units (regiments) that players can form and join.
Features:
- Unit hierarchy: Commander, Officers, Soldiers, Recruits
- Unit inventory and treasury
- Bounty contracts from Ministers of Defence
- Message board for unit communication
- Leaderboards and achievements
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from sqlalchemy import Numeric, CheckConstraint, Index, func, select
from app.extensions import db


class MilitaryUnitRank(Enum):
    """Ranks within a military unit."""
    COMMANDER = "commander"  # Can do everything
    OFFICER = "officer"  # Can approve/deny applications, kick soldiers/recruits
    SOLDIER = "soldier"  # Regular member
    RECRUIT = "recruit"  # New member (visually different from soldier)


class BountyContractStatus(Enum):
    """Status of a bounty contract."""
    PENDING = "pending"  # Unit applied, waiting for Minister approval
    APPROVED = "approved"  # Minister approved, contract is active
    REJECTED = "rejected"  # Minister rejected the application
    COMPLETED = "completed"  # Unit met the damage requirement
    FAILED = "failed"  # Battle ended without meeting requirement
    CANCELLED = "cancelled"  # Cancelled before completion


class MilitaryUnit(db.Model):
    """
    Military unit (regiment) that players can form and join.

    - Max 50 members
    - Based on the country where the leader's citizenship is
    - Can fight as mercenaries for any country
    - Commander can apply for bounty contracts from Ministers of Defence
    """
    __tablename__ = 'military_units'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    avatar = db.Column(db.Boolean, default=False, nullable=False)

    # Unit is based in the country of the commander's citizenship
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)

    # Commander (founder initially)
    commander_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Treasury (local currency of the country)
    treasury = db.Column(Numeric(20, 8), default=Decimal('0.0'), nullable=False)

    # Stats for leaderboards
    total_damage = db.Column(db.BigInteger, default=0, nullable=False)
    battles_participated = db.Column(db.Integer, default=0, nullable=False)
    battles_won = db.Column(db.Integer, default=0, nullable=False)
    contracts_completed = db.Column(db.Integer, default=0, nullable=False)

    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    disbanded_at = db.Column(db.DateTime, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    country = db.relationship('Country', backref=db.backref('military_units', lazy='dynamic'))
    commander = db.relationship('User', foreign_keys=[commander_id], backref=db.backref('commanded_unit', uselist=False))
    members = db.relationship('MilitaryUnitMember', back_populates='unit', lazy='dynamic', cascade='all, delete-orphan')
    inventory = db.relationship('MilitaryUnitInventory', back_populates='unit', lazy='dynamic', cascade='all, delete-orphan')
    transactions = db.relationship('MilitaryUnitTransaction', back_populates='unit', lazy='dynamic', cascade='all, delete-orphan')
    applications = db.relationship('MilitaryUnitApplication', back_populates='unit', lazy='dynamic', cascade='all, delete-orphan')
    messages = db.relationship('MilitaryUnitMessage', back_populates='unit', lazy='dynamic', cascade='all, delete-orphan')
    bounty_applications = db.relationship('BountyContractApplication', back_populates='unit', lazy='dynamic', cascade='all, delete-orphan')

    # Constants
    MAX_MEMBERS = 50
    CREATION_COST_GOLD = 20

    __table_args__ = (
        CheckConstraint('treasury >= 0', name='treasury_non_negative'),
    )

    def __repr__(self):
        return f'<MilitaryUnit {self.name}>'

    @property
    def member_count(self):
        """Get current number of active members."""
        return self.members.filter_by(is_active=True).count()

    @property
    def is_full(self):
        """Check if unit has reached max members."""
        return self.member_count >= self.MAX_MEMBERS

    def get_active_members(self):
        """Get all active members."""
        return self.members.filter_by(is_active=True).all()

    def get_officers(self):
        """Get all active officers."""
        return self.members.filter_by(is_active=True, rank=MilitaryUnitRank.OFFICER).all()

    def is_member(self, user_id):
        """Check if a user is an active member."""
        return self.members.filter_by(user_id=user_id, is_active=True).first() is not None

    def get_member(self, user_id):
        """Get a specific member by user ID."""
        return self.members.filter_by(user_id=user_id, is_active=True).first()

    def can_manage_applications(self, user_id):
        """Check if user can approve/deny applications (commander or officer)."""
        if user_id == self.commander_id:
            return True
        member = self.get_member(user_id)
        return member and member.rank == MilitaryUnitRank.OFFICER

    def can_kick_member(self, kicker_id, target_id):
        """Check if user can kick another member."""
        if kicker_id == target_id:
            return False, "You cannot kick yourself."

        if target_id == self.commander_id:
            return False, "You cannot kick the commander."

        kicker = self.get_member(kicker_id)
        target = self.get_member(target_id)

        if not kicker or not target:
            return False, "Member not found."

        # Commander can kick anyone
        if kicker_id == self.commander_id:
            return True, ""

        # Officers can kick soldiers and recruits
        if kicker.rank == MilitaryUnitRank.OFFICER:
            if target.rank in [MilitaryUnitRank.SOLDIER, MilitaryUnitRank.RECRUIT]:
                return True, ""
            return False, "Officers can only kick soldiers and recruits."

        return False, "You don't have permission to kick members."

    def get_active_bounty_contract(self):
        """Get the current active bounty contract if any."""
        from app.models.military_unit import BountyContractApplication
        return BountyContractApplication.query.filter_by(
            unit_id=self.id,
            status=BountyContractStatus.APPROVED
        ).first()

    def has_active_contract(self):
        """Check if unit has an active bounty contract."""
        return self.get_active_bounty_contract() is not None

    @property
    def average_rating(self):
        """Get average rating from completed bounty contracts."""
        from sqlalchemy import func
        result = db.session.query(func.avg(BountyContractApplication.review_rating)).filter(
            BountyContractApplication.unit_id == self.id,
            BountyContractApplication.status == BountyContractStatus.COMPLETED,
            BountyContractApplication.review_rating.isnot(None)
        ).scalar()
        return float(result) if result else None

    @property
    def review_count(self):
        """Get count of reviews received."""
        return BountyContractApplication.query.filter(
            BountyContractApplication.unit_id == self.id,
            BountyContractApplication.status == BountyContractStatus.COMPLETED,
            BountyContractApplication.review_rating.isnot(None)
        ).count()


class MilitaryUnitMember(db.Model):
    """
    Membership record for a player in a military unit.
    """
    __tablename__ = 'military_unit_members'

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('military_units.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Rank within the unit
    rank = db.Column(db.Enum(MilitaryUnitRank), nullable=False, default=MilitaryUnitRank.RECRUIT)

    # Membership status
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)

    # Personal stats while in this unit
    damage_dealt = db.Column(db.BigInteger, default=0, nullable=False)

    # Timestamps
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    left_at = db.Column(db.DateTime, nullable=True)
    left_reason = db.Column(db.String(100), nullable=True)  # "voluntary", "kicked", "unit_disbanded"

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    unit = db.relationship('MilitaryUnit', back_populates='members')
    user = db.relationship('User', backref=db.backref('military_unit_memberships', lazy='dynamic'))

    __table_args__ = (
        # Only one active membership per user
        Index('idx_active_unit_membership', 'user_id', 'is_active'),
    )

    def __repr__(self):
        return f'<MilitaryUnitMember {self.user_id} in {self.unit_id}>'

    def leave(self, reason="voluntary"):
        """Leave the unit."""
        self.is_active = False
        self.left_at = datetime.utcnow()
        self.left_reason = reason

    @staticmethod
    def get_user_active_membership(user_id):
        """Get user's active unit membership if any."""
        return MilitaryUnitMember.query.filter_by(
            user_id=user_id,
            is_active=True
        ).first()

    @staticmethod
    def get_user_unit(user_id):
        """Get the unit a user belongs to (if any)."""
        membership = MilitaryUnitMember.get_user_active_membership(user_id)
        if membership:
            return membership.unit
        return None


class MilitaryUnitApplication(db.Model):
    """
    Application to join a military unit.
    """
    __tablename__ = 'military_unit_applications'

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('military_units.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Application status
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)  # pending, approved, rejected

    # Who processed the application
    processed_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    processed_at = db.Column(db.DateTime, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    unit = db.relationship('MilitaryUnit', back_populates='applications')
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('unit_applications', lazy='dynamic'))
    processed_by = db.relationship('User', foreign_keys=[processed_by_id])

    __table_args__ = (
        # One pending application per user
        Index('idx_pending_unit_application', 'user_id', 'status'),
    )

    def __repr__(self):
        return f'<MilitaryUnitApplication {self.user_id} to {self.unit_id}>'

    def approve(self, processed_by_id):
        """Approve the application."""
        self.status = 'approved'
        self.processed_by_id = processed_by_id
        self.processed_at = datetime.utcnow()

    def reject(self, processed_by_id):
        """Reject the application."""
        self.status = 'rejected'
        self.processed_by_id = processed_by_id
        self.processed_at = datetime.utcnow()


class MilitaryUnitInventory(db.Model):
    """
    Military unit's inventory of weapons, food, and drinks.
    """
    __tablename__ = 'military_unit_inventory'

    # Composite primary key
    unit_id = db.Column(db.Integer, db.ForeignKey('military_units.id'), primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey('resource.id'), primary_key=True)
    quality = db.Column(db.Integer, primary_key=True, default=0, nullable=False)  # 0 for non-quality, 1-5 for quality items

    # Quantity
    quantity = db.Column(db.Integer, default=0, nullable=False)

    # Relationships
    unit = db.relationship('MilitaryUnit', back_populates='inventory')
    resource = db.relationship('Resource')

    __table_args__ = (
        CheckConstraint('quantity >= 0', name='unit_inventory_quantity_non_negative'),
    )

    def __repr__(self):
        return f'<MilitaryUnitInventory Unit:{self.unit_id} Res:{self.resource_id} Q:{self.quality} Qty:{self.quantity}>'


class MilitaryUnitTransaction(db.Model):
    """
    Transaction log for military unit treasury and inventory.
    """
    __tablename__ = 'military_unit_transactions'

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('military_units.id'), nullable=False, index=True)

    # Transaction type
    transaction_type = db.Column(db.String(50), nullable=False)  #
    # Types: 'bounty_received', 'item_given_to_member', 'item_received_from_bounty'

    # For currency transactions
    currency_amount = db.Column(Numeric(20, 8), nullable=True)
    currency_balance_after = db.Column(Numeric(20, 8), nullable=True)

    # For item transactions
    resource_id = db.Column(db.Integer, db.ForeignKey('resource.id'), nullable=True)
    resource_quality = db.Column(db.Integer, nullable=True)
    resource_quantity = db.Column(db.Integer, nullable=True)

    # Who performed the transaction
    performed_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    # Target member (for item distributions)
    target_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    # Additional details
    description = db.Column(db.String(255), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    unit = db.relationship('MilitaryUnit', back_populates='transactions')
    resource = db.relationship('Resource')
    performed_by = db.relationship('User', foreign_keys=[performed_by_id])
    target_user = db.relationship('User', foreign_keys=[target_user_id])

    def __repr__(self):
        return f'<MilitaryUnitTransaction {self.transaction_type} Unit:{self.unit_id}>'


class MilitaryUnitMessage(db.Model):
    """
    Message board for military unit internal communication.
    """
    __tablename__ = 'military_unit_messages'

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('military_units.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Message content
    content = db.Column(db.Text, nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships
    unit = db.relationship('MilitaryUnit', back_populates='messages')
    user = db.relationship('User', backref=db.backref('unit_messages', lazy='dynamic'))

    def __repr__(self):
        return f'<MilitaryUnitMessage {self.id} Unit:{self.unit_id}>'


class BountyContract(db.Model):
    """
    Bounty contract offered by a Minister of Defence.

    Minister can create a bounty for a specific battle, offering payment
    for a certain amount of damage dealt by a military unit.
    """
    __tablename__ = 'bounty_contracts'

    id = db.Column(db.Integer, primary_key=True)

    # The country offering the bounty (through their Minister of Defence)
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)

    # The battle this bounty is for
    battle_id = db.Column(db.Integer, db.ForeignKey('battles.id'), nullable=False, index=True)

    # Which side the unit should fight for (True = attacker side, False = defender side)
    fight_for_attacker = db.Column(db.Boolean, nullable=False)

    # Bounty details
    damage_required = db.Column(db.BigInteger, nullable=False)  # Damage threshold to complete
    payment_amount = db.Column(Numeric(20, 8), nullable=False)  # Payment in country currency

    # Who created this bounty
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)  # When battle ends

    # Relationships
    country = db.relationship('Country', backref=db.backref('bounty_contracts', lazy='dynamic'))
    battle = db.relationship('Battle', backref=db.backref('bounty_contracts', lazy='dynamic'))
    created_by = db.relationship('User', backref=db.backref('bounty_contracts_created', lazy='dynamic'))
    applications = db.relationship('BountyContractApplication', back_populates='contract', lazy='dynamic', cascade='all, delete-orphan')

    __table_args__ = (
        CheckConstraint('damage_required > 0', name='damage_required_positive'),
        CheckConstraint('payment_amount > 0', name='payment_amount_positive'),
    )

    def __repr__(self):
        return f'<BountyContract {self.id} Country:{self.country_id} Battle:{self.battle_id}>'

    @property
    def is_expired(self):
        """Check if the bounty has expired."""
        return datetime.utcnow() >= self.expires_at

    def get_approved_unit(self):
        """Get the unit that has an approved contract for this bounty."""
        app = self.applications.filter_by(status=BountyContractStatus.APPROVED).first()
        return app.unit if app else None

    def get_completed_application(self):
        """Get the completed application for this bounty (if any)."""
        return self.applications.filter_by(status=BountyContractStatus.COMPLETED).first()


class BountyContractApplication(db.Model):
    """
    Application from a military unit to fulfill a bounty contract.
    """
    __tablename__ = 'bounty_contract_applications'

    id = db.Column(db.Integer, primary_key=True)

    # The bounty contract
    contract_id = db.Column(db.Integer, db.ForeignKey('bounty_contracts.id'), nullable=False, index=True)

    # The military unit applying
    unit_id = db.Column(db.Integer, db.ForeignKey('military_units.id'), nullable=False, index=True)

    # Application status
    status = db.Column(db.Enum(BountyContractStatus), nullable=False, default=BountyContractStatus.PENDING, index=True)

    # Who applied (unit commander)
    applied_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Processing details
    processed_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    processed_at = db.Column(db.DateTime, nullable=True)

    # Damage tracking (updated during battle)
    damage_dealt = db.Column(db.BigInteger, default=0, nullable=False)

    # Payment tracking
    payment_received = db.Column(Numeric(20, 8), default=Decimal('0.0'), nullable=False)
    paid_at = db.Column(db.DateTime, nullable=True)

    # Review from Minister (after battle ends)
    review_rating = db.Column(db.Integer, nullable=True)  # 1-5 stars
    review_at = db.Column(db.DateTime, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    contract = db.relationship('BountyContract', back_populates='applications')
    unit = db.relationship('MilitaryUnit', back_populates='bounty_applications')
    applied_by = db.relationship('User', foreign_keys=[applied_by_id])
    processed_by = db.relationship('User', foreign_keys=[processed_by_id])

    __table_args__ = (
        # One application per unit per contract
        db.UniqueConstraint('contract_id', 'unit_id', name='unique_contract_unit_application'),
        CheckConstraint('review_rating IS NULL OR (review_rating >= 1 AND review_rating <= 5)', name='review_rating_range'),
    )

    def __repr__(self):
        return f'<BountyContractApplication Contract:{self.contract_id} Unit:{self.unit_id}>'

    def approve(self, processed_by_id):
        """Approve the application."""
        self.status = BountyContractStatus.APPROVED
        self.processed_by_id = processed_by_id
        self.processed_at = datetime.utcnow()

    def reject(self, processed_by_id):
        """Reject the application."""
        self.status = BountyContractStatus.REJECTED
        self.processed_by_id = processed_by_id
        self.processed_at = datetime.utcnow()

    def complete(self, payment_amount):
        """Mark contract as completed and record payment."""
        from app.models.messaging import Alert, AlertType

        self.status = BountyContractStatus.COMPLETED
        self.payment_received = payment_amount
        self.paid_at = datetime.utcnow()

        # Send alert to unit commander
        if self.unit and self.unit.commander_id:
            country = self.contract.country if self.contract else None
            currency_code = country.currency_code if country else 'currency'

            alert = Alert(
                user_id=self.unit.commander_id,
                alert_type=AlertType.BOUNTY_COMPLETED.value,
                priority='normal',
                title='Bounty Contract Completed!',
                content=f'Your military unit "{self.unit.name}" has successfully completed a bounty contract! '
                        f'Payment of {payment_amount:,.2f} {currency_code} has been deposited into the unit treasury.',
                alert_data={
                    'unit_id': self.unit.id,
                    'unit_name': self.unit.name,
                    'contract_id': self.contract_id,
                    'payment_amount': float(payment_amount),
                    'currency_code': currency_code
                },
                link_url=f'/military-unit/{self.unit.id}',
                link_text='View Unit'
            )
            db.session.add(alert)

    def fail(self):
        """Mark contract as failed (battle ended without meeting requirement)."""
        self.status = BountyContractStatus.FAILED

    def add_review(self, rating):
        """Add a review from the Minister."""
        if 1 <= rating <= 5:
            self.review_rating = rating
            self.review_at = datetime.utcnow()

    @property
    def progress_percent(self):
        """Get progress towards damage requirement as percentage."""
        if self.contract and self.contract.damage_required > 0:
            return min(100, (self.damage_dealt / self.contract.damage_required) * 100)
        return 0


class MilitaryUnitAchievement(db.Model):
    """
    Achievements earned by military units.
    """
    __tablename__ = 'military_unit_achievements'

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('military_units.id'), nullable=False, index=True)

    # Achievement type
    achievement_type = db.Column(db.String(50), nullable=False)
    # Types: 'first_bounty', 'damage_1m', 'contracts_10', 'contracts_50', 'damage_10m', etc.

    # Earned timestamp
    earned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    unit = db.relationship('MilitaryUnit', backref=db.backref('achievements', lazy='dynamic'))

    __table_args__ = (
        # One achievement per type per unit
        db.UniqueConstraint('unit_id', 'achievement_type', name='unique_unit_achievement'),
    )

    def __repr__(self):
        return f'<MilitaryUnitAchievement {self.achievement_type} Unit:{self.unit_id}>'

    # Achievement definitions
    ACHIEVEMENT_TYPES = {
        'first_bounty': {
            'name': 'First Blood',
            'description': 'Complete your first bounty contract',
            'icon': 'fa-crosshairs'
        },
        'damage_1m': {
            'name': 'Million Damage',
            'description': 'Deal 1,000,000 total damage',
            'icon': 'fa-fire'
        },
        'damage_10m': {
            'name': 'Ten Million Damage',
            'description': 'Deal 10,000,000 total damage',
            'icon': 'fa-fire-flame-curved'
        },
        'contracts_10': {
            'name': 'Veteran Mercenaries',
            'description': 'Complete 10 bounty contracts',
            'icon': 'fa-file-contract'
        },
        'contracts_50': {
            'name': 'Elite Mercenaries',
            'description': 'Complete 50 bounty contracts',
            'icon': 'fa-medal'
        },
        'battles_won_10': {
            'name': 'Battle Hardened',
            'description': 'Win 10 battles',
            'icon': 'fa-trophy'
        },
        'battles_won_50': {
            'name': 'War Veterans',
            'description': 'Win 50 battles',
            'icon': 'fa-crown'
        },
    }

    @classmethod
    def get_achievement_info(cls, achievement_type):
        """Get achievement information by type."""
        return cls.ACHIEVEMENT_TYPES.get(achievement_type, {
            'name': achievement_type,
            'description': '',
            'icon': 'fa-star'
        })
