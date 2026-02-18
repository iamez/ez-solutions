from __future__ import annotations

from django.core.mail import send_mail
from django.template.loader import render_to_string


def send_checkout_success_email(user_email: str, first_name: str, plan_name: str) -> int:
    greeting_name = first_name or "there"
    subject = "Your EZ Solutions subscription is active"
    body = render_to_string(
        "emails/order_confirmation.txt",
        {"name": greeting_name, "plan_name": plan_name},
    )
    return send_mail(subject, body, None, [user_email], fail_silently=False)


def send_subscription_canceled_email(user_email: str, first_name: str) -> int:
    greeting_name = first_name or "there"
    subject = "Your EZ Solutions subscription was updated"
    body = render_to_string("emails/subscription_canceled.txt", {"name": greeting_name})
    return send_mail(subject, body, None, [user_email], fail_silently=False)
