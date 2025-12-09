from app import create_app, db
from app.models import Resource, ResourceCategory, Country, CountryMarketItem
from slugify import slugify
from decimal import Decimal, InvalidOperation
import sys

def seed_global_resources(app):
    print("--- Seeding Global Resources ---")
    adjustments = {
        ResourceCategory.RAW_MATERIAL: Decimal('0.1'),
        ResourceCategory.MANUFACTURED_GOOD: Decimal('0.5'),
        ResourceCategory.FOOD: Decimal('1.0'),
        ResourceCategory.WEAPON: Decimal('1.0'),
        ResourceCategory.CONSTRUCTION: Decimal('0.5'),
        ResourceCategory.ENERGY: Decimal('0.5'),
    }
    default_volume_per_level = 200

    # Resources: (name, category, icon_path, can_have_quality)
    resources_to_add_data = [
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
        # Construction materials - no quality (intermediate)
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

    added_count = 0
    skipped_count = 0
    updated_count = 0
    resources_committed = False

    with app.app_context():
        for name, category, icon_path, can_have_quality in resources_to_add_data:
            resource_slug = slugify(name)
            adjustment = adjustments.get(category, Decimal('0.1'))
            existing_resource = db.session.scalar(db.select(Resource).filter_by(slug=resource_slug))

            if not existing_resource:
                resource = Resource(
                    name=name,
                    category=category,
                    icon_path=icon_path,
                    threshold=default_volume_per_level,
                    adjustment=adjustment,
                    can_have_quality=can_have_quality
                )
                db.session.add(resource)
                print(f"  Adding Resource: {resource.name} (quality={can_have_quality})")
                added_count += 1
            else:
                updated = False
                if existing_resource.market_volume_threshold != default_volume_per_level:
                    existing_resource.market_volume_threshold = default_volume_per_level
                    updated = True
                # Update can_have_quality if it changed
                if existing_resource.can_have_quality != can_have_quality:
                    existing_resource.can_have_quality = can_have_quality
                    updated = True
                    print(f"  Updating Resource: {existing_resource.name} can_have_quality -> {can_have_quality}")
                if updated:
                    updated_count += 1
                else:
                    skipped_count += 1

        try:
            db.session.commit()
            print(f"\nResource commit successful. Added: {added_count}, Updated: {updated_count}, Skipped: {skipped_count}.")
            resources_committed = True
        except Exception as e:
            db.session.rollback()
            print(f"--- ERROR during resource commit: {e} ---")
            if app and hasattr(app, 'logger'):
                app.logger.error(f"Resource seeding failed: {e}", exc_info=True)

    return resources_committed

def seed_market_items_for_countries(app, country_names):
    print(f"\n--- Seeding Initial Market Items for: {', '.join(country_names)} ---")
    initial_price = Decimal('5.00')

    added_market_count = 0
    skipped_market_count = 0
    updated_market_count = 0
    countries_processed_count = 0

    with app.app_context():
        all_resources = db.session.scalars(db.select(Resource)).all()
        if not all_resources:
            print("  No resources found in the database. Cannot seed market items.")
            return

        resource_map = {res.id: res for res in all_resources}
        print(f"  Found {len(resource_map)} global resources.")

        target_countries = db.session.scalars(
            db.select(Country).filter(Country.name.in_(country_names))
        ).all()

        if not target_countries:
            print(f"  ERROR: Could not find specified countries ({', '.join(country_names)}) in the database.")
            print("  Ensure you have run seed_countries.py first.")
            return

        print(f"  Processing {len(target_countries)} target countries...")

        items_to_commit = []

        for country in target_countries:
            countries_processed_count += 1
            print(f"  Processing market items for: {country.name}")
            for resource_id, resource in resource_map.items():
                # Determine quality levels to create
                # Resources with can_have_quality need Q1-Q5, others just Q0
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

                    market_item = db.session.scalar(
                        db.select(CountryMarketItem).filter_by(
                            country_id=country.id,
                            resource_id=resource_id,
                            quality=quality
                        )
                    )

                    if not market_item:
                        market_item = CountryMarketItem(
                            country_id=country.id,
                            resource_id=resource_id,
                            quality=quality,
                            initial_price=adjusted_price,
                            price_level=0,
                            progress_within_level=0
                        )
                        db.session.add(market_item)
                        added_market_count += 1
                        items_to_commit.append(market_item)
                    else:
                        updated = False
                        if market_item.price_level != 0 or market_item.progress_within_level != 0:
                            market_item.price_level = 0
                            market_item.progress_within_level = 0
                            updated = True
                        if updated:
                            updated_market_count += 1
                            items_to_commit.append(market_item)
                        else:
                            skipped_market_count += 1

        if items_to_commit:
            try:
                db.session.commit()
                print(f"\n--- Market item commit successful for {countries_processed_count} countries. ---")
                print(f"--- Added: {added_market_count}, Updated: {updated_market_count}, Skipped: {skipped_market_count}. ---")
            except Exception as e:
                db.session.rollback()
                print(f"--- ERROR during market item commit: {e} ---")
                if app and hasattr(app, 'logger'):
                    app.logger.error(f"Market item seeding failed: {e}", exc_info=True)
        else:
            print("\nNo new or updated market items to commit.")

if __name__ == "__main__":
    flask_app = create_app()

    resources_ok = seed_global_resources(flask_app)

    if resources_ok:
        target_country_list = ["United States", "Mexico", "Canada"]
        seed_market_items_for_countries(flask_app, target_country_list)
    else:
        print("\nSkipping market item seeding due to resource seeding issues.")

    print("\n--- Seeding Script Finished ---")
