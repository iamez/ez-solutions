"""Celery Beat periodic tasks for subscription lifecycle management."""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task

log = logging.getLogger(__name__)


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    soft_time_limit=120,
    time_limit=180,
)
def check_expiring_subscriptions() -> int:
    """Check for subscriptions expiring within 3 days and notify users.

    Runs daily.  Only notifies once per subscription by checking whether a
    NotificationLog with a subject containing "subscription expiring" already
    exists for the user within the last 3 days.

    Returns the number of notifications sent.
    """
    from django.utils import timezone

    from notifications.models import NotificationLog
    from notifications.tasks import send_notification_task
    from orders.models import Subscription, SubscriptionStatus

    now = timezone.now()
    expiry_window = now + timedelta(days=3)

    expiring_subs = Subscription.objects.filter(
        status__in=[SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING],
        current_period_end__lte=expiry_window,
        current_period_end__gt=now,
        cancel_at_period_end=True,
    ).select_related("customer__user")

    sent = 0
    for sub in expiring_subs:
        user = sub.customer.user

        # Skip if we already notified this user about an expiring sub recently
        already_notified = NotificationLog.objects.filter(
            user=user,
            subject__icontains="subscription expiring",
            created_at__gte=now - timedelta(days=3),
        ).exists()

        if already_notified:
            log.debug(
                "Skipping expiry notification for user %s (sub %s) — already notified",
                user.pk,
                sub.pk,
            )
            continue

        days_left = (sub.current_period_end - now).days
        subject = "Your subscription is expiring soon"
        body = (
            f"Hi {user.get_full_name() or user.email},\n\n"
            f"Your subscription ({sub.stripe_subscription_id}) is set to expire "
            f"in {days_left} day{'s' if days_left != 1 else ''}. "
            f"If you'd like to continue your service, please renew before "
            f"{sub.current_period_end:%Y-%m-%d %H:%M} UTC.\n\n"
            f"— EZ Solutions"
        )

        send_notification_task.delay(user.pk, subject, body)
        sent += 1
        log.info(
            "Queued expiry notification for user %s (sub %s, expires %s)",
            user.pk,
            sub.pk,
            sub.current_period_end,
        )

    log.info("check_expiring_subscriptions complete: %d notifications queued", sent)
    return sent


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    soft_time_limit=120,
    time_limit=180,
)
def cleanup_stale_provisioning_jobs() -> int:
    """Mark provisioning jobs stuck in 'provisioning' for >1 hour as failed.

    Notifies admins about each stale job.  Runs every 30 minutes.

    Returns the number of jobs marked as failed.
    """
    from django.utils import timezone

    from notifications.tasks import send_admin_notification_task
    from orders.models import ProvisioningJob, ProvisioningStatus

    now = timezone.now()
    stale_cutoff = now - timedelta(hours=1)

    stale_jobs = ProvisioningJob.objects.filter(
        status=ProvisioningStatus.PROVISIONING,
        started_at__lt=stale_cutoff,
    )

    count = 0
    for job in stale_jobs:
        job.status = ProvisioningStatus.FAILED
        job.error_message = "Timed out after 1 hour"
        job.save(update_fields=["status", "error_message", "updated_at"])
        count += 1

        send_admin_notification_task.delay(
            subject=f"Provisioning job #{job.pk} timed out",
            body=(
                f"ProvisioningJob #{job.pk} (order #{job.order_id}) has been stuck in "
                f"'provisioning' since {job.started_at:%Y-%m-%d %H:%M} UTC and was "
                f"automatically marked as failed."
            ),
        )
        log.warning("Marked stale ProvisioningJob #%d as failed", job.pk)

    log.info("cleanup_stale_provisioning_jobs complete: %d jobs failed", count)
    return count


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    soft_time_limit=60,
    time_limit=120,
)
def cleanup_old_payment_events() -> int:
    """Delete processed/skipped payment events older than 90 days.

    Runs weekly.

    Returns the number of events deleted.
    """
    from django.utils import timezone

    from orders.models import EventStatus, PaymentEvent

    cutoff = timezone.now() - timedelta(days=90)

    deleted_count, _ = PaymentEvent.objects.filter(
        status__in=[EventStatus.PROCESSED, EventStatus.SKIPPED],
        processed_at__lt=cutoff,
    ).delete()

    log.info("cleanup_old_payment_events complete: %d events deleted", deleted_count)
    return deleted_count
