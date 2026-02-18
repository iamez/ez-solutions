from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from .emailing import send_checkout_success_email, send_subscription_canceled_email
from .models import PaymentEvent
from .webhooks import HANDLED_EVENTS, handle_event

log = logging.getLogger(__name__)
User = get_user_model()


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    soft_time_limit=60,
    time_limit=120,
)
def process_stripe_event(payment_event_id: int) -> None:
    from django.utils import timezone

    from .models import EventStatus

    try:
        payment_event = PaymentEvent.objects.get(pk=payment_event_id)
    except PaymentEvent.DoesNotExist:
        log.warning("PaymentEvent %s disappeared before processing", payment_event_id)
        return

    # Guard: skip if already processed/failed (prevents double-processing on retry)
    if payment_event.status in (EventStatus.PROCESSED, EventStatus.SKIPPED):
        log.info("PaymentEvent %s already %s — skipping", payment_event_id, payment_event.status)
        return

    if payment_event.event_type not in HANDLED_EVENTS:
        payment_event.status = EventStatus.SKIPPED
        payment_event.processed_at = timezone.now()
        payment_event.save(update_fields=["status", "processed_at"])
        return

    payment_event.status = EventStatus.PROCESSING
    payment_event.save(update_fields=["status"])

    try:
        handle_event(payment_event.payload)
        payment_event.status = EventStatus.PROCESSED
        payment_event.processed_at = timezone.now()
        payment_event.save(update_fields=["status", "processed_at"])
    except Exception as exc:
        payment_event.status = EventStatus.FAILED
        payment_event.error_message = str(exc)[:2000]
        payment_event.processed_at = timezone.now()
        payment_event.save(update_fields=["status", "error_message", "processed_at"])
        log.exception("Async webhook handler failed for event %s", payment_event.stripe_event_id)
        raise


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    soft_time_limit=60,
    time_limit=120,
)
def send_checkout_success_email_task(user_id: int, plan_name: str) -> None:
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        log.warning("User %s not found for checkout email", user_id)
        return

    send_checkout_success_email(
        user_email=user.email,
        first_name=user.first_name,
        plan_name=plan_name,
    )


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    soft_time_limit=60,
    time_limit=120,
)
def send_subscription_canceled_email_task(user_id: int) -> None:
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        log.warning("User %s not found for canceled email", user_id)
        return

    send_subscription_canceled_email(
        user_email=user.email,
        first_name=user.first_name,
    )


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    soft_time_limit=60,
    time_limit=120,
)
def send_welcome_email_task(user_id: int) -> None:
    from .emailing import send_welcome_email

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        log.warning("User %s not found for welcome email", user_id)
        return

    send_welcome_email(
        user_email=user.email,
        first_name=user.first_name,
    )


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    soft_time_limit=60,
    time_limit=120,
)
def send_ticket_notification_task(ticket_id: int, message_id: int, recipient_email: str) -> None:
    from tickets.models import TicketMessage

    from .emailing import send_ticket_notification_email

    try:
        message = TicketMessage.objects.select_related("ticket").get(pk=message_id)
    except TicketMessage.DoesNotExist:
        log.warning("TicketMessage %s not found for notification", message_id)
        return

    send_ticket_notification_email(
        recipient_email=recipient_email,
        ticket_subject=message.ticket.subject,
        message_body=message.body[:500],
        ticket_id=ticket_id,
    )


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    soft_time_limit=60,
    time_limit=120,
)
def send_payment_failed_email_task(user_id: int, amount: str, currency: str) -> None:
    from .emailing import send_payment_failed_email

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        log.warning("User %s not found for payment-failed email", user_id)
        return

    send_payment_failed_email(
        user_email=user.email,
        first_name=user.first_name,
        amount=amount,
        currency=currency,
    )


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    soft_time_limit=120,
    time_limit=300,
)
def provision_vps_task(provisioning_job_id: int) -> None:
    """Process a queued ProvisioningJob: call provider and create VPSInstance."""
    from django.utils import timezone

    from .models import (
        ProvisioningJob,
        ProvisioningStatus,
        VPSInstance,
        VPSInstanceStatus,
    )
    from .provisioning import PLAN_SPECS, get_provider

    try:
        job = ProvisioningJob.objects.select_related(
            "order__customer__user",
            "order__service_plan",
        ).get(pk=provisioning_job_id)
    except ProvisioningJob.DoesNotExist:
        log.warning("ProvisioningJob %s not found", provisioning_job_id)
        return

    # Guard: don't re-process finished jobs
    if job.status in (ProvisioningStatus.READY, ProvisioningStatus.FAILED):
        log.info("ProvisioningJob %s already %s — skipping", provisioning_job_id, job.status)
        return

    # Mark as provisioning
    job.status = ProvisioningStatus.PROVISIONING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])

    order = job.order
    plan = order.service_plan
    tier_key = plan.tier_key if plan else ""
    specs = PLAN_SPECS.get(tier_key, PLAN_SPECS["starter"])
    hostname = f"vps-{order.pk}-{plan.slug}.ez-solutions.dev"

    try:
        provider = get_provider(job.provider)
        result = provider.provision(job)

        # Create VPSInstance
        VPSInstance.objects.create(
            provisioning_job=job,
            customer=order.customer,
            subscription=order.subscription,
            hostname=hostname,
            ip_address=result.get("ip_address", ""),
            proxmox_vmid=result.get("vmid"),
            os_template=specs["os_template"],
            cpu_cores=specs["cpu_cores"],
            ram_mb=specs["ram_mb"],
            disk_gb=specs["disk_gb"],
            status=VPSInstanceStatus.RUNNING,
        )

        # Mark job complete
        job.external_id = result.get("external_id", "")
        job.status = ProvisioningStatus.READY
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "external_id", "completed_at"])

        # Notify user
        _queue_vps_ready_notification(order.customer.user.pk, hostname)
        log.info("ProvisioningJob %s completed — %s", provisioning_job_id, hostname)

    except Exception as exc:
        job.status = ProvisioningStatus.FAILED
        job.error_message = str(exc)[:2000]
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_message", "completed_at"])
        log.exception("ProvisioningJob %s failed", provisioning_job_id)
        _queue_vps_failed_notification(provisioning_job_id, str(exc)[:500])
        raise


def _queue_vps_ready_notification(user_id: int, hostname: str) -> None:
    from notifications.tasks import send_notification_task

    body = f"Your VPS {hostname} is ready!"
    html_body = f"<p>Your VPS <strong>{hostname}</strong> is ready!</p>"
    try:
        send_notification_task.apply_async(
            args=[user_id, "VPS Ready", body],
            kwargs={"html_body": html_body},
            ignore_result=True,
        )
    except Exception:  # noqa: BLE001
        log.exception("VPS-ready notification enqueue failed for user %s", user_id)


def _queue_vps_failed_notification(job_id: int, error: str) -> None:
    from notifications.tasks import send_admin_notification_task

    body = f"ProvisioningJob #{job_id} failed: {error}"
    html_body = f"<p>ProvisioningJob <strong>#{job_id}</strong> failed: {error}</p>"
    try:
        send_admin_notification_task.apply_async(
            args=["VPS Provisioning Failed", body],
            kwargs={"html_body": html_body},
            ignore_result=True,
        )
    except Exception:  # noqa: BLE001
        log.exception("VPS-failed admin notification enqueue failed for job %s", job_id)
