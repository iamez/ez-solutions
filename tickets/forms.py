"""Forms for the Support Tickets app."""

from django import forms

from .models import Ticket, TicketMessage, TicketPriority


class TicketCreateForm(forms.ModelForm):
    """Form for submitting a new support ticket."""

    body = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 6, "class": "form-control"}),
        label="Describe your issue",
        help_text="Please be as detailed as possible so we can help you quickly.",
    )

    class Meta:
        model = Ticket
        fields = ("subject", "priority")
        widgets = {
            "subject": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Brief summary of your issue"}
            ),
            "priority": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["priority"].initial = TicketPriority.NORMAL


class TicketMessageForm(forms.ModelForm):
    """Form for adding a reply to an existing ticket."""

    class Meta:
        model = TicketMessage
        fields = ("body",)
        widgets = {
            "body": forms.Textarea(
                attrs={"rows": 4, "class": "form-control", "placeholder": "Type your reply…"}
            ),
        }
        labels = {"body": "Your reply"}
