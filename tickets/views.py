"""Support ticket views."""

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import TicketCreateForm, TicketMessageForm
from .models import Ticket, TicketMessage, TicketPriority, TicketStatus


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


# ---------------------------------------------------------------------------
# Staff ticket management views
# ---------------------------------------------------------------------------


@login_required
@staff_member_required
def staff_ticket_list(request):
    """Staff dashboard — list ALL tickets with filtering, search, and pagination."""
    tickets = Ticket.objects.select_related("user").annotate(
        msg_count=Count("messages"),
    )

    # Status filter
    status_filter = request.GET.get("status", "")
    if status_filter and status_filter in TicketStatus.values:
        tickets = tickets.filter(status=status_filter)

    # Priority filter
    priority_filter = request.GET.get("priority", "")
    if priority_filter and priority_filter in TicketPriority.values:
        tickets = tickets.filter(priority=priority_filter)

    # Search by subject or user email
    q = request.GET.get("q", "").strip()
    if q:
        tickets = tickets.filter(Q(subject__icontains=q) | Q(user__email__icontains=q))

    paginator = Paginator(tickets.order_by("-updated_at"), 20)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "tickets/staff_list.html",
        {
            "tickets": page,
            "status_filter": status_filter,
            "priority_filter": priority_filter,
            "q": q,
            "status_choices": TicketStatus.choices,
            "priority_choices": TicketPriority.choices,
        },
    )


@login_required
@staff_member_required
def staff_ticket_detail(request, pk):
    """Staff view — view any ticket thread, reply, and change status."""
    ticket = get_object_or_404(Ticket.objects.select_related("user"), pk=pk)
    reply_form = TicketMessageForm()

    if request.method == "POST":
        action = request.POST.get("action", "reply")

        if action == "status":
            new_status = request.POST.get("status", "")
            if new_status and new_status in TicketStatus.values:
                ticket.status = new_status
                ticket.save(update_fields=["status"])
                messages.success(
                    request,
                    f"Ticket status changed to {ticket.get_status_display()}.",
                )
            return redirect("tickets:staff_detail", pk=pk)

        # Default action: reply
        reply_form = TicketMessageForm(request.POST)
        if reply_form.is_valid():
            with transaction.atomic():
                reply = reply_form.save(commit=False)
                reply.ticket = ticket
                reply.sender = request.user
                reply.is_staff_reply = True
                reply.save()

                # Auto-set status to WAITING when staff replies
                if ticket.status != TicketStatus.WAITING:
                    ticket.status = TicketStatus.WAITING
                    ticket.save(update_fields=["status"])

            messages.success(request, "Staff reply sent.")
            return redirect("tickets:staff_detail", pk=pk)

    thread = ticket.messages.select_related("sender").all()
    return render(
        request,
        "tickets/staff_detail.html",
        {
            "ticket": ticket,
            "thread": thread,
            "reply_form": reply_form,
            "status_choices": TicketStatus.choices,
        },
    )
