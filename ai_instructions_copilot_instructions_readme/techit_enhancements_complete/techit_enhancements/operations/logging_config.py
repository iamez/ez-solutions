# operations/logging_config.py
"""
Centralized Logging Configuration
ELK Stack compatible (Elasticsearch, Logstash, Kibana)
"""

import os
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import json
from datetime import datetime

"""
Add to settings.py:

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
        'json': {
            '()': 'operations.logging_config.JSONFormatter',
        },
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/techit/django.log',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/techit/django_error.log',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/techit/security.log',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 20,
            'formatter': 'json',
        },
        'performance_file': {
            'level': 'INFO',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': '/var/log/techit/performance.log',
            'when': 'midnight',
            'interval': 1,
            'backupCount': 30,
            'formatter': 'json',
        },
        'json_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/techit/json.log',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 10,
            'formatter': 'json',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'filters': ['require_debug_false'],
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['error_file', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',  # Set to DEBUG to see all SQL queries
            'propagate': False,
        },
        'techit': {
            'handlers': ['console', 'file', 'json_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'performance': {
            'handlers': ['performance_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'security': {
            'handlers': ['security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}

# Additional logging configuration
ADMINS = [('Admin', 'admin@techitsolutions.com')]
SERVER_EMAIL = 'noreply@techitsolutions.com'
"""


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging
    Compatible with ELK stack and log aggregation tools
    """
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'process_id': record.process,
            'thread_id': record.thread,
        }
        
        # Add extra fields if available
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        
        if hasattr(record, 'ip_address'):
            log_data['ip_address'] = record.ip_address
        
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        
        if hasattr(record, 'duration'):
            log_data['duration'] = record.duration
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': self.formatException(record.exc_info)
            }
        
        return json.dumps(log_data)


class RequestLoggingMiddleware:
    """
    Middleware to log all requests with performance metrics
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger('performance')
    
    def __call__(self, request):
        import time
        
        # Record start time
        start_time = time.time()
        
        # Get request ID (or generate one)
        request_id = request.META.get('HTTP_X_REQUEST_ID', self.generate_request_id())
        
        # Process request
        response = self.get_response(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log request
        log_data = {
            'request_id': request_id,
            'method': request.method,
            'path': request.path,
            'status_code': response.status_code,
            'duration': f'{duration:.3f}s',
            'user_id': request.user.id if request.user.is_authenticated else None,
            'ip_address': self.get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        }
        
        # Determine log level based on status code
        if response.status_code >= 500:
            self.logger.error('Request completed', extra=log_data)
        elif response.status_code >= 400:
            self.logger.warning('Request completed', extra=log_data)
        else:
            self.logger.info('Request completed', extra=log_data)
        
        return response
    
    @staticmethod
    def generate_request_id():
        """Generate unique request ID"""
        import uuid
        return str(uuid.uuid4())
    
    @staticmethod
    def get_client_ip(request):
        """Get real client IP"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class SecurityLogger:
    """
    Utility class for security-related logging
    """
    
    def __init__(self):
        self.logger = logging.getLogger('security')
    
    def log_failed_login(self, username, ip_address, reason='Invalid credentials'):
        """Log failed login attempt"""
        self.logger.warning(
            f'Failed login attempt',
            extra={
                'event': 'failed_login',
                'username': username,
                'ip_address': ip_address,
                'reason': reason,
            }
        )
    
    def log_suspicious_activity(self, user_id, activity, ip_address, details=None):
        """Log suspicious activity"""
        extra = {
            'event': 'suspicious_activity',
            'user_id': user_id,
            'activity': activity,
            'ip_address': ip_address,
        }
        
        if details:
            extra['details'] = details
        
        self.logger.warning(f'Suspicious activity detected', extra=extra)
    
    def log_permission_denied(self, user_id, resource, action, ip_address):
        """Log permission denied"""
        self.logger.warning(
            f'Permission denied',
            extra={
                'event': 'permission_denied',
                'user_id': user_id,
                'resource': resource,
                'action': action,
                'ip_address': ip_address,
            }
        )
    
    def log_data_access(self, user_id, resource_type, resource_id, action):
        """Log sensitive data access"""
        self.logger.info(
            f'Data access',
            extra={
                'event': 'data_access',
                'user_id': user_id,
                'resource_type': resource_type,
                'resource_id': resource_id,
                'action': action,
            }
        )


class PerformanceLogger:
    """
    Utility class for performance monitoring
    """
    
    def __init__(self):
        self.logger = logging.getLogger('performance')
    
    def log_slow_query(self, query, duration, params=None):
        """Log slow database query"""
        self.logger.warning(
            f'Slow query detected',
            extra={
                'event': 'slow_query',
                'query': query[:200],  # Truncate long queries
                'duration': duration,
                'params': params,
            }
        )
    
    def log_api_call(self, endpoint, duration, status_code, method='GET'):
        """Log API call performance"""
        self.logger.info(
            f'API call',
            extra={
                'event': 'api_call',
                'endpoint': endpoint,
                'method': method,
                'duration': duration,
                'status_code': status_code,
            }
        )
    
    def log_cache_hit(self, cache_key, hit=True):
        """Log cache hit/miss"""
        self.logger.debug(
            f'Cache {"hit" if hit else "miss"}',
            extra={
                'event': 'cache_access',
                'cache_key': cache_key,
                'hit': hit,
            }
        )


# Log rotation script (run via cron)
"""
#!/bin/bash
# /etc/cron.daily/rotate-techit-logs.sh

# Compress logs older than 1 day
find /var/log/techit -name "*.log" -type f -mtime +1 -exec gzip {} \;

# Delete logs older than 30 days
find /var/log/techit -name "*.log.gz" -type f -mtime +30 -delete

# Ensure proper permissions
chown -R www-data:www-data /var/log/techit
chmod -R 755 /var/log/techit
"""


# ELK Stack integration example
"""
# Install: pip install python-logstash

LOGGING = {
    'handlers': {
        'logstash': {
            'level': 'INFO',
            'class': 'logstash.TCPLogstashHandler',
            'host': 'localhost',
            'port': 5000,
            'version': 1,
            'message_type': 'django',
            'fqdn': False,
            'tags': ['django', 'techit'],
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file', 'logstash'],
            'level': 'INFO',
        },
    },
}
"""
