from app import create_app, db
from app.models import Country, Region, country_regions
from slugify import slugify
import sys

def seed_countries():
    app = create_app()
    with app.app_context():
        countries_data = [
            ("United States", "us", "USD", [
                "New England", "New York & New Jersey", "Mid-Atlantic", "Appalachia",
                "The Carolinas", "Southeastern Coast", "Florida Panhandle & Lower Gulf",
                "Deep South Interior", "Texas", "Southern Plains", "Central Plains",
                "Great Lakes", "Upper Midwest", "Mountain West", "Southwest",
                "Pacific Coast", "Alaska", "Hawaii"
            ]),
            ("Mexico", "mx", "MXN", [
                "Northwest Mexico", "Northeast Mexico", "Central Mexico",
                "Pacific Coast and Sierra Region", "Gulf and Southeast Region",
                "Yucatán Peninsula and Southern Highlands"
            ]),
            ("Canada", "ca", "CAD", [
                "Atlantic Canada", "Quebec", "Ontario", "Prairie Provinces",
                "British Columbia", "Northern Territories"
            ])
        ]

        print("Clearing existing countries, regions, and links...")
        try:
            if db.engine.dialect.name == 'mysql':
                db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 0;"))

            db.session.execute(db.text("DELETE FROM country_regions;"))
            db.session.execute(db.text("DELETE FROM region;"))
            db.session.execute(db.text("DELETE FROM country;"))

            if db.engine.dialect.name == 'mysql':
                db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 1;"))

            db.session.commit()
            print("Existing country and region data cleared.")
        except Exception as e:
            db.session.rollback()
            print(f"Error clearing existing data: {e}")
            print("Aborting seed process.")
            sys.exit(1)

        total_regions_added = 0
        for country_name, flag_code, currency_code, region_names in countries_data:
            regions_added_this_country = 0
            print(f"Adding country: {country_name}")
            existing_country = db.session.scalar(db.select(Country).filter_by(slug=slugify(country_name)))
            if existing_country:
                print(f"  Skipping {country_name} - already exists (unexpected).")
                country = existing_country
            else:
                country = Country(
                    name=country_name,
                    flag_code=flag_code,
                    currency_code=currency_code,
                    currency_name=currency_code
                )
                db.session.add(country)
                try:
                    db.session.flush()
                except Exception as e:
                    db.session.rollback()
                    print(f"  Error flushing country {country_name}: {e}")
                    continue

            for region_name in region_names:
                existing_region = db.session.scalar(db.select(Region).filter_by(slug=slugify(region_name)))
                if existing_region:
                     print(f"    Skipping region {region_name} - already exists (unexpected).")
                else:
                    print(f"  Adding region: {region_name}")
                    region = Region(name=region_name, original_owner_id=country.id)
                    db.session.add(region)
                    try:
                        db.session.flush()
                        country.current_regions.append(region)
                        regions_added_this_country += 1
                    except Exception as e:
                         db.session.rollback()
                         print(f"    Error adding or linking region {region_name}: {e}")
                         continue

            print(f"  Added {regions_added_this_country} regions for {country_name}.")
            total_regions_added += regions_added_this_country

        try:
            db.session.commit()
            print(f"\nSuccessfully seeded {len(countries_data)} countries and {total_regions_added} regions!")
        except Exception as e:
            db.session.rollback()
            print(f"Error committing final changes: {e}")

if __name__ == "__main__":
    seed_countries()