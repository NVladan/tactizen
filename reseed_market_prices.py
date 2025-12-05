"""
Reseed script to reset all market prices to new exponential pricing.

This script will:
1. Reset all market items to price_level=0 and progress=0
2. Apply new exponential initial prices:
   - Regular items: Q1=5, Q2=10, Q3=20, Q4=40, Q5=80
   - House: Q1=50, Q2=100, Q3=200, Q4=400, Q5=800
   - Fort/Hospital: Q1=100, Q2=200, Q3=400, Q4=800, Q5=1600

Run with: python reseed_market_prices.py
"""

import sys
import os
from decimal import Decimal

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.resource import Resource, CountryMarketItem


def get_new_price(resource_name, quality):
    """Calculate new exponential price for a resource at given quality."""
    # Base exponential multiplier: Q1=1, Q2=2, Q3=4, Q4=8, Q5=16
    if quality > 0:
        quality_multiplier = Decimal(2 ** (quality - 1))
    else:
        quality_multiplier = Decimal('1.0')

    # Special pricing for construction items
    if resource_name == 'House':
        # House: 10x base price (50, 100, 200, 400, 800)
        base_price = Decimal('50.00')
    elif resource_name in ['Fort', 'Hospital']:
        # Fort/Hospital: 20x base price (100, 200, 400, 800, 1600)
        base_price = Decimal('100.00')
    else:
        # Regular items: base 5
        base_price = Decimal('5.00')

    return base_price * quality_multiplier


def reseed_market_prices():
    """Reset all market prices to new exponential values."""
    print("=" * 60)
    print("RESEEDING MARKET PRICES")
    print("=" * 60)

    # Get all market items
    market_items = db.session.query(CountryMarketItem).all()
    print(f"Found {len(market_items)} market items to update")

    # Build resource ID to name mapping
    resources = db.session.query(Resource).all()
    resource_map = {r.id: r.name for r in resources}

    updated_count = 0
    price_changes = {}

    for item in market_items:
        resource_name = resource_map.get(item.resource_id, 'Unknown')
        old_price = item.initial_price
        new_price = get_new_price(resource_name, item.quality)

        # Track price changes for summary
        key = f"{resource_name} Q{item.quality}"
        if key not in price_changes:
            price_changes[key] = {'old': old_price, 'new': new_price}

        # Update the market item
        item.initial_price = new_price
        item.price_level = 0
        item.progress_within_level = 0
        updated_count += 1

    # Commit all changes
    db.session.commit()

    # Print summary
    print("\n" + "=" * 60)
    print("PRICE CHANGES SUMMARY")
    print("=" * 60)
    print(f"{'Item':<30} {'Old Price':>12} {'New Price':>12}")
    print("-" * 60)

    for key in sorted(price_changes.keys()):
        old = price_changes[key]['old']
        new = price_changes[key]['new']
        print(f"{key:<30} {float(old):>12.2f} {float(new):>12.2f}")

    print("-" * 60)
    print(f"\nTotal market items updated: {updated_count}")
    print("All price levels and progress reset to 0")
    print("=" * 60)

    return updated_count


def main():
    """Run the reseed script."""
    app = create_app()
    with app.app_context():
        count = reseed_market_prices()
        print(f"\nDone! Updated {count} market items.")


if __name__ == '__main__':
    main()
