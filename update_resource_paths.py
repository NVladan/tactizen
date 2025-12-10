"""
Update resource icon paths from .png to .webp in the database.
Run this script after deploying the webp images.
"""

from app import create_app
from app.extensions import db
from app.models import Resource

app = create_app()

with app.app_context():
    resources = db.session.scalars(db.select(Resource)).all()
    updated = 0

    for resource in resources:
        if resource.icon_path and resource.icon_path.endswith('.png'):
            old_path = resource.icon_path
            resource.icon_path = resource.icon_path.replace('.png', '.webp')
            print(f"Updated: {old_path} -> {resource.icon_path}")
            updated += 1

    if updated > 0:
        db.session.commit()
        print(f"\nUpdated {updated} resource icon paths to .webp")
    else:
        print("No resources needed updating")
