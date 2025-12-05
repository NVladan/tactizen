# app/models/party.py

import enum
from datetime import datetime, timezone
from slugify import slugify
from sqlalchemy import CheckConstraint

from . import db
from app.mixins import SoftDeleteMixin

# --- Election Status Enum ---
class ElectionStatus(enum.Enum):
    SCHEDULED = 'scheduled'  # Election is scheduled but not started
    ACTIVE = 'active'        # Election is currently running
    COMPLETED = 'completed'  # Election has finished
    CANCELLED = 'cancelled'  # Election was cancelled (e.g., party disbanded)


# --- Political Party Model ---
class PoliticalParty(SoftDeleteMixin, db.Model):
    """Represents a political party in a specific country."""
    __tablename__ = 'political_party'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    slug = db.Column(db.String(60), nullable=False, index=True)
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)
    description = db.Column(db.Text(500), nullable=True)
    logo_path = db.Column(db.String(200), nullable=True)  # Path to uploaded logo
    president_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    founded_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    country = db.relationship('Country', backref=db.backref('political_parties', lazy='dynamic'))
    president = db.relationship('User', foreign_keys=[president_id], backref=db.backref('led_party', uselist=False))
    members = db.relationship('PartyMembership', back_populates='party', lazy='dynamic', cascade='all, delete-orphan')
    elections = db.relationship('PartyElection', back_populates='party', lazy='dynamic', cascade='all, delete-orphan')

    # Constraints
    # Note: Unique constraint for (country_id, slug) where is_deleted=0 is handled via a partial unique index in migrations
    __table_args__ = (
        CheckConstraint('char_length(name) >= 3', name='party_name_length'),
        CheckConstraint('char_length(description) <= 500', name='party_description_length'),
    )

    def __init__(self, name, country_id, president_id, description=None):
        """Initialize a new political party."""
        self.name = name
        self.slug = slugify(name)
        self.country_id = country_id
        self.president_id = president_id
        self.description = description

    @property
    def member_count(self):
        """Get the total number of party members."""
        return self.members.count()

    @property
    def active_election(self):
        """Get the currently active election for this party, if any."""
        return db.session.scalar(
            db.select(PartyElection)
            .where(PartyElection.party_id == self.id)
            .where(PartyElection.status == ElectionStatus.ACTIVE)
        )

    @property
    def current_election(self):
        """Get the current election (SCHEDULED or ACTIVE) for this party, if any."""
        return db.session.scalar(
            db.select(PartyElection)
            .where(PartyElection.party_id == self.id)
            .where(PartyElection.status.in_([ElectionStatus.SCHEDULED, ElectionStatus.ACTIVE]))
            .order_by(PartyElection.start_time.desc())
        )

    def has_active_election(self):
        """Check if party has an active election."""
        return self.active_election is not None

    @property
    def total_experience(self):
        """Get the total experience of all party members."""
        from app.models.user import User
        result = db.session.scalar(
            db.select(db.func.sum(User.experience))
            .join(PartyMembership)
            .where(PartyMembership.party_id == self.id)
        )
        return result or 0

    @property
    def average_level(self):
        """Get the average level of all party members."""
        from app.models.user import User
        members = db.session.scalars(
            db.select(User)
            .join(PartyMembership)
            .where(PartyMembership.party_id == self.id)
        ).all()

        if not members:
            return 0

        total_level = sum(member.level for member in members)
        return total_level / len(members)

    @property
    def congress_seats(self):
        """Get the number of congress seats held by this party."""
        from app.models.government import CongressMember
        # Count current congress members from this party
        count = db.session.scalar(
            db.select(db.func.count(CongressMember.id))
            .join(PartyMembership, CongressMember.user_id == PartyMembership.user_id)
            .where(PartyMembership.party_id == self.id)
        )
        return count or 0

    def get_next_president(self):
        """
        Get the member who should become politics if current politics leaves.
        Returns the member with highest level, then exp, then lowest ID.
        Returns None if no other members exist.
        """
        from app.models.user import User

        # Get all members except current politics
        # Sort by experience (level is computed from it), then by ID
        members = db.session.scalars(
            db.select(User)
            .join(PartyMembership)
            .where(PartyMembership.party_id == self.id)
            .where(User.id != self.president_id)
            .order_by(User.experience.desc(), User.id.asc())
        ).all()

        return members[0] if members else None

    def __repr__(self):
        return f'<PoliticalParty {self.name} ({self.country.name if self.country else "N/A"})>'


# --- Party Membership Model ---
class PartyMembership(db.Model):
    """Represents a user's membership in a political party."""
    __tablename__ = 'party_membership'

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    party_id = db.Column(db.Integer, db.ForeignKey('political_party.id'), primary_key=True)
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    user = db.relationship('User', back_populates='party_membership')
    party = db.relationship('PoliticalParty', back_populates='members')

    def __repr__(self):
        return f'<PartyMembership User:{self.user_id} Party:{self.party_id}>'


# --- Party Election Model ---
class PartyElection(db.Model):
    """Represents a scheduled or active party election."""
    __tablename__ = 'party_election'

    id = db.Column(db.Integer, primary_key=True)
    party_id = db.Column(db.Integer, db.ForeignKey('political_party.id'), nullable=False, index=True)
    start_time = db.Column(db.DateTime, nullable=False, index=True)  # 15th at 9AM CET (stored as UTC)
    end_time = db.Column(db.DateTime, nullable=False, index=True)    # 16th at 9AM CET (stored as UTC)
    status = db.Column(db.Enum(ElectionStatus), default=ElectionStatus.SCHEDULED, nullable=False, index=True)
    winner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Set after election completes

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    party = db.relationship('PoliticalParty', back_populates='elections')
    candidates = db.relationship('PartyCandidate', back_populates='election', lazy='dynamic', cascade='all, delete-orphan')
    votes = db.relationship('PartyVote', back_populates='election', lazy='dynamic', cascade='all, delete-orphan')
    winner = db.relationship('User', foreign_keys=[winner_id])

    def is_active(self):
        """Check if this election is currently active."""
        return self.status == ElectionStatus.ACTIVE

    def can_announce_candidacy(self):
        """Check if candidacy announcements are still allowed (before election starts)."""
        return self.status == ElectionStatus.SCHEDULED

    def get_candidate_count(self):
        """Get the number of candidates in this election."""
        return self.candidates.count()

    def get_vote_count(self):
        """Get the total number of votes cast."""
        return self.votes.count()

    def calculate_winner(self):
        """
        Calculate the election winner based on votes.
        Tiebreaker: highest level -> highest exp -> lowest user ID
        Returns the winning user or None if no votes.
        """
        from app.models.user import User

        # Get all candidates with their vote counts
        candidates_votes = db.session.execute(
            db.select(
                PartyCandidate.user_id,
                db.func.count(PartyVote.voter_id).label('vote_count')
            )
            .outerjoin(PartyVote,
                (PartyVote.election_id == PartyCandidate.election_id) &
                (PartyVote.candidate_id == PartyCandidate.user_id)
            )
            .where(PartyCandidate.election_id == self.id)
            .group_by(PartyCandidate.user_id)
        ).all()

        if not candidates_votes:
            return None

        # Find maximum vote count
        max_votes = max(cv.vote_count for cv in candidates_votes)

        # Get all candidates with max votes (for tiebreaker)
        tied_candidate_ids = [cv.user_id for cv in candidates_votes if cv.vote_count == max_votes]

        # If only one winner, return them
        if len(tied_candidate_ids) == 1:
            return db.session.get(User, tied_candidate_ids[0])

        # Tiebreaker: experience DESC (level is computed from it), id ASC
        winner = db.session.scalar(
            db.select(User)
            .where(User.id.in_(tied_candidate_ids))
            .order_by(User.experience.desc(), User.id.asc())
        )

        return winner

    def __repr__(self):
        return f'<PartyElection {self.id} Party:{self.party_id} Status:{self.status.value}>'


# --- Party Candidate Model ---
class PartyCandidate(db.Model):
    """Represents a candidate running in a party election."""
    __tablename__ = 'party_candidate'

    election_id = db.Column(db.Integer, db.ForeignKey('party_election.id'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    announced_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    election = db.relationship('PartyElection', back_populates='candidates')
    user = db.relationship('User', backref=db.backref('party_candidacies', lazy='dynamic'))

    def get_vote_count(self):
        """Get the number of votes this candidate received."""
        return db.session.scalar(
            db.select(db.func.count(PartyVote.voter_id))
            .where(PartyVote.election_id == self.election_id)
            .where(PartyVote.candidate_id == self.user_id)
        ) or 0

    def __repr__(self):
        return f'<PartyCandidate Election:{self.election_id} User:{self.user_id}>'


# --- Party Vote Model ---
class PartyVote(db.Model):
    """Represents a vote cast in a party election."""
    __tablename__ = 'party_vote'

    election_id = db.Column(db.Integer, db.ForeignKey('party_election.id'), primary_key=True)
    voter_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    voted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Blockchain signature fields
    wallet_address = db.Column(db.String(42), nullable=True, index=True)  # Ethereum address
    vote_message = db.Column(db.String(500), nullable=True)  # Message that was signed
    vote_signature = db.Column(db.String(132), nullable=True)  # Hex signature (65 bytes = 130 hex + 0x)

    # Relationships
    election = db.relationship('PartyElection', back_populates='votes')
    voter = db.relationship('User', foreign_keys=[voter_id], backref=db.backref('party_votes_cast', lazy='dynamic'))
    candidate = db.relationship('User', foreign_keys=[candidate_id])

    def __repr__(self):
        return f'<PartyVote Election:{self.election_id} Voter:{self.voter_id} -> Candidate:{self.candidate_id}>'
