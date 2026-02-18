from django.contrib import admin

from .models import NotificationLog, NotificationPreference


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "email_enabled", "telegram_enabled", "signal_enabled")
    list_filter = ("email_enabled", "telegram_enabled", "signal_enabled")
    search_fields = ("user__email",)
    readonly_fields = ("masked_telegram_chat_id", "masked_signal_phone")

    @admin.display(description="Telegram Chat ID")
    def masked_telegram_chat_id(self, obj):
        val = obj.telegram_chat_id
        if not val:
            return "—"
        return val[:3] + "***" + val[-2:] if len(val) > 5 else "***"

    @admin.display(description="Signal Phone")
    def masked_signal_phone(self, obj):
        val = obj.signal_phone
        if not val:
            return "—"
        return val[:4] + "****" + val[-2:] if len(val) > 6 else "***"

    def get_exclude(self, request, obj=None):
        # Hide raw fields; show masked versions instead
        return ("telegram_chat_id", "signal_phone")


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "channel", "subject", "recipient", "success")
    list_filter = ("channel", "success")
    search_fields = ("subject", "recipient")
    readonly_fields = (
        "user",
        "channel",
        "subject",
        "recipient",
        "success",
        "error_message",
        "created_at",
    )
    date_hierarchy = "created_at"
