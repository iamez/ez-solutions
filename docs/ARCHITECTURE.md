# EZ Solutions — Architecture & Decisions

> Generated: February 18, 2026
> Sources: Codebase audit, ChatGPT deep research (docs/ez-solutions-research.md),
> session analysis, Django SaaS best practices

---

## 1. High-Level Architecture

EZ Solutions follows a **three-layer architecture**:

```
┌─────────────────────────────────────────────────────┐
│                   BROWSER / CLIENT                   │
│            (HTML pages + REST API calls)              │
└───────────────┬──────────────────┬──────────────────┘
                │ Sessions         │ JWT (future)
                ▼                  ▼
┌─────────────────────────────────────────────────────┐
│              DJANGO APPLICATION (Brain)               │
│                                                       │
│  config/       — Settings (base → dev | prod)        │
│  users/        — Custom User model, dashboard        │
│  services/     — ServicePlan catalog                 │
│  orders/       — Stripe billing, webhooks            │
│  tickets/      — Support system                      │
│  api/          — DRF REST API v1                     │
│  home/         — Public marketing pages              │
│  domains/      — (empty, future DNS management)      │
│                                                       │
│  Celery workers (future) → async webhook handling    │
└───────┬───────────┬──────────┬──────────────────────┘
        │           │          │
        ▼           ▼          ▼
┌───────────┐ ┌──────────┐ ┌──────────────────────────┐
│ PostgreSQL│ │  Redis   │ │ Self-Hosted OSS Services  │
│ (DB)      │ │ (cache/  │ │                          │
│           │ │  broker) │ │ • Chatwoot  (live chat)   │
└───────────┘ └──────────┘ │ • HestiaCP  (panel)      │
                           │ • Prometheus (metrics)    │
                           │ • Grafana   (dashboards)  │
                           │ • Mailpit   (dev email)   │
                           └──────────────────────────┘
                                      │
                           ┌──────────┴──────────┐
                           │  External Services   │
                           │                      │
                           │ • Stripe (billing)   │
                           │ • Mailgun (email)    │
                           │ • Cloudflare (CDN)   │
                           │ • Sentry (errors)    │
                           │ • Proxmox (VPS API)  │
                           └──────────────────────┘
```

### Guiding Principles

| # | Principle | Rationale |
|---|-----------|-----------|
| 1 | Stripe is the billing source of truth | Django mirrors Stripe state via webhooks; never diverge |
| 2 | Async webhooks | Return 2xx immediately, process via Celery |
| 3 | Inbox-table pattern for events | Insert PaymentEvent first, then dispatch processing |
| 4 | Idempotent everything | Duplicate Stripe events must be safe no-ops |
| 5 | Sessions for browser, JWT for API | Two auth strategies, never mix them |
| 6 | No custom card forms | Stripe Checkout + Portal only → SAQ A PCI scope |
| 7 | Feature flags over feature branches | Ship dark code, enable via DB/admin toggle |
| 8 | Delete before adding | Remove stubs/dead code before writing new code |

---

## 2. Django Project Layout

```
config/                 ← Project settings & URL root
  settings/
    __init__.py
    base.py             ← Shared settings (209 lines)
    dev.py              ← DEBUG=True, SQLite, console email
    prod.py             ← PostgreSQL, Mailgun, Sentry, SSL
  urls.py               ← URL router (7 app includes)
  wsgi.py / asgi.py

users/                  ← AUTH_USER_MODEL = "users.User"
services/               ← ServicePlan + PlanFeature (catalog)
orders/                 ← Customer + Subscription + PaymentEvent (billing)
tickets/                ← Ticket + TicketMessage (support)
api/                    ← DRF ViewSets (/api/v1/)
home/                   ← Public pages (landing, pricing, about)
domains/                ← EMPTY — future DNS management

templates/              ← Global templates (base.html, account/, etc.)
static/css/             ← Tailwind CSS output
tests/                  ← Centralized tests (conftest + phase tests)
```

### Settings Strategy

| Setting | `dev.py` | `prod.py` |
|---------|----------|-----------|
| `DEBUG` | `True` | `False` |
| Database | SQLite | PostgreSQL |
| Email | Console backend | Anymail/Mailgun |
| Static | Django dev server | WhiteNoise |
| Cache | Local memory | Redis |
| Error tracking | None | Sentry |
| CORS | Allow all | Restricted origins |
| HTTPS | Off | Full HSTS + secure cookies |

---

## 3. Canonical Data Model

### Current Models (implemented and tested)

```
┌──────────┐     1:1      ┌──────────────┐
│  User    │─────────────▶│  Customer    │
│          │              │ (Stripe CID) │
│ email    │              └──────┬───────┘
│ tier     │                     │ 1:N
│ is_paid  │              ┌──────▼───────┐
└────┬─────┘              │ Subscription │
     │                    │ (Stripe SID) │
     │ 1:N                │ status       │
     │                    │ period_start │
     │                    │ period_end   │
     │                    └──────────────┘
     │
     │ 1:N                ┌──────────────┐
     ├───────────────────▶│   Ticket     │
     │                    │ reference    │
     │                    │ status       │
     │                    │ priority     │
     │                    └──────┬───────┘
     │                           │ 1:N
     │                    ┌──────▼───────┐
     │                    │TicketMessage │
     │                    │ body         │
     │                    │ is_staff_reply│
     │                    └──────────────┘

┌──────────────┐
│ ServicePlan  │          ┌──────────────┐
│ name/slug    │──── 1:N─▶│ PlanFeature  │
│ price_monthly│          │ label/value  │
│ stripe_price │          │ sort_order   │
│ tier_key     │          └──────────────┘
└──────────────┘

┌──────────────┐
│ PaymentEvent │   (webhook inbox — idempotency log)
│ stripe_event_id (unique)
│ event_type
│ payload (JSON)
│ processed_at
└──────────────┘
```

### Future Models (Phase 2-3, from research)

```
┌──────────────────────────────────────────────────────────────┐
│                    FULFILLMENT LAYER                          │
│                                                              │
│  Order                              ProvisioningJob           │
│  ────────                           ──────────────           │
│  customer (FK→Customer)             order (FK→Order)         │
│  service_plan (FK→ServicePlan)      status (enum: queued,    │
│  status (pending/paid/cancelled)       provisioning, ready,  │
│  stripe_payment_intent_id                failed)             │
│  created_at                         provider (proxmox, etc.) │
│  total_amount                       external_id              │
│                                     started_at / completed_at│
│                                     error_message            │
│                                                              │
│  VPSInstance                        Entitlement              │
│  ────────────                       ────────────             │
│  provisioning_job (FK)              customer (FK→Customer)   │
│  hostname                           plan (FK→ServicePlan)    │
│  ip_address                         subscription (FK→Sub)    │
│  proxmox_vmid                       is_active                │
│  os_template                        granted_at / expires_at  │
│  specs (JSON: cpu/ram/disk)                                  │
│  status (running/stopped/etc.)                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. URL Architecture

### Current Routes

| Path | App | Purpose |
|------|-----|---------|
| `/` | `home` | Landing page |
| `/admin/` | Django admin | Staff administration |
| `/accounts/` | `allauth` | Login, register, email verify, password reset |
| `/dashboard/` | `users` | Authenticated user area |
| `/services/` | `services` | Pricing page |
| `/checkout/` | `orders` | Stripe Checkout session creation |
| `/billing/portal/` | `orders` | Stripe Customer Portal redirect |
| `/webhooks/stripe/` | `orders` | Stripe webhook receiver |
| `/tickets/` | `tickets` | Support ticket CRUD |
| `/api/v1/health/` | `api` | Health check endpoint |
| `/api/v1/plans/` | `api` | Service plan list (public) |
| `/api/v1/tickets/` | `api` | Ticket list + create (auth) |
| `/api/v1/tickets/<id>/` | `api` | Ticket detail (auth) |
| `/api/v1/tickets/<id>/reply/` | `api` | Ticket reply (auth) |
| `/api/v1/me/` | `api` | Current user profile (auth) |

### Future Routes (by phase)

| Path | Phase | Purpose |
|------|-------|---------|
| `/api/v1/schema/` | B | OpenAPI schema (drf-spectacular) |
| `/api/v1/docs/` | B | Swagger UI |
| `/api/v1/auth/token/` | B | JWT obtain pair |
| `/api/v1/auth/token/refresh/` | B | JWT refresh |
| `/dashboard/orders/` | 2 | Order history |
| `/dashboard/vps/` | 3 | VPS instance management |
| `/dashboard/domains/` | 3 | Domain management |

---

## 5. Authentication Strategy

### Browser Users (current)

```
Browser → Session cookie → Django SessionAuthentication
         ↓
         allauth handles: login, register, verify email, password reset
         ↓
         Session stored in DB (default) or Redis (future)
```

- **Custom User model**: `users.User` with `USERNAME_FIELD = "email"`
- **No username**: email-only authentication
- **SubscriptionTier**: stored directly on User model (free/starter/professional/enterprise)
- **Permission**: `is_paid` property checks tier ≠ free

### API Clients (future — Phase B)

```
Client → Authorization: Bearer <JWT> → djangorestframework-simplejwt
         ↓
         /api/v1/auth/token/          → obtain access + refresh tokens
         /api/v1/auth/token/refresh/  → rotate access token
```

- **Access token**: 5-minute lifetime (short-lived)
- **Refresh token**: 1-day lifetime
- **Rotation**: new refresh token issued on each refresh call
- **Blacklist**: old refresh tokens invalidated

### Auth Configuration

```python
# allauth settings (in base.py)
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "optional"  # → change to "mandatory" for prod

# DRF default authentication (in base.py)
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
}
```

---

## 6. Stripe Integration Architecture

### Current Flow (synchronous)

```
Customer clicks "Subscribe"
  → POST /checkout/session/create/
  → Django creates Stripe Checkout Session
  → Redirect to Stripe-hosted Checkout page
  → Customer pays
  → Stripe sends webhook to /webhooks/stripe/
  → Django verifies signature with raw request.body
  → Django processes event SYNCHRONOUSLY ← (problem: slow)
  → Returns 200
```

### Target Flow (async — Phase 1)

```
Stripe sends webhook to /webhooks/stripe/
  → Django verifies signature ✓
  → Inserts PaymentEvent row (inbox table)
  → Returns 200 immediately  ← (fast, Stripe happy)
  → Celery worker picks up PaymentEvent
  → Dispatches to handler based on event_type
  → Idempotency check: if already processed → skip
  → Updates Subscription model state
  → Syncs User.subscription_tier
  → Marks PaymentEvent as processed
```

### Webhook Events Handled

| Event | Action |
|-------|--------|
| `checkout.session.completed` | Create/link Customer, lookup Subscription |
| `customer.subscription.updated` | Update Subscription status + period dates |
| `customer.subscription.deleted` | Mark Subscription canceled, downgrade User tier |
| `invoice.payment_succeeded` | (future) Create PaymentRecord |
| `invoice.payment_failed` | (future) Send dunning email, flag account |

---

## 7. Key Architecture Decisions

### ADR-001: Email-only authentication

- **Decision**: Use email as sole login identifier (no username)
- **Context**: Modern SaaS standard; simplifies UX
- **Implementation**: Custom User model with `USERNAME_FIELD = "email"`, allauth configured accordingly
- **Status**: Implemented ✅

### ADR-002: Split settings with python-decouple

- **Decision**: Three-file settings split (base/dev/prod) with env var injection
- **Context**: Prevents secrets in code; enables different configs per environment
- **Implementation**: `config/settings/{base,dev,prod}.py` + `.env` file
- **Status**: Implemented ✅

### ADR-003: Stripe Checkout + Portal only (no custom forms)

- **Decision**: Never build custom card input forms; use Stripe-hosted surfaces exclusively
- **Context**: Reduces PCI scope to SAQ A; Stripe handles all card data
- **Implementation**: Redirect to `stripe.checkout.Session`, redirect to `stripe.billing_portal.Session`
- **Status**: Implemented ✅

### ADR-004: PaymentEvent as inbox table

- **Decision**: Every Stripe webhook inserts a PaymentEvent row BEFORE processing
- **Context**: Ensures idempotency, auditability, and enables async processing
- **Implementation**: PaymentEvent model exists; needs Celery worker (Phase 1)
- **Status**: Partially implemented (model exists, sync processing)

### ADR-005: PostgreSQL for production

- **Decision**: SQLite in dev, PostgreSQL in prod
- **Context**: PostgreSQL handles concurrency, supports JSON fields natively, required for Celery beat
- **Implementation**: Configured in prod.py via `DATABASE_URL` env var
- **Status**: Implemented ✅

### ADR-006: Celery + Redis for async work

- **Decision**: Use Celery with Redis broker for background tasks
- **Context**: Webhook processing, email sending, VPS provisioning all need async
- **Implementation**: Packages installed, django_celery_beat in INSTALLED_APPS, but Celery app NOT created
- **Status**: Not yet implemented (Phase 1)

### ADR-007: WhiteNoise for static files

- **Decision**: Serve static files via WhiteNoise middleware (no separate Nginx for static)
- **Context**: Simplifies deployment; sufficient for small-to-medium SaaS
- **Implementation**: WhiteNoiseMiddleware in MIDDLEWARE, STATICFILES_STORAGE configured
- **Status**: Implemented ✅

### ADR-008: Centralized test suite

- **Decision**: All tests in `tests/` directory with phase-based organization
- **Context**: Prevents test files from cluttering app directories; enables phase-gated testing
- **Implementation**: `tests/conftest.py` + `test_phase{0,1,2,3,4}.py`
- **Status**: Implemented ✅ (143 tests passing)

---

## 8. Deployment Architecture (Target)

```
┌─────────────────────────────────────────────────────────┐
│                    Cloudflare CDN                        │
│              (DNS + SSL termination + WAF)               │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│                   Proxmox Host Server                    │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │             Docker Compose Stack                 │   │
│  │                                                   │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐      │   │
│  │  │  Django   │  │  Celery  │  │  Celery  │      │   │
│  │  │  (Gunicorn│  │  Worker  │  │  Beat    │      │   │
│  │  │  + Nginx) │  │          │  │ (scheduler│     │   │
│  │  └─────┬─────┘  └─────┬────┘  └──────────┘      │   │
│  │        │              │                           │   │
│  │  ┌─────▼──────────────▼──────┐                   │   │
│  │  │        Redis              │                   │   │
│  │  │  (cache + Celery broker)  │                   │   │
│  │  └───────────────────────────┘                   │   │
│  │                                                   │   │
│  │  ┌───────────────────────────┐                   │   │
│  │  │      PostgreSQL           │                   │   │
│  │  └───────────────────────────┘                   │   │
│  └───────────────────────────────────────────────────┘   │
│                                                         │
│  ┌───────────────┐  ┌──────────────┐                   │
│  │  Chatwoot     │  │  HestiaCP    │                   │
│  │  (live chat)  │  │  (hosting)   │                   │
│  └───────────────┘  └──────────────┘                   │
│                                                         │
│  ┌───────────────┐  ┌──────────────┐                   │
│  │  Prometheus   │  │  Grafana     │                   │
│  │  (metrics)    │  │  (dashboard) │                   │
│  └───────────────┘  └──────────────┘                   │
│                                                         │
│  ┌──────────────────────────────────┐                   │
│  │      Customer VPS Instances      │                   │
│  │   (provisioned via Proxmox API)  │                   │
│  └──────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────┘
```

---

## 9. Technology Stack Summary

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Framework | Django | 4.2.21 (LTS) | Web framework |
| Python | CPython | 3.13.7 | Runtime |
| Auth | django-allauth | 65.14.3 | Registration, login, email verify |
| API | DRF | 3.15.2 | REST API framework |
| Billing | stripe | 11.5.0 | Payment processing |
| Task queue | Celery | 5.4.0 | Async workers (not yet wired) |
| Broker/cache | Redis | 5.2.1 | Celery broker + Django cache |
| Static files | WhiteNoise | latest | Serve static from Django |
| CORS | django-cors-headers | latest | Cross-origin API access |
| Config | python-decouple | latest | Env var management |
| Linting | ruff | latest | Lint + format |
| Security scan | bandit | latest | Static security analysis |
| Testing | pytest-django | latest | Test runner + fixtures |
| Coverage | pytest-cov | latest | Code coverage |
| Error tracking | sentry-sdk | latest | Production error reporting |

---

## 10. What Does NOT Exist Yet (and Must Be Built)

| Gap | Impact | Phase |
|-----|--------|-------|
| Celery app + worker | Webhooks process synchronously (fragile) | Phase 1 |
| Order model | No record of what was purchased | Phase 2 |
| ProvisioningJob model | No way to track VPS creation progress | Phase 3 |
| VPSInstance model | No record of running VPS instances | Phase 3 |
| Entitlement model | No formal "what does this customer have access to?" | Phase 2 |
| Domains integration | Empty models.py — placeholder only | Phase 3 |
| Admin dashboard | No staff-facing overview beyond raw Django admin | Phase 2 |
| Email templates | No transactional email templates | Phase 2 |
| CI/CD pipeline | GitHub Actions workflow exists but not verified | Phase 0 |
| Docker Compose | No containerization config yet | Phase 2 |
| Proxmox API client | No integration with Proxmox for VPS provisioning | Phase 3 |
| HestiaCP integration | No integration with HestiaCP for hosting panel | Phase 3 |
| Chatwoot widget | No live chat yet | Future |
