# security/database_optimization.py
"""
Database optimization utilities and management commands
Run with: python manage.py optimize_database
"""

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.apps import apps
import logging

logger = logging.getLogger(__name__)

"""
# Add these optimized settings to settings.py:

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'techit_db'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': 600,  # Connection pooling
        'OPTIONS': {
            'connect_timeout': 10,
            'options': '-c statement_timeout=30000'  # 30 second query timeout
        },
    }
}

# Database query optimization
LOGGING = {
    'loggers': {
        'django.db.backends': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'handlers': ['console', 'file'],
        },
    },
}
"""


class Command(BaseCommand):
    help = 'Optimize database performance'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--analyze',
            action='store_true',
            help='Run ANALYZE on all tables',
        )
        parser.add_argument(
            '--vacuum',
            action='store_true',
            help='Run VACUUM on database',
        )
        parser.add_argument(
            '--indexes',
            action='store_true',
            help='Create recommended indexes',
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show database statistics',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Database Optimization ==='))
        
        if options['analyze']:
            self.run_analyze()
        
        if options['vacuum']:
            self.run_vacuum()
        
        if options['indexes']:
            self.create_indexes()
        
        if options['stats']:
            self.show_statistics()
        
        if not any([options['analyze'], options['vacuum'], options['indexes'], options['stats']]):
            self.stdout.write(self.style.WARNING('No action specified. Use --help for options.'))
    
    def run_analyze(self):
        """Run ANALYZE on all tables"""
        self.stdout.write('Running ANALYZE on all tables...')
        
        with connection.cursor() as cursor:
            cursor.execute("ANALYZE;")
        
        self.stdout.write(self.style.SUCCESS('✓ ANALYZE completed'))
    
    def run_vacuum(self):
        """Run VACUUM to reclaim storage"""
        self.stdout.write('Running VACUUM...')
        
        # Cannot run VACUUM inside transaction
        old_autocommit = connection.get_autocommit()
        connection.set_autocommit(True)
        
        try:
            with connection.cursor() as cursor:
                cursor.execute("VACUUM ANALYZE;")
            self.stdout.write(self.style.SUCCESS('✓ VACUUM completed'))
        finally:
            connection.set_autocommit(old_autocommit)
    
    def create_indexes(self):
        """Create recommended indexes for better performance"""
        self.stdout.write('Creating recommended indexes...')
        
        indexes = [
            # Users indexes
            ('CREATE INDEX IF NOT EXISTS idx_users_email ON users_customuser(email);', 'User email'),
            ('CREATE INDEX IF NOT EXISTS idx_users_is_active ON users_customuser(is_active);', 'User active status'),
            
            # Services indexes
            ('CREATE INDEX IF NOT EXISTS idx_services_user ON services_service(user_id);', 'Service user'),
            ('CREATE INDEX IF NOT EXISTS idx_services_status ON services_service(status);', 'Service status'),
            ('CREATE INDEX IF NOT EXISTS idx_services_expiry ON services_service(expiry_date) WHERE status = \'active\';', 'Service expiry'),
            ('CREATE INDEX IF NOT EXISTS idx_services_created ON services_service(created_at DESC);', 'Service created'),
            
            # Orders indexes
            ('CREATE INDEX IF NOT EXISTS idx_orders_user ON orders_order(user_id);', 'Order user'),
            ('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders_order(status);', 'Order status'),
            ('CREATE INDEX IF NOT EXISTS idx_orders_created ON orders_order(created_at DESC);', 'Order created'),
            
            # Tickets indexes
            ('CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets_ticket(user_id);', 'Ticket user'),
            ('CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets_ticket(status);', 'Ticket status'),
            ('CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets_ticket(priority);', 'Ticket priority'),
            
            # Composite indexes
            ('CREATE INDEX IF NOT EXISTS idx_services_user_status ON services_service(user_id, status);', 'Service user+status'),
            ('CREATE INDEX IF NOT EXISTS idx_orders_user_status ON orders_order(user_id, status);', 'Order user+status'),
        ]
        
        with connection.cursor() as cursor:
            for sql, description in indexes:
                try:
                    cursor.execute(sql)
                    self.stdout.write(f'✓ Created index: {description}')
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'⚠ Failed to create index ({description}): {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS('✓ Index creation completed'))
    
    def show_statistics(self):
        """Show database statistics"""
        self.stdout.write('\n=== Database Statistics ===\n')
        
        # Table sizes
        self.stdout.write(self.style.SUCCESS('Table Sizes:'))
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
                FROM pg_tables
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                LIMIT 10;
            """)
            
            for schema, table, size in cursor.fetchall():
                self.stdout.write(f'  {schema}.{table}: {size}')
        
        # Index usage
        self.stdout.write(self.style.SUCCESS('\nIndex Usage:'))
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan,
                    idx_tup_read,
                    idx_tup_fetch
                FROM pg_stat_user_indexes
                ORDER BY idx_scan DESC
                LIMIT 10;
            """)
            
            for schema, table, index, scans, reads, fetches in cursor.fetchall():
                self.stdout.write(f'  {index}: {scans} scans')
        
        # Query performance
        self.stdout.write(self.style.SUCCESS('\nSlow Queries:'))
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    query,
                    calls,
                    total_time,
                    mean_time,
                    max_time
                FROM pg_stat_statements
                WHERE mean_time > 100
                ORDER BY mean_time DESC
                LIMIT 5;
            """)
            
            rows = cursor.fetchall()
            if rows:
                for query, calls, total, mean, max_time in rows:
                    self.stdout.write(f'  Calls: {calls}, Mean: {mean:.2f}ms')
                    self.stdout.write(f'    {query[:100]}...')
            else:
                self.stdout.write('  (pg_stat_statements extension not enabled)')
        
        # Database size
        self.stdout.write(self.style.SUCCESS('\nDatabase Size:'))
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT pg_size_pretty(pg_database_size(current_database()));
            """)
            size = cursor.fetchone()[0]
            self.stdout.write(f'  {size}')


# Query optimization utilities
class QueryOptimizer:
    """
    Utilities for optimizing Django ORM queries
    """
    
    @staticmethod
    def optimize_queryset_example():
        """
        Examples of query optimization techniques
        """
        from services.models import Service
        
        # Bad: N+1 query problem
        services = Service.objects.all()
        for service in services:
            print(service.user.email)  # Triggers one query per service
        
        # Good: Use select_related for foreign keys
        services = Service.objects.select_related('user').all()
        for service in services:
            print(service.user.email)  # No additional queries
        
        # Good: Use prefetch_related for reverse relations and M2M
        from users.models import User
        users = User.objects.prefetch_related('services').all()
        for user in users:
            print(user.services.count())  # No additional queries
        
        # Good: Use only() to fetch specific fields
        services = Service.objects.only('name', 'status').all()
        
        # Good: Use defer() to exclude fields
        services = Service.objects.defer('description').all()
        
        # Good: Use values() for aggregation
        service_counts = Service.objects.values('service_type').annotate(count=Count('id'))
        
        # Good: Use iterator() for large querysets
        for service in Service.objects.iterator(chunk_size=1000):
            # Process service
            pass
        
        # Good: Use exists() instead of count() > 0
        has_services = Service.objects.filter(status='active').exists()
        
        # Good: Use bulk operations
        Service.objects.bulk_create([
            Service(name='Service 1'),
            Service(name='Service 2'),
        ])
        
        Service.objects.bulk_update(services, ['status'], batch_size=1000)


# Database connection pooling (for production)
"""
# Install: pip install psycopg2-binary django-db-pool

DATABASES = {
    'default': {
        'ENGINE': 'django_db_pool.backends.postgresql',
        'POOL_OPTIONS': {
            'POOL_SIZE': 10,
            'MAX_OVERFLOW': 10,
            'RECYCLE': 3600,  # Recycle connections after 1 hour
            'TIMEOUT': 30,
        }
    }
}
"""
