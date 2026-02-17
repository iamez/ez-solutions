# QUICK START GUIDE
Tech-IT Solutions - Complete Enhancement Package

## 🚀 5-Minute Setup

### Step 1: Download and Extract
```bash
# You should already have the package extracted
cd techit_enhancements
```

### Step 2: Run Master Installation Script
```bash
sudo bash master_install.sh
```

This will:
- Install all system dependencies
- Set up Redis and PostgreSQL
- Copy all enhancement files
- Configure Celery
- Set up cron jobs
- Create .env template

### Step 3: Configure Environment
```bash
# Edit the .env file with your settings
nano /var/www/techit_solutions/.env

# At minimum, update these:
# - SECRET_KEY
# - DB_PASSWORD
# - EMAIL credentials
# - STRIPE keys
```

### Step 4: Run Django Setup
```bash
cd /var/www/techit_solutions

# Activate virtual environment (if using one)
source venv/bin/activate

# Run migrations
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Initialize onboarding steps
python manage.py shell << EOF
from customer_experience.onboarding.onboarding_system import OnboardingStep, DEFAULT_ONBOARDING_STEPS
for step_data in DEFAULT_ONBOARDING_STEPS:
    OnboardingStep.objects.get_or_create(**step_data)
EOF
```

### Step 5: Start Services
```bash
# Start application
sudo systemctl restart gunicorn

# Start Celery (via supervisor)
sudo supervisorctl restart celery celerybeat

# Start nginx
sudo systemctl restart nginx
```

### Step 6: Verify Installation
```bash
# Check service status
systemctl status gunicorn
supervisorctl status
systemctl status nginx
systemctl status redis-server
systemctl status postgresql

# Test application
curl http://localhost/health/

# Check logs
tail -f /var/log/techit/django.log
```

## ✅ What You Get

### Email System
- ✅ Transactional emails (orders, invoices, tickets)
- ✅ Welcome emails for new users
- ✅ Password reset emails
- ✅ Service expiry warnings
- ✅ Marketing email capabilities
- ✅ Async email sending via Celery

### Automation
- ✅ Daily automated backups (DB + media + configs)
- ✅ Automated restore scripts
- ✅ SSL certificate auto-renewal
- ✅ CI/CD pipeline configuration
- ✅ Scheduled tasks for cleanup and monitoring

### Security
- ✅ Rate limiting middleware
- ✅ DDoS protection
- ✅ Security headers (CSP, HSTS, etc.)
- ✅ CORS configuration
- ✅ IP whitelisting for admin
- ✅ Request throttling

### Performance
- ✅ Redis caching (multi-layer)
- ✅ Database query optimization
- ✅ Connection pooling
- ✅ Cache warming
- ✅ Static file compression

### Customer Experience
- ✅ Knowledge base with search
- ✅ FAQ system
- ✅ User onboarding system
- ✅ Progress tracking
- ✅ Legal pages (Terms, Privacy, etc.)

### Operations
- ✅ Centralized logging (JSON format)
- ✅ Performance monitoring
- ✅ Security event logging
- ✅ Disaster recovery procedures
- ✅ Database optimization tools

## 📧 Testing Emails

```bash
# Test email sending
cd /var/www/techit_solutions
python manage.py shell

>>> from email_system.email_config import EmailService
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> user = User.objects.first()
>>> EmailService.send_welcome_email(user)
```

## 🔄 Testing Backups

```bash
# Run manual backup
/var/www/techit_solutions/automation/backup_script.sh

# Check backup files
ls -lh /var/backups/techit/database/

# Test restore (be careful - this overwrites data!)
# /var/www/techit_solutions/automation/restore_script.sh YYYYMMDD_HHMMSS
```

## 🔍 Monitoring

### Check Logs
```bash
# Application logs
tail -f /var/log/techit/django.log

# Error logs
tail -f /var/log/techit/django_error.log

# Security logs
tail -f /var/log/techit/security.log

# Celery logs
tail -f /var/log/techit/celery.log
```

### Check Services
```bash
# Redis
redis-cli ping

# PostgreSQL
sudo -u postgres psql -c "\l"

# Celery tasks
celery -A techit_solutions inspect active
celery -A techit_solutions inspect scheduled
```

## 🎯 Common Tasks

### Add New Email Template
1. Create template in `/var/www/techit_solutions/templates/emails/`
2. Use `EmailService.send_email()` to send

### Create Knowledge Base Article
1. Go to admin panel: `/admin/`
2. Navigate to Knowledge Base → Articles
3. Create new article with category

### View User Onboarding Progress
```python
python manage.py shell
>>> from customer_experience.onboarding.onboarding_system import OnboardingManager
>>> from django.contrib.auth import get_user_model
>>> user = get_user_model().objects.get(email='user@example.com')
>>> checklist = OnboardingManager.get_onboarding_checklist(user)
```

### Optimize Database
```bash
python manage.py optimize_database --indexes --analyze --stats
```

### Clear Cache
```python
python manage.py shell
>>> from django.core.cache import cache
>>> cache.clear()
```

## 🆘 Troubleshooting

### Emails Not Sending
1. Check `.env` email settings
2. Verify Celery is running: `supervisorctl status celery`
3. Check logs: `tail -f /var/log/techit/celery.log`

### Rate Limit Too Strict
1. Edit `/var/www/techit_solutions/techit_solutions/settings.py`
2. Adjust `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW`
3. Restart: `systemctl restart gunicorn`

### Backup Failing
1. Check disk space: `df -h`
2. Verify permissions: `ls -la /var/backups/techit`
3. Check logs: `tail -f /var/log/techit_backup.log`

### Database Slow
1. Run: `python manage.py optimize_database --stats`
2. Create indexes: `python manage.py optimize_database --indexes`
3. Run VACUUM: `python manage.py optimize_database --vacuum`

## 📚 Documentation

- **Full README**: `/var/www/techit_solutions/README.md`
- **Disaster Recovery**: `/var/www/techit_solutions/docs/DISASTER_RECOVERY.md`
- **Email Configuration**: Check `email_system/email_config.py`
- **Security Settings**: Check `security/` directory files

## 🎉 You're All Set!

Your Tech-IT Solutions platform now has:
✅ Complete email system
✅ Automated backups
✅ Enhanced security
✅ Performance optimization
✅ Customer experience features
✅ Operational tools

## 🔗 Next Steps

1. Configure your email provider
2. Test the backup system
3. Populate the knowledge base
4. Set up monitoring alerts
5. Review security settings
6. Test disaster recovery procedures

## 💡 Tips

- Review logs daily: `/var/log/techit/`
- Test backups weekly
- Keep dependencies updated: `pip install -r requirements.txt --upgrade`
- Monitor disk space for backups
- Review security logs for suspicious activity

---

**Need Help?**
- Email: support@techitsolutions.com
- Documentation: Check the README.md
- Logs: `/var/log/techit/`

**Happy Hosting! 🚀**
