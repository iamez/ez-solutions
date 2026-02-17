from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from tickets.models import Ticket, TicketStatus

from .forms import UserProfileForm


@login_required
def dashboard(request):
    """Main authenticated dashboard — shows account overview."""
    user = request.user

    # Ticket stats
    tickets_qs = Ticket.objects.filter(user=user)
    total_tickets = tickets_qs.count()
    open_tickets = tickets_qs.filter(
        status__in=[TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.WAITING]
    ).count()

    # Active subscription (may not exist yet for free users)
    customer = getattr(user, "stripe_customer", None)
    subscription = getattr(customer, "subscription", None) if customer else None

    ctx = {
        "user": user,
        "total_tickets": total_tickets,
        "open_tickets": open_tickets,
        "subscription": subscription,
    }
    return render(request, "users/dashboard.html", ctx)


@login_required
def profile(request):
    """Let users update their first/last name."""
    if request.method == "POST":
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("users:profile")
    else:
        form = UserProfileForm(instance=request.user)
    return render(request, "users/profile.html", {"form": form})
