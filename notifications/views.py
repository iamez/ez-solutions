"""Views for notification preferences and email unsubscribe."""

import re

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.signing import BadSignature, TimestampSigner
from django.shortcuts import redirect, render

from .models import NotificationPreference

User = get_user_model()
signer = TimestampSigner(salt="unsubscribe")

# Telegram chat IDs are numeric (optionally negative for groups)
_TELEGRAM_CHAT_ID_RE = re.compile(r"^-?\d{1,20}$")
# E.164 phone numbers: + followed by 7-15 digits
_E164_PHONE_RE = re.compile(r"^\+\d{7,15}$")


def make_unsubscribe_token(user_id: int) -> str:
    """Generate a signed token for one-click unsubscribe."""
    return signer.sign(str(user_id))


def verify_unsubscribe_token(token: str, max_age: int = 60 * 60 * 24 * 30) -> int | None:
    """Verify token, valid for 30 days. Returns user_id or None."""
    try:
        value = signer.unsign(token, max_age=max_age)
        return int(value)
    except (BadSignature, ValueError):
        return None


@login_required
def notification_preferences(request):
    """Let users manage their notification channel preferences."""
    prefs, _ = NotificationPreference.objects.get_or_create(user=request.user)

    if request.method == "POST":
        prefs.email_enabled = request.POST.get("email_enabled") == "on"
        prefs.telegram_enabled = request.POST.get("telegram_enabled") == "on"
        prefs.signal_enabled = request.POST.get("signal_enabled") == "on"

        # Validate and sanitise channel identifiers
        telegram_chat_id = request.POST.get("telegram_chat_id", "").strip()
        signal_phone = request.POST.get("signal_phone", "").strip()

        errors = []
        if telegram_chat_id and not _TELEGRAM_CHAT_ID_RE.match(telegram_chat_id):
            errors.append("Telegram Chat ID must be a numeric value.")
            prefs.telegram_enabled = False
        if signal_phone and not _E164_PHONE_RE.match(signal_phone):
            errors.append("Signal phone must be in E.164 format (e.g. +1234567890).")
            prefs.signal_enabled = False

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            prefs.telegram_chat_id = telegram_chat_id
            prefs.signal_phone = signal_phone

        prefs.save()
        if not errors:
            messages.success(request, "Notification preferences updated.")
        return redirect("notifications:preferences")

    return render(request, "notifications/preferences.html", {"prefs": prefs})


def unsubscribe(request, token: str):
    """One-click email unsubscribe (no login required, token-authenticated)."""
    user_id = verify_unsubscribe_token(token)
    if user_id is None:
        return render(request, "notifications/unsubscribe_invalid.html", status=400)

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return render(request, "notifications/unsubscribe_invalid.html", status=400)

    prefs, _ = NotificationPreference.objects.get_or_create(user=user)

    if request.method == "POST":
        prefs.email_enabled = False
        prefs.save()
        return render(request, "notifications/unsubscribe_done.html")

    return render(request, "notifications/unsubscribe_confirm.html", {"email": user.email})
