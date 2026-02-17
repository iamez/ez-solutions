# security/security_headers.py
"""
Comprehensive security headers middleware
Implements OWASP security best practices
"""

from django.conf import settings


class SecurityHeadersMiddleware:
    """
    Add security headers to all responses

    Add to MIDDLEWARE in settings.py:
        'security.security_headers.SecurityHeadersMiddleware',

    Headers implemented:
    - Content Security Policy (CSP)
    - X-Frame-Options
    - X-Content-Type-Options
    - X-XSS-Protection
    - Strict-Transport-Security (HSTS)
    - Referrer-Policy
    - Permissions-Policy
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Content Security Policy
        self.csp = self.build_csp()

        # HSTS configuration
        self.hsts_max_age = getattr(settings, "HSTS_MAX_AGE", 31536000)  # 1 year
        self.hsts_include_subdomains = getattr(settings, "HSTS_INCLUDE_SUBDOMAINS", True)
        self.hsts_preload = getattr(settings, "HSTS_PRELOAD", True)

    def __call__(self, request):
        response = self.get_response(request)

        # Only add security headers to HTML responses
        content_type = response.get("Content-Type", "")

        # Content Security Policy
        if "text/html" in content_type:
            response["Content-Security-Policy"] = self.csp

        # X-Frame-Options: Prevent clickjacking
        response["X-Frame-Options"] = "DENY"

        # X-Content-Type-Options: Prevent MIME sniffing
        response["X-Content-Type-Options"] = "nosniff"

        # X-XSS-Protection: Enable XSS filter
        response["X-XSS-Protection"] = "1; mode=block"

        # Strict-Transport-Security: Force HTTPS
        if request.is_secure():
            hsts_header = f"max-age={self.hsts_max_age}"
            if self.hsts_include_subdomains:
                hsts_header += "; includeSubDomains"
            if self.hsts_preload:
                hsts_header += "; preload"
            response["Strict-Transport-Security"] = hsts_header

        # Referrer-Policy: Control referrer information
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions-Policy: Control browser features
        response["Permissions-Policy"] = self.build_permissions_policy()

        # Remove sensitive headers
        response.pop("Server", None)
        response.pop("X-Powered-By", None)

        return response

    def build_csp(self):
        """Build Content Security Policy header"""
        # Get CSP configuration from settings
        csp_config = getattr(
            settings,
            "CSP_CONFIG",
            {
                "default-src": ["'self'"],
                "script-src": [
                    "'self'",
                    "'unsafe-inline'",
                    "cdn.jsdelivr.net",
                    "cdnjs.cloudflare.com",
                ],
                "style-src": [
                    "'self'",
                    "'unsafe-inline'",
                    "cdn.jsdelivr.net",
                    "fonts.googleapis.com",
                ],
                "img-src": ["'self'", "data:", "https:"],
                "font-src": ["'self'", "fonts.gstatic.com", "cdn.jsdelivr.net"],
                "connect-src": ["'self'"],
                "frame-ancestors": ["'none'"],
                "base-uri": ["'self'"],
                "form-action": ["'self'"],
                "upgrade-insecure-requests": [],
            },
        )

        # Build CSP string
        csp_parts = []
        for directive, sources in csp_config.items():
            if sources:
                csp_parts.append(f"{directive} {' '.join(sources)}")
            else:
                csp_parts.append(directive)

        return "; ".join(csp_parts)

    def build_permissions_policy(self):
        """Build Permissions-Policy header"""
        policies = [
            "geolocation=()",
            "microphone=()",
            "camera=()",
            "payment=(self)",
            "usb=()",
            "magnetometer=()",
            "gyroscope=()",
            "accelerometer=()",
        ]
        return ", ".join(policies)


class CORSSecurityMiddleware:
    """
    Secure CORS middleware with configurable origins

    Add to MIDDLEWARE in settings.py:
        'security.security_headers.CORSSecurityMiddleware',
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed_origins = getattr(settings, "CORS_ALLOWED_ORIGINS", [])
        self.allowed_methods = getattr(
            settings, "CORS_ALLOWED_METHODS", ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
        )
        self.allowed_headers = getattr(
            settings, "CORS_ALLOWED_HEADERS", ["Content-Type", "Authorization", "X-Requested-With"]
        )
        self.max_age = getattr(settings, "CORS_MAX_AGE", 86400)  # 24 hours
        self.allow_credentials = getattr(settings, "CORS_ALLOW_CREDENTIALS", True)

    def __call__(self, request):
        # Handle preflight requests
        if request.method == "OPTIONS":
            response = self.handle_preflight(request)
        else:
            response = self.get_response(request)
            self.add_cors_headers(request, response)

        return response

    def is_origin_allowed(self, origin):
        """Check if origin is allowed"""
        if not origin:
            return False

        # Check against allowed origins list
        for allowed_origin in self.allowed_origins:
            if allowed_origin == "*":
                return True
            if origin == allowed_origin:
                return True

        return False

    def handle_preflight(self, request):
        """Handle CORS preflight requests"""
        from django.http import HttpResponse

        response = HttpResponse()
        origin = request.META.get("HTTP_ORIGIN")

        if self.is_origin_allowed(origin):
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Methods"] = ", ".join(self.allowed_methods)
            response["Access-Control-Allow-Headers"] = ", ".join(self.allowed_headers)
            response["Access-Control-Max-Age"] = str(self.max_age)

            if self.allow_credentials:
                response["Access-Control-Allow-Credentials"] = "true"

        return response

    def add_cors_headers(self, request, response):
        """Add CORS headers to response"""
        origin = request.META.get("HTTP_ORIGIN")

        if self.is_origin_allowed(origin):
            response["Access-Control-Allow-Origin"] = origin

            if self.allow_credentials:
                response["Access-Control-Allow-Credentials"] = "true"

        return response


class IPWhitelistMiddleware:
    """
    Restrict access to specific IP addresses (for admin/sensitive areas)

    Usage in settings.py:
        IP_WHITELIST_ENABLED = True
        IP_WHITELIST = ['127.0.0.1', '192.168.1.0/24']
        IP_WHITELIST_PATHS = ['/admin/', '/api/internal/']
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = getattr(settings, "IP_WHITELIST_ENABLED", False)
        self.whitelist = getattr(settings, "IP_WHITELIST", [])
        self.protected_paths = getattr(settings, "IP_WHITELIST_PATHS", ["/admin/"])

    def __call__(self, request):
        if not self.enabled:
            return self.get_response(request)

        # Check if path is protected
        is_protected = any(request.path.startswith(path) for path in self.protected_paths)

        if is_protected:
            client_ip = self.get_client_ip(request)

            if not self.is_ip_whitelisted(client_ip):
                from django.http import HttpResponseForbidden

                return HttpResponseForbidden("Access denied: IP not whitelisted")

        return self.get_response(request)

    def get_client_ip(self, request):
        """Get real client IP"""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

    def is_ip_whitelisted(self, ip):
        """Check if IP is in whitelist"""
        import ipaddress

        try:
            client_ip = ipaddress.ip_address(ip)
        except ValueError:
            return False

        for allowed in self.whitelist:
            try:
                # Check if it's a network (CIDR notation)
                if "/" in allowed:
                    network = ipaddress.ip_network(allowed, strict=False)
                    if client_ip in network:
                        return True
                else:
                    # Direct IP comparison
                    if str(client_ip) == allowed:
                        return True
            except ValueError:
                continue

        return False
