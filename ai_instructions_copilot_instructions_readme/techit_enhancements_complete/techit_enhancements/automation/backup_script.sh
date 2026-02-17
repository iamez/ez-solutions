#!/bin/bash
# automation/backup_script.sh
# Automated backup script for Tech-IT Solutions platform
# Run daily via cron: 0 2 * * * /path/to/backup_script.sh

set -e  # Exit on error

# Configuration
PROJECT_NAME="techit_solutions"
BACKUP_DIR="/var/backups/techit"
S3_BUCKET="s3://your-backup-bucket"
RETENTION_DAYS=30
DATE=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/var/log/techit_backup.log"

# Database credentials (load from env or secure location)
DB_NAME="${DB_NAME:-techit_db}"
DB_USER="${DB_USER:-postgres}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

# Create backup directory
mkdir -p "$BACKUP_DIR"/{database,media,logs,configs}

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Starting backup for $PROJECT_NAME ==="

# 1. Database Backup (PostgreSQL)
log "Backing up database..."
PGPASSWORD="$DB_PASSWORD" pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -F c \
    -b \
    -v \
    -f "$BACKUP_DIR/database/${PROJECT_NAME}_db_${DATE}.dump" \
    "$DB_NAME" 2>&1 | tee -a "$LOG_FILE"

# Compress database backup
log "Compressing database backup..."
gzip "$BACKUP_DIR/database/${PROJECT_NAME}_db_${DATE}.dump"

# 2. Media Files Backup
log "Backing up media files..."
if [ -d "/var/www/techit_solutions/media" ]; then
    tar -czf "$BACKUP_DIR/media/${PROJECT_NAME}_media_${DATE}.tar.gz" \
        -C /var/www/techit_solutions media/ 2>&1 | tee -a "$LOG_FILE"
fi

# 3. Static Files Backup (optional)
log "Backing up static files..."
if [ -d "/var/www/techit_solutions/staticfiles" ]; then
    tar -czf "$BACKUP_DIR/media/${PROJECT_NAME}_static_${DATE}.tar.gz" \
        -C /var/www/techit_solutions staticfiles/ 2>&1 | tee -a "$LOG_FILE"
fi

# 4. Configuration Files Backup
log "Backing up configuration files..."
tar -czf "$BACKUP_DIR/configs/${PROJECT_NAME}_configs_${DATE}.tar.gz" \
    /etc/nginx/sites-available/${PROJECT_NAME} \
    /etc/systemd/system/gunicorn.service \
    /var/www/techit_solutions/.env \
    2>&1 | tee -a "$LOG_FILE" || true

# 5. Application Logs Backup
log "Backing up logs..."
if [ -d "/var/www/techit_solutions/logs" ]; then
    tar -czf "$BACKUP_DIR/logs/${PROJECT_NAME}_logs_${DATE}.tar.gz" \
        -C /var/www/techit_solutions logs/ 2>&1 | tee -a "$LOG_FILE"
fi

# 6. Create manifest file
log "Creating backup manifest..."
cat > "$BACKUP_DIR/manifest_${DATE}.txt" << EOF
Backup Date: $(date)
Hostname: $(hostname)
Database: ${PROJECT_NAME}_db_${DATE}.dump.gz
Media: ${PROJECT_NAME}_media_${DATE}.tar.gz
Static: ${PROJECT_NAME}_static_${DATE}.tar.gz
Configs: ${PROJECT_NAME}_configs_${DATE}.tar.gz
Logs: ${PROJECT_NAME}_logs_${DATE}.tar.gz
EOF

# 7. Upload to S3 (if configured)
if command -v aws &> /dev/null && [ -n "$S3_BUCKET" ]; then
    log "Uploading to S3..."
    aws s3 sync "$BACKUP_DIR" "$S3_BUCKET/backups/$(date +%Y/%m/%d)/" \
        --exclude "*" \
        --include "database/*${DATE}*" \
        --include "media/*${DATE}*" \
        --include "configs/*${DATE}*" \
        --include "manifest_${DATE}.txt" \
        2>&1 | tee -a "$LOG_FILE"
fi

# 8. Clean up old backups (local)
log "Cleaning up old backups (older than $RETENTION_DAYS days)..."
find "$BACKUP_DIR" -type f -name "*.dump.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -type f -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -type f -name "manifest_*.txt" -mtime +$RETENTION_DAYS -delete

# 9. Verify backup integrity
log "Verifying database backup..."
if [ -f "$BACKUP_DIR/database/${PROJECT_NAME}_db_${DATE}.dump.gz" ]; then
    gunzip -t "$BACKUP_DIR/database/${PROJECT_NAME}_db_${DATE}.dump.gz" 2>&1 | tee -a "$LOG_FILE"
    if [ $? -eq 0 ]; then
        log "✓ Database backup verified successfully"
    else
        log "✗ Database backup verification failed!"
        exit 1
    fi
fi

# 10. Calculate backup sizes
DB_SIZE=$(du -h "$BACKUP_DIR/database/${PROJECT_NAME}_db_${DATE}.dump.gz" 2>/dev/null | cut -f1 || echo "N/A")
MEDIA_SIZE=$(du -h "$BACKUP_DIR/media/${PROJECT_NAME}_media_${DATE}.tar.gz" 2>/dev/null | cut -f1 || echo "N/A")
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)

log "=== Backup Summary ==="
log "Database: $DB_SIZE"
log "Media: $MEDIA_SIZE"
log "Total Backup Size: $TOTAL_SIZE"
log "=== Backup completed successfully ==="

# Send notification (optional)
if command -v curl &> /dev/null && [ -n "$SLACK_WEBHOOK_URL" ]; then
    curl -X POST "$SLACK_WEBHOOK_URL" \
        -H 'Content-Type: application/json' \
        -d "{\"text\":\"✓ Backup completed successfully\nDatabase: $DB_SIZE | Media: $MEDIA_SIZE | Total: $TOTAL_SIZE\"}"
fi

exit 0
