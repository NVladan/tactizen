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
