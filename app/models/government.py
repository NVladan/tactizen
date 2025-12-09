"""
Government Models

Models for country government: presidents, congress members, elections.
"""

from datetime import datetime, timedelta
from app.extensions import db
from enum import Enum


class ElectionType(Enum):
    """Types of government elections."""
    PRESIDENTIAL = "presidential"
    CONGRESSIONAL = "congressional"


class MinistryType(Enum):
    """Types of government ministries."""
    FOREIGN_AFFAIRS = "foreign_affairs"
    DEFENCE = "defence"
    FINANCE = "finance"


class LawType(Enum):
    """Types of laws that can be proposed."""
    DECLARE_WAR = "declare_war"
    MUTUAL_PROTECTION_PACT = "mutual_protection_pact"  # DEPRECATED - kept for historical laws
    NON_AGGRESSION_PACT = "non_aggression_pact"  # DEPRECATED - kept for historical laws
    MILITARY_BUDGET = "military_budget"
    PRINT_CURRENCY = "print_currency"
    IMPORT_TAX = "import_tax"
    SALARY_TAX = "salary_tax"
    INCOME_TAX = "income_tax"
    # Alliance law types
    ALLIANCE_INVITE = "alliance_invite"  # Inviting country votes to invite another country
    ALLIANCE_JOIN = "alliance_join"  # Invited country votes to join alliance
    ALLIANCE_KICK = "alliance_kick"  # Leader's country votes to kick a member
    ALLIANCE_LEAVE = "alliance_leave"  # Country votes to leave alliance
    ALLIANCE_DISSOLVE = "alliance_dissolve"  # Member votes on alliance dissolution
    # Impeachment
    IMPEACHMENT = "impeachment"  # Congress/President proposes to replace current president
    # Trade embargo
    EMBARGO = "embargo"  # Impose trade embargo on another country
    REMOVE_EMBARGO = "remove_embargo"  # Lift existing trade embargo


class LawStatus(Enum):
    """Status of a law proposal."""
    VOTING = "voting"  # Currently being voted on
    PASSED = "passed"  # Passed by congress (majority vote)
    REJECTED = "rejected"  # Rejected by congress (failed to get majority or tie)
    EXPIRED = "expired"  # Voting period expired without enough votes


class WarStatus(Enum):
    """Status of a war."""
    ACTIVE = "active"  # War is currently active
    PEACE_PROPOSED = "peace_proposed"  # Peace treaty proposed, awaiting votes
    ENDED_PEACE = "ended_peace"  # War ended by peace treaty
    ENDED_EXPIRED = "ended_expired"  # War ended after 30 days


class WarType(Enum):
    """Type of war."""
    NORMAL = "normal"  # Standard war declared by law
    RESISTANCE = "resistance"  # Resistance war to liberate a region


class GovernmentElectionStatus(Enum):
    """Status of a government election."""
    NOMINATIONS = "nominations"  # Presidential: Party presidents nominating
    APPLICATIONS = "applications"  # Congressional: Members applying
    VOTING = "voting"  # Voting period active
    COMPLETED = "completed"  # Election finished, results calculated
    CANCELLED = "cancelled"  # Election cancelled by admin


class CandidateStatus(Enum):
    """Status of a candidate."""
    PENDING = "pending"  # Waiting for party politics approval (congressional only)
    APPROVED = "approved"  # Approved to run
    REJECTED = "rejected"  # Rejected by party politics
    WITHDRAWN = "withdrawn"  # Candidate withdrew


class GovernmentElection(db.Model):
    """Government election (presidential or congressional)."""
    __tablename__ = 'government_elections'

    id = db.Column(db.Integer, primary_key=True)
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)
    election_type = db.Column(db.Enum(ElectionType), nullable=False, index=True)
    status = db.Column(db.Enum(GovernmentElectionStatus), nullable=False, default=GovernmentElectionStatus.NOMINATIONS, index=True)

    # Election dates (all times in UTC, but displayed in CET to users)
    # Presidential: nominations 1st-5th 9AM CET, voting 5th-6th 9AM CET
    # Congressional: applications 1st-25th 9AM CET, voting 25th-26th 9AM CET
    nominations_start = db.Column(db.DateTime, nullable=False)
    nominations_end = db.Column(db.DateTime, nullable=False)
    voting_start = db.Column(db.DateTime, nullable=False)
    voting_end = db.Column(db.DateTime, nullable=False)

    # Term dates (when winner takes office and term ends)
    term_start = db.Column(db.DateTime, nullable=False)
    term_end = db.Column(db.DateTime, nullable=False)

    # Results (calculated when status = COMPLETED)
    results_calculated_at = db.Column(db.DateTime)
    winner_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Presidential only
    total_votes_cast = db.Column(db.Integer, default=0)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    country = db.relationship('Country', backref=db.backref('elections', lazy='dynamic'))
    winner = db.relationship('User', foreign_keys=[winner_user_id])
    candidates = db.relationship('ElectionCandidate', back_populates='election', lazy='dynamic',
                                  cascade='all, delete-orphan')
    votes = db.relationship('ElectionVote', back_populates='election', lazy='dynamic',
                            cascade='all, delete-orphan')

    def __repr__(self):
        return f'<GovernmentElection {self.election_type.value} - {self.country.name} - {self.status.value}>'

    def is_nominations_open(self):
        """Check if nomination/application period is open."""
        now = datetime.utcnow()
        return (self.status in [GovernmentElectionStatus.NOMINATIONS, GovernmentElectionStatus.APPLICATIONS] and
                self.nominations_start <= now <= self.nominations_end)

    def is_voting_open(self):
        """Check if voting period is open."""
        now = datetime.utcnow()
        return self.status == GovernmentElectionStatus.VOTING and self.voting_start <= now <= self.voting_end

    def get_approved_candidates(self):
        """Get all approved candidates."""
        return self.candidates.filter_by(status=CandidateStatus.APPROVED).all()

    def get_vote_count(self, candidate_id):
        """Get vote count for a specific candidate."""
        return self.votes.filter_by(candidate_id=candidate_id).count()


class ElectionCandidate(db.Model):
    """Candidate running in an election."""
    __tablename__ = 'election_candidates'

    id = db.Column(db.Integer, primary_key=True)
    election_id = db.Column(db.Integer, db.ForeignKey('government_elections.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    party_id = db.Column(db.Integer, db.ForeignKey('political_party.id'), nullable=False, index=True)
    status = db.Column(db.Enum(CandidateStatus), nullable=False, default=CandidateStatus.PENDING, index=True)

    # Who nominated/approved this candidate
    # Presidential: nominated by party politics
    # Congressional: self-applied, approved by party politics
    nominated_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    # Results
    votes_received = db.Column(db.Integer, default=0, nullable=False)
    final_rank = db.Column(db.Integer, nullable=True)  # 1 = winner, 2 = second place, etc.
    won_seat = db.Column(db.Boolean, default=False)  # True if won (politics or congress seat)

    # Metadata
    applied_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    approved_at = db.Column(db.DateTime, nullable=True)
    rejected_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    election = db.relationship('GovernmentElection', back_populates='candidates')
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('election_candidacies', lazy='dynamic'))
    party = db.relationship('PoliticalParty', backref=db.backref('election_candidates', lazy='dynamic'))
    nominated_by = db.relationship('User', foreign_keys=[nominated_by_user_id])
    votes = db.relationship('ElectionVote', back_populates='candidate', lazy='dynamic', cascade='all, delete-orphan')

    __table_args__ = (
        # One candidacy per user per election
        db.UniqueConstraint('election_id', 'user_id', name='uq_election_user'),
    )

    def __repr__(self):
        return f'<ElectionCandidate {self.user.username} - {self.election.election_type.value}>'

    def approve(self, approved_by_user_id=None):
        """Approve this candidate."""
        self.status = CandidateStatus.APPROVED
        self.approved_at = datetime.utcnow()
        if approved_by_user_id:
            self.nominated_by_user_id = approved_by_user_id

    def reject(self):
        """Reject this candidate."""
        self.status = CandidateStatus.REJECTED
        self.rejected_at = datetime.utcnow()

    def withdraw(self):
        """Withdraw candidacy."""
        self.status = CandidateStatus.WITHDRAWN


class ElectionVote(db.Model):
    """Vote cast in an election."""
    __tablename__ = 'election_votes'

    id = db.Column(db.Integer, primary_key=True)
    election_id = db.Column(db.Integer, db.ForeignKey('government_elections.id'), nullable=False, index=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey('election_candidates.id'), nullable=False, index=True)
    voter_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Metadata
    voted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ip_address = db.Column(db.String(45))  # For audit trail

    # Blockchain signature fields
    wallet_address = db.Column(db.String(42), nullable=True, index=True)  # Ethereum address
    vote_message = db.Column(db.String(500), nullable=True)  # Message that was signed
    vote_signature = db.Column(db.String(132), nullable=True)  # Hex signature (65 bytes = 130 hex + 0x)

    # Relationships
    election = db.relationship('GovernmentElection', back_populates='votes')
    candidate = db.relationship('ElectionCandidate', back_populates='votes')
    voter = db.relationship('User', backref=db.backref('election_votes', lazy='dynamic'))

    __table_args__ = (
        # One vote per user per election
        db.UniqueConstraint('election_id', 'voter_user_id', name='uq_election_voter'),
    )

    def __repr__(self):
        return f'<ElectionVote {self.voter.username} -> {self.candidate.user.username}>'


class CountryPresident(db.Model):
    """Current and historical country presidents."""
    __tablename__ = 'country_presidents'

    id = db.Column(db.Integer, primary_key=True)
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    election_id = db.Column(db.Integer, db.ForeignKey('government_elections.id'), nullable=True)  # Nullable for impeachment

    # Term
    term_start = db.Column(db.DateTime, nullable=False)
    term_end = db.Column(db.DateTime, nullable=False)
    is_current = db.Column(db.Boolean, default=True, nullable=False, index=True)

    # How they became politics
    # "elected" = won election
    # "succession" = became politics after elected politics left (was 2nd place)
    became_president_via = db.Column(db.String(20), default='elected', nullable=False)

    # If they left office early
    left_office_early = db.Column(db.Boolean, default=False)
    left_office_at = db.Column(db.DateTime, nullable=True)
    left_office_reason = db.Column(db.String(100), nullable=True)  # "banned", "deleted", "resigned"

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    country = db.relationship('Country', backref=db.backref('presidents', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('presidencies', lazy='dynamic'))
    election = db.relationship('GovernmentElection')

    __table_args__ = (
        # Only one current politics per country
        db.Index('idx_country_current_president', 'country_id', 'is_current'),
    )

    def __repr__(self):
        return f'<CountryPresident {self.user.username} of {self.country.name}>'


class CongressMember(db.Model):
    """Current and historical congress members."""
    __tablename__ = 'congress_members'

    id = db.Column(db.Integer, primary_key=True)
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    election_id = db.Column(db.Integer, db.ForeignKey('government_elections.id'), nullable=False)
    party_id = db.Column(db.Integer, db.ForeignKey('political_party.id'), nullable=False)

    # Term
    term_start = db.Column(db.DateTime, nullable=False)
    term_end = db.Column(db.DateTime, nullable=False)
    is_current = db.Column(db.Boolean, default=True, nullable=False, index=True)

    # Election results
    votes_received = db.Column(db.Integer, nullable=False)
    final_rank = db.Column(db.Integer, nullable=False)  # Rank when elected (1-20 won seats)

    # If they left seat early
    left_seat_early = db.Column(db.Boolean, default=False)
    left_seat_at = db.Column(db.DateTime, nullable=True)
    left_seat_reason = db.Column(db.String(100), nullable=True)  # "banned", "deleted", "resigned"

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    country = db.relationship('Country', backref=db.backref('congress_members_history', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('congress_memberships', lazy='dynamic'))
    election = db.relationship('GovernmentElection')
    party = db.relationship('PoliticalParty')

    __table_args__ = (
        db.Index('idx_country_current_congress', 'country_id', 'is_current'),
    )

    def __repr__(self):
        return f'<CongressMember {self.user.username} of {self.country.name}>'


class Minister(db.Model):
    """Government ministers appointed by the politics."""
    __tablename__ = 'ministers'

    id = db.Column(db.Integer, primary_key=True)
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    ministry_type = db.Column(db.Enum(MinistryType), nullable=False, index=True)
    appointed_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)

    # Dates
    appointed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    resigned_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    country = db.relationship('Country', backref=db.backref('ministers', lazy='dynamic'))
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('minister_positions', lazy='dynamic'))
    appointed_by = db.relationship('User', foreign_keys=[appointed_by_user_id])

    __table_args__ = (
        # Only one active minister per ministry per country
        db.Index('idx_country_ministry_active', 'country_id', 'ministry_type', 'is_active'),
    )

    def __repr__(self):
        return f'<Minister {self.user.username} - {self.ministry_type.value} of {self.country.name}>'

    def resign(self):
        """Resign from minister position."""
        self.is_active = False
        self.resigned_at = datetime.utcnow()


class Law(db.Model):
    """Law proposals submitted by politics or ministers for congress voting."""
    __tablename__ = 'laws'

    id = db.Column(db.Integer, primary_key=True)
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)
    law_type = db.Column(db.Enum(LawType), nullable=False, index=True)
    status = db.Column(db.Enum(LawStatus), nullable=False, default=LawStatus.VOTING, index=True)

    # Who proposed the law
    proposed_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    proposed_by_role = db.Column(db.String(50), nullable=False)  # "politics", "minister_foreign_affairs", "minister_finance"

    # Law details (stored as JSON for flexibility)
    # Examples:
    # - declare_war: {"target_country_id": 5}
    # - mutual_protection_pact: {"ally_country_id": 3}
    # - military_budget: {"amount": 10000}
    # - print_currency: {"gold_amount": 1000, "currency_amount": 200000}
    # - import_tax: {"rate": 0.05}
    # - salary_tax: {"rate": 0.10}
    # - income_tax: {"rate": 0.15}
    law_details = db.Column(db.JSON, nullable=False)

    # Voting
    voting_start = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    voting_end = db.Column(db.DateTime, nullable=False)  # 48 hours from creation
    votes_for = db.Column(db.Integer, default=0, nullable=False)
    votes_against = db.Column(db.Integer, default=0, nullable=False)
    total_votes = db.Column(db.Integer, default=0, nullable=False)

    # Results (calculated when voting ends)
    result_calculated_at = db.Column(db.DateTime, nullable=True)
    passed = db.Column(db.Boolean, nullable=True)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    country = db.relationship('Country', backref=db.backref('laws', lazy='dynamic'))
    proposed_by = db.relationship('User', backref=db.backref('proposed_laws', lazy='dynamic'))
    votes = db.relationship('LawVote', back_populates='law', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Law {self.law_type.value} - {self.country.name} - {self.status.value}>'

    def is_voting_open(self):
        """Check if voting is still open."""
        now = datetime.utcnow()
        return self.status == LawStatus.VOTING and self.voting_start <= now <= self.voting_end

    def calculate_result(self):
        """Calculate the result of the vote and handle gold/cooldown."""
        from decimal import Decimal
        from datetime import timedelta

        # Majority wins, tie means rejected
        if self.votes_for > self.votes_against:
            self.status = LawStatus.PASSED
            self.passed = True
        else:
            self.status = LawStatus.REJECTED
            self.passed = False

        self.result_calculated_at = datetime.utcnow()

        # Handle reserved gold - return or consume based on result
        reserved_gold = self.law_details.get('reserved_gold', 0) if self.law_details else 0
        if reserved_gold > 0:
            reserved_amount = Decimal(str(reserved_gold))

            if self.passed:
                # Law passed - consume the gold (deduct from treasury, release from reserved)
                self.country.treasury_gold -= reserved_amount
                self.country.reserved_gold -= reserved_amount
            else:
                # Law rejected - just release the reserved gold back to available
                self.country.reserved_gold -= reserved_amount

        # Handle reserved currency - return or consume based on result
        reserved_currency = self.law_details.get('reserved_currency', 0) if self.law_details else 0
        if reserved_currency > 0:
            reserved_amount = Decimal(str(reserved_currency))

            if self.passed:
                # Law passed - consume the currency (deduct from treasury, release from reserved)
                self.country.treasury_currency -= reserved_amount
                self.country.reserved_currency -= reserved_amount
            else:
                # Law rejected - just release the reserved currency back to available
                self.country.reserved_currency -= reserved_amount

        # Handle impeachment - replace president if passed
        if self.passed and self.law_type == LawType.IMPEACHMENT:
            self._handle_impeachment()

        # Handle congress member cooldown on rejection
        if not self.passed:
            # Check if proposer was a congress member (not president)
            if self.proposed_by_role != 'president' and self.proposed_by:
                # Check if proposer is a congress member
                proposer = self.proposed_by
                if proposer.is_congress_member_of(self.country_id):
                    # Set 48-hour cooldown
                    proposer.law_proposal_cooldown_until = datetime.utcnow() + timedelta(hours=48)

    def _handle_impeachment(self):
        """Handle impeachment - remove current president and install replacement."""
        from app.models import User
        from datetime import timedelta

        replacement_user_id = self.law_details.get('replacement_user_id') if self.law_details else None
        if not replacement_user_id:
            return

        replacement_user = db.session.get(User, replacement_user_id)
        if not replacement_user or replacement_user.citizenship_id != self.country_id:
            return

        # Find and end current president's term
        current_president = db.session.scalar(
            db.select(CountryPresident)
            .where(CountryPresident.country_id == self.country_id)
            .where(CountryPresident.is_current == True)
        )

        # Store original term_end and election_id before modifying
        original_term_end = None
        election_id = None

        if current_president:
            original_term_end = current_president.term_end
            election_id = current_president.election_id
            current_president.is_current = False
            current_president.left_office_early = True
            current_president.left_office_at = datetime.utcnow()
            current_president.left_office_reason = 'impeached'

        # New president inherits the remaining term from the impeached president
        # Or serves until the next scheduled election if there was no president
        if original_term_end:
            term_end = original_term_end
        else:
            # Calculate term end as the next 6th of the month at 9AM CET
            from pytz import timezone as pytz_timezone
            from dateutil.relativedelta import relativedelta

            now = datetime.utcnow()
            cet = pytz_timezone('CET')

            # Start with current month's 6th
            current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            term_end_cet = cet.localize(
                current_month.replace(day=6, hour=9, minute=0, second=0, microsecond=0, tzinfo=None)
            )
            term_end = term_end_cet.astimezone(pytz_timezone('UTC')).replace(tzinfo=None)

            # If we're past the 6th of this month, use next month's 6th
            if now >= term_end:
                next_month = current_month + relativedelta(months=1)
                term_end_cet = cet.localize(
                    next_month.replace(day=6, hour=9, minute=0, second=0, microsecond=0, tzinfo=None)
                )
                term_end = term_end_cet.astimezone(pytz_timezone('UTC')).replace(tzinfo=None)

        # Determine how they became president
        became_via = 'impeachment' if current_president else 'congressional_appointment'

        # Create new president record for replacement
        new_president = CountryPresident(
            country_id=self.country_id,
            user_id=replacement_user.id,
            election_id=election_id,  # Link to same election (or None if no president existed)
            term_start=datetime.utcnow(),
            term_end=term_end,
            is_current=True,
            became_president_via=became_via
        )
        db.session.add(new_president)


class LawVote(db.Model):
    """Vote on a law proposal by politics or congress member."""
    __tablename__ = 'law_votes'

    id = db.Column(db.Integer, primary_key=True)
    law_id = db.Column(db.Integer, db.ForeignKey('laws.id'), nullable=False, index=True)
    voter_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    vote = db.Column(db.Boolean, nullable=False)  # True = For, False = Against

    # Voter role at time of voting
    voter_role = db.Column(db.String(50), nullable=False)  # "politics" or "congress_member"

    # Metadata
    voted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ip_address = db.Column(db.String(45))  # For audit trail

    # Relationships
    law = db.relationship('Law', back_populates='votes')
    voter = db.relationship('User', backref=db.backref('law_votes', lazy='dynamic'))

    __table_args__ = (
        # One vote per user per law
        db.UniqueConstraint('law_id', 'voter_user_id', name='uq_law_voter'),
    )

    def __repr__(self):
        return f'<LawVote {self.voter.username} -> {"For" if self.vote else "Against"}>'


class War(db.Model):
    """Active and historical wars between countries."""
    __tablename__ = 'wars'

    id = db.Column(db.Integer, primary_key=True)
    attacker_country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)
    defender_country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)
    status = db.Column(db.Enum(WarStatus), nullable=False, default=WarStatus.ACTIVE, index=True)

    # War type (normal or resistance)
    war_type = db.Column(db.Enum(WarType), nullable=False, default=WarType.NORMAL, index=True)

    # War was declared by this law (nullable for resistance wars)
    declared_by_law_id = db.Column(db.Integer, db.ForeignKey('laws.id'), nullable=True)

    # Resistance war specific fields
    is_resistance_war = db.Column(db.Boolean, default=False, nullable=False, index=True)
    resistance_region_id = db.Column(db.Integer, db.ForeignKey('region.id'), nullable=True, index=True)
    resistance_started_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    # The original country that the resistance is fighting for (the conquered country)
    resistance_country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=True, index=True)

    # War timeline
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    scheduled_end_at = db.Column(db.DateTime, nullable=False)  # 30 days from start
    ended_at = db.Column(db.DateTime, nullable=True)

    # Peace treaty (if proposed)
    peace_proposed_at = db.Column(db.DateTime, nullable=True)
    peace_proposed_by_country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=True)

    # Peace votes from both countries
    attacker_peace_votes_for = db.Column(db.Integer, default=0)
    attacker_peace_votes_against = db.Column(db.Integer, default=0)
    defender_peace_votes_for = db.Column(db.Integer, default=0)
    defender_peace_votes_against = db.Column(db.Integer, default=0)

    # Battle initiative tracking
    # After war declaration passes, attacker has 24h initiative to start first battle
    # If they win a battle, they keep initiative for another 24h
    # If they lose or initiative expires, defender gets 24h initiative
    initiative_holder_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=True)
    initiative_expires_at = db.Column(db.DateTime, nullable=True)
    # Track if initiative has been lost (both sides can attack)
    initiative_lost = db.Column(db.Boolean, default=False, nullable=False)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    attacker_country = db.relationship('Country', foreign_keys=[attacker_country_id], backref=db.backref('wars_as_attacker', lazy='dynamic'))
    defender_country = db.relationship('Country', foreign_keys=[defender_country_id], backref=db.backref('wars_as_defender', lazy='dynamic'))
    peace_proposed_by = db.relationship('Country', foreign_keys=[peace_proposed_by_country_id])
    initiative_holder = db.relationship('Country', foreign_keys=[initiative_holder_id])
    declared_by_law = db.relationship('Law', backref='war')
    peace_votes = db.relationship('PeaceVote', back_populates='war', lazy='dynamic', cascade='all, delete-orphan')
    resistance_region = db.relationship('Region', foreign_keys=[resistance_region_id])
    resistance_started_by = db.relationship('User', foreign_keys=[resistance_started_by_user_id])
    resistance_country = db.relationship('Country', foreign_keys=[resistance_country_id])

    def __repr__(self):
        return f'<War {self.attacker_country.name if self.attacker_country_id else "?"} vs {self.defender_country.name if self.defender_country_id else "?"} - {self.status.value}>'

    def is_active(self):
        """Check if war is currently active."""
        return self.status == WarStatus.ACTIVE

    def is_peace_voting_open(self):
        """Check if peace treaty voting is open."""
        return self.status == WarStatus.PEACE_PROPOSED

    def get_opponent_country_id(self, country_id):
        """Get the opponent country ID for a given country."""
        if country_id == self.attacker_country_id:
            return self.defender_country_id
        elif country_id == self.defender_country_id:
            return self.attacker_country_id
        return None

    def check_peace_approval(self):
        """Check if both countries approved peace (majority in both)."""
        # Both countries need majority FOR votes
        attacker_approved = self.attacker_peace_votes_for > self.attacker_peace_votes_against
        defender_approved = self.defender_peace_votes_for > self.defender_peace_votes_against

        return attacker_approved and defender_approved

    def end_war_with_peace(self):
        """End the war with a peace treaty."""
        self.status = WarStatus.ENDED_PEACE
        self.ended_at = datetime.utcnow()

    def set_initiative(self, country_id):
        """Set initiative to a specific country for 24 hours."""
        self.initiative_holder_id = country_id
        self.initiative_expires_at = datetime.utcnow() + timedelta(hours=24)
        self.initiative_lost = False

    def lose_initiative(self):
        """Mark initiative as lost (both sides can now attack)."""
        self.initiative_lost = True
        self.initiative_holder_id = None
        self.initiative_expires_at = None

    def check_initiative_expired(self):
        """Check if initiative has expired and update accordingly."""
        if self.initiative_expires_at and datetime.utcnow() >= self.initiative_expires_at:
            self.lose_initiative()
            return True
        return False

    def can_country_attack(self, country_id):
        """Check if a country can start a new battle."""
        # Country must be part of this war
        if country_id not in [self.attacker_country_id, self.defender_country_id]:
            return False

        # War must be active
        if not self.is_active():
            return False

        # Check for existing active battle
        from app.models.battle import Battle, BattleStatus
        active_battle = Battle.query.filter_by(
            war_id=self.id,
            status=BattleStatus.ACTIVE
        ).first()
        if active_battle:
            return False

        # Check initiative
        self.check_initiative_expired()

        # If initiative is lost, anyone can attack
        if self.initiative_lost:
            return True

        # If there's an active initiative, only the holder can attack
        if self.initiative_holder_id:
            return country_id == self.initiative_holder_id

        # No initiative set (shouldn't happen normally)
        return True

    def get_active_battle(self):
        """Get the currently active battle for this war, if any."""
        from app.models.battle import Battle, BattleStatus
        return Battle.query.filter_by(
            war_id=self.id,
            status=BattleStatus.ACTIVE
        ).first()

    def has_active_battle(self):
        """Check if there's an active battle in this war."""
        return self.get_active_battle() is not None


class PeaceVote(db.Model):
    """Vote on a peace treaty proposal."""
    __tablename__ = 'peace_votes'

    id = db.Column(db.Integer, primary_key=True)
    war_id = db.Column(db.Integer, db.ForeignKey('wars.id'), nullable=False, index=True)
    voter_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)  # Which country's congress
    vote = db.Column(db.Boolean, nullable=False)  # True = For peace, False = Against peace

    # Voter role at time of voting
    voter_role = db.Column(db.String(50), nullable=False)  # "politics" or "congress_member"

    # Metadata
    voted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ip_address = db.Column(db.String(45))  # For audit trail

    # Relationships
    war = db.relationship('War', back_populates='peace_votes')
    voter = db.relationship('User', backref=db.backref('peace_votes', lazy='dynamic'))
    country = db.relationship('Country', backref=db.backref('peace_votes', lazy='dynamic'))

    __table_args__ = (
        # One vote per user per war
        db.UniqueConstraint('war_id', 'voter_user_id', name='uq_war_voter'),
    )

    def __repr__(self):
        return f'<PeaceVote {self.voter.username} -> {"For" if self.vote else "Against"}>'


class Embargo(db.Model):
    """Trade embargo between countries. Embargoes are two-way (mutual) - when imposed,
    trade is blocked in both directions between the two countries."""
    __tablename__ = 'embargoes'

    id = db.Column(db.Integer, primary_key=True)
    imposing_country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)
    target_country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)
    imposed_by_law_id = db.Column(db.Integer, db.ForeignKey('laws.id'), nullable=False)
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)  # NULL = active
    ended_by_law_id = db.Column(db.Integer, db.ForeignKey('laws.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True, index=True)

    # Relationships
    imposing_country = db.relationship('Country', foreign_keys=[imposing_country_id], backref='imposed_embargoes')
    target_country = db.relationship('Country', foreign_keys=[target_country_id], backref='received_embargoes')
    imposed_by_law = db.relationship('Law', foreign_keys=[imposed_by_law_id])
    ended_by_law = db.relationship('Law', foreign_keys=[ended_by_law_id])

    __table_args__ = (
        # Prevent duplicate active embargoes between same countries
        db.Index('ix_embargo_active_countries', 'imposing_country_id', 'target_country_id', 'is_active'),
    )

    @staticmethod
    def has_embargo(country_a_id, country_b_id):
        """Check if there is an active embargo between two countries (in either direction).
        Since embargoes are two-way, we check both directions."""
        return Embargo.query.filter(
            Embargo.is_active == True,
            db.or_(
                db.and_(Embargo.imposing_country_id == country_a_id, Embargo.target_country_id == country_b_id),
                db.and_(Embargo.imposing_country_id == country_b_id, Embargo.target_country_id == country_a_id)
            )
        ).first() is not None

    @staticmethod
    def get_active_embargo(imposing_country_id, target_country_id):
        """Get active embargo from imposing country to target country."""
        return Embargo.query.filter_by(
            imposing_country_id=imposing_country_id,
            target_country_id=target_country_id,
            is_active=True
        ).first()

    def __repr__(self):
        status = "active" if self.is_active else "ended"
        return f'<Embargo {self.imposing_country_id} -> {self.target_country_id} ({status})>'
