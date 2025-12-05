# tactizen/seed_currency_markets.py
from app import create_app, db
# Ensure this now imports Country from the correct consolidated model source implicitly via app.models
from app.models import Country, GoldMarket
from decimal import Decimal

def seed_gold_markets(app):
    print("--- Seeding Gold Markets ---")
    with app.app_context():
        # --- Removed db.configure_mappers() ---

        # --- Proceed with seeding logic ---
        countries = db.session.scalars(db.select(Country)).all()
        if not countries:
            print("  No countries found. Please seed countries first.")
            return

        added_count = 0
        skipped_count = 0
        updated_count = 0

        for country in countries:
            # Check using the relationship directly (if it exists and is None)
            # or query separately if preferred
            # existing_gold_market = country.gold_market # Easier if relationship works

            # Querying separately is safer during initial setup/debugging
            existing_gold_market = db.session.scalar(
                db.select(GoldMarket).filter_by(country_id=country.id)
            )

            if not existing_gold_market:
                gold_market = GoldMarket(
                    country_id=country.id, # Or country=country if using relationship assignment
                    initial_exchange_rate=Decimal('100.00'),
                    price_level=0,
                    progress_within_level=0,
                    volume_per_level=1000,
                    price_adjustment_per_level=Decimal('1.00')
                )
                db.session.add(gold_market)
                print(f"  Adding Gold Market for: {country.name}")
                added_count += 1
            else:
                 # Optional: Update existing settings if needed
                needs_update = False
                if existing_gold_market.initial_exchange_rate != Decimal('100.00'):
                     existing_gold_market.initial_exchange_rate = Decimal('100.00')
                     needs_update = True
                if existing_gold_market.volume_per_level != 1000:
                     existing_gold_market.volume_per_level = 1000
                     needs_update = True
                if existing_gold_market.price_adjustment_per_level != Decimal('1.00'):
                    existing_gold_market.price_adjustment_per_level = Decimal('1.00')
                    needs_update = True

                if needs_update:
                    print(f"  Updating existing Gold Market for: {country.name}")
                    updated_count += 1
                else:
                    print(f"  Gold Market already exists and is up-to-date for: {country.name}. Skipping.")
                    skipped_count +=1

        if added_count > 0 or updated_count > 0:
            try:
                db.session.commit()
                print(f"\nSuccessfully committed changes. Added: {added_count}, Updated: {updated_count}.")
            except Exception as e:
                db.session.rollback()
                print(f"\nError committing gold markets: {e}")
        else:
            print("\nNo new or updated gold markets to commit.")

        if skipped_count > 0:
            print(f"Skipped {skipped_count} existing gold markets.")


if __name__ == "__main__":
    flask_app = create_app()
    seed_gold_markets(flask_app)
    print("\n--- Gold Market Seeding Finished ---")