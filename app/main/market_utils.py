# app/main/market_utils.py
# Helper functions for market routes

from collections import defaultdict
from flask import current_app
from app.extensions import db, cache
from app.models import Resource

@cache.memoize(timeout=None)  # Cache indefinitely, invalidate manually when resources change
def get_grouped_resource_choices():
    """Fetches and groups resources for dropdowns.

    Returns:
        List of tuples: [(category_name, [(resource_id, resource_name, icon_path), ...]), ...]

    Caching: Cached indefinitely since resources rarely change.
             Invalidated when resources are added/updated/deleted.
    """
    current_app.logger.debug("Cache MISS: Fetching grouped resource choices from database")
    resources = db.session.scalars(db.select(Resource).filter_by(is_deleted=False).order_by(Resource.category, Resource.name)).all()
    grouped_choices = defaultdict(list)
    for r in resources:
        grouped_choices[r.category.value].append((r.id, r.name, r.icon_path))

    # Custom category order: Food, Weapons, Raw Materials, Semi Products, Construction, Energy
    category_order = ['Food', 'Weapon', 'Raw Material', 'Semi Products', 'Construction', 'Energy', 'House']

    # Sort categories by custom order, then sort choices within each category
    result = []
    for category in category_order:
        if category in grouped_choices:
            result.append((category, sorted(grouped_choices[category], key=lambda x: x[1])))

    # Add any categories not in the predefined order (shouldn't happen but just in case)
    for category, choices in grouped_choices.items():
        if category not in category_order:
            result.append((category, sorted(choices, key=lambda x: x[1])))

    return result


@cache.memoize(timeout=None)  # Cache indefinitely, invalidate manually when resources change
def get_resource_slug_map():
     """Creates a mapping from resource ID to resource slug.

     Returns:
         Dict: {resource_id: resource_slug, ...}

     Caching: Cached indefinitely since resources rarely change.
              Invalidated when resources are added/updated/deleted.
     """
     current_app.logger.debug("Cache MISS: Fetching resource slug map from database")
     resources_data = db.session.execute(db.select(Resource.id, Resource.slug).filter_by(is_deleted=False)).all()
     return {res_id: res_slug for res_id, res_slug in resources_data}


def invalidate_resource_cache():
    """Invalidate cached resource data when resources are modified."""
    cache.delete_memoized(get_grouped_resource_choices)
    cache.delete_memoized(get_resource_slug_map)
    current_app.logger.info("Resource cache invalidated")