"""Cache utility functions for managing and invalidating cached data."""

from flask import current_app
from app.extensions import cache


def invalidate_country_cache(country_id=None):
    if country_id:
        from app.models import Country
        country = cache.get(Country, country_id)
        if country:
            cache.delete(f'country_page_{country.slug}')
            current_app.logger.info(f"Cache invalidated for country {country_id}")
    else:
        cache.delete('country_query')
        current_app.logger.info("All country caches invalidated")


def invalidate_resource_cache(resource_id=None):
    from app.main.market_utils import invalidate_resource_cache as inv_market_cache
    inv_market_cache()

    if resource_id:
        current_app.logger.info(f"Cache invalidated for resource {resource_id}")
    else:
        current_app.logger.info("All resource caches invalidated")


def invalidate_user_cache(user_id):
    current_app.logger.info(f"Cache invalidated for user {user_id}")


def invalidate_all_caches():
    cache.clear()
    current_app.logger.warning("ALL caches cleared!")


def get_cache_stats():
    stats = {}

    try:
        cache_config = current_app.config.get('CACHE_TYPE', 'SimpleCache')
        stats['cache_type'] = cache_config

        if cache_config == 'RedisCache' and hasattr(cache, 'cache'):
            redis_client = cache.cache._client
            info = redis_client.info('stats')
            stats['hits'] = info.get('keyspace_hits', 0)
            stats['misses'] = info.get('keyspace_misses', 0)
            stats['keys'] = redis_client.dbsize()

            total = stats['hits'] + stats['misses']
            stats['hit_rate'] = (stats['hits'] / total * 100) if total > 0 else 0

    except Exception as e:
        current_app.logger.error(f"Error getting cache stats: {e}")
        stats['error'] = str(e)

    return stats


def warm_cache():
    current_app.logger.info("Starting cache warming...")

    try:
        from app.main.market_utils import get_grouped_resource_choices, get_resource_slug_map
        get_grouped_resource_choices()
        get_resource_slug_map()
        current_app.logger.info("Resource caches warmed")

        from app.main.forms import country_query
        list(country_query())
        current_app.logger.info("Country query cache warmed")

        current_app.logger.info("Cache warming completed successfully")

    except Exception as e:
        current_app.logger.error(f"Error during cache warming: {e}", exc_info=True)


def invalidate_cache_on_commit(entity_type):
    def decorator(func):
        from functools import wraps

        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            if entity_type == 'country':
                invalidate_country_cache()
            elif entity_type == 'resource':
                invalidate_resource_cache()
            elif entity_type == 'user':
                user_id = kwargs.get('user_id') or getattr(result, 'id', None)
                if user_id:
                    invalidate_user_cache(user_id)

            return result

        return wrapper
    return decorator
