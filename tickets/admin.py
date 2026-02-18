"""Admin registration for Support Tickets."""

from django.contrib import admin
from django.db.models import Count

from .models import Ticket, TicketMessage


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 1
    fields = ("sender", "body", "is_staff_reply", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "reference_short",
        "subject",
        "user",
        "status",
        "priority",
        "message_count",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "priority")
    search_fields = ("subject", "user__email", "reference")
    readonly_fields = ("reference", "reference_short", "created_at", "updated_at")
    list_per_page = 25
    inlines = [TicketMessageInline]
    fieldsets = (
        (None, {"fields": ("reference_short", "user", "subject")}),
        ("Status", {"fields": ("status", "priority")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_msg_count=Count("messages"))

    @admin.display(description="Replies")
    def message_count(self, obj):
        return obj._msg_count

    def save_formset(self, request, form, formset, change):
        """Auto-mark messages saved via admin as staff replies."""
        for obj in formset.deleted_objects:
            obj.delete()
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, TicketMessage):
                instance.is_staff_reply = True
                if not instance.sender_id:
                    instance.sender = request.user
            instance.save()
        formset.save_m2m()

        # Auto-update ticket status to In Progress when staff replies
        if any(isinstance(i, TicketMessage) for i in instances):
            ticket = form.instance
            if ticket.status == "open":
                ticket.status = "in_progress"
                ticket.save(update_fields=["status"])
