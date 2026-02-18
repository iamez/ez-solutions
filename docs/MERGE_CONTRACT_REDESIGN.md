# EZ Solutions — Backend/Redesign Merge Contract

## Purpose

Define what must stay stable while the website redesign is in progress, so frontend and backend can ship in parallel without blocking each other.

## Contract Window

- Start: 2026-02-18
- Ends: first integration pass after redesign PR is ready
- Owner: Backend API contract owned by backend track

## Stable API Contracts (Do Not Break)

- `GET /api/health/`
- `GET /api/v1/schema/`
- `GET /api/v1/docs/`
- `POST /api/v1/auth/token/`
- `POST /api/v1/auth/token/refresh/`
- `GET /api/v1/plans/`
- `GET /api/v1/tickets/`
- `POST /api/v1/tickets/`
- `GET /api/v1/tickets/<id>/`
- `POST /api/v1/tickets/<id>/reply/`
- `GET /api/v1/me/`
- `PATCH /api/v1/me/`

## Stable Core Models (Do Not Rename)

- `users.User`
- `services.ServicePlan`
- `orders.Customer`
- `orders.Subscription`
- `orders.PaymentEvent`
- `orders.Order`
- `orders.ProvisioningJob`
- `orders.VPSInstance`
- `tickets.Ticket`
- `tickets.TicketMessage`

## Allowed Changes During Redesign

- HTML templates and CSS/Tailwind only
- Component/layout restructuring
- Improved content/UX copy
- Non-breaking JS enhancements

## Restricted Changes During Redesign

- No endpoint renames or path changes
- No serializer field removals
- No auth flow changes without backend approval
- No model renames/migration rewrites

## Integration Checklist

1. Pull latest backend branch
2. Run migrations
3. Run API tests (`tests/test_api.py`)
4. Validate `/api/v1/schema/` and `/api/v1/docs/`
5. Verify redesigned pages hit existing endpoints without 4xx/5xx
6. Run full test suite before merge

## Conflict Resolution Rules

- API/model changes override template assumptions
- If UI needs different fields, add backward-compatible fields first
- Deprecate old fields for at least one release cycle

## Notes

- Backend currently supports both session auth (browser) and JWT auth (API clients).
- Stripe webhook flow is async-first with synchronous fallback if queue is unavailable.
