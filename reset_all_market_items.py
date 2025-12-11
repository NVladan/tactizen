"""
Reset ALL CountryMarketItem entries for ALL countries and ALL quality levels.
This script will:
1. Delete all existing CountryMarketItem entries
2. Recreate them fresh for every country x resource x quality combination

Usage:
    python reset_all_market_items.py
"""

from app import create_app, db
from app.models import Country, Resource, CountryMarketItem
from decimal import Decimal
import sys

# Fix console encoding for Windows
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def reset_all_market_items(app):
    """Delete all market items and recreate them fresh."""

    print("=" * 60)
    print("RESET ALL MARKET ITEMS")
    print("=" * 60)

    initial_price = Decimal('5.00')

    with app.app_context():
        # Step 1: Count existing items
        existing_count = db.session.scalar(
            db.select(db.func.count()).select_from(CountryMarketItem)
        )
        print(f"\nExisting market items: {existing_count}")

        # Step 2: Delete ALL existing market items
        print("\nDeleting all existing market items...")
        db.session.execute(db.delete(CountryMarketItem))
        db.session.commit()
        print("  All market items deleted.")

        # Step 3: Get all countries and resources
        all_countries = db.session.scalars(db.select(Country)).all()
        all_resources = db.session.scalars(db.select(Resource)).all()

        print(f"\nCountries found: {len(all_countries)}")
        print(f"Resources found: {len(all_resources)}")

        if not all_countries:
            print("ERROR: No countries found in database!")
            return False

        if not all_resources:
            print("ERROR: No resources found in database!")
            return False

        # Step 4: Create new market items for ALL countries x resources x qualities
        print("\nCreating new market items...")
        added_count = 0

        for country in all_countries:
            print(f"  Processing: {country.name}...", end="")
            country_items = 0

            for resource in all_resources:
                # Determine quality levels based on resource type
                if resource.can_have_quality:
                    quality_levels = [1, 2, 3, 4, 5]
                else:
                    quality_levels = [0]

                for quality in quality_levels:
                    # Calculate quality-adjusted price using EXPONENTIAL scaling
                    # Q1=base, Q2=2x, Q3=4x, Q4=8x, Q5=16x
                    if quality > 0:
                        quality_multiplier = Decimal(2 ** (quality - 1))  # 1, 2, 4, 8, 16
                    else:
                        quality_multiplier = Decimal('1.0')

                    # Special pricing for construction items (House, Fort, Hospital)
                    if resource.name == 'House':
                        # House: 10x base price (50, 100, 200, 400, 800)
                        base_construction_price = Decimal('50.00')
                        adjusted_price = base_construction_price * quality_multiplier
                    elif resource.name in ['Fort', 'Hospital']:
                        # Fort/Hospital: 20x base price (100, 200, 400, 800, 1600)
                        base_construction_price = Decimal('100.00')
                        adjusted_price = base_construction_price * quality_multiplier
                    else:
                        # Regular items: exponential from base 5
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
                    added_count += 1
                    country_items += 1

            print(f" {country_items} items")

        # Step 5: Commit all new items
        try:
            db.session.commit()
            print(f"\n{'=' * 60}")
            print(f"SUCCESS! Created {added_count} market items")
            print(f"{'=' * 60}")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"\nERROR during commit: {e}")
            return False


if __name__ == "__main__":
    print("\nThis will DELETE all existing market items and recreate them fresh.")
    print("This affects ALL countries and ALL products for ALL quality levels.\n")

    confirm = input("Are you sure you want to continue? (yes/no): ").strip().lower()

    if confirm != "yes":
        print("Aborted.")
        sys.exit(0)

    flask_app = create_app()

    if reset_all_market_items(flask_app):
        print("\nMarket items reset successfully!")
    else:
        print("\nFailed to reset market items.")
        sys.exit(1)
