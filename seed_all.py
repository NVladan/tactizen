#!/usr/bin/env python3
"""
Master Seed Script for Tactizen
================================
This script seeds ALL initial data required for the game to function:
- Military Ranks (60 ranks)
- Resources (with quality flags)
- Countries and Regions
- Country Market Items (all qualities)
- Currency Markets
- Achievements
- Missions
- ZEN Market

Run this script on a fresh database after running migrations:
    python seed_all.py

Or run specific seeders:
    python seed_all.py --only military_ranks
    python seed_all.py --only resources
    python seed_all.py --skip countries
"""

import sys
import argparse
from decimal import Decimal
from datetime import datetime

from app import create_app
from app.extensions import db


def seed_military_ranks(app):
    """Seed all 60 military ranks."""
    print("\n" + "="*60)
    print("SEEDING MILITARY RANKS")
    print("="*60)

    from app.models.military_rank import MilitaryRank

    MILITARY_RANKS = [
        (1, 'Recruit', 0, 2),
        (2, 'Apprentice', 100, 4),
        (3, 'Private III', 212, 6),
        (4, 'Private II', 337, 8),
        (5, 'Private I', 477, 10),
        (6, 'Specialist III', 634, 12),
        (7, 'Specialist II', 810, 14),
        (8, 'Specialist I', 1007, 16),
        (9, 'Lance Corporal', 1228, 18),
        (10, 'Corporal', 1475, 20),
        (11, 'Senior Corporal', 1752, 22),
        (12, 'Master Corporal', 2062, 24),
        (13, 'Sergeant III', 2409, 26),
        (14, 'Sergeant II', 2798, 28),
        (15, 'Sergeant I', 3234, 30),
        (16, 'Staff Sergeant III', 3722, 32),
        (17, 'Staff Sergeant II', 4269, 34),
        (18, 'Staff Sergeant I', 4882, 36),
        (19, 'Technical Sergeant', 5568, 38),
        (20, 'Senior Sergeant', 6336, 40),
        (21, 'First Sergeant', 7197, 42),
        (22, 'Master Sergeant III', 8161, 44),
        (23, 'Master Sergeant II', 9241, 46),
        (24, 'Master Sergeant I', 10451, 48),
        (25, 'Sergeant Major', 11806, 50),
        (26, 'Command Sergeant Major', 13323, 52),
        (27, 'Sergeant Major of the Guard', 15023, 54),
        (28, 'Warrant Officer III', 16927, 56),
        (29, 'Warrant Officer II', 19059, 58),
        (30, 'Warrant Officer I', 21447, 60),
        (31, 'Chief Warrant Officer', 24121, 62),
        (32, 'Master Warrant Officer', 27116, 64),
        (33, '2nd Lieutenant', 30471, 66),
        (34, '1st Lieutenant', 34229, 68),
        (35, 'Captain III', 38438, 70),
        (36, 'Captain II', 43152, 72),
        (37, 'Captain I', 48431, 74),
        (38, 'Major III', 54344, 76),
        (39, 'Major II', 60967, 78),
        (40, 'Major I', 68384, 80),
        (41, 'Lieutenant Colonel III', 76692, 82),
        (42, 'Lieutenant Colonel II', 85997, 84),
        (43, 'Lieutenant Colonel I', 96418, 86),
        (44, 'Colonel III', 108090, 88),
        (45, 'Colonel II', 121162, 90),
        (46, 'Colonel I', 135803, 92),
        (47, 'Senior Colonel', 152201, 94),
        (48, 'Brigadier General III', 170567, 96),
        (49, 'Brigadier General II', 191137, 98),
        (50, 'Brigadier General I', 214176, 100),
        (51, 'Major General III', 239979, 102),
        (52, 'Major General II', 268879, 104),
        (53, 'Major General I', 301247, 106),
        (54, 'Lieutenant General III', 337499, 108),
        (55, 'Lieutenant General II', 378101, 110),
        (56, 'Lieutenant General I', 423576, 112),
        (57, 'General III', 474508, 114),
        (58, 'General II', 531551, 116),
        (59, 'General I', 595440, 118),
        (60, 'Field Marshal', 666995, 120),
    ]

    with app.app_context():
        existing = MilitaryRank.query.count()
        if existing > 0:
            print(f"  Military ranks already exist ({existing} ranks). Skipping.")
            return True

        for rank_id, name, xp_required, damage_bonus in MILITARY_RANKS:
            rank = MilitaryRank(
                id=rank_id,
                name=name,
                xp_required=xp_required,
                damage_bonus=damage_bonus
            )
            db.session.add(rank)

        db.session.commit()
        print(f"  ✓ Added {len(MILITARY_RANKS)} military ranks")
        return True


def seed_resources(app):
    """Seed all resources with correct quality flags."""
    print("\n" + "="*60)
    print("SEEDING RESOURCES")
    print("="*60)

    from app.models import Resource, ResourceCategory
    from slugify import slugify

    # Resources: (name, category, icon_path, can_have_quality)
    RESOURCES = [
        # Raw materials - no quality
        ('Coal', ResourceCategory.RAW_MATERIAL, 'images/resources/coal.png', False),
        ('Iron ore', ResourceCategory.RAW_MATERIAL, 'images/resources/iron-ore.png', False),
        ('Clay', ResourceCategory.RAW_MATERIAL, 'images/resources/clay.png', False),
        ('Wheat', ResourceCategory.RAW_MATERIAL, 'images/resources/wheat.png', False),
        ('Grape', ResourceCategory.RAW_MATERIAL, 'images/resources/grape.png', False),
        ('Sand', ResourceCategory.RAW_MATERIAL, 'images/resources/sand.png', False),
        ('Stone', ResourceCategory.RAW_MATERIAL, 'images/resources/stone.png', False),
        ('Oil', ResourceCategory.RAW_MATERIAL, 'images/resources/oil.png', False),

        # Manufactured goods - no quality (intermediate products)
        ('Iron Bar', ResourceCategory.MANUFACTURED_GOOD, 'images/resources/iron-bar.png', False),
        ('Steel', ResourceCategory.MANUFACTURED_GOOD, 'images/resources/steel.png', False),
        ('Bricks', ResourceCategory.CONSTRUCTION, 'images/resources/bricks.png', False),
        ('Concrete', ResourceCategory.CONSTRUCTION, 'images/resources/concrete.png', False),

        # Energy - no quality
        ('Electricity', ResourceCategory.ENERGY, 'images/resources/electricity.png', False),

        # Food - HAS quality (Q1-Q5)
        ('Beer', ResourceCategory.FOOD, 'images/resources/beer.png', True),
        ('Bread', ResourceCategory.FOOD, 'images/resources/bread.png', True),
        ('Wine', ResourceCategory.FOOD, 'images/resources/wine.png', True),

        # Weapons - HAS quality (Q1-Q5)
        ('Rifle', ResourceCategory.WEAPON, 'images/resources/rifle.png', True),
        ('Tank', ResourceCategory.WEAPON, 'images/resources/tank.png', True),
        ('Helicopter', ResourceCategory.WEAPON, 'images/resources/heli.png', True),

        # Construction buildings - HAS quality (Q1-Q5)
        ('Fort', ResourceCategory.CONSTRUCTION, 'images/resources/fort.png', True),
        ('Hospital', ResourceCategory.CONSTRUCTION, 'images/resources/hospital.png', True),
        ('House', ResourceCategory.CONSTRUCTION, 'images/resources/house.png', True),
    ]

    adjustments = {
        ResourceCategory.RAW_MATERIAL: Decimal('0.1'),
        ResourceCategory.MANUFACTURED_GOOD: Decimal('0.5'),
        ResourceCategory.FOOD: Decimal('1.0'),
        ResourceCategory.WEAPON: Decimal('1.0'),
        ResourceCategory.CONSTRUCTION: Decimal('0.5'),
        ResourceCategory.ENERGY: Decimal('0.5'),
    }

    with app.app_context():
        added = 0
        updated = 0

        for name, category, icon_path, can_have_quality in RESOURCES:
            resource_slug = slugify(name)
            adjustment = adjustments.get(category, Decimal('0.1'))

            existing = db.session.scalar(db.select(Resource).filter_by(slug=resource_slug))

            if not existing:
                resource = Resource(
                    name=name,
                    category=category,
                    icon_path=icon_path,
                    threshold=200,
                    adjustment=adjustment,
                    can_have_quality=can_have_quality
                )
                db.session.add(resource)
                added += 1
            else:
                # Update can_have_quality if it changed
                if existing.can_have_quality != can_have_quality:
                    existing.can_have_quality = can_have_quality
                    updated += 1

        db.session.commit()
        print(f"  ✓ Added {added} resources, updated {updated}")
        return True


def seed_zen_market(app):
    """Seed the ZEN/Gold exchange market."""
    print("\n" + "="*60)
    print("SEEDING ZEN MARKET")
    print("="*60)

    from app.models import ZenMarket

    with app.app_context():
        existing = db.session.scalar(db.select(ZenMarket).where(ZenMarket.id == 1))
        if existing:
            print("  ZEN Market already exists. Skipping.")
            return True

        market = ZenMarket(
            id=1,
            initial_exchange_rate=Decimal('50.00'),
            price_level=0,
            progress_within_level=0,
            volume_per_level=100,
            price_adjustment_per_level=Decimal('0.50')
        )
        db.session.add(market)
        db.session.commit()
        print("  ✓ Created ZEN Market (1 ZEN = 50 Gold base rate)")
        return True


def seed_country_market_items(app, country_names=None):
    """Seed market items for countries with all quality levels."""
    print("\n" + "="*60)
    print("SEEDING COUNTRY MARKET ITEMS")
    print("="*60)

    from app.models import Resource, Country, CountryMarketItem

    if country_names is None:
        country_names = ["United States", "Mexico", "Canada"]

    initial_price = Decimal('5.00')

    with app.app_context():
        all_resources = db.session.scalars(db.select(Resource)).all()
        if not all_resources:
            print("  ERROR: No resources found. Run resource seeding first.")
            return False

        target_countries = db.session.scalars(
            db.select(Country).filter(Country.name.in_(country_names))
        ).all()

        if not target_countries:
            print(f"  ERROR: Countries not found. Run country seeding first.")
            return False

        added = 0

        for country in target_countries:
            print(f"  Processing {country.name}...")

            for resource in all_resources:
                # Determine quality levels
                if resource.can_have_quality:
                    quality_levels = [1, 2, 3, 4, 5]
                else:
                    quality_levels = [0]

                for quality in quality_levels:
                    # Check if already exists
                    existing = db.session.scalar(
                        db.select(CountryMarketItem).filter_by(
                            country_id=country.id,
                            resource_id=resource.id,
                            quality=quality
                        )
                    )

                    if existing:
                        continue

                    # Calculate price with exponential quality scaling
                    if quality > 0:
                        quality_multiplier = Decimal(2 ** (quality - 1))
                    else:
                        quality_multiplier = Decimal('1.0')

                    # Special pricing for construction
                    if resource.name == 'House':
                        adjusted_price = Decimal('50.00') * quality_multiplier
                    elif resource.name in ['Fort', 'Hospital']:
                        adjusted_price = Decimal('100.00') * quality_multiplier
                    else:
                        adjusted_price = initial_price * quality_multiplier

                    market_item = CountryMarketItem(
                        country_id=country.id,
                        resource_id=resource.id,
                        quality=quality,
                        initial_price=adjusted_price,
                        price_level=0,
                        progress_within_level=0
                    )
                    db.session.add(market_item)
                    added += 1

        db.session.commit()
        print(f"  ✓ Added {added} market items")
        return True


def run_existing_seeders(app):
    """Run existing seed scripts."""
    import subprocess
    import os

    scripts = [
        ('seed_countries.py', 'Countries and Regions'),
        ('seed_achievements.py', 'Achievements'),
        ('seed_missions.py', 'Missions'),
        ('seed_currency_markets.py', 'Currency Markets'),
    ]

    for script, description in scripts:
        script_path = os.path.join(os.path.dirname(__file__), script)
        if os.path.exists(script_path):
            print(f"\n" + "="*60)
            print(f"RUNNING: {description}")
            print("="*60)
            result = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  ✓ {description} seeded successfully")
            else:
                print(f"  ✗ {description} failed:")
                print(result.stderr)
        else:
            print(f"  Skipping {script} (not found)")


def main():
    parser = argparse.ArgumentParser(description='Seed Tactizen database')
    parser.add_argument('--only', help='Only run specific seeder (military_ranks, resources, zen_market, market_items)')
    parser.add_argument('--skip', help='Skip specific seeder', action='append', default=[])
    parser.add_argument('--skip-existing', help='Skip running existing seed scripts', action='store_true')
    args = parser.parse_args()

    print("\n" + "="*60)
    print("   TACTIZEN MASTER SEED SCRIPT")
    print("="*60)

    app = create_app()

    seeders = [
        ('military_ranks', seed_military_ranks),
        ('resources', seed_resources),
        ('zen_market', seed_zen_market),
    ]

    if args.only:
        seeders = [(name, func) for name, func in seeders if name == args.only]
        if not seeders:
            print(f"Unknown seeder: {args.only}")
            sys.exit(1)

    # Run seeders
    for name, func in seeders:
        if name in args.skip:
            print(f"\nSkipping {name}...")
            continue
        func(app)

    # Run existing seed scripts (countries, achievements, etc.)
    if not args.skip_existing and not args.only:
        run_existing_seeders(app)

    # Seed market items after countries and resources are done
    if 'market_items' not in args.skip and not args.only:
        seed_country_market_items(app)

    print("\n" + "="*60)
    print("   SEEDING COMPLETE!")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()
