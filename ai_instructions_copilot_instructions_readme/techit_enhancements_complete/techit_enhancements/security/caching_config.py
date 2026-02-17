# security/caching_config.py
"""
Comprehensive caching configuration for Django
Implements multi-layer caching strategy
"""

from django.conf import settings
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from functools import wraps
import hashlib
import json

"""
Add to settings.py:

# Redis Cache Configuration
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
        },
        'KEY_PREFIX': 'techit',
        'TIMEOUT': 300,  # 5 minutes default
    },
    'sessions': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/2'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'session',
        'TIMEOUT': 86400,  # 24 hours
    },
    'static': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/3'),
        'KEY_PREFIX': 'static',
        'TIMEOUT': 604800,  # 7 days
    },
}

# Session cache
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'sessions'

# Cache middleware
MIDDLEWARE = [
    'django.middleware.cache.UpdateCacheMiddleware',  # Must be first
    # ... other middleware ...
    'django.middleware.cache.FetchFromCacheMiddleware',  # Must be last
]

CACHE_MIDDLEWARE_ALIAS = 'default'
CACHE_MIDDLEWARE_SECONDS = 300
CACHE_MIDDLEWARE_KEY_PREFIX = 'techit'
"""


def cache_key_generator(*args, **kwargs):
    """Generate cache key from function args"""
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
    return hashlib.md5(key_data.encode()).hexdigest()


def smart_cache(timeout=300, cache_key=None, vary_on_user=True):
    """
    Smart caching decorator with automatic cache invalidation

    Usage:
        @smart_cache(timeout=600, vary_on_user=True)
        def get_user_dashboard(request, user_id):
            ...
    """

    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            # Generate cache key
            if cache_key:
                key = cache_key
            else:
                key = f"{func.__module__}.{func.__name__}"

            # Add user ID if needed
            if vary_on_user and hasattr(request, "user") and request.user.is_authenticated:
                key = f"{key}:user_{request.user.id}"

            # Add args/kwargs to key
            if args or kwargs:
                key = f"{key}:{cache_key_generator(*args, **kwargs)}"

            # Try to get from cache
            cached_result = cache.get(key)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = func(request, *args, **kwargs)
            cache.set(key, result, timeout)

            return result

        return wrapper

    return decorator


def cache_queryset(timeout=300, cache_key=None):
    """
    Cache database queryset results

    Usage:
        @cache_queryset(timeout=600, cache_key='active_services')
        def get_active_services():
            return Service.objects.filter(status='active')
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if cache_key:
                key = f"queryset:{cache_key}"
            else:
                key = f"queryset:{func.__module__}.{func.__name__}"

            if args or kwargs:
                key = f"{key}:{cache_key_generator(*args, **kwargs)}"

            # Try to get from cache
            cached_result = cache.get(key)
            if cached_result is not None:
                return cached_result

            # Execute query and cache result
            result = func(*args, **kwargs)

            # Convert QuerySet to list for caching
            if hasattr(result, "_result_cache"):
                result = list(result)

            cache.set(key, result, timeout)

            return result

        return wrapper

    return decorator


class CacheManager:
    """
    Centralized cache management utilities
    """

    @staticmethod
    def invalidate_user_cache(user_id):
        """Invalidate all cache entries for a specific user"""
        pattern = f"*:user_{user_id}:*"
        cache.delete_pattern(pattern)

    @staticmethod
    def invalidate_model_cache(model_name):
        """Invalidate cache for a specific model"""
        pattern = f"queryset:*{model_name}*"
        cache.delete_pattern(pattern)

    @staticmethod
    def warm_cache():
        """Pre-populate cache with frequently accessed data"""
        from services.models import Service
        from users.models import User

        # Cache active services
        active_services = list(Service.objects.filter(status="active"))
        cache.set("queryset:active_services", active_services, 3600)

        # Cache service plans
        service_plans = list(Service.objects.values("service_type").distinct())
        cache.set("queryset:service_plans", service_plans, 3600)

    @staticmethod
    def get_cache_stats():
        """Get cache statistics"""
        from django.core.cache import caches

        stats = {}
        for alias in caches:
            try:
                cache_backend = caches[alias]
                # Redis-specific stats
                if hasattr(cache_backend, "client"):
                    info = cache_backend.client.get_client().info()
                    stats[alias] = {
                        "keys": info.get("db0", {}).get("keys", 0),
                        "memory_used": info.get("used_memory_human", "N/A"),
                        "hit_rate": info.get("keyspace_hits", 0)
                        / (info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1)),
                    }
            except:
                stats[alias] = "unavailable"

        return stats

    @staticmethod
    def clear_all_caches():
        """Clear all cache backends"""
        from django.core.cache import caches

        for alias in caches:
            caches[alias].clear()


# Template fragment caching example
"""
{% load cache %}
{% cache 500 sidebar request.user.username %}
    .. sidebar content ..
{% endcache %}
"""


# Low-level cache API examples
class CacheExamples:
    """
    Examples of using Django's cache framework
    """

    @staticmethod
    def basic_cache():
        """Basic cache operations"""
        # Set cache
        cache.set("my_key", "my_value", 300)

        # Get cache
        value = cache.get("my_key")

        # Get with default
        value = cache.get("my_key", "default_value")

        # Delete cache
        cache.delete("my_key")

        # Set multiple
        cache.set_many({"key1": "val1", "key2": "val2"}, 300)

        # Get multiple
        values = cache.get_many(["key1", "key2"])

        # Increment/Decrement
        cache.set("counter", 0)
        cache.incr("counter")
        cache.decr("counter")

    @staticmethod
    def advanced_cache():
        """Advanced cache operations"""

        # Get or set
        def expensive_operation():
            return "expensive_result"

        value = cache.get_or_set("my_key", expensive_operation, 300)

        # Touch (update expiry)
        cache.touch("my_key", 600)

        # Add (only if not exists)
        cache.add("my_key", "value", 300)

    @staticmethod
    def cache_versioning():
        """Cache versioning for easy invalidation"""
        # Version 1
        cache.set("user_data", {"name": "John"}, 300, version=1)

        # Version 2 (automatically invalidates v1)
        cache.set("user_data", {"name": "John", "email": "john@example.com"}, 300, version=2)

        # Get specific version
        data = cache.get("user_data", version=2)


# Database query result caching
class CachedQuerySet:
    """
    Example model manager with caching
    """

    @cache_queryset(timeout=600, cache_key="popular_services")
    def get_popular_services(self):
        """Get popular services with caching"""
        from services.models import Service

        return Service.objects.filter(status="active").order_by("-order_count")[:10]

    @cache_queryset(timeout=300, cache_key="user_services")
    def get_user_services(self, user_id):
        """Get user services with caching"""
        from services.models import Service

        return Service.objects.filter(user_id=user_id, status="active")


# View caching examples
@cache_page(60 * 15)  # Cache for 15 minutes
def cached_view(request):
    """View with full-page caching"""
    pass


@method_decorator(cache_page(60 * 15), name="dispatch")
class CachedClassView:
    """Class-based view with caching"""

    pass
