# security/rate_limiting.py
"""
Advanced rate limiting middleware for Django
Protects against brute force, DDoS, and API abuse
"""

from django.core.cache import cache
from django.http import JsonResponse
from django.conf import settings
import time
import hashlib

class RateLimitMiddleware:
    """
    Rate limiting middleware with multiple strategies
    
    Add to MIDDLEWARE in settings.py:
        'security.rate_limiting.RateLimitMiddleware',
    
    Configuration in settings.py:
        RATE_LIMIT_ENABLED = True
        RATE_LIMIT_REQUESTS = 100  # requests per window
        RATE_LIMIT_WINDOW = 60  # window in seconds
        RATE_LIMIT_CACHE_PREFIX = 'ratelimit'
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = getattr(settings, 'RATE_LIMIT_ENABLED', True)
        self.default_limit = getattr(settings, 'RATE_LIMIT_REQUESTS', 100)
        self.window = getattr(settings, 'RATE_LIMIT_WINDOW', 60)
        self.cache_prefix = getattr(settings, 'RATE_LIMIT_CACHE_PREFIX', 'ratelimit')
        
        # Path-specific rate limits
        self.path_limits = {
            '/api/': (1000, 60),  # 1000 req/min for API
            '/login/': (5, 300),  # 5 req/5min for login
            '/register/': (3, 3600),  # 3 req/hour for registration
            '/reset-password/': (3, 3600),  # 3 req/hour for password reset
            '/checkout/': (10, 600),  # 10 req/10min for checkout
        }
    
    def __call__(self, request):
        if not self.enabled:
            return self.get_response(request)
        
        # Get client identifier
        client_id = self.get_client_identifier(request)
        
        # Check rate limit
        is_allowed, retry_after = self.check_rate_limit(request, client_id)
        
        if not is_allowed:
            return self.rate_limit_exceeded_response(retry_after)
        
        # Process request
        response = self.get_response(request)
        
        # Add rate limit headers
        response = self.add_rate_limit_headers(response, request, client_id)
        
        return response
    
    def get_client_identifier(self, request):
        """Get unique client identifier (IP + User Agent hash)"""
        ip = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Include user ID if authenticated
        if request.user.is_authenticated:
            identifier = f"user:{request.user.id}"
        else:
            # Hash IP + User Agent for privacy
            identifier = hashlib.sha256(
                f"{ip}:{user_agent}".encode()
            ).hexdigest()[:16]
        
        return identifier
    
    def get_client_ip(self, request):
        """Get real client IP (handles proxies)"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def get_rate_limit_for_path(self, path):
        """Get rate limit configuration for specific path"""
        for prefix, (limit, window) in self.path_limits.items():
            if path.startswith(prefix):
                return limit, window
        return self.default_limit, self.window
    
    def check_rate_limit(self, request, client_id):
        """Check if request is within rate limit"""
        path = request.path
        limit, window = self.get_rate_limit_for_path(path)
        
        # Create cache key
        cache_key = f"{self.cache_prefix}:{client_id}:{path}"
        
        # Get current request count and timestamp
        data = cache.get(cache_key, {'count': 0, 'start_time': time.time()})
        current_time = time.time()
        
        # Reset if window expired
        if current_time - data['start_time'] > window:
            data = {'count': 0, 'start_time': current_time}
        
        # Increment count
        data['count'] += 1
        
        # Calculate retry after
        time_elapsed = current_time - data['start_time']
        retry_after = max(0, window - time_elapsed)
        
        # Check if over limit
        if data['count'] > limit:
            return False, int(retry_after)
        
        # Update cache
        cache.set(cache_key, data, window)
        
        return True, 0
    
    def add_rate_limit_headers(self, response, request, client_id):
        """Add rate limit info to response headers"""
        path = request.path
        limit, window = self.get_rate_limit_for_path(path)
        cache_key = f"{self.cache_prefix}:{client_id}:{path}"
        data = cache.get(cache_key, {'count': 0, 'start_time': time.time()})
        
        remaining = max(0, limit - data['count'])
        
        response['X-RateLimit-Limit'] = limit
        response['X-RateLimit-Remaining'] = remaining
        response['X-RateLimit-Reset'] = int(data['start_time'] + window)
        
        return response
    
    def rate_limit_exceeded_response(self, retry_after):
        """Return rate limit exceeded response"""
        return JsonResponse({
            'error': 'Rate limit exceeded',
            'message': 'Too many requests. Please try again later.',
            'retry_after': retry_after
        }, status=429)


class DDoSProtectionMiddleware:
    """
    Advanced DDoS protection middleware
    
    Detects and blocks suspicious traffic patterns:
    - Rapid successive requests
    - Unusual request patterns
    - Known attack signatures
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = getattr(settings, 'DDOS_PROTECTION_ENABLED', True)
        self.threshold = getattr(settings, 'DDOS_THRESHOLD', 50)  # requests per second
        self.block_duration = getattr(settings, 'DDOS_BLOCK_DURATION', 3600)  # 1 hour
    
    def __call__(self, request):
        if not self.enabled:
            return self.get_response(request)
        
        client_ip = self.get_client_ip(request)
        
        # Check if IP is blocked
        if self.is_blocked(client_ip):
            return JsonResponse({
                'error': 'Access denied',
                'message': 'Your IP has been temporarily blocked due to suspicious activity.'
            }, status=403)
        
        # Track request
        if self.detect_ddos(client_ip):
            self.block_ip(client_ip)
            return JsonResponse({
                'error': 'Access denied',
                'message': 'Too many requests detected. IP blocked.'
            }, status=403)
        
        return self.get_response(request)
    
    def get_client_ip(self, request):
        """Get real client IP"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
    
    def detect_ddos(self, ip):
        """Detect DDoS attack patterns"""
        cache_key = f"ddos:requests:{ip}"
        
        # Get request timestamps
        requests = cache.get(cache_key, [])
        current_time = time.time()
        
        # Remove old timestamps (older than 1 second)
        requests = [t for t in requests if current_time - t < 1]
        requests.append(current_time)
        
        # Save updated list
        cache.set(cache_key, requests, 2)
        
        # Check if threshold exceeded
        return len(requests) > self.threshold
    
    def is_blocked(self, ip):
        """Check if IP is blocked"""
        cache_key = f"ddos:blocked:{ip}"
        return cache.get(cache_key, False)
    
    def block_ip(self, ip):
        """Block an IP address"""
        cache_key = f"ddos:blocked:{ip}"
        cache.set(cache_key, True, self.block_duration)
        
        # Log the block
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"IP blocked for DDoS: {ip}")


# Decorator for view-level rate limiting
def rate_limit(requests=10, window=60):
    """
    Decorator to apply rate limiting to specific views
    
    Usage:
        @rate_limit(requests=5, window=60)
        def my_view(request):
            ...
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            from django.core.cache import cache
            
            # Get client identifier
            client_ip = request.META.get('REMOTE_ADDR')
            cache_key = f"ratelimit:{view_func.__name__}:{client_ip}"
            
            # Check rate limit
            data = cache.get(cache_key, {'count': 0, 'start_time': time.time()})
            current_time = time.time()
            
            if current_time - data['start_time'] > window:
                data = {'count': 0, 'start_time': current_time}
            
            data['count'] += 1
            
            if data['count'] > requests:
                retry_after = int(window - (current_time - data['start_time']))
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'retry_after': retry_after
                }, status=429)
            
            cache.set(cache_key, data, window)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator
