"""
Alliance Service

Handles all alliance-related business logic including:
- Alliance creation
- Invitations (with dual congress voting)
- Membership management
- Kicks, leaves, and dissolution
"""

from datetime import datetime, timedelta
from typing import Tuple, Optional, List
from app.extensions import db
from app.models import (
    Alliance, AllianceMembership, AllianceInvitation, AllianceKick,
    AllianceLeave, AllianceDissolution, AllianceInvitationStatus, AllianceKickStatus,
    Country, User, Law, LawType, LawStatus, War, WarStatus
)
import logging

logger = logging.getLogger(__name__)

# Constants
INVITATION_VOTING_HOURS = 24
LEAVE_COOLDOWN_HOURS = 24
REJOIN_COOLDOWN_DAYS = 7
MAX_ALLIANCE_MEMBERS = 5


class AllianceService:
    """Service class for alliance operations."""

    # =========================================================================
    # ALLIANCE CREATION
    # =========================================================================

    @staticmethod
    def create_alliance(user: User, name: str) -> Tuple[Optional[Alliance], str]:
        """
        Create a new alliance.

        Args:
            user: The user creating the alliance (must be president)
            name: Name of the alliance

        Returns:
            Tuple of (alliance, message)
        """
        country_id = user.citizenship_id
        if not country_id:
            return None, "You must be a citizen of a country to create an alliance."

        # Check user is president
        if not user.is_president_of(country_id):
            return None, "Only the President can create an alliance."

        # Check country is not already in an alliance
        existing = AllianceMembership.query.filter_by(
            country_id=country_id, is_active=True
        ).first()
        if existing:
            return None, "Your country is already in an alliance."

        # Check name is unique
        existing_name = Alliance.query.filter_by(name=name, is_active=True).first()
        if existing_name:
            return None, "An alliance with this name already exists."

        # Check name length
        if len(name) < 3 or len(name) > 100:
            return None, "Alliance name must be between 3 and 100 characters."

        # Create alliance
        alliance = Alliance(
            name=name,
            leader_country_id=country_id,
            is_active=True,
            created_at=datetime.utcnow()
        )
        db.session.add(alliance)
        db.session.flush()  # Get the alliance ID

        # Create founding membership
        membership = AllianceMembership(
            alliance_id=alliance.id,
            country_id=country_id,
            is_founder=True,
            is_active=True,
            joined_at=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        db.session.add(membership)
        db.session.commit()

        logger.info(f"Alliance '{name}' created by country {country_id}")
        return alliance, f"Alliance '{name}' has been created successfully!"

    # =========================================================================
    # INVITATIONS
    # =========================================================================

    @staticmethod
    def propose_invitation(
        user: User,
        alliance_id: int,
        invited_country_id: int
    ) -> Tuple[Optional[AllianceInvitation], str]:
        """
        Propose inviting a country to the alliance.
        Creates two law proposals that must both pass.

        Args:
            user: User proposing (must be Defense Minister of an alliance member)
            alliance_id: Alliance ID
            invited_country_id: Country to invite

        Returns:
            Tuple of (invitation, message)
        """
        country_id = user.citizenship_id
        if not country_id:
            return None, "You must be a citizen to propose an invitation."

        # Check user is Foreign Affairs Minister or President
        is_foreign_affairs_minister = user.is_minister_of(country_id, 'foreign_affairs')
        is_president = user.is_president_of(country_id)
        if not is_foreign_affairs_minister and not is_president:
            return None, "Only the President or Minister of Foreign Affairs can propose alliance invitations."

        # Check alliance exists and is active
        alliance = Alliance.query.get(alliance_id)
        if not alliance or not alliance.is_active:
            return None, "Alliance not found or is inactive."

        # Check user's country is a member
        if not alliance.is_member(country_id):
            return None, "Your country is not a member of this alliance."

        # Check can invite
        can_invite, error = alliance.can_invite(invited_country_id)
        if not can_invite:
            return None, error

        # Check no pending invitation for this country
        pending = AllianceInvitation.query.filter_by(
            alliance_id=alliance_id,
            invited_country_id=invited_country_id,
            status=AllianceInvitationStatus.PENDING_VOTES
        ).first()
        if pending:
            return None, "There is already a pending invitation for this country."

        invited_country = Country.query.get(invited_country_id)
        if not invited_country:
            return None, "Invited country not found."

        # Create the two law proposals
        voting_end = datetime.utcnow() + timedelta(hours=INVITATION_VOTING_HOURS)

        # Law 1: Inviting country votes to invite
        inviter_law = Law(
            country_id=country_id,
            law_type=LawType.ALLIANCE_INVITE,
            status=LawStatus.VOTING,
            proposed_by_user_id=user.id,
            proposed_by_role='minister_foreign_affairs',
            law_details={
                'alliance_id': alliance_id,
                'alliance_name': alliance.name,
                'invited_country_id': invited_country_id,
                'invited_country_name': invited_country.name
            },
            voting_start=datetime.utcnow(),
            voting_end=voting_end
        )
        db.session.add(inviter_law)

        # Law 2: Invited country votes to join
        invited_law = Law(
            country_id=invited_country_id,
            law_type=LawType.ALLIANCE_JOIN,
            status=LawStatus.VOTING,
            proposed_by_user_id=user.id,
            proposed_by_role='external_invitation',
            law_details={
                'alliance_id': alliance_id,
                'alliance_name': alliance.name,
                'leader_country_id': alliance.leader_country_id,
                'leader_country_name': alliance.leader_country.name,
                'inviting_country_id': country_id,
                'inviting_country_name': Country.query.get(country_id).name
            },
            voting_start=datetime.utcnow(),
            voting_end=voting_end
        )
        db.session.add(invited_law)
        db.session.flush()

        # Create invitation record
        invitation = AllianceInvitation(
            alliance_id=alliance_id,
            inviting_country_id=country_id,
            invited_country_id=invited_country_id,
            initiated_by_user_id=user.id,
            status=AllianceInvitationStatus.PENDING_VOTES,
            inviter_law_id=inviter_law.id,
            invited_law_id=invited_law.id,
            created_at=datetime.utcnow(),
            expires_at=voting_end
        )
        db.session.add(invitation)
        db.session.commit()

        logger.info(f"Alliance invitation created: {alliance.name} inviting {invited_country.name}")
        return invitation, f"Invitation proposal created. Both congresses have 24 hours to vote."

    @staticmethod
    def process_invitation_vote(law: Law):
        """
        Process a vote result for an alliance invitation law.
        Called when a law voting period ends.

        Args:
            law: The law that finished voting
        """
        if law.law_type == LawType.ALLIANCE_INVITE:
            # Find the invitation
            invitation = AllianceInvitation.query.filter_by(inviter_law_id=law.id).first()
            if invitation:
                invitation.inviter_accepted = law.passed
                invitation.check_and_resolve()
                if invitation.status == AllianceInvitationStatus.ACCEPTED:
                    AllianceService._complete_invitation(invitation)
                db.session.commit()

        elif law.law_type == LawType.ALLIANCE_JOIN:
            invitation = AllianceInvitation.query.filter_by(invited_law_id=law.id).first()
            if invitation:
                invitation.invited_accepted = law.passed
                invitation.check_and_resolve()
                if invitation.status == AllianceInvitationStatus.ACCEPTED:
                    AllianceService._complete_invitation(invitation)
                db.session.commit()

    @staticmethod
    def _complete_invitation(invitation: AllianceInvitation):
        """Complete an accepted invitation by adding the country to the alliance."""
        alliance = invitation.alliance

        # Double-check alliance isn't full
        if alliance.is_full:
            invitation.status = AllianceInvitationStatus.REJECTED
            logger.warning(f"Invitation rejected - alliance {alliance.name} is full")
            return

        # Create membership
        membership = AllianceMembership(
            alliance_id=alliance.id,
            country_id=invitation.invited_country_id,
            is_founder=False,
            is_active=True,
            joined_at=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        db.session.add(membership)

        logger.info(f"Country {invitation.invited_country_id} joined alliance {alliance.name}")

    # =========================================================================
    # KICKING MEMBERS
    # =========================================================================

    @staticmethod
    def propose_kick(
        user: User,
        alliance_id: int,
        target_country_id: int
    ) -> Tuple[Optional[AllianceKick], str]:
        """
        Propose kicking a country from the alliance.
        Only the leader's Defense Minister can propose kicks.

        Args:
            user: User proposing (must be Defense Minister of leader country)
            alliance_id: Alliance ID
            target_country_id: Country to kick

        Returns:
            Tuple of (kick, message)
        """
        country_id = user.citizenship_id
        if not country_id:
            return None, "You must be a citizen to propose a kick."

        alliance = Alliance.query.get(alliance_id)
        if not alliance or not alliance.is_active:
            return None, "Alliance not found or is inactive."

        # Check user's country is the leader
        if country_id != alliance.leader_country_id:
            return None, "Only the alliance leader's country can propose kicks."

        # Check user is Foreign Affairs Minister or President
        is_foreign_affairs_minister = user.is_minister_of(country_id, 'foreign_affairs')
        is_president = user.is_president_of(country_id)
        if not is_foreign_affairs_minister and not is_president:
            return None, "Only the President or Minister of Foreign Affairs can propose kicks."

        # Check target is a member
        if not alliance.is_member(target_country_id):
            return None, "Target country is not a member of this alliance."

        # Can't kick yourself (leader)
        if target_country_id == alliance.leader_country_id:
            return None, "The leader country cannot be kicked. Transfer leadership first."

        # Check no pending kick for this country
        pending = AllianceKick.query.filter_by(
            alliance_id=alliance_id,
            target_country_id=target_country_id,
            status=AllianceKickStatus.PENDING_VOTE
        ).first()
        if pending:
            return None, "There is already a pending kick proposal for this country."

        target_country = Country.query.get(target_country_id)
        if not target_country:
            return None, "Target country not found."

        # Create law proposal
        voting_end = datetime.utcnow() + timedelta(hours=INVITATION_VOTING_HOURS)
        law = Law(
            country_id=country_id,
            law_type=LawType.ALLIANCE_KICK,
            status=LawStatus.VOTING,
            proposed_by_user_id=user.id,
            proposed_by_role='minister_foreign_affairs',
            law_details={
                'alliance_id': alliance_id,
                'alliance_name': alliance.name,
                'target_country_id': target_country_id,
                'target_country_name': target_country.name
            },
            voting_start=datetime.utcnow(),
            voting_end=voting_end
        )
        db.session.add(law)
        db.session.flush()

        # Create kick record
        kick = AllianceKick(
            alliance_id=alliance_id,
            target_country_id=target_country_id,
            initiated_by_user_id=user.id,
            status=AllianceKickStatus.PENDING_VOTE,
            law_id=law.id,
            created_at=datetime.utcnow()
        )
        db.session.add(kick)
        db.session.commit()

        logger.info(f"Kick proposal created: {target_country.name} from {alliance.name}")
        return kick, f"Kick proposal created. Congress has 24 hours to vote."

    @staticmethod
    def process_kick_vote(law: Law):
        """Process a kick vote result."""
        if law.law_type != LawType.ALLIANCE_KICK:
            return

        kick = AllianceKick.query.filter_by(law_id=law.id).first()
        if not kick:
            return

        if law.passed:
            kick.status = AllianceKickStatus.APPROVED
            kick.resolved_at = datetime.utcnow()

            # Remove membership
            membership = AllianceMembership.query.filter_by(
                alliance_id=kick.alliance_id,
                country_id=kick.target_country_id,
                is_active=True
            ).first()
            if membership:
                membership.leave(reason="kicked")

            logger.info(f"Country {kick.target_country_id} kicked from alliance {kick.alliance_id}")
        else:
            kick.status = AllianceKickStatus.REJECTED
            kick.resolved_at = datetime.utcnow()

        db.session.commit()

    # =========================================================================
    # LEAVING ALLIANCE
    # =========================================================================

    @staticmethod
    def propose_leave(user: User, alliance_id: int) -> Tuple[Optional[AllianceLeave], str]:
        """
        Propose leaving an alliance.
        Defense Minister proposes, congress votes.
        If passed, country leaves after 24h delay.

        Args:
            user: User proposing (must be Defense Minister)
            alliance_id: Alliance ID

        Returns:
            Tuple of (leave_request, message)
        """
        country_id = user.citizenship_id
        if not country_id:
            return None, "You must be a citizen to propose leaving."

        # Check user is Foreign Affairs Minister or President
        is_foreign_affairs_minister = user.is_minister_of(country_id, 'foreign_affairs')
        is_president = user.is_president_of(country_id)
        if not is_foreign_affairs_minister and not is_president:
            return None, "Only the President or Minister of Foreign Affairs can propose leaving an alliance."

        alliance = Alliance.query.get(alliance_id)
        if not alliance or not alliance.is_active:
            return None, "Alliance not found or is inactive."

        # Check country is a member
        if not alliance.is_member(country_id):
            return None, "Your country is not a member of this alliance."

        # Check no pending leave request
        pending = AllianceLeave.query.filter_by(
            alliance_id=alliance_id,
            country_id=country_id,
            status='pending_vote'
        ).first()
        if pending:
            return None, "There is already a pending leave proposal."

        # Create law proposal
        voting_end = datetime.utcnow() + timedelta(hours=INVITATION_VOTING_HOURS)
        law = Law(
            country_id=country_id,
            law_type=LawType.ALLIANCE_LEAVE,
            status=LawStatus.VOTING,
            proposed_by_user_id=user.id,
            proposed_by_role='minister_foreign_affairs',
            law_details={
                'alliance_id': alliance_id,
                'alliance_name': alliance.name
            },
            voting_start=datetime.utcnow(),
            voting_end=voting_end
        )
        db.session.add(law)
        db.session.flush()

        # Create leave request
        leave = AllianceLeave(
            alliance_id=alliance_id,
            country_id=country_id,
            initiated_by_user_id=user.id,
            status='pending_vote',
            law_id=law.id,
            created_at=datetime.utcnow()
        )
        db.session.add(leave)
        db.session.commit()

        logger.info(f"Leave proposal created: {country_id} from {alliance.name}")
        return leave, f"Leave proposal created. Congress has 24 hours to vote."

    @staticmethod
    def process_leave_vote(law: Law):
        """Process a leave vote result."""
        if law.law_type != LawType.ALLIANCE_LEAVE:
            return

        leave = AllianceLeave.query.filter_by(law_id=law.id).first()
        if not leave:
            return

        if law.passed:
            leave.status = 'approved'
            leave.approved_at = datetime.utcnow()
            leave.execute_at = datetime.utcnow() + timedelta(hours=LEAVE_COOLDOWN_HOURS)
            logger.info(f"Leave approved for country {leave.country_id}, executing in 24h")
        else:
            leave.status = 'rejected'

        db.session.commit()

    @staticmethod
    def execute_pending_leaves():
        """
        Execute approved leave requests that have passed the cooldown period.
        Called by scheduler.
        """
        now = datetime.utcnow()
        pending = AllianceLeave.query.filter(
            AllianceLeave.status == 'approved',
            AllianceLeave.execute_at <= now
        ).all()

        for leave in pending:
            alliance = leave.alliance

            # Remove membership
            membership = AllianceMembership.query.filter_by(
                alliance_id=leave.alliance_id,
                country_id=leave.country_id,
                is_active=True
            ).first()
            if membership:
                membership.leave(reason="voluntary")

            leave.status = 'executed'
            leave.executed_at = now

            # If leader leaves, transfer or dissolve
            if leave.country_id == alliance.leader_country_id:
                AllianceService._handle_leader_leaving(alliance)

            logger.info(f"Country {leave.country_id} left alliance {alliance.name}")

        if pending:
            db.session.commit()

    @staticmethod
    def _handle_leader_leaving(alliance: Alliance):
        """Handle when the alliance leader leaves."""
        remaining_members = alliance.get_active_members()

        if len(remaining_members) == 0:
            # No members left, dissolve
            alliance.is_active = False
            alliance.dissolved_at = datetime.utcnow()
            alliance.dissolved_reason = "all_members_left"
            logger.info(f"Alliance {alliance.name} dissolved - no members left")
        else:
            # Transfer to first remaining member (by join date)
            oldest_membership = AllianceMembership.query.filter_by(
                alliance_id=alliance.id,
                is_active=True
            ).order_by(AllianceMembership.joined_at.asc()).first()

            if oldest_membership:
                alliance.leader_country_id = oldest_membership.country_id
                logger.info(f"Alliance {alliance.name} leadership transferred to {oldest_membership.country_id}")

    # =========================================================================
    # LEADERSHIP TRANSFER
    # =========================================================================

    @staticmethod
    def transfer_leadership(
        user: User,
        alliance_id: int,
        new_leader_country_id: int
    ) -> Tuple[bool, str]:
        """
        Transfer alliance leadership to another member.
        Only the current leader's President can do this.

        Args:
            user: User transferring (must be President of leader country)
            alliance_id: Alliance ID
            new_leader_country_id: New leader country ID

        Returns:
            Tuple of (success, message)
        """
        country_id = user.citizenship_id
        if not country_id:
            return False, "You must be a citizen."

        alliance = Alliance.query.get(alliance_id)
        if not alliance or not alliance.is_active:
            return False, "Alliance not found or is inactive."

        # Check user's country is the leader
        if country_id != alliance.leader_country_id:
            return False, "Only the alliance leader's country can transfer leadership."

        # Check user is President
        if not user.is_president_of(country_id):
            return False, "Only the President can transfer alliance leadership."

        # Check new leader is a member
        if not alliance.is_member(new_leader_country_id):
            return False, "Target country is not a member of this alliance."

        # Can't transfer to self
        if new_leader_country_id == alliance.leader_country_id:
            return False, "Country is already the leader."

        old_leader = alliance.leader_country_id
        alliance.leader_country_id = new_leader_country_id
        db.session.commit()

        logger.info(f"Alliance {alliance.name} leadership transferred from {old_leader} to {new_leader_country_id}")
        return True, f"Leadership transferred successfully."

    # =========================================================================
    # RENAME ALLIANCE
    # =========================================================================

    @staticmethod
    def rename_alliance(user: User, alliance_id: int, new_name: str) -> Tuple[bool, str]:
        """
        Rename an alliance. Only leader's President can do this.

        Args:
            user: User renaming
            alliance_id: Alliance ID
            new_name: New name

        Returns:
            Tuple of (success, message)
        """
        country_id = user.citizenship_id
        if not country_id:
            return False, "You must be a citizen."

        alliance = Alliance.query.get(alliance_id)
        if not alliance or not alliance.is_active:
            return False, "Alliance not found or is inactive."

        if country_id != alliance.leader_country_id:
            return False, "Only the alliance leader's country can rename the alliance."

        if not user.is_president_of(country_id):
            return False, "Only the President can rename the alliance."

        if len(new_name) < 3 or len(new_name) > 100:
            return False, "Alliance name must be between 3 and 100 characters."

        # Check name is unique
        existing = Alliance.query.filter(
            Alliance.name == new_name,
            Alliance.is_active == True,
            Alliance.id != alliance_id
        ).first()
        if existing:
            return False, "An alliance with this name already exists."

        old_name = alliance.name
        alliance.name = new_name
        db.session.commit()

        logger.info(f"Alliance renamed from '{old_name}' to '{new_name}'")
        return True, f"Alliance renamed to '{new_name}'."

    # =========================================================================
    # DISSOLUTION
    # =========================================================================

    @staticmethod
    def propose_dissolution(user: User, alliance_id: int) -> Tuple[Optional[AllianceDissolution], str]:
        """
        Propose dissolving an alliance.
        Only leader's President can propose.
        ALL member congresses must vote to approve.

        Args:
            user: User proposing
            alliance_id: Alliance ID

        Returns:
            Tuple of (dissolution, message)
        """
        country_id = user.citizenship_id
        if not country_id:
            return None, "You must be a citizen."

        alliance = Alliance.query.get(alliance_id)
        if not alliance or not alliance.is_active:
            return None, "Alliance not found or is inactive."

        if country_id != alliance.leader_country_id:
            return None, "Only the alliance leader's country can propose dissolution."

        if not user.is_president_of(country_id):
            return None, "Only the President can propose dissolution."

        # Check no pending dissolution
        pending = AllianceDissolution.query.filter_by(
            alliance_id=alliance_id,
            status='pending_votes'
        ).first()
        if pending:
            return None, "There is already a pending dissolution proposal."

        # Get all member countries
        member_ids = alliance.get_member_country_ids()
        voting_end = datetime.utcnow() + timedelta(hours=INVITATION_VOTING_HOURS)

        # Create a law for each member country
        member_laws = {}
        member_votes = {}

        for mid in member_ids:
            law = Law(
                country_id=mid,
                law_type=LawType.ALLIANCE_DISSOLVE,
                status=LawStatus.VOTING,
                proposed_by_user_id=user.id,
                proposed_by_role='alliance_leader',
                law_details={
                    'alliance_id': alliance_id,
                    'alliance_name': alliance.name
                },
                voting_start=datetime.utcnow(),
                voting_end=voting_end
            )
            db.session.add(law)
            db.session.flush()
            member_laws[str(mid)] = law.id
            member_votes[str(mid)] = None

        # Create dissolution record
        dissolution = AllianceDissolution(
            alliance_id=alliance_id,
            initiated_by_user_id=user.id,
            status='pending_votes',
            member_laws=member_laws,
            member_votes=member_votes,
            created_at=datetime.utcnow(),
            expires_at=voting_end
        )
        db.session.add(dissolution)
        db.session.commit()

        logger.info(f"Dissolution proposed for alliance {alliance.name}")
        return dissolution, f"Dissolution proposal created. All member congresses have 24 hours to vote."

    @staticmethod
    def process_dissolution_vote(law: Law):
        """Process a dissolution vote result."""
        if law.law_type != LawType.ALLIANCE_DISSOLVE:
            return

        # Find the dissolution where this law is involved
        dissolutions = AllianceDissolution.query.filter_by(status='pending_votes').all()

        for dissolution in dissolutions:
            if str(law.country_id) in dissolution.member_laws:
                if dissolution.member_laws[str(law.country_id)] == law.id:
                    # Update the vote
                    votes = dict(dissolution.member_votes)
                    votes[str(law.country_id)] = law.passed
                    dissolution.member_votes = votes

                    # Check if resolved
                    dissolution.check_and_resolve()

                    if dissolution.status == 'approved':
                        # Dissolve the alliance
                        alliance = dissolution.alliance
                        alliance.is_active = False
                        alliance.dissolved_at = datetime.utcnow()
                        alliance.dissolved_reason = "dissolution_vote"

                        # Deactivate all memberships
                        for membership in alliance.members.filter_by(is_active=True).all():
                            membership.leave(reason="alliance_dissolved")

                        logger.info(f"Alliance {alliance.name} dissolved by vote")

                    db.session.commit()
                    break

    # =========================================================================
    # QUERIES
    # =========================================================================

    @staticmethod
    def get_country_alliance(country_id: int) -> Optional[Alliance]:
        """Get the alliance a country belongs to."""
        return Alliance.get_country_alliance(country_id)

    @staticmethod
    def get_alliance_members(alliance_id: int) -> List[Country]:
        """Get all member countries of an alliance."""
        alliance = Alliance.query.get(alliance_id)
        if alliance:
            return alliance.get_active_members()
        return []

    @staticmethod
    def get_all_alliances() -> List[Alliance]:
        """Get all active alliances."""
        return Alliance.query.filter_by(is_active=True).all()
