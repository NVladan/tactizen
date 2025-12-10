from app import create_app
from app.extensions import db
from app.models import Resource, Country, CountryMarketItem
from datetime import datetime, timezone

app = create_app()
ctx = app.app_context()
ctx.push()

print("=== Sample Market Prices ===")
market_items = db.session.scalars(db.select(CountryMarketItem).limit(10)).all()
for item in market_items:
    if item.resource:
        print(f"{item.resource.name}: Buy ${item.buy_price:.2f}, Sell ${item.sell_price:.2f}")

print("\n=== Adding New Resources ===")

fort = db.session.scalar(db.select(Resource).where(Resource.name == 'Fort'))
hospital = db.session.scalar(db.select(Resource).where(Resource.name == 'Hospital'))
house = db.session.scalar(db.select(Resource).where(Resource.name == 'House'))

if not fort:
    fort = Resource(
        name='Fort',
        description='Military fortification for defense',
        icon_path='images/resources/fort.webp',
        category='military',
        base_price=5000.00
    )
    db.session.add(fort)
    print("✓ Added Fort")
else:
    print("Fort already exists")

if not hospital:
    hospital = Resource(
        name='Hospital',
        description='Healthcare facility for treating citizens',
        icon_path='images/resources/hospital.webp',
        category='infrastructure',
        base_price=8000.00
    )
    db.session.add(hospital)
    print("✓ Added Hospital")
else:
    print("Hospital already exists")

if not house:
    house = Resource(
        name='House',
        description='Residential building for citizens',
        icon_path='images/resources/house.webp',
        category='infrastructure',
        base_price=2000.00
    )
    db.session.add(house)
    print("✓ Added House")
else:
    print("House already exists")

db.session.commit()
print("\n✓ Resources committed to database")

countries = db.session.scalars(db.select(Country).where(Country.is_deleted == False)).all()
print(f"\n=== Adding to {len(countries)} country markets ===")

db.session.flush()
fort = db.session.scalar(db.select(Resource).where(Resource.name == 'Fort'))
hospital = db.session.scalar(db.select(Resource).where(Resource.name == 'Hospital'))
house = db.session.scalar(db.select(Resource).where(Resource.name == 'House'))

new_resources = [fort, hospital, house]

for country in countries:
    for resource in new_resources:
        existing = db.session.scalar(
            db.select(CountryMarketItem)
            .where(CountryMarketItem.country_id == country.id)
            .where(CountryMarketItem.resource_id == resource.id)
        )

        if not existing:
            market_item = CountryMarketItem(
                country_id=country.id,
                resource_id=resource.id,
                buy_price=resource.base_price * 1.2,
                sell_price=resource.base_price * 0.8,
                stock=100,
                updated_at=datetime.now(timezone.utc)
            )
            db.session.add(market_item)
            print(f"  ✓ Added {resource.name} to {country.name} market")

db.session.commit()
print("\n✓ All market items added successfully!")

print("\n=== Summary ===")
print(f"Fort: Buy ${fort.base_price * 1.2:.2f}, Sell ${fort.base_price * 0.8:.2f}")
print(f"Hospital: Buy ${hospital.base_price * 1.2:.2f}, Sell ${hospital.base_price * 0.8:.2f}")
print(f"House: Buy ${house.base_price * 1.2:.2f}, Sell ${house.base_price * 0.8:.2f}")
