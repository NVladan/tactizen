# app/cli.py
"""
Flask CLI commands for manual election management and testing.
"""

import click
from flask import current_app
from app.extensions import db
from app.models import PoliticalParty, PartyElection, ElectionStatus, User
from app.scheduler import (
    check_and_create_elections,
    check_and_start_elections,
    check_and_end_elections,
    get_next_election_dates
)
from app.services.nft_service import NFTService


def register_cli_commands(app):
    """Register CLI commands with the Flask app."""

    @app.cli.command('seed-resistance-achievements')
    def seed_resistance_achievements_command():
        """Seed resistance war achievements into the database."""
        from app.models.achievement import Achievement

        with app.app_context():
            achievements = [
                {
                    'code': 'resistance_hero_10',
                    'name': 'Resistance Hero',
                    'description': 'Successfully start and win 10 resistance wars to liberate occupied territories.',
                    'category': 'combat',
                    'icon': 'fa-fist-raised',
                    'gold_reward': 50,
                    'free_nft_reward': 1,
                    'requirement_value': 10,
                    'is_active': True
                },
                {
                    'code': 'resistance_hero_100',
                    'name': 'Resistance Legend',
                    'description': 'Successfully start and win 100 resistance wars. A true liberator of nations!',
                    'category': 'combat',
                    'icon': 'fa-star',
                    'gold_reward': 500,
                    'free_nft_reward': 3,
                    'requirement_value': 100,
                    'is_active': True
                }
            ]

            for ach_data in achievements:
                existing = db.session.scalar(
                    db.select(Achievement).where(Achievement.code == ach_data['code'])
                )
                if existing:
                    click.echo(f"Achievement '{ach_data['code']}' already exists, skipping...")
                    continue

                achievement = Achievement(**ach_data)
                db.session.add(achievement)
                click.echo(f"Added achievement: {ach_data['name']} ({ach_data['code']})")

            db.session.commit()
            click.echo('Resistance achievements seeded successfully!')

    @app.cli.command('create-elections')
    def create_elections_command():
        """Manually create elections for all parties."""
        click.echo('Creating elections for all parties...')
        check_and_create_elections(app)
        click.echo('Done!')

    @app.cli.command('start-elections')
    def start_elections_command():
        """Manually start scheduled elections whose time has come."""
        click.echo('Starting scheduled elections...')
        check_and_start_elections(app)
        click.echo('Done!')

    @app.cli.command('end-elections')
    def end_elections_command():
        """Manually end active elections and calculate winners."""
        click.echo('Ending active elections...')
        check_and_end_elections(app)
        click.echo('Done!')

    @app.cli.command('election-status')
    def election_status_command():
        """Show status of all elections."""
        click.echo('Election Status Report')
        click.echo('=' * 60)

        with app.app_context():
            # Show next election dates
            start_time, end_time = get_next_election_dates()
            click.echo(f'\nNext election period:')
            click.echo(f'  Start: {start_time} UTC')
            click.echo(f'  End:   {end_time} UTC')

            # Show scheduled elections
            scheduled = db.session.scalars(
                db.select(PartyElection)
                .where(PartyElection.status == ElectionStatus.SCHEDULED)
            ).all()

            click.echo(f'\nScheduled Elections: {len(scheduled)}')
            for election in scheduled[:5]:  # Show first 5
                party = db.session.get(PoliticalParty, election.party_id)
                click.echo(f'  - Party: {party.name if party else "Unknown"} '
                          f'(ID: {election.party_id}) | '
                          f'Start: {election.start_time}')

            # Show active elections
            active = db.session.scalars(
                db.select(PartyElection)
                .where(PartyElection.status == ElectionStatus.ACTIVE)
            ).all()

            click.echo(f'\nActive Elections: {len(active)}')
            for election in active[:5]:  # Show first 5
                party = db.session.get(PoliticalParty, election.party_id)
                click.echo(f'  - Party: {party.name if party else "Unknown"} '
                          f'(ID: {election.party_id}) | '
                          f'Votes: {election.get_vote_count()} | '
                          f'Candidates: {election.get_candidate_count()}')

            # Show recently completed elections
            completed = db.session.scalars(
                db.select(PartyElection)
                .where(PartyElection.status == ElectionStatus.COMPLETED)
                .order_by(PartyElection.end_time.desc())
                .limit(5)
            ).all()

            click.echo(f'\nRecently Completed Elections: {len(completed)}')
            for election in completed:
                party = db.session.get(PoliticalParty, election.party_id)
                winner_text = f'Winner: User {election.winner_id}' if election.winner_id else 'No winner'
                click.echo(f'  - Party: {party.name if party else "Unknown"} '
                          f'(ID: {election.party_id}) | '
                          f'{winner_text}')

        click.echo('\n' + '=' * 60)

    @app.cli.command('mint-nft')
    @click.option('--user-id', '-u', type=int, required=True, help='User ID to mint NFT for')
    @click.option('--tier', '-t', type=int, default=1, help='NFT tier (1-5), default: 1')
    @click.option('--type', '-T', default='player', help='NFT type (player/company), default: player')
    @click.option('--category', '-c', default=None, help='NFT category (optional, random if not specified)')
    @click.option('--count', '-n', type=int, default=1, help='Number of NFTs to mint, default: 1')
    def mint_nft_command(user_id, tier, type, category, count):
        """Mint test NFTs for a user."""
        with app.app_context():
            # Verify user exists
            user = db.session.get(User, user_id)
            if not user:
                click.echo(f'Error: User with ID {user_id} not found!')
                return

            click.echo(f'Minting {count} NFT(s) for user: {user.username} (ID: {user_id})')
            click.echo(f'Tier: Q{tier}, Type: {type}, Category: {category or "random"}')
            click.echo('-' * 60)

            minted_nfts = []
            errors = []

            for i in range(count):
                nft, error = NFTService.mint_nft_direct(
                    user_id=user_id,
                    tier=tier,
                    nft_type=type,
                    category=category
                )

                if nft:
                    minted_nfts.append(nft)
                    click.echo(f'[OK] Minted NFT #{nft.id}: {nft.nft_type} - {nft.category} Q{nft.tier} (+{nft.bonus_value}% bonus)')
                else:
                    errors.append(error)
                    click.echo(f'[ERROR] Failed to mint NFT: {error}')

            click.echo('-' * 60)
            click.echo(f'Successfully minted: {len(minted_nfts)}/{count}')
            if errors:
                click.echo(f'Errors: {len(errors)}')

    @app.cli.command('list-nfts')
    @click.option('--user-id', '-u', type=int, required=True, help='User ID to list NFTs for')
    def list_nfts_command(user_id):
        """List all NFTs owned by a user."""
        with app.app_context():
            user = db.session.get(User, user_id)
            if not user:
                click.echo(f'Error: User with ID {user_id} not found!')
                return

            nfts = NFTService.get_user_nfts(user_id)

            click.echo(f'NFT Inventory for: {user.username} (ID: {user_id})')
            click.echo('=' * 80)

            if not nfts:
                click.echo('No NFTs found.')
                return

            # Group by type
            player_nfts = [n for n in nfts if n.nft_type == 'player']
            company_nfts = [n for n in nfts if n.nft_type == 'company']

            click.echo(f'\nPlayer NFTs ({len(player_nfts)}):')
            click.echo('-' * 80)
            for nft in player_nfts:
                equipped = '[EQUIPPED]' if nft.is_equipped else ''
                click.echo(f'  ID: {nft.id:4d} | Q{nft.tier} | {nft.category:20s} | +{nft.bonus_value:3d}% | {equipped}')

            click.echo(f'\nCompany NFTs ({len(company_nfts)}):')
            click.echo('-' * 80)
            for nft in company_nfts:
                equipped = '[EQUIPPED]' if nft.is_equipped else ''
                click.echo(f'  ID: {nft.id:4d} | Q{nft.tier} | {nft.category:20s} | +{nft.bonus_value:3d}% | {equipped}')

            click.echo('\n' + '=' * 80)
            click.echo(f'Total NFTs: {len(nfts)}')

    @app.cli.command('fix-battle')
    @click.option('--battle-id', '-b', type=int, required=True, help='Battle ID to fix')
    def fix_battle_command(battle_id):
        """Fix a battle that failed to complete properly (region capture + initiative)."""
        with app.app_context():
            from app.models import Battle
            from app.models.battle import BattleStatus
            from app.services.battle_service import BattleService

            battle = db.session.get(Battle, battle_id)
            if not battle:
                click.echo(f'Error: Battle with ID {battle_id} not found!')
                return

            click.echo(f'Battle ID: {battle.id}')
            click.echo(f'Region: {battle.region.name if battle.region else "Unknown"}')
            click.echo(f'Status: {battle.status.value}')
            click.echo(f'Attacker rounds won: {battle.attacker_rounds_won}')
            click.echo(f'Defender rounds won: {battle.defender_rounds_won}')

            war = battle.war
            if not war:
                click.echo('Error: No war associated with this battle!')
                return

            click.echo(f'War: {war.attacker_country.name} vs {war.defender_country.name}')
            click.echo(f'Current region owner(s): {[c.name for c in battle.region.current_owners]}')
            click.echo('-' * 60)

            # Check if attacker won
            if battle.status == BattleStatus.ATTACKER_WON:
                click.echo('Battle was won by attacker. Applying region capture and initiative...')

                # Capture region
                BattleService.capture_region(battle)
                click.echo(f'Region captured! New owner(s): {[c.name for c in battle.region.current_owners]}')

                # Set initiative
                war.set_initiative(war.attacker_country_id)
                click.echo(f'Initiative set to: {war.attacker_country.name} (expires: {war.initiative_expires_at})')

                db.session.commit()
                click.echo('Done! Battle fixed successfully.')

            elif battle.status == BattleStatus.DEFENDER_WON:
                click.echo('Battle was won by defender. Applying initiative...')

                # Set initiative
                war.set_initiative(war.defender_country_id)
                click.echo(f'Initiative set to: {war.defender_country.name} (expires: {war.initiative_expires_at})')

                db.session.commit()
                click.echo('Done! Battle fixed successfully.')

            else:
                click.echo(f'Battle status is {battle.status.value}, not ATTACKER_WON or DEFENDER_WON. Cannot fix.')

    @app.cli.command('list-battles')
    @click.option('--limit', '-l', type=int, default=10, help='Number of battles to show')
    def list_battles_command(limit):
        """List recent battles."""
        with app.app_context():
            from app.models import Battle

            battles = db.session.scalars(
                db.select(Battle).order_by(Battle.id.desc()).limit(limit)
            ).all()

            click.echo(f'Recent Battles (last {limit}):')
            click.echo('=' * 80)

            for battle in battles:
                region_name = battle.region.name if battle.region else 'Unknown'
                war = battle.war
                attacker = war.attacker_country.name if war else 'Unknown'
                defender = war.defender_country.name if war else 'Unknown'
                click.echo(f'ID: {battle.id:4d} | {region_name:25s} | {battle.status.value:15s} | {attacker} vs {defender}')

    @app.cli.command('seed-missions')
    def seed_missions_command():
        """Seed initial missions into the database."""
        from seed_missions import seed_missions as do_seed_missions

        with app.app_context():
            click.echo('Seeding missions...')
            created, updated = do_seed_missions()
            click.echo(f'Done! Created: {created}, Updated: {updated}')

    @app.cli.command('fix-battle-rounds')
    @click.option('--battle-id', '-b', type=int, default=None, help='Battle ID to fix (or all active battles if not specified)')
    def fix_battle_rounds_command(battle_id):
        """Fix battle rounds where round end time exceeds battle end time."""
        with app.app_context():
            from app.models import Battle, BattleRound
            from app.models.battle import BattleStatus, RoundStatus

            if battle_id:
                battles = [db.session.get(Battle, battle_id)]
                if not battles[0]:
                    click.echo(f'Error: Battle with ID {battle_id} not found!')
                    return
            else:
                battles = db.session.scalars(
                    db.select(Battle).where(Battle.status == BattleStatus.ACTIVE)
                ).all()

            click.echo(f'Checking {len(battles)} battle(s) for round timing issues...')
            click.echo('=' * 80)

            fixed_count = 0
            for battle in battles:
                if not battle.ends_at:
                    continue

                current_round = battle.get_current_round()
                if not current_round or not current_round.ends_at:
                    continue

                region_name = battle.region.name if battle.region else 'Unknown'
                click.echo(f'\nBattle {battle.id}: {region_name}')
                click.echo(f'  Battle ends at: {battle.ends_at}')
                click.echo(f'  Round {current_round.round_number} ends at: {current_round.ends_at}')

                if current_round.ends_at > battle.ends_at:
                    old_end = current_round.ends_at
                    current_round.ends_at = battle.ends_at
                    click.echo(f'  [FIX] Round end time exceeded battle end time!')
                    click.echo(f'  [FIX] Changed from {old_end} to {battle.ends_at}')
                    fixed_count += 1
                else:
                    click.echo(f'  [OK] Round timing is correct')

            if fixed_count > 0:
                db.session.commit()
                click.echo(f'\n{"=" * 80}')
                click.echo(f'Fixed {fixed_count} round(s) with timing issues.')
            else:
                click.echo(f'\n{"=" * 80}')
                click.echo('No timing issues found.')

    @app.cli.command('list-elections')
    @click.option('--limit', '-l', type=int, default=10, help='Number of elections to show')
    def list_elections_command(limit):
        """List government elections."""
        with app.app_context():
            from app.models import GovernmentElection

            elections = db.session.scalars(
                db.select(GovernmentElection).order_by(GovernmentElection.id.desc()).limit(limit)
            ).all()

            click.echo(f'Government Elections (last {limit}):')
            click.echo('=' * 80)

            for e in elections:
                country_name = e.country.name if e.country else 'Unknown'
                click.echo(f'ID: {e.id:4d} | {e.election_type.value:15s} | {e.status.value:15s} | {country_name}')

    @app.cli.command('advance-election')
    @click.option('--election-id', '-e', type=int, required=True, help='Election ID to advance')
    def advance_election_command(election_id):
        """Advance an election to the next phase (for testing)."""
        with app.app_context():
            from app.models import GovernmentElection, GovernmentElectionStatus

            election = db.session.get(GovernmentElection, election_id)
            if not election:
                click.echo(f'Error: Election with ID {election_id} not found!')
                return

            status_order = [
                GovernmentElectionStatus.NOMINATIONS,
                GovernmentElectionStatus.APPLICATIONS,
                GovernmentElectionStatus.VOTING,
                GovernmentElectionStatus.COMPLETED
            ]

            current_idx = -1
            for i, s in enumerate(status_order):
                if election.status == s:
                    current_idx = i
                    break

            if current_idx == -1:
                click.echo(f'Election status {election.status.value} cannot be advanced.')
                return

            if current_idx >= len(status_order) - 1:
                click.echo('Election is already completed.')
                return

            old_status = election.status.value
            election.status = status_order[current_idx + 1]
            db.session.commit()

            click.echo(f'Election {election_id} advanced from {old_status} to {election.status.value}')

    @app.cli.command('add-test-candidate')
    @click.option('--election-id', '-e', type=int, required=True, help='Election ID')
    @click.option('--user-id', '-u', type=int, required=True, help='User ID to add as candidate')
    def add_test_candidate_command(election_id, user_id):
        """Add a test candidate to an election."""
        with app.app_context():
            from app.models import GovernmentElection, ElectionCandidate, CandidateStatus

            election = db.session.get(GovernmentElection, election_id)
            if not election:
                click.echo(f'Error: Election with ID {election_id} not found!')
                return

            user = db.session.get(User, user_id)
            if not user:
                click.echo(f'Error: User with ID {user_id} not found!')
                return

            # Check if already a candidate
            existing = db.session.scalars(
                db.select(ElectionCandidate).where(
                    ElectionCandidate.election_id == election_id,
                    ElectionCandidate.user_id == user_id
                )
            ).first()

            if existing:
                click.echo(f'User {user.username} is already a candidate (status: {existing.status.value})')
                return

            # Get user's party
            party_id = None
            if user.party_memberships:
                party_id = user.party_memberships[0].party_id

            candidate = ElectionCandidate(
                election_id=election_id,
                user_id=user_id,
                party_id=party_id,
                status=CandidateStatus.APPROVED
            )
            db.session.add(candidate)
            db.session.commit()

            click.echo(f'Added {user.username} as candidate to election {election_id}')

    @app.cli.command('reset-zk-voting')
    def reset_zk_voting_command():
        """Reset all ZK voting data (for testing after hash algorithm change)."""
        with app.app_context():
            from app.models import VoterCommitment, MerkleTree, ZKVote

            # Delete all ZK voting data
            vc_count = VoterCommitment.query.delete()
            mt_count = MerkleTree.query.delete()
            zv_count = ZKVote.query.delete()

            db.session.commit()

            click.echo(f'Deleted {vc_count} voter commitments')
            click.echo(f'Deleted {mt_count} merkle trees')
            click.echo(f'Deleted {zv_count} ZK votes')
            click.echo('Done! Users need to clear localStorage and re-register for anonymous voting.')
