"""
Tech-IT Solutions - Monitoring Middleware
Tracks request metrics, response times, and errors
"""

import time
import logging
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache

logger = logging.getLogger("monitoring")


class MonitoringMiddleware(MiddlewareMixin):
    """
    Middleware to track request metrics
    """

    def process_request(self, request):
        """Record request start time"""
        request._monitoring_start_time = time.time()

    def process_response(self, request, response):
        """Record request completion and metrics"""
        if hasattr(request, "_monitoring_start_time"):
            duration = time.time() - request._monitoring_start_time

            # Log slow requests
            if duration > 2.0:  # More than 2 seconds
                logger.warning(
                    f"Slow request: {request.method} {request.path} "
                    f"took {duration:.2f}s - Status: {response.status_code}"
                )

            # Track metrics in cache for Prometheus
            self._record_metrics(request, response, duration)

        return response

    def process_exception(self, request, exception):
        """Log exceptions"""
        logger.error(
            f"Exception in {request.method} {request.path}: {str(exception)}",
            exc_info=True,
        )

        # Increment error counter
        cache.incr("monitoring:errors:total", 1)

    def _record_metrics(self, request, response, duration):
        """Record metrics for monitoring"""
        # Request count
        cache.incr("monitoring:requests:total", 1)

        # Status code counts
        status_group = f"{response.status_code // 100}xx"
        cache.incr(f"monitoring:requests:{status_group}", 1)

        # Response time buckets
        if duration < 0.1:
            cache.incr("monitoring:response_time:under_100ms", 1)
        elif duration < 0.5:
            cache.incr("monitoring:response_time:100ms_500ms", 1)
        elif duration < 1.0:
            cache.incr("monitoring:response_time:500ms_1s", 1)
        elif duration < 2.0:
            cache.incr("monitoring:response_time:1s_2s", 1)
        else:
            cache.incr("monitoring:response_time:over_2s", 1)

        # Track endpoint-specific metrics
        endpoint = f"{request.method}:{request.path[:50]}"
        cache.incr(f"monitoring:endpoint:{endpoint}", 1)


class SecurityMonitoringMiddleware(MiddlewareMixin):
    """
    Middleware to detect and log security events
    """

    def process_request(self, request):
        """Check for suspicious activity"""
        # Track failed login attempts
        if request.path == "/users/login/" and request.method == "POST":
            user_ip = self.get_client_ip(request)
            failed_attempts_key = f"security:failed_login:{user_ip}"
            failed_attempts = cache.get(failed_attempts_key, 0)

            if failed_attempts > 5:
                logger.warning(f"Multiple failed login attempts from IP: {user_ip}")

        # Check for suspicious user agents
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        suspicious_agents = ["sqlmap", "nikto", "nmap", "masscan"]
        if any(agent in user_agent.lower() for agent in suspicious_agents):
            logger.warning(
                f"Suspicious user agent detected: {user_agent} "
                f"from IP: {self.get_client_ip(request)}"
            )

    def process_response(self, request, response):
        """Track failed login attempts"""
        if request.path == "/users/login/" and request.method == "POST":
            user_ip = self.get_client_ip(request)
            failed_attempts_key = f"security:failed_login:{user_ip}"

            if response.status_code == 200 and "Please enter a correct" in str(response.content):
                # Failed login
                cache.incr(failed_attempts_key, 1)
                cache.expire(failed_attempts_key, 3600)  # Expire after 1 hour
            elif response.status_code == 302:
                # Successful login, clear counter
                cache.delete(failed_attempts_key)

        return response

    @staticmethod
    def get_client_ip(request):
        """Get client IP address"""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


class PerformanceMonitoringMiddleware(MiddlewareMixin):
    """
    Middleware to track database query performance
    """

    def process_request(self, request):
        """Track query count before request"""
        from django.db import connection

        request._monitoring_query_count = len(connection.queries)

    def process_response(self, request, response):
        """Check for N+1 query problems"""
        if hasattr(request, "_monitoring_query_count"):
            from django.db import connection

            queries = len(connection.queries) - request._monitoring_query_count

            # Alert on high query counts
            if queries > 50:
                logger.warning(
                    f"High query count: {request.method} {request.path} "
                    f"executed {queries} queries"
                )

        return response
