# app/models/battle.py
"""
Battle System Models

Models for the war battle system including:
- MutualProtectionPact: 30-day alliance agreements between countries
- Battle: Individual battles within a war (24h duration, 3 rounds)
- BattleRound: 8-hour rounds within a battle
- BattleParticipation: Player's chosen wall for a battle
- BattleDamage: Individual damage records for leaderboards
"""

from datetime import datetime, timedelta
from enum import Enum
from app.extensions import db


class BattleStatus(Enum):
    """Status of a battle."""
    ACTIVE = "active"  # Battle is currently in progress
    ATTACKER_WON = "attacker_won"  # Attackers won the battle
    DEFENDER_WON = "defender_won"  # Defenders won the battle


class RoundStatus(Enum):
    """Status of a battle round."""
    ACTIVE = "active"  # Round is currently in progress
    COMPLETED = "completed"  # Round has ended


class WallType(Enum):
    """Types of battle walls (matching military skills)."""
    INFANTRY = "infantry"  # Uses Infantry skill, Rifle weapons
    ARMOURED = "armoured"  # Uses Armoured skill, Tank weapons
    AVIATION = "aviation"  # Uses Aviation skill, Helicopter weapons


class MutualProtectionPact(db.Model):
    """
    Mutual Protection Pact between two countries.

    When active, citizens of the allied country can fight on the same side
    as if they were located in that country.
    Duration: 30 days from activation.
    """
    __tablename__ = 'mutual_protection_pacts'

    id = db.Column(db.Integer, primary_key=True)

    # The two countries in the pact
    country_a_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)
    country_b_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)

    # The law that created this pact (from country_a)
    created_by_law_id = db.Column(db.Integer, db.ForeignKey('laws.id'), nullable=False)

    # Pact timeline
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)  # 30 days from start

    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    ended_early = db.Column(db.Boolean, default=False, nullable=False)
    ended_at = db.Column(db.DateTime, nullable=True)
    ended_reason = db.Column(db.String(100), nullable=True)  # "expired", "cancelled", etc.

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    country_a = db.relationship('Country', foreign_keys=[country_a_id], backref=db.backref('pacts_initiated', lazy='dynamic'))
    country_b = db.relationship('Country', foreign_keys=[country_b_id], backref=db.backref('pacts_received', lazy='dynamic'))
    created_by_law = db.relationship('Law', backref='mutual_protection_pact')

    __table_args__ = (
        # Prevent duplicate active pacts between same countries
        db.Index('idx_active_pact', 'country_a_id', 'country_b_id', 'is_active'),
    )

    def __repr__(self):
        return f'<MutualProtectionPact {self.country_a_id} <-> {self.country_b_id}>'

    @property
    def is_expired(self):
        """Check if the pact has expired."""
        return datetime.utcnow() >= self.expires_at

    def get_partner_country_id(self, country_id):
        """Get the partner country ID for a given country."""
        if country_id == self.country_a_id:
            return self.country_b_id
        elif country_id == self.country_b_id:
            return self.country_a_id
        return None

    @staticmethod
    def get_active_pact(country_a_id, country_b_id):
        """Get active pact between two countries (order doesn't matter)."""
        return MutualProtectionPact.query.filter(
            MutualProtectionPact.is_active == True,
            db.or_(
                db.and_(
                    MutualProtectionPact.country_a_id == country_a_id,
                    MutualProtectionPact.country_b_id == country_b_id
                ),
                db.and_(
                    MutualProtectionPact.country_a_id == country_b_id,
                    MutualProtectionPact.country_b_id == country_a_id
                )
            )
        ).first()

    @staticmethod
    def get_all_allies(country_id):
        """Get all countries that have active MPP with given country."""
        pacts = MutualProtectionPact.query.filter(
            MutualProtectionPact.is_active == True,
            db.or_(
                MutualProtectionPact.country_a_id == country_id,
                MutualProtectionPact.country_b_id == country_id
            )
        ).all()

        allies = []
        for pact in pacts:
            if pact.country_a_id == country_id:
                allies.append(pact.country_b_id)
            else:
                allies.append(pact.country_a_id)
        return allies


class Battle(db.Model):
    """
    Individual battle within a war.

    Each battle lasts 24 hours and consists of 3 rounds (8 hours each).
    To win a battle, a side must win 2/3 rounds.
    All 3 rounds are played regardless of early victory.
    """
    __tablename__ = 'battles'

    id = db.Column(db.Integer, primary_key=True)

    # The war this battle belongs to
    war_id = db.Column(db.Integer, db.ForeignKey('wars.id'), nullable=False, index=True)

    # The region being fought over
    region_id = db.Column(db.Integer, db.ForeignKey('region.id'), nullable=False, index=True)

    # Which country started this battle
    started_by_country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False)
    started_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Battle status
    status = db.Column(db.Enum(BattleStatus), nullable=False, default=BattleStatus.ACTIVE, index=True)

    # Round wins tracking
    attacker_rounds_won = db.Column(db.Integer, default=0, nullable=False)
    defender_rounds_won = db.Column(db.Integer, default=0, nullable=False)

    # Current round (1, 2, or 3)
    current_round = db.Column(db.Integer, default=1, nullable=False)

    # Battle timeline
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=False)  # 24 hours from start
    ended_at = db.Column(db.DateTime, nullable=True)  # Actual end time

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    war = db.relationship('War', backref=db.backref('battles', lazy='dynamic'))
    region = db.relationship('Region', backref=db.backref('battles', lazy='dynamic'))
    started_by_country = db.relationship('Country', foreign_keys=[started_by_country_id])
    started_by_user = db.relationship('User', foreign_keys=[started_by_user_id])
    rounds = db.relationship('BattleRound', back_populates='battle', lazy='dynamic',
                            cascade='all, delete-orphan', order_by='BattleRound.round_number')
    participations = db.relationship('BattleParticipation', back_populates='battle', lazy='dynamic',
                                     cascade='all, delete-orphan')
    damage_records = db.relationship('BattleDamage', back_populates='battle', lazy='dynamic',
                                     cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Battle {self.id} War:{self.war_id} Region:{self.region_id} Status:{self.status.value}>'

    @property
    def is_active(self):
        """Check if battle is currently active."""
        return self.status == BattleStatus.ACTIVE and datetime.utcnow() < self.ends_at

    @property
    def attacker_country_id(self):
        """Get the attacking country ID from the war."""
        return self.war.attacker_country_id if self.war else None

    @property
    def defender_country_id(self):
        """Get the defending country ID from the war."""
        return self.war.defender_country_id if self.war else None

    def get_current_round(self):
        """Get the current active round."""
        return self.rounds.filter_by(round_number=self.current_round).first()

    def get_round(self, round_number):
        """Get a specific round by number."""
        return self.rounds.filter_by(round_number=round_number).first()


class BattleRound(db.Model):
    """
    Individual round within a battle (8 hours each).

    Each round has 3 walls (Infantry, Armoured, Aviation).
    Winner of a round is determined by who leads 2/3 walls.
    """
    __tablename__ = 'battle_rounds'

    id = db.Column(db.Integer, primary_key=True)

    # The battle this round belongs to
    battle_id = db.Column(db.Integer, db.ForeignKey('battles.id'), nullable=False, index=True)

    # Round number (1, 2, or 3)
    round_number = db.Column(db.Integer, nullable=False)

    # Round status
    status = db.Column(db.Enum(RoundStatus), nullable=False, default=RoundStatus.ACTIVE, index=True)

    # Damage totals for each wall (positive = attacker leads, negative = defender leads)
    # Stored as the difference: attacker_damage - defender_damage
    infantry_damage_diff = db.Column(db.Integer, default=0, nullable=False)
    armoured_damage_diff = db.Column(db.Integer, default=0, nullable=False)
    aviation_damage_diff = db.Column(db.Integer, default=0, nullable=False)

    # Wall winners (True = attacker won, False = defender won, None = not yet determined)
    infantry_winner_is_attacker = db.Column(db.Boolean, nullable=True)
    armoured_winner_is_attacker = db.Column(db.Boolean, nullable=True)
    aviation_winner_is_attacker = db.Column(db.Boolean, nullable=True)

    # Round winner (True = attacker won, False = defender won, None = tie/not yet determined)
    winner_is_attacker = db.Column(db.Boolean, nullable=True)

    # Round timeline
    started_at = db.Column(db.DateTime, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=False)  # 8 hours from start
    ended_at = db.Column(db.DateTime, nullable=True)  # Actual end time

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    battle = db.relationship('Battle', back_populates='rounds')

    __table_args__ = (
        db.UniqueConstraint('battle_id', 'round_number', name='unique_battle_round'),
    )

    def __repr__(self):
        return f'<BattleRound Battle:{self.battle_id} Round:{self.round_number} Status:{self.status.value}>'

    @property
    def is_active(self):
        """Check if round is currently active."""
        return self.status == RoundStatus.ACTIVE and datetime.utcnow() < self.ends_at

    def get_wall_damage(self, wall_type):
        """Get the damage difference for a specific wall."""
        if wall_type == WallType.INFANTRY:
            return self.infantry_damage_diff
        elif wall_type == WallType.ARMOURED:
            return self.armoured_damage_diff
        elif wall_type == WallType.AVIATION:
            return self.aviation_damage_diff
        return 0

    def add_damage(self, wall_type, damage, is_attacker):
        """Add damage to a wall. Positive for attacker, negative for defender."""
        damage_value = damage if is_attacker else -damage

        if wall_type == WallType.INFANTRY:
            self.infantry_damage_diff += damage_value
        elif wall_type == WallType.ARMOURED:
            self.armoured_damage_diff += damage_value
        elif wall_type == WallType.AVIATION:
            self.aviation_damage_diff += damage_value

    def calculate_wall_winners(self):
        """Calculate winners for each wall based on damage difference."""
        # Infantry wall
        if self.infantry_damage_diff > 0:
            self.infantry_winner_is_attacker = True
        elif self.infantry_damage_diff < 0:
            self.infantry_winner_is_attacker = False
        else:
            self.infantry_winner_is_attacker = False  # Tie goes to defender

        # Armoured wall
        if self.armoured_damage_diff > 0:
            self.armoured_winner_is_attacker = True
        elif self.armoured_damage_diff < 0:
            self.armoured_winner_is_attacker = False
        else:
            self.armoured_winner_is_attacker = False  # Tie goes to defender

        # Aviation wall
        if self.aviation_damage_diff > 0:
            self.aviation_winner_is_attacker = True
        elif self.aviation_damage_diff < 0:
            self.aviation_winner_is_attacker = False
        else:
            self.aviation_winner_is_attacker = False  # Tie goes to defender

    def calculate_round_winner(self):
        """Calculate the round winner based on wall winners."""
        self.calculate_wall_winners()

        attacker_walls = 0
        if self.infantry_winner_is_attacker:
            attacker_walls += 1
        if self.armoured_winner_is_attacker:
            attacker_walls += 1
        if self.aviation_winner_is_attacker:
            attacker_walls += 1

        # Need 2/3 walls to win
        self.winner_is_attacker = attacker_walls >= 2


class BattleParticipation(db.Model):
    """
    Tracks a player's participation in a battle.

    Players choose which wall to fight at for each round.
    """
    __tablename__ = 'battle_participations'

    id = db.Column(db.Integer, primary_key=True)

    # The battle and round
    battle_id = db.Column(db.Integer, db.ForeignKey('battles.id'), nullable=False, index=True)
    round_number = db.Column(db.Integer, nullable=False)

    # The player
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Which side they're fighting for (based on location at time of joining)
    is_attacker = db.Column(db.Boolean, nullable=False)

    # Which wall they chose for this round
    wall_type = db.Column(db.Enum(WallType), nullable=False)

    # Total damage dealt this round
    total_damage = db.Column(db.Integer, default=0, nullable=False)

    # Fight count and cooldown
    fight_count = db.Column(db.Integer, default=0, nullable=False)
    last_fight_at = db.Column(db.DateTime, nullable=True)

    # Metadata
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    battle = db.relationship('Battle', back_populates='participations')
    user = db.relationship('User', backref=db.backref('battle_participations', lazy='dynamic'))

    __table_args__ = (
        # One participation per user per battle per round
        db.UniqueConstraint('battle_id', 'round_number', 'user_id', name='unique_battle_round_user'),
    )

    def __repr__(self):
        return f'<BattleParticipation User:{self.user_id} Battle:{self.battle_id} Round:{self.round_number}>'

    @property
    def can_fight(self):
        """Check if player can fight (1.5 second cooldown)."""
        if self.last_fight_at is None:
            return True
        cooldown = timedelta(seconds=1.5)
        return datetime.utcnow() >= self.last_fight_at + cooldown

    @property
    def cooldown_remaining(self):
        """Get remaining cooldown in seconds."""
        if self.last_fight_at is None:
            return 0
        cooldown = timedelta(seconds=1.5)
        remaining = (self.last_fight_at + cooldown) - datetime.utcnow()
        return max(0, remaining.total_seconds())


class BattleDamage(db.Model):
    """
    Individual damage record for tracking and leaderboards.

    Used to determine Battle Hero awards at end of battle.
    """
    __tablename__ = 'battle_damages'

    id = db.Column(db.Integer, primary_key=True)

    # The battle and round
    battle_id = db.Column(db.Integer, db.ForeignKey('battles.id'), nullable=False, index=True)
    round_number = db.Column(db.Integer, nullable=False)

    # The player
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Which side they're fighting for
    is_attacker = db.Column(db.Boolean, nullable=False, index=True)

    # Which wall they fought at
    wall_type = db.Column(db.Enum(WallType), nullable=False, index=True)

    # Damage dealt this hit
    damage = db.Column(db.Integer, nullable=False)

    # Weapon used (null if barehanded)
    weapon_resource_id = db.Column(db.Integer, db.ForeignKey('resource.id'), nullable=True)
    weapon_quality = db.Column(db.Integer, nullable=True)  # Q1-Q5

    # Player stats at time of damage (for auditing)
    player_level = db.Column(db.Integer, nullable=False)
    player_skill = db.Column(db.Float, nullable=False)
    military_rank_id = db.Column(db.Integer, nullable=False)
    rank_damage_bonus = db.Column(db.Integer, nullable=False)  # Percentage
    nft_damage_bonus = db.Column(db.Integer, default=0, nullable=False)  # Percentage

    # Timestamp
    dealt_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    battle = db.relationship('Battle', back_populates='damage_records')
    user = db.relationship('User', backref=db.backref('battle_damage_records', lazy='dynamic'))
    weapon_resource = db.relationship('Resource')

    __table_args__ = (
        db.Index('idx_battle_wall_side', 'battle_id', 'wall_type', 'is_attacker'),
        db.Index('idx_battle_user', 'battle_id', 'user_id'),
    )

    def __repr__(self):
        return f'<BattleDamage User:{self.user_id} Battle:{self.battle_id} Damage:{self.damage}>'


class BattleHero(db.Model):
    """
    Battle Hero awards for top damage dealers.

    6 awards per battle: 3 walls x 2 sides.
    Each award grants 5 Gold to the player.
    """
    __tablename__ = 'battle_heroes'

    id = db.Column(db.Integer, primary_key=True)

    # The battle
    battle_id = db.Column(db.Integer, db.ForeignKey('battles.id'), nullable=False, index=True)

    # The player who won
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Which wall and side they won for
    wall_type = db.Column(db.Enum(WallType), nullable=False)
    is_attacker = db.Column(db.Boolean, nullable=False)

    # Total damage they dealt on this wall across all rounds
    total_damage = db.Column(db.Integer, nullable=False)

    # Gold reward (always 5)
    gold_reward = db.Column(db.Integer, default=5, nullable=False)

    # Timestamp
    awarded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    battle = db.relationship('Battle', backref=db.backref('heroes', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('battle_hero_awards', lazy='dynamic'))

    __table_args__ = (
        # One hero per wall per side per battle
        db.UniqueConstraint('battle_id', 'wall_type', 'is_attacker', name='unique_battle_wall_side_hero'),
    )

    def __repr__(self):
        side = "Attacker" if self.is_attacker else "Defender"
        return f'<BattleHero User:{self.user_id} Battle:{self.battle_id} {self.wall_type.value} {side}>'
