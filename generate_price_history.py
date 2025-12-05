"""
Generate sample historical price data for the past 30 days.
This script creates MarketPriceHistory records using the initial_price from CountryMarketItem.
"""

from datetime import date, timedelta, datetime, timezone
from decimal import Decimal
from app import create_app, db
from app.models.resource import CountryMarketItem, MarketPriceHistory

def generate_historical_prices():
    app = create_app()

    with app.app_context():
        from app.models import Country

        # Get all market items that have valid countries (not deleted)
        valid_country_ids = [c.id for c in Country.query.filter_by(is_deleted=False).all()]
        market_items = CountryMarketItem.query.filter(CountryMarketItem.country_id.in_(valid_country_ids)).all()
        print(f"Found {len(market_items)} market items for valid countries")

        # Generate data for past 30 days
        today = date.today()
        records_created = 0
        records_skipped = 0

        for market_item in market_items:
            # Use the initial_price (base price at level 0) for all historical entries
            base_price = market_item.initial_price

            for days_ago in range(30, 0, -1):
                record_date = today - timedelta(days=days_ago)

                # Check if record already exists using db.session
                existing = db.session.query(MarketPriceHistory).filter_by(
                    country_id=market_item.country_id,
                    resource_id=market_item.resource_id,
                    quality=market_item.quality,
                    recorded_date=record_date
                ).first()

                if existing:
                    records_skipped += 1
                    continue

                # Create new price history record with OHLC data
                # For historical data, use base_price for all OHLC values
                price_history = MarketPriceHistory(
                    country_id=market_item.country_id,
                    resource_id=market_item.resource_id,
                    quality=market_item.quality,
                    price_open=base_price,
                    price_high=base_price,
                    price_low=base_price,
                    price_close=base_price,
                    price=base_price,  # Legacy field
                    recorded_date=record_date,
                    created_at=datetime.now(timezone.utc)
                )

                db.session.add(price_history)
                records_created += 1

                # Commit in batches of 100
                if records_created % 100 == 0:
                    db.session.commit()
                    print(f"Created {records_created} records...")

        # Final commit
        db.session.commit()

        print(f"\nComplete!")
        print(f"   Created: {records_created} records")
        print(f"   Skipped: {records_skipped} existing records")

if __name__ == '__main__':
    generate_historical_prices()
