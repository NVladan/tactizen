# seed_neighbors.py
from app import create_app, db # Import app factory and db instance
from app.models import Region, region_neighbors # Import Region and the association table
# --- Import select and exists ---
from sqlalchemy import select, and_, or_, exists

def link_neighbors(app, region1_name, region2_name):
    """Links two regions as neighbors if they exist and aren't already linked."""
    print(f"Attempting to link '{region1_name}' and '{region2_name}' as neighbors...")

    with app.app_context(): # Ensure operations happen within app context
        # Find the regions by name
        region1 = db.session.scalar(select(Region).filter_by(name=region1_name))
        region2 = db.session.scalar(select(Region).filter_by(name=region2_name))

        # Check if both regions were found
        if region1 and region2:
            # --- CORRECTED QUERY ---
            # Check if the relationship already exists using select(exists()...)
            stmt = select(exists().where(
                or_(
                    and_(region_neighbors.c.region_id == region1.id, region_neighbors.c.neighbor_id == region2.id),
                    and_(region_neighbors.c.region_id == region2.id, region_neighbors.c.neighbor_id == region1.id)
                )
            ))
            # Execute the select statement containing the exists() check
            already_neighbors = db.session.scalar(stmt)
            # --- END CORRECTION ---

            if not already_neighbors:
                # Use relationship append for cleaner code (handles both sides if relationship is set up correctly)
                # Ensure back_populates is correctly set up in the Region model for 'neighbors' and 'neighbor_of'
                try:
                     # Appending to one side should be sufficient if back_populates is correct
                     region1.neighbors.append(region2)
                     db.session.commit()
                     print(f" -> Successfully linked {region1.name} and {region2.name}.")
                except Exception as e:
                     db.session.rollback()
                     print(f" -> ERROR linking neighbors: {e}")
                     # Use Flask logger if available within context
                     if app and hasattr(app, 'logger'):
                         app.logger.error(f"Neighbor linking failed for {region1.name}/{region2.name}: {e}", exc_info=True)

            else:
                print(f" -> Already neighbors.")
        else:
            if not region1:
                print(f" -> Error: Could not find region '{region1_name}'.")
            if not region2:
                print(f" -> Error: Could not find region '{region2_name}'.")

# --- You can add more calls to link_neighbors here for other pairs ---
if __name__ == "__main__":
     flask_app = create_app() # Create app instance

     print("\n--- Seeding Region Neighbors ---")
     # Add pairs of region names you want to link. Assumes regions exist from seed_data.py

     # === UNITED STATES INTERNAL NEIGHBORS ===
     print("\n-- US Internal Neighbors --")
     # New England connections
     link_neighbors(flask_app, "New England", "New York & New Jersey")

     # New York & New Jersey connections
     link_neighbors(flask_app, "New York & New Jersey", "Mid-Atlantic")

     # Mid-Atlantic connections
     link_neighbors(flask_app, "Mid-Atlantic", "Appalachia")
     link_neighbors(flask_app, "Mid-Atlantic", "The Carolinas")

     # Appalachia connections
     link_neighbors(flask_app, "Appalachia", "The Carolinas")
     link_neighbors(flask_app, "Appalachia", "Deep South Interior")
     link_neighbors(flask_app, "Appalachia", "Great Lakes")

     # The Carolinas connections
     link_neighbors(flask_app, "The Carolinas", "Southeastern Coast")
     link_neighbors(flask_app, "The Carolinas", "Deep South Interior")

     # Southeastern Coast connections
     link_neighbors(flask_app, "Southeastern Coast", "Florida Panhandle & Lower Gulf")
     link_neighbors(flask_app, "Southeastern Coast", "Deep South Interior")

     # Florida Panhandle & Lower Gulf connections
     link_neighbors(flask_app, "Florida Panhandle & Lower Gulf", "Deep South Interior")
     link_neighbors(flask_app, "Florida Panhandle & Lower Gulf", "Texas")

     # Deep South Interior connections
     link_neighbors(flask_app, "Deep South Interior", "Texas")
     link_neighbors(flask_app, "Deep South Interior", "Southern Plains")

     # Texas connections
     link_neighbors(flask_app, "Texas", "Southwest")
     link_neighbors(flask_app, "Texas", "Central Plains")
     link_neighbors(flask_app, "Texas", "Southern Plains")

     # Southern Plains connections
     link_neighbors(flask_app, "Southern Plains", "Central Plains")
     link_neighbors(flask_app, "Southern Plains", "Southwest")

     # Central Plains connections
     link_neighbors(flask_app, "Central Plains", "Great Lakes")
     link_neighbors(flask_app, "Central Plains", "Upper Midwest")
     link_neighbors(flask_app, "Central Plains", "Mountain West")
     link_neighbors(flask_app, "Central Plains", "Southwest")

     # Great Lakes connections
     link_neighbors(flask_app, "Great Lakes", "Upper Midwest")
     link_neighbors(flask_app, "Great Lakes", "New York & New Jersey")

     # Upper Midwest connections
     link_neighbors(flask_app, "Upper Midwest", "Mountain West")

     # Mountain West connections
     link_neighbors(flask_app, "Mountain West", "Southwest")
     link_neighbors(flask_app, "Mountain West", "Pacific Coast")

     # Southwest connections
     link_neighbors(flask_app, "Southwest", "Pacific Coast")

     # === CANADA INTERNAL NEIGHBORS ===
     print("\n-- Canada Internal Neighbors --")
     link_neighbors(flask_app, "Atlantic Canada", "Quebec")
     link_neighbors(flask_app, "Quebec", "Ontario")
     link_neighbors(flask_app, "Quebec", "Northern Territories")
     link_neighbors(flask_app, "Ontario", "Prairie Provinces")
     link_neighbors(flask_app, "Ontario", "Northern Territories")
     link_neighbors(flask_app, "Prairie Provinces", "British Columbia")
     link_neighbors(flask_app, "Prairie Provinces", "Northern Territories")
     link_neighbors(flask_app, "British Columbia", "Northern Territories")

     # === CANADA-USA CROSS-BORDER NEIGHBORS ===
     print("\n-- Canada-USA Cross-Border Neighbors --")
     link_neighbors(flask_app, "Atlantic Canada", "New England")
     link_neighbors(flask_app, "Quebec", "New England")
     link_neighbors(flask_app, "Quebec", "New York & New Jersey")
     link_neighbors(flask_app, "Ontario", "New York & New Jersey")
     link_neighbors(flask_app, "Ontario", "Great Lakes")
     link_neighbors(flask_app, "Prairie Provinces", "Upper Midwest")
     link_neighbors(flask_app, "Prairie Provinces", "Mountain West")
     link_neighbors(flask_app, "British Columbia", "Pacific Coast")
     link_neighbors(flask_app, "Northern Territories", "Alaska")

     # === MEXICO-USA CROSS-BORDER NEIGHBORS ===
     print("\n-- Mexico-USA Cross-Border Neighbors --")
     link_neighbors(flask_app, "Northwest Mexico", "Southwest")
     link_neighbors(flask_app, "Northwest Mexico", "Pacific Coast")
     link_neighbors(flask_app, "Northeast Mexico", "Texas")
     link_neighbors(flask_app, "Northeast Mexico", "Southwest")

     # === MEXICO INTERNAL NEIGHBORS ===
     print("\n-- Mexico Internal Neighbors --")
     link_neighbors(flask_app, "Northwest Mexico", "Northeast Mexico")
     link_neighbors(flask_app, "Northwest Mexico", "Pacific Coast and Sierra Region")
     link_neighbors(flask_app, "Northeast Mexico", "Central Mexico")
     link_neighbors(flask_app, "Northeast Mexico", "Gulf and Southeast Region")
     link_neighbors(flask_app, "Central Mexico", "Pacific Coast and Sierra Region")
     link_neighbors(flask_app, "Central Mexico", "Gulf and Southeast Region")
     link_neighbors(flask_app, "Pacific Coast and Sierra Region", "Gulf and Southeast Region")
     link_neighbors(flask_app, "Gulf and Southeast Region", "Yucatán Peninsula and Southern Highlands")

     print("\n--- Neighbor Seeding Complete ---")
