"""Management command to create/update django-celery-beat PeriodicTask entries."""

import json

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update Celery Beat periodic tasks for subscription lifecycle management."

    def handle(self, *args, **options):
        from django_celery_beat.models import (
            CrontabSchedule,
            IntervalSchedule,
            PeriodicTask,
        )

        self.stdout.write("Setting up periodic tasks…")

        # ── Schedule: daily at 08:00 UTC ──────────────────────────────
        daily_0800, _ = CrontabSchedule.objects.get_or_create(
            minute="0",
            hour="8",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            defaults={"timezone": "UTC"},
        )

        PeriodicTask.objects.update_or_create(
            name="check-expiring-subscriptions",
            defaults={
                "task": "orders.periodic.check_expiring_subscriptions",
                "crontab": daily_0800,
                "interval": None,
                "enabled": True,
                "description": "Check for subscriptions expiring within 3 days and notify users.",
                "kwargs": json.dumps({}),
            },
        )
        self.stdout.write(self.style.SUCCESS("  ✓ check-expiring-subscriptions (daily 08:00 UTC)"))

        # ── Schedule: every 30 minutes ────────────────────────────────
        every_30_min, _ = IntervalSchedule.objects.get_or_create(
            every=30,
            period=IntervalSchedule.MINUTES,
        )

        PeriodicTask.objects.update_or_create(
            name="cleanup-stale-provisioning-jobs",
            defaults={
                "task": "orders.periodic.cleanup_stale_provisioning_jobs",
                "interval": every_30_min,
                "crontab": None,
                "enabled": True,
                "description": (
                    "Mark provisioning jobs stuck in 'provisioning' for >1 hour as failed."
                ),
                "kwargs": json.dumps({}),
            },
        )
        self.stdout.write(self.style.SUCCESS("  ✓ cleanup-stale-provisioning-jobs (every 30 min)"))

        # ── Schedule: weekly on Sunday at 03:00 UTC ───────────────────
        weekly_sun_0300, _ = CrontabSchedule.objects.get_or_create(
            minute="0",
            hour="3",
            day_of_week="0",  # Sunday
            day_of_month="*",
            month_of_year="*",
            defaults={"timezone": "UTC"},
        )

        PeriodicTask.objects.update_or_create(
            name="cleanup-old-payment-events",
            defaults={
                "task": "orders.periodic.cleanup_old_payment_events",
                "crontab": weekly_sun_0300,
                "interval": None,
                "enabled": True,
                "description": "Delete processed/skipped payment events older than 90 days.",
                "kwargs": json.dumps({}),
            },
        )
        self.stdout.write(self.style.SUCCESS("  ✓ cleanup-old-payment-events (Sunday 03:00 UTC)"))

        self.stdout.write(self.style.SUCCESS("\nAll periodic tasks configured."))
