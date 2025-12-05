"""
API Routes

Example API endpoints demonstrating the authentication system.
All routes require API token authentication.
"""

from flask import current_app, g
from app.api import bp
from app.extensions import limiter
from app.api_auth import (
    api_token_required,
    api_scope_required,
    api_admin_required,
    api_success,
    api_error,
    api_paginated_response
)
from app.models import APITokenScope, User, Country, Resource
from app.extensions import db


# ==================== Public/Info Endpoints ====================

@bp.route('/v1/info', methods=['GET'])
def api_info():
    """
    Get API information (no authentication required).

    This endpoint provides basic information about the API.
    """
    if not current_app.config.get('API_ENABLED'):
        return api_error('API functionality is currently disabled', 503)

    return api_success({
        'name': 'Tactizen API',
        'version': '1.0',
        'status': 'active',
        'documentation': '/api/docs',
        'authentication': 'Bearer token',
        'endpoints': {
            'tokens': '/api/tokens',
            'profile': '/api/v1/profile',
            'countries': '/api/v1/countries',
            'resources': '/api/v1/resources'
        }
    })


# ==================== Profile Endpoints ====================

@bp.route('/v1/profile', methods=['GET'])
@api_token_required
@api_scope_required(APITokenScope.READ_PROFILE)
@limiter.limit(lambda: current_app.config.get("RATELIMIT_API_READ", "200 per hour"))
def get_profile():
    """
    Get authenticated user's profile.

    Requires scope: read:profile
    """
    if not current_app.config.get('API_ENABLED'):
        return api_error('API functionality is currently disabled', 503)

    user = g.current_user

    profile_data = {
        'id': user.id,
        'username': user.username,
        'wallet_address': user.wallet_address,
        'xp': user.xp,
        'level': user.level,
        'health': user.health,
        'energy': user.energy,
        'morale': user.morale,
        'citizenship': {
            'country_id': user.citizenship_id,
            'country_name': user.citizenship.name if user.citizenship else None
        },
        'current_region': {
            'region_id': user.current_region_id,
            'region_name': user.current_region.name if user.current_region else None
        },
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'is_admin': user.is_admin
    }

    return api_success(profile_data)


@bp.route('/v1/profile/stats', methods=['GET'])
@api_token_required
@api_scope_required(APITokenScope.READ_STATS)
@limiter.limit(lambda: current_app.config.get("RATELIMIT_API_READ", "200 per hour"))
def get_profile_stats():
    """
    Get detailed statistics for authenticated user.

    Requires scope: read:stats
    """
    if not current_app.config.get('API_ENABLED'):
        return api_error('API functionality is currently disabled', 503)

    user = g.current_user

    stats_data = {
        'basic_stats': {
            'strength': user.strength,
            'intelligence': user.intelligence,
            'charisma': user.charisma
        },
        'resources': {
            'health': user.health,
            'energy': user.energy,
            'morale': user.morale
        },
        'progression': {
            'xp': user.xp,
            'level': user.level
        }
    }

    return api_success(stats_data)


# ==================== Inventory Endpoints ====================

@bp.route('/v1/inventory', methods=['GET'])
@api_token_required
@api_scope_required(APITokenScope.READ_INVENTORY)
@limiter.limit(lambda: current_app.config.get("RATELIMIT_API_READ", "200 per hour"))
def get_inventory():
    """
    Get authenticated user's inventory.

    Requires scope: read:inventory
    """
    if not current_app.config.get('API_ENABLED'):
        return api_error('API functionality is currently disabled', 503)

    user = g.current_user

    inventory_items = []
    for item in user.inventory:
        inventory_items.append({
            'resource_id': item.resource_id,
            'resource_name': item.resource.name,
            'quantity': item.quantity,
            'quality': item.quality
        })

    return api_success({
        'items': inventory_items,
        'total_items': len(inventory_items)
    })


# ==================== Country Endpoints ====================

@bp.route('/v1/countries', methods=['GET'])
@api_token_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_API_READ", "200 per hour"))
def get_countries():
    """
    Get list of all countries.

    Query parameters:
    - page: Page number (default: 1)
    - per_page: Items per page (default: 20, max: 100)
    """
    if not current_app.config.get('API_ENABLED'):
        return api_error('API functionality is currently disabled', 503)

    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    query = Country.query.filter_by(is_deleted=False)
    total_count = query.count()

    countries = query.offset((page - 1) * per_page).limit(per_page).all()

    countries_data = []
    for country in countries:
        countries_data.append({
            'id': country.id,
            'name': country.name,
            'currency_code': country.currency_code,
            'tax_rate': country.tax_rate,
            'region_count': len(country.regions.filter_by(is_deleted=False).all()) if country.regions else 0
        })

    return api_paginated_response(countries_data, page, per_page, total_count)


@bp.route('/v1/countries/<int:country_id>', methods=['GET'])
@api_token_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_API_READ", "200 per hour"))
def get_country(country_id):
    """Get details of a specific country."""
    if not current_app.config.get('API_ENABLED'):
        return api_error('API functionality is currently disabled', 503)

    country = Country.query.filter_by(id=country_id, is_deleted=False).first()

    if not country:
        return api_error('Country not found', 404)

    country_data = {
        'id': country.id,
        'name': country.name,
        'currency_code': country.currency_code,
        'tax_rate': country.tax_rate,
        'regions': [
            {
                'id': region.id,
                'name': region.name
            }
            for region in country.regions.filter_by(is_deleted=False).all()
        ]
    }

    return api_success(country_data)


# ==================== Market Endpoints ====================

@bp.route('/v1/market', methods=['GET'])
@api_token_required
@api_scope_required(APITokenScope.READ_MARKET)
@limiter.limit(lambda: current_app.config.get("RATELIMIT_API_READ", "200 per hour"))
def get_market():
    """
    Get market listings.

    Requires scope: read:market
    """
    if not current_app.config.get('API_ENABLED'):
        return api_error('API functionality is currently disabled', 503)

    from app.models import CountryMarketItem

    user = g.current_user

    if not user.current_region_id or not user.citizenship_id:
        return api_error('User must have citizenship and be in a region', 400)

    # Get market items for user's country
    market_items = CountryMarketItem.query.filter_by(
        country_id=user.citizenship_id
    ).all()

    market_data = []
    for item in market_items:
        market_data.append({
            'resource_id': item.resource_id,
            'resource_name': item.resource.name,
            'quantity': item.quantity,
            'quality': item.quality,
            'price': item.price
        })

    return api_success({
        'market_items': market_data,
        'country_id': user.citizenship_id,
        'currency_code': user.citizenship.currency_code
    })


# ==================== Admin Endpoints ====================

@bp.route('/v1/admin/users', methods=['GET'])
@api_token_required
@api_admin_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_API_ADMIN", "500 per hour"))
def admin_get_users():
    """
    Get list of all users (admin only).

    Requires scopes: admin:read, admin:write
    """
    if not current_app.config.get('API_ENABLED'):
        return api_error('API functionality is currently disabled', 503)

    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    query = User.query.filter_by(is_deleted=False)
    total_count = query.count()

    users = query.offset((page - 1) * per_page).limit(per_page).all()

    users_data = []
    for user in users:
        users_data.append({
            'id': user.id,
            'username': user.username,
            'wallet_address': user.wallet_address,
            'level': user.level,
            'citizenship_id': user.citizenship_id,
            'is_admin': user.is_admin,
            'is_banned': user.is_banned,
            'created_at': user.created_at.isoformat() if user.created_at else None
        })

    return api_paginated_response(users_data, page, per_page, total_count)


@bp.route('/v1/admin/stats', methods=['GET'])
@api_token_required
@api_admin_required
@limiter.limit(lambda: current_app.config.get("RATELIMIT_API_ADMIN", "500 per hour"))
def admin_get_stats():
    """
    Get system statistics (admin only).

    Requires scopes: admin:read, admin:write
    """
    if not current_app.config.get('API_ENABLED'):
        return api_error('API functionality is currently disabled', 503)

    stats = {
        'users': {
            'total': User.query.filter_by(is_deleted=False).count(),
            'admins': User.query.filter_by(is_deleted=False, is_admin=True).count(),
            'banned': User.query.filter_by(is_banned=True).count()
        },
        'countries': {
            'total': Country.query.filter_by(is_deleted=False).count()
        },
        'resources': {
            'total': Resource.query.filter_by(is_deleted=False).count()
        }
    }

    return api_success(stats)
