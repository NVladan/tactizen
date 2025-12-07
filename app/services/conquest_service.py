"""
Conquest Service - Handles country conquest and liberation logic.

When a country loses all its regions through war, this service:
- Marks the country as conquered
- Transfers treasury gold to the conqueror
- Freezes all companies and fires workers
- Clears government positions
- Rejects pending laws
- Cancels elections
- Kicks country from alliance
- Ends the war

When a country is liberated through resistance war:
- Unfreezes companies
- Restores citizen rights
- Optionally assigns liberator as president
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.extensions import db
from sqlalchemy import select

logger = logging.getLogger(__name__)


class ConquestService:
    """Service for managing country conquest and liberation."""

    @staticmethod
    def check_full_conquest(country_id: int) -> bool:
        """
        Check if a country has lost all its regions.

        Args:
            country_id: ID of the country to check

        Returns:
            True if country has zero regions (fully conquered)
        """
        from app.models.location import Country

        country = db.session.get(Country, country_id)
        if not country:
            return False

        # Check if country has any current regions
        region_count = country.current_regions.count()
        return region_count == 0

    @staticmethod
    def conquer_country(conquered_country_id: int, conquering_country_id: int, war) -> bool:
        """
        Execute full conquest of a country.

        Args:
            conquered_country_id: ID of the country being conquered
            conquering_country_id: ID of the conquering country
            war: The War object that led to conquest

        Returns:
            True if conquest was successful
        """
        from app.models.location import Country
        from app.models.government import WarStatus

        try:
            # Get countries with row locks
            conquered = db.session.scalar(
                select(Country).where(Country.id == conquered_country_id).with_for_update()
            )
            conqueror = db.session.scalar(
                select(Country).where(Country.id == conquering_country_id).with_for_update()
            )

            if not conquered or not conqueror:
                logger.error(f"[Conquest] Invalid country IDs: conquered={conquered_country_id}, conqueror={conquering_country_id}")
                return False

            if conquered.is_conquered:
                logger.warning(f"[Conquest] {conquered.name} is already conquered")
                return False

            logger.info(f"[Conquest] Starting conquest of {conquered.name} by {conqueror.name}")

            # 1. Mark country as conquered
            conquered.is_conquered = True
            conquered.conquered_by_id = conquering_country_id
            conquered.conquered_at = datetime.utcnow()

            # 2. Transfer treasury gold (not currency)
            ConquestService._transfer_treasury(conquered, conqueror)

            # 3. Freeze all companies and fire workers
            ConquestService._freeze_companies(conquered_country_id)

            # 4. Clear government positions
            ConquestService._clear_government(conquered_country_id)

            # 5. Reject all pending laws
            ConquestService._reject_pending_laws(conquered_country_id)

            # 6. Cancel ongoing elections
            ConquestService._cancel_elections(conquered_country_id)

            # 7. Kick from alliance
            ConquestService._kick_from_alliance(conquered_country_id)

            # 8. End the war
            if war:
                war.status = WarStatus.ENDED_EXPIRED
                war.ended_at = datetime.utcnow()

            # 9. Send alerts to all citizens
            ConquestService._send_conquest_alerts(conquered, conqueror)

            db.session.commit()
            logger.info(f"[Conquest] {conquered.name} has been fully conquered by {conqueror.name}")
            return True

        except Exception as e:
            db.session.rollback()
            logger.error(f"[Conquest] Error during conquest: {str(e)}")
            raise

    @staticmethod
    def _transfer_treasury(conquered, conqueror):
        """Transfer treasury gold from conquered country to conqueror."""
        # Transfer treasury gold (not reserved gold - that gets released via law rejection)
        gold_amount = conquered.treasury_gold or Decimal('0')

        if gold_amount > 0:
            conquered.treasury_gold = Decimal('0')
            conqueror.treasury_gold = (conqueror.treasury_gold or Decimal('0')) + gold_amount
            logger.info(f"[Conquest] Transferred {gold_amount} gold from {conquered.name} to {conqueror.name}")

        # Note: treasury_currency stays with conquered country (frozen)
        # Note: military_budget_gold and military_budget_currency stay with MoD

    @staticmethod
    def _freeze_companies(country_id: int):
        """Freeze all companies in the country and fire all workers."""
        from app.models.company import Company, Employment, JobOffer
        from app.alert_helpers import create_alert
        from app.models.activity import AlertType

        # Get all companies in this country
        companies = Company.query.filter_by(
            country_id=country_id,
            is_deleted=False
        ).all()

        fired_count = 0
        frozen_count = 0

        for company in companies:
            # Fire all workers
            for employment in company.employees.all():
                # Send alert to worker
                create_alert(
                    user=employment.user,
                    alert_type=AlertType.EMPLOYMENT,
                    title="Employment Terminated - Country Conquered",
                    content=f"Your employment at {company.name} has been terminated because {company.country.name} was conquered."
                )
                db.session.delete(employment)
                fired_count += 1

            # Deactivate all job offers
            for job_offer in company.job_offers.filter_by(is_active=True).all():
                job_offer.is_active = False

            # Freeze the company
            company.freeze()
            frozen_count += 1

            # Alert company owner
            create_alert(
                user=company.owner,
                alert_type=AlertType.COMPANY,
                title="Company Frozen - Country Conquered",
                content=f"Your company {company.name} has been frozen because {company.country.name} was conquered. Operations will resume upon liberation."
            )

        logger.info(f"[Conquest] Frozen {frozen_count} companies, fired {fired_count} workers")

    @staticmethod
    def _clear_government(country_id: int):
        """Clear all government positions (president, congress, ministers)."""
        from app.models.government import CountryPresident, CongressMember, Minister
        from app.alert_helpers import create_alert
        from app.models.activity import AlertType

        # Clear president
        current_president = CountryPresident.query.filter_by(
            country_id=country_id,
            is_current=True
        ).first()

        if current_president:
            current_president.is_current = False
            current_president.left_office_early = True
            current_president.left_office_at = datetime.utcnow()
            current_president.left_office_reason = 'country_conquered'

            create_alert(
                user=current_president.user,
                alert_type=AlertType.GOVERNMENT,
                title="Presidency Lost - Country Conquered",
                content=f"You have lost your position as President because your country was conquered."
            )
            logger.info(f"[Conquest] Removed president: {current_president.user.username}")

        # Clear congress
        congress_members = CongressMember.query.filter_by(
            country_id=country_id,
            is_current=True
        ).all()

        for member in congress_members:
            member.is_current = False
            member.left_seat_early = True
            member.left_seat_at = datetime.utcnow()
            member.left_seat_reason = 'country_conquered'

            create_alert(
                user=member.user,
                alert_type=AlertType.GOVERNMENT,
                title="Congress Seat Lost - Country Conquered",
                content=f"You have lost your Congress seat because your country was conquered."
            )

        logger.info(f"[Conquest] Removed {len(congress_members)} congress members")

        # Clear ministers
        ministers = Minister.query.filter_by(
            country_id=country_id,
            is_active=True
        ).all()

        for minister in ministers:
            minister.is_active = False
            minister.resigned_at = datetime.utcnow()

            create_alert(
                user=minister.user,
                alert_type=AlertType.GOVERNMENT,
                title="Ministry Position Lost - Country Conquered",
                content=f"You have lost your Minister position because your country was conquered."
            )

        logger.info(f"[Conquest] Removed {len(ministers)} ministers")

    @staticmethod
    def _reject_pending_laws(country_id: int):
        """Reject all pending laws and release reserved funds."""
        from app.models.government import Law, LawStatus
        from app.models.location import Country

        pending_laws = Law.query.filter_by(
            country_id=country_id,
            status=LawStatus.VOTING
        ).all()

        country = db.session.get(Country, country_id)

        for law in pending_laws:
            law.status = LawStatus.REJECTED
            law.passed = False
            law.result_calculated_at = datetime.utcnow()

            # Release reserved gold/currency
            if law.law_details:
                reserved_gold = Decimal(str(law.law_details.get('reserved_gold', 0)))
                reserved_currency = Decimal(str(law.law_details.get('reserved_currency', 0)))

                if reserved_gold > 0 and country:
                    country.reserved_gold = max(Decimal('0'), (country.reserved_gold or Decimal('0')) - reserved_gold)

                if reserved_currency > 0 and country:
                    country.reserved_currency = max(Decimal('0'), (country.reserved_currency or Decimal('0')) - reserved_currency)

        logger.info(f"[Conquest] Rejected {len(pending_laws)} pending laws")

    @staticmethod
    def _cancel_elections(country_id: int):
        """Cancel all ongoing elections."""
        from app.models.government import GovernmentElection, GovernmentElectionStatus

        active_elections = GovernmentElection.query.filter(
            GovernmentElection.country_id == country_id,
            GovernmentElection.status.in_([
                GovernmentElectionStatus.NOMINATIONS,
                GovernmentElectionStatus.APPLICATIONS,
                GovernmentElectionStatus.VOTING
            ])
        ).all()

        for election in active_elections:
            election.status = GovernmentElectionStatus.CANCELLED

        logger.info(f"[Conquest] Cancelled {len(active_elections)} elections")

    @staticmethod
    def _kick_from_alliance(country_id: int):
        """Remove country from any alliance it's a member of."""
        from app.models.alliance import AllianceMembership

        membership = AllianceMembership.query.filter_by(
            country_id=country_id,
            is_active=True
        ).first()

        if membership:
            alliance_name = membership.alliance.name
            membership.leave(reason='country_conquered')
            logger.info(f"[Conquest] Removed country from alliance: {alliance_name}")

    @staticmethod
    def _send_conquest_alerts(conquered, conqueror):
        """Send alerts to all citizens of conquered country."""
        from app.alert_helpers import create_alert
        from app.models.activity import AlertType

        for citizen in conquered.citizens.all():
            create_alert(
                user=citizen,
                alert_type=AlertType.GOVERNMENT,
                title="Your Country Has Been Conquered",
                content=f"{conquered.name} has been fully conquered by {conqueror.name}. Your political rights are suspended until liberation."
            )

    @staticmethod
    def liberate_country(country_id: int, liberator_user_id: Optional[int] = None) -> bool:
        """
        Liberate a conquered country.

        Args:
            country_id: ID of the country being liberated
            liberator_user_id: ID of the user who started the successful resistance war

        Returns:
            True if liberation was successful
        """
        from app.models.location import Country
        from app.models.user import User
        from app.models.government import CountryPresident

        try:
            country = db.session.scalar(
                select(Country).where(Country.id == country_id).with_for_update()
            )

            if not country:
                logger.error(f"[Liberation] Country {country_id} not found")
                return False

            if not country.is_conquered:
                logger.warning(f"[Liberation] {country.name} is not conquered")
                return False

            conqueror_name = country.conquered_by.name if country.conquered_by else "unknown"
            logger.info(f"[Liberation] Starting liberation of {country.name} from {conqueror_name}")

            # 1. Mark country as not conquered
            country.is_conquered = False
            country.conquered_by_id = None
            country.conquered_at = None

            # 2. Unfreeze all companies
            ConquestService._unfreeze_companies(country_id)

            # 3. Handle president assignment
            if liberator_user_id:
                liberator = db.session.get(User, liberator_user_id)
                if liberator and liberator.citizenship_id == country_id:
                    # Liberator is citizen of this country - make them president
                    ConquestService._assign_liberator_as_president(country_id, liberator)
                    logger.info(f"[Liberation] {liberator.username} assigned as President")
                else:
                    logger.info(f"[Liberation] Liberator is not citizen of {country.name}, government remains empty")
            else:
                logger.info(f"[Liberation] No liberator specified, government remains empty")

            # 4. Send liberation alerts
            ConquestService._send_liberation_alerts(country)

            db.session.commit()
            logger.info(f"[Liberation] {country.name} has been liberated!")
            return True

        except Exception as e:
            db.session.rollback()
            logger.error(f"[Liberation] Error during liberation: {str(e)}")
            raise

    @staticmethod
    def _unfreeze_companies(country_id: int):
        """Unfreeze all companies in the country."""
        from app.models.company import Company
        from app.alert_helpers import create_alert
        from app.models.activity import AlertType

        companies = Company.query.filter_by(
            country_id=country_id,
            is_frozen=True,
            is_deleted=False
        ).all()

        for company in companies:
            company.unfreeze()

            # Alert owner
            create_alert(
                user=company.owner,
                alert_type=AlertType.COMPANY,
                title="Company Operations Restored",
                content=f"Your company {company.name} can now resume operations. Your country has been liberated!"
            )

        logger.info(f"[Liberation] Unfroze {len(companies)} companies")

    @staticmethod
    def _assign_liberator_as_president(country_id: int, liberator):
        """Assign the liberator as president of the liberated country."""
        from app.models.government import CountryPresident
        from app.alert_helpers import create_alert
        from app.models.activity import AlertType

        # Create new president record
        new_president = CountryPresident(
            country_id=country_id,
            user_id=liberator.id,
            election_id=None,  # Not elected, assigned as liberator
            term_start=datetime.utcnow(),
            term_end=datetime.utcnow() + timedelta(days=30),  # 30-day term
            is_current=True,
            became_president_via='liberation'
        )
        db.session.add(new_president)

        # Alert the liberator
        create_alert(
            user=liberator,
            alert_type=AlertType.GOVERNMENT,
            title="You Are Now President!",
            content=f"As the liberator of your country, you have been appointed as President. Lead your people to recovery!"
        )

    @staticmethod
    def _send_liberation_alerts(country):
        """Send alerts to all citizens of liberated country."""
        from app.alert_helpers import create_alert
        from app.models.activity import AlertType

        for citizen in country.citizens.all():
            create_alert(
                user=citizen,
                alert_type=AlertType.GOVERNMENT,
                title="Your Country Has Been Liberated!",
                content=f"{country.name} has been liberated! Your political rights have been restored."
            )


# Import timedelta at module level for use in _assign_liberator_as_president
from datetime import timedelta
