from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone


def _site_url() -> str:
    return getattr(settings, "SITE_URL", "http://localhost:8000")


def _unsubscribe_url(user_email: str) -> str:
    """Generate unsubscribe URL. Falls back to preferences page if no user found."""
    try:
        from django.contrib.auth import get_user_model

        from notifications.views import make_unsubscribe_token

        User = get_user_model()
        user = User.objects.get(email=user_email)
        token = make_unsubscribe_token(user.pk)
        return f"{_site_url()}/notifications/unsubscribe/{token}/"
    except Exception:
        return f"{_site_url()}/notifications/preferences/"


def send_checkout_success_email(user_email: str, first_name: str, plan_name: str) -> int:
    greeting_name = first_name or "there"
    subject = "Your EZ Solutions subscription is active"
    ctx = {
        "name": greeting_name,
        "plan_name": plan_name,
        "dashboard_url": f"{_site_url()}/dashboard/",
        "billing_url": f"{_site_url()}/billing/",
        "year": timezone.now().year,
        "unsubscribe_url": _unsubscribe_url(user_email),
        "preferences_url": f"{_site_url()}/notifications/preferences/",
    }
    text_body = render_to_string("emails/order_confirmation.txt", ctx)
    html_body = render_to_string("emails/order_confirmation.html", ctx)
    msg = EmailMultiAlternatives(subject, text_body, None, [user_email])
    msg.attach_alternative(html_body, "text/html")
    return msg.send(fail_silently=False)


def send_subscription_canceled_email(user_email: str, first_name: str) -> int:
    greeting_name = first_name or "there"
    subject = "Your EZ Solutions subscription was updated"
    ctx = {
        "name": greeting_name,
        "support_url": f"{_site_url()}/tickets/create/",
        "pricing_url": f"{_site_url()}/pricing/",
        "year": timezone.now().year,
        "unsubscribe_url": _unsubscribe_url(user_email),
        "preferences_url": f"{_site_url()}/notifications/preferences/",
    }
    text_body = render_to_string("emails/subscription_canceled.txt", ctx)
    html_body = render_to_string("emails/subscription_canceled.html", ctx)
    msg = EmailMultiAlternatives(subject, text_body, None, [user_email])
    msg.attach_alternative(html_body, "text/html")
    return msg.send(fail_silently=False)


def send_welcome_email(user_email: str, first_name: str) -> int:
    greeting_name = first_name or "there"
    subject = "Welcome to EZ Solutions!"
    ctx = {
        "name": greeting_name,
        "dashboard_url": f"{_site_url()}/dashboard/",
        "pricing_url": f"{_site_url()}/pricing/",
        "year": timezone.now().year,
        "unsubscribe_url": _unsubscribe_url(user_email),
        "preferences_url": f"{_site_url()}/notifications/preferences/",
    }
    text_body = render_to_string("emails/welcome.txt", ctx)
    html_body = render_to_string("emails/welcome.html", ctx)
    msg = EmailMultiAlternatives(subject, text_body, None, [user_email])
    msg.attach_alternative(html_body, "text/html")
    return msg.send(fail_silently=False)


def send_ticket_notification_email(
    recipient_email: str, ticket_subject: str, message_body: str, ticket_id: int
) -> int:
    safe_subject = ticket_subject.replace("\n", " ").replace("\r", " ")[:100]
    subject = f"[Ticket #{ticket_id}] New reply: {safe_subject}"
    ctx = {
        "ticket_subject": ticket_subject,
        "message_body": message_body,
        "ticket_url": f"{_site_url()}/tickets/{ticket_id}/",
        "year": timezone.now().year,
        "unsubscribe_url": _unsubscribe_url(recipient_email),
        "preferences_url": f"{_site_url()}/notifications/preferences/",
    }
    text_body = render_to_string("emails/ticket_notification.txt", ctx)
    html_body = render_to_string("emails/ticket_notification.html", ctx)
    msg = EmailMultiAlternatives(subject, text_body, None, [recipient_email])
    msg.attach_alternative(html_body, "text/html")
    return msg.send(fail_silently=False)


def send_payment_failed_email(user_email: str, first_name: str, amount: str, currency: str) -> int:
    greeting_name = first_name or "there"
    subject = "Action required: payment failed"
    ctx = {
        "name": greeting_name,
        "amount": amount,
        "currency": currency.upper(),
        "billing_url": f"{_site_url()}/billing/",
        "support_url": f"{_site_url()}/tickets/create/",
        "year": timezone.now().year,
        "unsubscribe_url": _unsubscribe_url(user_email),
        "preferences_url": f"{_site_url()}/notifications/preferences/",
    }
    text_body = render_to_string("emails/payment_failed.txt", ctx)
    html_body = render_to_string("emails/payment_failed.html", ctx)
    msg = EmailMultiAlternatives(subject, text_body, None, [user_email])
    msg.attach_alternative(html_body, "text/html")
    return msg.send(fail_silently=False)
