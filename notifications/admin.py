from django.contrib import admin

from .models import NotificationLog, NotificationPreference


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "email_enabled", "telegram_enabled", "signal_enabled")
    list_filter = ("email_enabled", "telegram_enabled", "signal_enabled")
    search_fields = ("user__email",)


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "channel", "subject", "recipient", "success")
    list_filter = ("channel", "success")
    search_fields = ("subject", "recipient")
    readonly_fields = ("user", "channel", "subject", "recipient", "success", "error_message", "created_at")
    date_hierarchy = "created_at"
