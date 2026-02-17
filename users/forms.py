from django import forms

from .models import User


class UserProfileForm(forms.ModelForm):
    """Lets a logged-in user update their own profile details."""

    class Meta:
        model = User
        fields = ["first_name", "last_name"]
        widgets = {
            "first_name": forms.TextInput(
                attrs={"class": "form-control form-control-lg", "placeholder": "First name"}
            ),
            "last_name": forms.TextInput(
                attrs={"class": "form-control form-control-lg", "placeholder": "Last name"}
            ),
        }
