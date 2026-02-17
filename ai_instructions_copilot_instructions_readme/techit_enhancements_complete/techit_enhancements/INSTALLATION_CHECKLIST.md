# INSTALLATION CHECKLIST

## Pre-Installation
- [ ] Server meets requirements (Ubuntu 20.04+, 2GB+ RAM, 20GB+ disk)
- [ ] Root/sudo access available
- [ ] Domain name configured (optional but recommended)
- [ ] Email provider credentials ready (Gmail, SendGrid, etc.)
- [ ] Stripe account set up (for payments)
- [ ] AWS account for backups (optional but recommended)

## Installation Steps
- [ ] Run `sudo bash master_install.sh`
- [ ] Script completes without errors
- [ ] All services installed (Redis, PostgreSQL, Supervisor)
- [ ] Files copied to `/var/www/techit_solutions/`

## Configuration
- [ ] Edit `/var/www/techit_solutions/.env`
- [ ] Set SECRET_KEY (generate new one!)
- [ ] Set database password
- [ ] Configure email settings (SMTP)
- [ ] Add Stripe API keys
- [ ] Add AWS credentials (for backups)
- [ ] Set ALLOWED_HOSTS with your domain

## Django Setup
- [ ] Run `python manage.py migrate`
- [ ] Create superuser (`python manage.py createsuperuser`)
- [ ] Collect static files (`python manage.py collectstatic`)
- [ ] Initialize onboarding steps
- [ ] Load sample data (optional)

## Service Startup
- [ ] Gunicorn started (`systemctl start gunicorn`)
- [ ] Celery worker running (`supervisorctl status celery`)
- [ ] Celery beat running (`supervisorctl status celerybeat`)
- [ ] Nginx running (`systemctl status nginx`)
- [ ] Redis running (`systemctl status redis-server`)
- [ ] PostgreSQL running (`systemctl status postgresql`)

## Verification
- [ ] Website accessible (http://localhost or your domain)
- [ ] Admin panel accessible (`/admin/`)
- [ ] Can log in with superuser account
- [ ] Health check passes (`/health/`)
- [ ] Test email sends successfully
- [ ] Redis connection works (`redis-cli ping`)
- [ ] Database queries work
- [ ] Static files load correctly

## Automated Tasks
- [ ] Backup cron job configured (`crontab -l`)
- [ ] SSL renewal cron job set up
- [ ] Log rotation configured
- [ ] Celery beat schedule verified

## Security
- [ ] Changed default passwords
- [ ] SECRET_KEY is unique
- [ ] Debug mode disabled (`DEBUG=False`)
- [ ] ALLOWED_HOSTS configured
- [ ] Rate limiting enabled
- [ ] Security headers configured
- [ ] SSL certificate installed (for production)
- [ ] Firewall rules set up

## Backup & Recovery
- [ ] Backup script tested (`./automation/backup_script.sh`)
- [ ] Backup files created in `/var/backups/techit/`
- [ ] S3 sync working (if configured)
- [ ] Restore script tested on staging/dev
- [ ] Disaster recovery plan reviewed

## Monitoring
- [ ] Log directory exists (`/var/log/techit/`)
- [ ] Logs being written
- [ ] Can view application logs
- [ ] Can view error logs
- [ ] Security logs recording events
- [ ] Performance logs tracking requests

## Email System
- [ ] Email templates exist in templates directory
- [ ] SMTP settings correct in .env
- [ ] Test email sent successfully
- [ ] Welcome email template works
- [ ] Order confirmation template works
- [ ] Celery processing email tasks

## Knowledge Base
- [ ] Knowledge base tables migrated
- [ ] Can access `/kb/` (if URL configured)
- [ ] Can create categories
- [ ] Can create articles
- [ ] Search functionality works
- [ ] FAQ section accessible

## Onboarding
- [ ] Onboarding steps created
- [ ] New user sees onboarding
- [ ] Progress tracking works
- [ ] Email sequences configured
- [ ] Can complete onboarding steps

## Legal Pages
- [ ] Terms of Service accessible
- [ ] Privacy Policy accessible
- [ ] Legal pages customized for your company
- [ ] Links in footer working

## Performance
- [ ] Redis cache working
- [ ] Query optimization applied
- [ ] Database indexes created
- [ ] Static files compressed
- [ ] CDN configured (optional)

## Production Checklist (Additional)
- [ ] SSL certificate installed and working
- [ ] Domain DNS configured
- [ ] Production database backed up
- [ ] Staging environment tested
- [ ] Load testing performed
- [ ] Security audit completed
- [ ] Error tracking set up (Sentry, etc.)
- [ ] Uptime monitoring configured
- [ ] Customer data encrypted
- [ ] GDPR compliance checked
- [ ] Backup restoration tested
- [ ] Team trained on disaster recovery

## Post-Installation
- [ ] Documentation reviewed
- [ ] Team access configured
- [ ] Monitoring dashboards set up
- [ ] Alert rules configured
- [ ] Support procedures documented
- [ ] Customer onboarding flow tested
- [ ] Knowledge base populated
- [ ] Legal pages reviewed by legal team

## Ongoing Maintenance
- [ ] Daily log review scheduled
- [ ] Weekly backup verification scheduled
- [ ] Monthly disaster recovery drill scheduled
- [ ] Quarterly security audit scheduled
- [ ] Dependency updates scheduled
- [ ] Performance review scheduled

---

## Sign-Off

### Installation Completed By
- Name: ___________________
- Date: ___________________
- Signature: _______________

### Verified By
- Name: ___________________
- Date: ___________________
- Signature: _______________

### Production Approved By
- Name: ___________________
- Date: ___________________
- Signature: _______________

---

**Notes:**
(Add any installation notes, issues encountered, or special configurations here)

____________________________________________________________
____________________________________________________________
____________________________________________________________
____________________________________________________________
