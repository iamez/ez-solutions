"""Support ticket views."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .forms import TicketCreateForm, TicketMessageForm
from .models import Ticket, TicketMessage, TicketStatus


@login_required
def ticket_list(request):
    """Show all tickets belonging to the logged-in user with filtering + pagination."""
    tickets = request.user.tickets.prefetch_related("messages").all()

    # Status filter
    status_filter = request.GET.get("status", "")
    if status_filter and status_filter in TicketStatus.values:
        tickets = tickets.filter(status=status_filter)

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        tickets = tickets.filter(subject__icontains=q)

    paginator = Paginator(tickets.order_by("-updated_at"), 15)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "tickets/ticket_list.html",
        {
            "tickets": page,
            "status_filter": status_filter,
            "q": q,
            "status_choices": TicketStatus.choices,
        },
    )


@login_required
def ticket_create(request):
    """Submit a new support ticket."""
    if request.method == "POST":
        form = TicketCreateForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                ticket = form.save(commit=False)
                ticket.user = request.user
                ticket.save()

                # Create the first message from the body field
                TicketMessage.objects.create(
                    ticket=ticket,
                    sender=request.user,
                    body=form.cleaned_data["body"],
                    is_staff_reply=False,
                )
            messages.success(
                request,
                f"Ticket #{ticket.reference_short} submitted. We'll be in touch shortly.",
            )
            return redirect("tickets:detail", pk=ticket.pk)
    else:
        form = TicketCreateForm()
    return render(request, "tickets/ticket_create.html", {"form": form})


@login_required
def ticket_detail(request, pk):
    """View a ticket thread; users can only see their own tickets."""
    ticket = get_object_or_404(Ticket, pk=pk, user=request.user)
    reply_form = TicketMessageForm()

    if request.method == "POST":
        if not ticket.is_open:
            messages.warning(
                request,
                "This ticket is closed. Please open a new one if you need further help.",
            )
            return redirect("tickets:detail", pk=pk)

        reply_form = TicketMessageForm(request.POST)
        if reply_form.is_valid():
            reply = reply_form.save(commit=False)
            reply.ticket = ticket
            reply.sender = request.user
            reply.is_staff_reply = False
            reply.save()

            # Customer replied → move status back to Open if it was waiting
            if ticket.status == TicketStatus.WAITING:
                ticket.status = TicketStatus.OPEN
                ticket.save(update_fields=["status"])

            messages.success(request, "Your reply has been sent.")
            return redirect("tickets:detail", pk=pk)

    thread = ticket.messages.select_related("sender").all()
    return render(
        request,
        "tickets/ticket_detail.html",
        {
            "ticket": ticket,
            "thread": thread,
            "reply_form": reply_form,
        },
    )
