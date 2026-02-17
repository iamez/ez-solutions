"""Support ticket models — Ticket and TicketMessage."""

import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse


class TicketStatus(models.TextChoices):
    OPEN = "open", "Open"
    IN_PROGRESS = "in_progress", "In Progress"
    WAITING = "waiting", "Waiting on Customer"
    RESOLVED = "resolved", "Resolved"
    CLOSED = "closed", "Closed"


class TicketPriority(models.TextChoices):
    LOW = "low", "Low"
    NORMAL = "normal", "Normal"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class Ticket(models.Model):
    """A support request submitted by a user."""

    reference = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tickets",
    )
    subject = models.CharField(max_length=200)
    status = models.CharField(
        max_length=20,
        choices=TicketStatus.choices,
        default=TicketStatus.OPEN,
        db_index=True,
    )
    priority = models.CharField(
        max_length=10,
        choices=TicketPriority.choices,
        default=TicketPriority.NORMAL,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Support Ticket"
        verbose_name_plural = "Support Tickets"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"[{self.reference_short}] {self.subject}"

    def get_absolute_url(self):
        return reverse("tickets:detail", kwargs={"pk": self.pk})

    @property
    def reference_short(self) -> str:
        """First 8 chars of the UUID — used as a human-readable ticket number."""
        return str(self.reference)[:8].upper()

    @property
    def is_open(self) -> bool:
        return self.status in (TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.WAITING)

    @property
    def message_count(self) -> int:
        return self.messages.count()


class TicketMessage(models.Model):
    """A reply in a ticket thread (from user or staff)."""

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="ticket_messages",
    )
    body = models.TextField()
    is_staff_reply = models.BooleanField(
        default=False,
        help_text="True when the message is sent by a staff member",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ticket Message"
        verbose_name_plural = "Ticket Messages"
        ordering = ["created_at"]

    def __str__(self) -> str:
        sender_name = self.sender.email if self.sender else "deleted user"
        return f"Reply by {sender_name} on {self.created_at:%Y-%m-%d}"
