# email_system/tasks.py
"""
Celery tasks for asynchronous email sending
"""

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def send_async_email(self, subject, message, recipient_list, html_message=None):
    """
    Send email asynchronously via Celery
    
    Usage:
        from .tasks import send_async_email
        send_async_email.delay('Subject', 'Message', ['user@example.com'])
    """
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False
        )
        logger.info(f"Async email sent: {subject} to {recipient_list}")
        return True
    except Exception as exc:
        logger.error(f"Failed to send async email: {str(exc)}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

@shared_task
def send_bulk_emails(subject, message, recipient_lists, html_message=None):
    """
    Send emails to multiple recipients in batches
    
    Args:
        subject: Email subject
        message: Plain text message
        recipient_lists: List of email addresses
        html_message: HTML version of message
    """
    batch_size = 50
    success_count = 0
    fail_count = 0
    
    for i in range(0, len(recipient_lists), batch_size):
        batch = recipient_lists[i:i + batch_size]
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=batch,
                html_message=html_message,
                fail_silently=False
            )
            success_count += len(batch)
            logger.info(f"Sent batch email to {len(batch)} recipients")
        except Exception as e:
            fail_count += len(batch)
            logger.error(f"Failed to send batch: {str(e)}")
    
    logger.info(f"Bulk email complete. Success: {success_count}, Failed: {fail_count}")
    return {'success': success_count, 'failed': fail_count}

@shared_task
def send_daily_digest():
    """
    Send daily digest emails to users with new activity
    Run via: celery -A techit_solutions beat
    """
    from django.contrib.auth import get_user_model
    from .email_config import EmailService
    
    User = get_user_model()
    users = User.objects.filter(is_active=True, receive_digest=True)
    
    for user in users:
        # Gather user's activity
        context = {
            'user': user,
            'new_tickets': user.tickets.filter(status='open').count(),
            'expiring_services': user.services.filter(
                expiry_date__lte=timezone.now() + timedelta(days=7)
            ).count(),
        }
        
        if context['new_tickets'] > 0 or context['expiring_services'] > 0:
            EmailService.send_email(
                subject='Your Daily Digest',
                template_name='daily_digest',
                context=context,
                recipient_list=[user.email]
            )

@shared_task
def check_expiring_services():
    """
    Check for expiring services and send warnings
    Run daily via celery beat
    """
    from django.utils import timezone
    from datetime import timedelta
    from services.models import Service
    from .email_config import EmailService
    
    # Check services expiring in 30, 7, and 1 days
    warning_days = [30, 7, 1]
    
    for days in warning_days:
        expiry_date = timezone.now() + timedelta(days=days)
        
        services = Service.objects.filter(
            status='active',
            expiry_date__date=expiry_date.date(),
            expiry_warning_sent=False
        )
        
        for service in services:
            EmailService.send_service_expiry_warning(service, days)
            service.expiry_warning_sent = True
            service.save()
        
        logger.info(f"Sent {services.count()} expiry warnings for {days} days")

@shared_task
def send_abandoned_cart_reminder():
    """
    Send reminder emails for abandoned carts
    Run hourly via celery beat
    """
    from django.utils import timezone
    from datetime import timedelta
    from orders.models import Order
    from .email_config import EmailService
    
    # Find orders created 24 hours ago that are still pending
    cutoff_time = timezone.now() - timedelta(hours=24)
    
    abandoned_orders = Order.objects.filter(
        status='pending',
        created_at__lte=cutoff_time,
        reminder_sent=False
    )
    
    for order in abandoned_orders:
        context = {
            'order': order,
            'user': order.user,
            'checkout_url': f"{settings.SITE_URL}/checkout/{order.id}/",
        }
        
        EmailService.send_email(
            subject='Complete Your Order',
            template_name='abandoned_cart',
            context=context,
            recipient_list=[order.user.email]
        )
        
        order.reminder_sent = True
        order.save()
    
    logger.info(f"Sent {abandoned_orders.count()} abandoned cart reminders")

@shared_task
def cleanup_old_emails():
    """
    Archive old email logs (if you implement email logging)
    Run weekly via celery beat
    """
    from django.utils import timezone
    from datetime import timedelta
    
    # Archive emails older than 90 days
    cutoff_date = timezone.now() - timedelta(days=90)
    
    # If you have an EmailLog model:
    # EmailLog.objects.filter(created_at__lte=cutoff_date).delete()
    
    logger.info(f"Cleaned up emails older than {cutoff_date}")
