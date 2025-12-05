"""
Generate sample historical currency price data for the past 30 days.
This script creates CurrencyPriceHistory records using the initial_exchange_rate from GoldMarket.
"""

from datetime import date, timedelta, datetime, timezone
from decimal import Decimal
from app import create_app, db
from app.models.currency_market import GoldMarket, CurrencyPriceHistory

def generate_currency_historical_prices():
    app = create_app()

    with app.app_context():
        from app.models import Country

        # Get all gold markets that have valid countries (not deleted)
        valid_country_ids = [c.id for c in Country.query.filter_by(is_deleted=False).all()]
        gold_markets = GoldMarket.query.filter(GoldMarket.country_id.in_(valid_country_ids)).all()
        print(f"Found {len(gold_markets)} currency markets for valid countries")

        # Generate data for past 30 days
        today = date.today()
        records_created = 0
        records_skipped = 0

        for gold_market in gold_markets:
            # Use the initial_exchange_rate (base rate at level 0) for all historical entries
            base_rate = gold_market.initial_exchange_rate

            for days_ago in range(30, 0, -1):
                record_date = today - timedelta(days=days_ago)

                # Check if record already exists using db.session
                existing = db.session.query(CurrencyPriceHistory).filter_by(
                    country_id=gold_market.country_id,
                    recorded_date=record_date
                ).first()

                if existing:
                    records_skipped += 1
                    continue

                # Create new price history record with OHLC data
                # For historical data, use base_rate for all OHLC values
                price_history = CurrencyPriceHistory(
                    country_id=gold_market.country_id,
                    rate_open=base_rate,
                    rate_high=base_rate,
                    rate_low=base_rate,
                    rate_close=base_rate,
                    exchange_rate=base_rate,  # Legacy field
                    recorded_date=record_date,
                    created_at=datetime.now(timezone.utc)
                )

                db.session.add(price_history)
                records_created += 1

                # Commit in batches of 50
                if records_created % 50 == 0:
                    db.session.commit()
                    print(f"Created {records_created} records...")

        # Final commit
        db.session.commit()

        print(f"\nComplete!")
        print(f"   Created: {records_created} records")
        print(f"   Skipped: {records_skipped} existing records")

if __name__ == '__main__':
    generate_currency_historical_prices()
