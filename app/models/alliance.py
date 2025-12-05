"""
Alliance Models

Models for military alliances between countries.
"""

from datetime import datetime, timedelta
from app.extensions import db
from enum import Enum


class AllianceInvitationStatus(Enum):
    """Status of an alliance invitation."""
    PENDING_VOTES = "pending_votes"  # Both congresses are voting
    ACCEPTED = "accepted"  # Both congresses accepted
    REJECTED = "rejected"  # At least one congress rejected
    EXPIRED = "expired"  # Voting period ended without resolution


class AllianceKickStatus(Enum):
    """Status of an alliance kick proposal."""
    PENDING_VOTE = "pending_vote"  # Congress is voting
    APPROVED = "approved"  # Congress approved the kick
    REJECTED = "rejected"  # Congress rejected the kick


class Alliance(db.Model):
    """
    Military alliance between countries.

    - Max 5 members
    - Founded by a President
    - Leader can rename, transfer leadership, propose dissolution
    - Members can fight alongside each other in wars (like old MPA)
    """
    __tablename__ = 'alliances'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

    # Leader country (founder initially, can be transferred)
    leader_country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)

    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    dissolved_at = db.Column(db.DateTime, nullable=True)
    dissolved_reason = db.Column(db.String(100), nullable=True)  # "leader_dissolved", "all_members_left", "dissolution_vote"

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    leader_country = db.relationship('Country', foreign_keys=[leader_country_id], backref=db.backref('led_alliance', uselist=False))
    members = db.relationship('AllianceMembership', back_populates='alliance', lazy='dynamic', cascade='all, delete-orphan')
    invitations = db.relationship('AllianceInvitation', back_populates='alliance', lazy='dynamic', cascade='all, delete-orphan')
    kicks = db.relationship('AllianceKick', back_populates='alliance', lazy='dynamic', cascade='all, delete-orphan')

    # Constants
    MAX_MEMBERS = 5

    def __repr__(self):
        return f'<Alliance {self.name}>'

    @property
    def member_count(self):
        """Get current number of members."""
        return self.members.filter_by(is_active=True).count()

    @property
    def is_full(self):
        """Check if alliance has reached max members."""
        return self.member_count >= self.MAX_MEMBERS

    def get_active_members(self):
        """Get all active member countries."""
        return [m.country for m in self.members.filter_by(is_active=True).all()]

    def get_member_country_ids(self):
        """Get list of active member country IDs."""
        return [m.country_id for m in self.members.filter_by(is_active=True).all()]

    def is_member(self, country_id):
        """Check if a country is an active member."""
        return self.members.filter_by(country_id=country_id, is_active=True).first() is not None

    def can_invite(self, country_id):
        """Check if a country can be invited (not at war with any member, not in another alliance)."""
        from app.models import War, WarStatus

        # Check if already a member
        if self.is_member(country_id):
            return False, "Country is already a member of this alliance."

        # Check if alliance is full
        if self.is_full:
            return False, "Alliance has reached maximum members (5)."

        # Check if country is in another alliance
        existing = AllianceMembership.query.filter_by(country_id=country_id, is_active=True).first()
        if existing:
            return False, "Country is already in another alliance."

        # Check if country is at war with any alliance member
        member_ids = self.get_member_country_ids()
        for member_id in member_ids:
            active_war = War.query.filter(
                War.status == WarStatus.ACTIVE,
                db.or_(
                    db.and_(War.attacker_country_id == country_id, War.defender_country_id == member_id),
                    db.and_(War.attacker_country_id == member_id, War.defender_country_id == country_id)
                )
            ).first()
            if active_war:
                return False, "Country is at war with an alliance member."

        return True, ""

    @staticmethod
    def get_country_alliance(country_id):
        """Get the alliance a country belongs to (if any)."""
        membership = AllianceMembership.query.filter_by(country_id=country_id, is_active=True).first()
        if membership:
            return membership.alliance
        return None

    @staticmethod
    def are_allies(country_a_id, country_b_id):
        """Check if two countries are in the same alliance."""
        alliance_a = Alliance.get_country_alliance(country_a_id)
        alliance_b = Alliance.get_country_alliance(country_b_id)

        if alliance_a and alliance_b and alliance_a.id == alliance_b.id:
            return True
        return False

    @staticmethod
    def get_all_allies(country_id):
        """Get all countries that are allies (in same alliance) with given country."""
        alliance = Alliance.get_country_alliance(country_id)
        if not alliance:
            return []

        member_ids = alliance.get_member_country_ids()
        # Remove the country itself from the list
        return [mid for mid in member_ids if mid != country_id]


class AllianceMembership(db.Model):
    """
    Membership record for a country in an alliance.
    """
    __tablename__ = 'alliance_memberships'

    id = db.Column(db.Integer, primary_key=True)
    alliance_id = db.Column(db.Integer, db.ForeignKey('alliances.id'), nullable=False, index=True)
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)

    # Membership details
    is_founder = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)

    # Timestamps
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    left_at = db.Column(db.DateTime, nullable=True)
    left_reason = db.Column(db.String(100), nullable=True)  # "voluntary", "kicked", "alliance_dissolved"

    # Cooldown tracking (can't rejoin same alliance for 7 days after leaving)
    can_rejoin_at = db.Column(db.DateTime, nullable=True)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    alliance = db.relationship('Alliance', back_populates='members')
    country = db.relationship('Country', backref=db.backref('alliance_memberships', lazy='dynamic'))

    __table_args__ = (
        # Only one active membership per country
        db.Index('idx_active_membership', 'country_id', 'is_active'),
    )

    def __repr__(self):
        return f'<AllianceMembership {self.country.name} in {self.alliance.name}>'

    def leave(self, reason="voluntary"):
        """Leave the alliance."""
        self.is_active = False
        self.left_at = datetime.utcnow()
        self.left_reason = reason
        self.can_rejoin_at = datetime.utcnow() + timedelta(days=7)


class AllianceInvitation(db.Model):
    """
    Invitation for a country to join an alliance.

    Requires dual congress votes:
    - Inviting country congress votes to invite
    - Invited country congress votes to join
    Both must pass within 24 hours for invitation to succeed.
    """
    __tablename__ = 'alliance_invitations'

    id = db.Column(db.Integer, primary_key=True)
    alliance_id = db.Column(db.Integer, db.ForeignKey('alliances.id'), nullable=False, index=True)

    # Countries involved
    inviting_country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)
    invited_country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)

    # Who initiated the invitation
    initiated_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Status
    status = db.Column(db.Enum(AllianceInvitationStatus), nullable=False, default=AllianceInvitationStatus.PENDING_VOTES, index=True)

    # Linked law proposals (both created simultaneously)
    inviter_law_id = db.Column(db.Integer, db.ForeignKey('laws.id'), nullable=True)
    invited_law_id = db.Column(db.Integer, db.ForeignKey('laws.id'), nullable=True)

    # Vote results tracking
    inviter_accepted = db.Column(db.Boolean, nullable=True)  # None = pending, True = accepted, False = rejected
    invited_accepted = db.Column(db.Boolean, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False)  # 24 hours from creation

    # Relationships
    alliance = db.relationship('Alliance', back_populates='invitations')
    inviting_country = db.relationship('Country', foreign_keys=[inviting_country_id], backref=db.backref('alliance_invitations_sent', lazy='dynamic'))
    invited_country = db.relationship('Country', foreign_keys=[invited_country_id], backref=db.backref('alliance_invitations_received', lazy='dynamic'))
    initiated_by = db.relationship('User', backref=db.backref('alliance_invitations_initiated', lazy='dynamic'))
    inviter_law = db.relationship('Law', foreign_keys=[inviter_law_id], backref='alliance_invitation_inviter')
    invited_law = db.relationship('Law', foreign_keys=[invited_law_id], backref='alliance_invitation_invited')

    def __repr__(self):
        return f'<AllianceInvitation {self.invited_country.name} to {self.alliance.name}>'

    @property
    def is_expired(self):
        """Check if the invitation has expired."""
        return datetime.utcnow() >= self.expires_at

    def check_and_resolve(self):
        """Check if both votes are complete and resolve the invitation."""
        if self.status != AllianceInvitationStatus.PENDING_VOTES:
            return

        # Check if both votes are in - prioritize this over expiration check
        # since votes are processed when voting ends (which is the expiration time)
        if self.inviter_accepted is not None and self.invited_accepted is not None:
            if self.inviter_accepted and self.invited_accepted:
                self.status = AllianceInvitationStatus.ACCEPTED
            else:
                self.status = AllianceInvitationStatus.REJECTED
            self.resolved_at = datetime.utcnow()
            return

        # Check if expired (only if votes haven't both been cast)
        if self.is_expired:
            self.status = AllianceInvitationStatus.EXPIRED
            self.resolved_at = datetime.utcnow()
            return


class AllianceKick(db.Model):
    """
    Proposal to kick a country from the alliance.

    Only the alliance leader can propose kicks.
    Leader's congress must vote to approve.
    """
    __tablename__ = 'alliance_kicks'

    id = db.Column(db.Integer, primary_key=True)
    alliance_id = db.Column(db.Integer, db.ForeignKey('alliances.id'), nullable=False, index=True)

    # Country being kicked
    target_country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)

    # Who initiated the kick
    initiated_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Status
    status = db.Column(db.Enum(AllianceKickStatus), nullable=False, default=AllianceKickStatus.PENDING_VOTE, index=True)

    # Linked law proposal
    law_id = db.Column(db.Integer, db.ForeignKey('laws.id'), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    alliance = db.relationship('Alliance', back_populates='kicks')
    target_country = db.relationship('Country', foreign_keys=[target_country_id], backref=db.backref('alliance_kick_targets', lazy='dynamic'))
    initiated_by = db.relationship('User', backref=db.backref('alliance_kicks_initiated', lazy='dynamic'))
    law = db.relationship('Law', backref='alliance_kick')

    def __repr__(self):
        return f'<AllianceKick {self.target_country.name} from {self.alliance.name}>'


class AllianceLeave(db.Model):
    """
    Proposal for a country to leave an alliance.

    Defense Minister proposes, congress votes.
    If passed, country leaves after 24h cooldown.
    """
    __tablename__ = 'alliance_leaves'

    id = db.Column(db.Integer, primary_key=True)
    alliance_id = db.Column(db.Integer, db.ForeignKey('alliances.id'), nullable=False, index=True)
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'), nullable=False, index=True)

    # Who initiated
    initiated_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Status
    status = db.Column(db.String(20), nullable=False, default='pending_vote', index=True)  # pending_vote, approved, rejected, executed

    # Linked law proposal
    law_id = db.Column(db.Integer, db.ForeignKey('laws.id'), nullable=True)

    # Execution tracking (24h delay after approval)
    approved_at = db.Column(db.DateTime, nullable=True)
    execute_at = db.Column(db.DateTime, nullable=True)  # 24h after approval
    executed_at = db.Column(db.DateTime, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    alliance = db.relationship('Alliance', backref=db.backref('leave_requests', lazy='dynamic'))
    country = db.relationship('Country', backref=db.backref('alliance_leave_requests', lazy='dynamic'))
    initiated_by = db.relationship('User', backref=db.backref('alliance_leaves_initiated', lazy='dynamic'))
    law = db.relationship('Law', backref='alliance_leave')

    def __repr__(self):
        return f'<AllianceLeave {self.country.name} from {self.alliance.name}>'


class AllianceDissolution(db.Model):
    """
    Proposal to dissolve an alliance.

    Only the leader can propose.
    ALL member congresses must vote to approve.
    """
    __tablename__ = 'alliance_dissolutions'

    id = db.Column(db.Integer, primary_key=True)
    alliance_id = db.Column(db.Integer, db.ForeignKey('alliances.id'), nullable=False, index=True)

    # Who initiated
    initiated_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Status
    status = db.Column(db.String(20), nullable=False, default='pending_votes', index=True)  # pending_votes, approved, rejected, expired

    # Track votes from each member country (stored as JSON: {country_id: law_id})
    member_laws = db.Column(db.JSON, nullable=False, default=dict)
    member_votes = db.Column(db.JSON, nullable=False, default=dict)  # {country_id: True/False/None}

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)  # 24h from creation
    resolved_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    alliance = db.relationship('Alliance', backref=db.backref('dissolution_requests', lazy='dynamic'))
    initiated_by = db.relationship('User', backref=db.backref('alliance_dissolutions_initiated', lazy='dynamic'))

    def __repr__(self):
        return f'<AllianceDissolution {self.alliance.name}>'

    def check_and_resolve(self):
        """Check if all votes are in and resolve."""
        if self.status != 'pending_votes':
            return

        # Check expiry
        if datetime.utcnow() >= self.expires_at:
            self.status = 'expired'
            self.resolved_at = datetime.utcnow()
            return

        # Check if all members have voted
        member_ids = self.alliance.get_member_country_ids()
        all_voted = all(str(mid) in self.member_votes and self.member_votes[str(mid)] is not None for mid in member_ids)

        if all_voted:
            # All must approve
            all_approved = all(self.member_votes.get(str(mid)) == True for mid in member_ids)
            if all_approved:
                self.status = 'approved'
            else:
                self.status = 'rejected'
            self.resolved_at = datetime.utcnow()
