# email_system/celery.py
"""
Celery Configuration for Tech-IT Solutions
Place this file in your Django project root (same level as settings.py)
"""

import os
from celery import Celery
from celery.schedules import crontab

# Set default Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "techit_solutions.settings")

app = Celery("techit_solutions")

# Load config from Django settings with CELERY namespace
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

# Celery Beat Schedule for periodic tasks
app.conf.beat_schedule = {
    "send-daily-digest": {
        "task": "email_system.tasks.send_daily_digest",
        "schedule": crontab(hour=8, minute=0),  # Daily at 8 AM
    },
    "check-expiring-services": {
        "task": "email_system.tasks.check_expiring_services",
        "schedule": crontab(hour=0, minute=0),  # Daily at midnight
    },
    "send-abandoned-cart-reminders": {
        "task": "email_system.tasks.send_abandoned_cart_reminder",
        "schedule": crontab(minute="*/60"),  # Every hour
    },
    "cleanup-old-emails": {
        "task": "email_system.tasks.cleanup_old_emails",
        "schedule": crontab(day_of_week=0, hour=1, minute=0),  # Weekly on Sunday at 1 AM
    },
}

# Celery task configuration
app.conf.task_routes = {
    "email_system.tasks.*": {"queue": "emails"},
    "monitoring.*": {"queue": "monitoring"},
}

app.conf.task_time_limit = 300  # 5 minutes
app.conf.task_soft_time_limit = 240  # 4 minutes


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
