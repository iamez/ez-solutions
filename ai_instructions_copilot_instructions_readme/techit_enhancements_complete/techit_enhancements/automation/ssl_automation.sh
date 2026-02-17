#!/bin/bash
# automation/ssl_automation.sh
# Automated SSL certificate management with Let's Encrypt
# Usage: ./ssl_automation.sh <domain> [--renew]

set -e

DOMAIN=$1
MODE=${2:-install}
EMAIL="admin@techitsolutions.com"
WEBROOT="/var/www/techit_solutions"
LOG_FILE="/var/log/ssl_automation.log"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

if [ -z "$DOMAIN" ]; then
    echo "Usage: $0 <domain> [--renew]"
    echo "Example: $0 techitsolutions.com"
    exit 1
fi

log "=== SSL Certificate Management for $DOMAIN ==="

# Check if certbot is installed
if ! command -v certbot &> /dev/null; then
    log "Certbot not found. Installing..."
    apt-get update
    apt-get install -y certbot python3-certbot-nginx
fi

if [ "$MODE" == "--renew" ]; then
    # Renew existing certificate
    log "Renewing SSL certificate..."
    certbot renew --quiet --nginx
    
    # Reload nginx
    nginx -t && systemctl reload nginx
    
    log "✓ Certificate renewed successfully"
else
    # Install new certificate
    log "Installing SSL certificate for $DOMAIN..."
    
    # Obtain certificate
    certbot --nginx \
        -d "$DOMAIN" \
        -d "www.$DOMAIN" \
        --email "$EMAIL" \
        --agree-tos \
        --no-eff-email \
        --redirect \
        --quiet
    
    if [ $? -eq 0 ]; then
        log "✓ SSL certificate installed successfully"
    else
        log "✗ Failed to install SSL certificate"
        exit 1
    fi
fi

# Configure auto-renewal via cron
CRON_JOB="0 3 * * * certbot renew --quiet --nginx && systemctl reload nginx"
(crontab -l 2>/dev/null | grep -v "certbot renew"; echo "$CRON_JOB") | crontab -

log "✓ Auto-renewal configured (runs daily at 3 AM)"

# Test certificate
log "Testing SSL certificate..."
curl -sI "https://$DOMAIN" | head -n 1

# Display certificate info
certbot certificates -d "$DOMAIN"

log "=== SSL setup completed successfully ==="

exit 0
