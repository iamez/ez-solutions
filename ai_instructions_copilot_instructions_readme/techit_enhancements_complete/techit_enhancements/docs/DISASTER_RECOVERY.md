# DISASTER RECOVERY PLAN
# Tech-IT Solutions Platform

## Table of Contents
1. [Overview](#overview)
2. [Recovery Objectives](#recovery-objectives)
3. [Backup Strategy](#backup-strategy)
4. [Recovery Procedures](#recovery-procedures)
5. [Testing](#testing)
6. [Contact Information](#contact-information)

## Overview

This document outlines the disaster recovery procedures for Tech-IT Solutions platform. It defines the processes and responsibilities for recovering from various disaster scenarios to minimize downtime and data loss.

### Disaster Scenarios Covered
- Hardware failure
- Data center outage
- Cyber attack / Security breach
- Human error / Accidental deletion
- Natural disaster
- Software corruption

## Recovery Objectives

### RTO (Recovery Time Objective)
- **Critical Services**: 4 hours
- **Standard Services**: 24 hours
- **Non-Critical Services**: 72 hours

### RPO (Recovery Point Objective)
- **Database**: 1 hour (hourly backups retained)
- **Media Files**: 24 hours (daily backups)
- **Configuration**: Real-time (version controlled)

## Backup Strategy

### Backup Schedule

#### Daily Backups (2:00 AM UTC)
- Full database dump (PostgreSQL)
- Media files backup
- Configuration files backup
- Application logs

#### Weekly Backups (Sunday 3:00 AM UTC)
- Full system snapshot
- Static files backup
- SSL certificates

#### Monthly Backups (1st of month)
- Complete archive
- Long-term retention

### Backup Locations

#### Primary Backup
- Location: `/var/backups/techit`
- Retention: 7 days
- Type: Local disk

#### Secondary Backup
- Location: AWS S3 `s3://techit-backups/`
- Retention: 30 days
- Type: Cloud storage (encrypted)

#### Tertiary Backup (Off-site)
- Location: Azure Blob Storage
- Retention: 90 days
- Type: Cold storage

### Backup Verification
- Automated verification runs after each backup
- Weekly restore test to staging environment
- Monthly full disaster recovery drill

## Recovery Procedures

### 1. Complete System Failure

**Estimated Recovery Time: 4-8 hours**

#### Step 1: Provision New Infrastructure
```bash
# Provision new server (manual or via IaC)
# Update DNS records to point to new server
# Allow 5-30 minutes for DNS propagation
```

#### Step 2: Install Base System
```bash
# Run system setup
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip postgresql nginx redis-server

# Clone repository
git clone https://github.com/yourusername/techit-solutions.git
cd techit-solutions
```

#### Step 3: Restore Database
```bash
# Download latest backup
aws s3 cp s3://techit-backups/database/latest.dump.gz /tmp/

# Restore database
gunzip -c /tmp/latest.dump.gz | sudo -u postgres pg_restore -d techit_db

# Verify database
sudo -u postgres psql techit_db -c "SELECT COUNT(*) FROM users_customuser;"
```

#### Step 4: Restore Application Files
```bash
# Restore media files
aws s3 sync s3://techit-backups/media/ /var/www/techit_solutions/media/

# Restore configurations
aws s3 cp s3://techit-backups/configs/.env /var/www/techit_solutions/.env
```

#### Step 5: Start Services
```bash
# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Start services
sudo systemctl start gunicorn
sudo systemctl start celery
sudo systemctl start nginx

# Verify
curl http://localhost/health/
```

#### Step 6: Validation
- [ ] Database accessible
- [ ] Application responding
- [ ] User login working
- [ ] Orders processing
- [ ] Emails sending
- [ ] Monitoring active

### 2. Database Corruption

**Estimated Recovery Time: 1-2 hours**

```bash
# Stop application
sudo systemctl stop gunicorn celery

# Backup current (corrupted) database
sudo -u postgres pg_dump techit_db > /tmp/corrupted_backup.sql

# Restore from latest good backup
./automation/restore_script.sh 20241023_020000 --database-only

# Verify data integrity
python manage.py check
python manage.py test

# Restart services
sudo systemctl start gunicorn celery
```

### 3. Accidental Data Deletion

**Estimated Recovery Time: 30 minutes - 2 hours**

#### For Single Record/User
```python
# Connect to Django shell
python manage.py shell

# Restore from backup database
from users.models import User
# Query backup database and restore specific records
```

#### For Multiple Records
```bash
# Use point-in-time restore script
./automation/restore_script.sh YYYYMMDD_HHMMSS --database-only
```

### 4. Security Breach / Ransomware

**Estimated Recovery Time: 4-24 hours**

#### Immediate Actions (First Hour)
1. **Isolate affected systems**
   ```bash
   # Disable network access
   sudo iptables -A INPUT -j DROP
   sudo iptables -A OUTPUT -j DROP
   ```

2. **Preserve evidence**
   ```bash
   # Create forensic image
   sudo dd if=/dev/sda of=/mnt/external/forensic_image.img bs=4M
   ```

3. **Change all credentials**
   - Database passwords
   - Admin passwords
   - API keys
   - SSL certificates

#### Recovery Actions
1. Provision clean infrastructure
2. Restore from verified clean backup (before infection)
3. Apply security patches
4. Implement additional security measures
5. Monitor for reinfection

### 5. Media Files Loss

**Estimated Recovery Time: 2-4 hours**

```bash
# Restore from S3
aws s3 sync s3://techit-backups/media/latest/ /var/www/techit_solutions/media/

# Fix permissions
sudo chown -R www-data:www-data /var/www/techit_solutions/media
sudo chmod -R 755 /var/www/techit_solutions/media

# Verify files
python manage.py check_media_files
```

## Recovery Priority Order

1. **Critical (0-4 hours)**
   - Database
   - Authentication system
   - Payment processing
   - Core API

2. **High (4-24 hours)**
   - Customer dashboard
   - Service provisioning
   - Support ticketing
   - Email notifications

3. **Medium (24-72 hours)**
   - Knowledge base
   - Marketing pages
   - Analytics
   - Reporting

4. **Low (72+ hours)**
   - Historical logs
   - Archived data
   - Development environments

## Testing

### Monthly DR Drill
**First Saturday of each month, 2:00 AM - 6:00 AM UTC**

1. Create staging environment
2. Restore latest backups
3. Run validation tests
4. Document results and improvements
5. Update procedures as needed

### Test Checklist
- [ ] Backup restoration successful
- [ ] All services operational
- [ ] Data integrity verified
- [ ] User authentication working
- [ ] Payment processing functional
- [ ] Email delivery operational
- [ ] Performance acceptable

## Contact Information

### Emergency Response Team

**Primary Contact:**
- Name: [Your Name]
- Phone: [Emergency Phone]
- Email: [Emergency Email]

**Technical Lead:**
- Name: [Technical Lead]
- Phone: [Phone]
- Email: [Email]

**Database Administrator:**
- Name: [DBA Name]
- Phone: [Phone]
- Email: [Email]

### Vendor Contacts

**Hosting Provider:**
- Support: [Phone/Email]
- Account ID: [Account ID]
- SLA: 99.9% uptime

**Cloud Storage:**
- AWS Support: [Phone]
- Account ID: [AWS Account]

**Domain Registrar:**
- Support: [Phone/Email]
- Account: [Account Details]

## Escalation Procedure

### Level 1: Operations Team (0-30 minutes)
- Assess situation
- Begin initial recovery
- Alert management

### Level 2: Management (30-60 minutes)
- Approve major changes
- Customer communication
- Vendor engagement

### Level 3: Executive (1+ hour)
- External communication
- Legal/compliance
- Business continuity decisions

## Post-Incident Review

Within 48 hours of recovery:
1. Document timeline of events
2. Analyze root cause
3. Identify improvements
4. Update DR plan
5. Team debrief meeting

## Appendices

### A. Quick Reference Commands
```bash
# View backup status
./automation/backup_script.sh --status

# Restore database
./automation/restore_script.sh YYYYMMDD_HHMMSS --database-only

# Check system health
curl http://localhost/health/
systemctl status gunicorn celery nginx postgresql redis
```

### B. Recovery Time Estimates
| Scenario | RTO | RPO | Priority |
|----------|-----|-----|----------|
| Database failure | 2h | 1h | Critical |
| Web server failure | 1h | 0 | Critical |
| Media files loss | 4h | 24h | High |
| Configuration loss | 1h | 0 | Critical |
| Complete disaster | 8h | 1h | Critical |

### C. Backup Storage Capacity
- Database: ~5GB (growing ~500MB/month)
- Media: ~50GB (growing ~5GB/month)
- Logs: ~10GB (rotating monthly)
- Total backup size: ~65GB
- S3 storage cost: ~$1.50/month

---

**Document Version:** 1.0  
**Last Updated:** October 24, 2025  
**Next Review:** January 24, 2026  
**Owner:** Operations Team
