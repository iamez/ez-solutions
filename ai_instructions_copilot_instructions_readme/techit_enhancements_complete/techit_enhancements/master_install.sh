#!/bin/bash
# master_install.sh
# Master installation script for Tech-IT Solutions enhancements
# Run with: sudo bash master_install.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/var/www/techit_solutions"
BACKUP_DIR="/var/backups/techit"
LOG_DIR="/var/log/techit"
VENV_DIR="$PROJECT_DIR/venv"

# Logging
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    error "Please run as root (use sudo)"
    exit 1
fi

log "=== Tech-IT Solutions Enhancement Installation ==="
log "This script will install all missing pieces for your platform"

# Confirm installation
read -p "Continue with installation? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    log "Installation cancelled"
    exit 0
fi

# 1. System Packages
log "Installing system packages..."
apt update
apt install -y \
    python3-pip \
    python3-dev \
    postgresql \
    postgresql-contrib \
    redis-server \
    nginx \
    certbot \
    python3-certbot-nginx \
    supervisor \
    curl \
    git \
    vim

# 2. Create directories
log "Creating directories..."
mkdir -p "$BACKUP_DIR"/{database,media,logs,configs}
mkdir -p "$LOG_DIR"
mkdir -p "$PROJECT_DIR"

# Set permissions
chown -R www-data:www-data "$BACKUP_DIR"
chown -R www-data:www-data "$LOG_DIR"
chmod -R 755 "$BACKUP_DIR"
chmod -R 755 "$LOG_DIR"

# 3. Python dependencies
log "Installing Python dependencies..."
pip3 install --upgrade pip

# Install required packages
pip3 install \
    django \
    psycopg2-binary \
    celery[redis] \
    redis \
    django-redis \
    gunicorn \
    python-dotenv \
    markdown \
    python-dateutil \
    stripe \
    requests \
    pillow \
    boto3

log "Python dependencies installed"

# 4. Configure Redis
log "Configuring Redis..."
systemctl enable redis-server
systemctl start redis-server

# 5. Configure PostgreSQL
log "Configuring PostgreSQL..."
systemctl enable postgresql
systemctl start postgresql

# Create database and user (if not exists)
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = 'techit_db'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE techit_db;"

sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname = 'techit_user'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER techit_user WITH PASSWORD 'change_this_password';"

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE techit_db TO techit_user;"

log "PostgreSQL configured"

# 6. Copy enhancement files
log "Copying enhancement files..."

if [ -d "./email_system" ]; then
    cp -r ./email_system "$PROJECT_DIR/"
    log "✓ Email system copied"
fi

if [ -d "./automation" ]; then
    cp -r ./automation "$PROJECT_DIR/"
    chmod +x "$PROJECT_DIR"/automation/*.sh
    log "✓ Automation scripts copied"
fi

if [ -d "./security" ]; then
    cp -r ./security "$PROJECT_DIR/"
    log "✓ Security modules copied"
fi

if [ -d "./customer_experience" ]; then
    cp -r ./customer_experience "$PROJECT_DIR/"
    log "✓ Customer experience modules copied"
fi

if [ -d "./operations" ]; then
    cp -r ./operations "$PROJECT_DIR/"
    log "✓ Operations modules copied"
fi

if [ -d "./docs" ]; then
    cp -r ./docs "$PROJECT_DIR/"
    log "✓ Documentation copied"
fi

# 7. Configure Celery with Supervisor
log "Configuring Celery..."

cat > /etc/supervisor/conf.d/celery.conf << 'EOF'
[program:celery]
command=/var/www/techit_solutions/venv/bin/celery -A techit_solutions worker -l info
directory=/var/www/techit_solutions
user=www-data
numprocs=1
stdout_logfile=/var/log/techit/celery.log
stderr_logfile=/var/log/techit/celery_error.log
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=600
killasgroup=true
priority=998

[program:celerybeat]
command=/var/www/techit_solutions/venv/bin/celery -A techit_solutions beat -l info
directory=/var/www/techit_solutions
user=www-data
numprocs=1
stdout_logfile=/var/log/techit/celerybeat.log
stderr_logfile=/var/log/techit/celerybeat_error.log
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=600
killasgroup=true
priority=999
EOF

supervisorctl reread
supervisorctl update

log "Celery configured"

# 8. Configure cron jobs
log "Setting up cron jobs..."

# Daily backups
(crontab -l 2>/dev/null; echo "0 2 * * * $PROJECT_DIR/automation/backup_script.sh") | crontab -

# SSL renewal
(crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet --nginx && systemctl reload nginx") | crontab -

# Log rotation
(crontab -l 2>/dev/null; echo "0 0 * * * find $LOG_DIR -name '*.log' -type f -mtime +7 -exec gzip {} \;") | crontab -

log "Cron jobs configured"

# 9. Environment file template
log "Creating .env template..."

cat > "$PROJECT_DIR/.env.example" << 'EOF'
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DB_NAME=techit_db
DB_USER=techit_user
DB_PASSWORD=change_this_password
DB_HOST=localhost
DB_PORT=5432

# Email Configuration
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@techitsolutions.com
SUPPORT_EMAIL=support@techitsolutions.com
BILLING_EMAIL=billing@techitsolutions.com

# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Stripe
STRIPE_PUBLIC_KEY=your-stripe-public-key
STRIPE_SECRET_KEY=your-stripe-secret-key
STRIPE_WEBHOOK_SECRET=your-webhook-secret

# AWS (for backups)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_STORAGE_BUCKET_NAME=your-bucket-name
AWS_S3_REGION_NAME=us-east-1

# Security
RATE_LIMIT_ENABLED=True
DDOS_PROTECTION_ENABLED=True

# Site Configuration
SITE_URL=https://yourdomain.com
SITE_NAME=Tech-IT Solutions
EOF

if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    log "✓ .env file created - PLEASE UPDATE WITH YOUR SETTINGS!"
else
    log "✓ .env file already exists (not overwritten)"
fi

# 10. Set permissions
log "Setting permissions..."
chown -R www-data:www-data "$PROJECT_DIR"
chmod -R 755 "$PROJECT_DIR"
chmod 600 "$PROJECT_DIR/.env"

# 11. Test services
log "Testing services..."

# Test Redis
if redis-cli ping | grep -q "PONG"; then
    log "✓ Redis is running"
else
    error "✗ Redis is not responding"
fi

# Test PostgreSQL
if sudo -u postgres psql -c "\l" | grep -q "techit_db"; then
    log "✓ PostgreSQL database exists"
else
    error "✗ PostgreSQL database not found"
fi

# 12. Summary
log ""
log "=== Installation Complete ==="
log ""
log "Next steps:"
log "1. Update $PROJECT_DIR/.env with your settings"
log "2. Run: cd $PROJECT_DIR && python manage.py migrate"
log "3. Run: python manage.py collectstatic --noinput"
log "4. Run: python manage.py createsuperuser"
log "5. Start services:"
log "   - systemctl restart gunicorn"
log "   - supervisorctl restart celery celerybeat"
log "   - systemctl restart nginx"
log ""
log "Configuration files:"
log "- Environment: $PROJECT_DIR/.env"
log "- Backups: $BACKUP_DIR"
log "- Logs: $LOG_DIR"
log ""
log "Automation scripts:"
log "- Backup: $PROJECT_DIR/automation/backup_script.sh"
log "- Restore: $PROJECT_DIR/automation/restore_script.sh"
log "- SSL: $PROJECT_DIR/automation/ssl_automation.sh"
log ""
log "Documentation:"
log "- README: $PROJECT_DIR/README.md"
log "- Disaster Recovery: $PROJECT_DIR/docs/DISASTER_RECOVERY.md"
log ""
warning "IMPORTANT: Update your .env file before starting the application!"
log ""

exit 0
