#!/bin/bash
# automation/restore_script.sh
# Restore script for Tech-IT Solutions platform
# Usage: ./restore_script.sh <backup_date> [--database-only|--media-only]

set -e

# Configuration
PROJECT_NAME="techit_solutions"
BACKUP_DIR="/var/backups/techit"
RESTORE_LOG="/var/log/techit_restore.log"

# Database credentials
DB_NAME="${DB_NAME:-techit_db}"
DB_USER="${DB_USER:-postgres}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$RESTORE_LOG"
}

# Check arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup_date> [--database-only|--media-only]"
    echo "Example: $0 20241023_020000"
    echo ""
    echo "Available backups:"
    ls -lh "$BACKUP_DIR/database/" | grep ".dump.gz$" | awk '{print $9}'
    exit 1
fi

BACKUP_DATE=$1
RESTORE_MODE=${2:-all}

log "=== Starting restore for backup date: $BACKUP_DATE ==="

# Verify backup files exist
DB_BACKUP="$BACKUP_DIR/database/${PROJECT_NAME}_db_${BACKUP_DATE}.dump.gz"
MEDIA_BACKUP="$BACKUP_DIR/media/${PROJECT_NAME}_media_${BACKUP_DATE}.tar.gz"

if [ "$RESTORE_MODE" != "--media-only" ]; then
    if [ ! -f "$DB_BACKUP" ]; then
        log "Error: Database backup not found: $DB_BACKUP"
        exit 1
    fi
fi

if [ "$RESTORE_MODE" != "--database-only" ]; then
    if [ ! -f "$MEDIA_BACKUP" ]; then
        log "Warning: Media backup not found: $MEDIA_BACKUP"
    fi
fi

# Confirmation prompt
read -p "⚠️  This will OVERWRITE existing data. Are you sure? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    log "Restore cancelled by user"
    exit 0
fi

# 1. Stop application services
log "Stopping application services..."
sudo systemctl stop gunicorn || true
sudo systemctl stop celery || true

# 2. Database Restore
if [ "$RESTORE_MODE" != "--media-only" ]; then
    log "Restoring database..."
    
    # Create backup of current database (just in case)
    log "Creating safety backup of current database..."
    PGPASSWORD="$DB_PASSWORD" pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -F c \
        -f "$BACKUP_DIR/database/${PROJECT_NAME}_pre_restore_$(date +%Y%m%d_%H%M%S).dump" \
        "$DB_NAME"
    
    # Drop existing connections
    log "Dropping existing database connections..."
    PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d postgres \
        -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();"
    
    # Drop and recreate database
    log "Recreating database..."
    PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d postgres \
        -c "DROP DATABASE IF EXISTS $DB_NAME;"
    
    PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d postgres \
        -c "CREATE DATABASE $DB_NAME;"
    
    # Restore from backup
    log "Restoring database from backup..."
    gunzip -c "$DB_BACKUP" | PGPASSWORD="$DB_PASSWORD" pg_restore \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        -v \
        2>&1 | tee -a "$RESTORE_LOG"
    
    log "✓ Database restored successfully"
fi

# 3. Media Files Restore
if [ "$RESTORE_MODE" != "--database-only" ] && [ -f "$MEDIA_BACKUP" ]; then
    log "Restoring media files..."
    
    # Backup current media
    if [ -d "/var/www/techit_solutions/media" ]; then
        log "Backing up current media files..."
        mv /var/www/techit_solutions/media "/var/www/techit_solutions/media_backup_$(date +%Y%m%d_%H%M%S)"
    fi
    
    # Extract media backup
    tar -xzf "$MEDIA_BACKUP" -C /var/www/techit_solutions/
    
    # Fix permissions
    chown -R www-data:www-data /var/www/techit_solutions/media
    chmod -R 755 /var/www/techit_solutions/media
    
    log "✓ Media files restored successfully"
fi

# 4. Run Django migrations (in case schema changed)
log "Running Django migrations..."
cd /var/www/techit_solutions
source venv/bin/activate
python manage.py migrate --noinput 2>&1 | tee -a "$RESTORE_LOG"

# 5. Collect static files
log "Collecting static files..."
python manage.py collectstatic --noinput 2>&1 | tee -a "$RESTORE_LOG"

# 6. Clear cache
log "Clearing application cache..."
python manage.py clear_cache 2>&1 | tee -a "$RESTORE_LOG" || true

# 7. Restart services
log "Restarting application services..."
sudo systemctl start gunicorn
sudo systemctl start celery
sleep 5

# 8. Verify services
log "Verifying services..."
if systemctl is-active --quiet gunicorn; then
    log "✓ Gunicorn is running"
else
    log "✗ Gunicorn failed to start!"
    exit 1
fi

if systemctl is-active --quiet celery; then
    log "✓ Celery is running"
else
    log "⚠ Celery is not running"
fi

log "=== Restore completed successfully ==="
log "Please verify the application is working correctly"

exit 0
