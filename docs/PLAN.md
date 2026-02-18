# EZ Solutions — Master Implementation Plan

> Generated: February 18, 2026
> Sources: Copilot project audit + ChatGPT deep research (docs/ez-solutions-research.md)

---

## Current Reality (as of commit 6465ea3)

| Metric | Value |
|--------|-------|
| Tests | 143 passing |
| Coverage | 88% |
| Linting | ruff + black clean |
| Security scan | bandit 0 issues |
| Django check | 0 issues |
| Python | 3.13.7 |
| Django | 4.2.21 |

### What's Working

- Custom `User` model (email-only auth, `subscription_tier` field)
- `django-allauth` for registration/login/email verification/password reset
- `ServicePlan` + `PlanFeature` models with seed command
- Stripe Checkout + Customer Portal + webhook handler with signature verification
- `Customer`, `Subscription`, `PaymentEvent` models (Stripe object mirroring)
- Support tickets (`Ticket`, `TicketMessage`, full CRUD + admin)
- REST API: 6 endpoints under `/api/v1/`
- CI/CD: 3-job pipeline (quality + test matrix + security), CodeQL, Dependabot
- 26 Bootstrap templates covering auth, dashboard, pricing, tickets, errors
- Admin panels for all 4 apps (users, orders, services, tickets)
- Pre-commit hooks, Makefile, pyproject.toml config

### What's NOT Working (stub/dead files)

24 placeholder files with zero code — just 2-line comments:

- `security/` — 4 files (caching, db optimization, rate limiting, headers)
- `operations/` — 1 file (logging config)
- `email_system/` — 3 Python files + 5 HTML templates (all stubs)
- `customer_experience/` — 4 files (knowledge base, legal pages, onboarding)
- `automation/` — 4 files (backup, restore, SSL, CI/CD)
- `docs/DISASTER_RECOVERY.md` — stub
- `domains/` — models/views/tests/admin all empty (only `apps.py` is real)
- `apps/` — entire directory is empty test folders, mirrors top-level apps

### What's Real But Not Integrated

9 files in `ai_instructions_copilot_instructions_readme/` contain actual implementations
(health checks, monitoring middleware, test suites, Prometheus configs, alert rules)
that were never wired into the project.

---

## Guiding Principles

1. **Django monolith is the brain** — owns customers, billing, entitlements, fulfillment tracking
2. **Stripe webhooks are the source of truth** — never provision based on redirect alone
3. **Process webhooks async** — insert event, return 2xx, process in Celery
4. **Don't rebuild what OSS already solved** — chat (Chatwoot), hosting (HestiaCP), monitoring (Grafana)
5. **Fulfillment tracking before automation** — track orders/jobs manually first, automate later
6. **Quality gates on every change** — ruff + black + pytest + bandit + pip-audit must pass

---

## Phase 0 — Clean House + Prod Hardening (~2 hours)

**Goal:** Honest codebase with production-safe defaults.

### Tasks

- [ ] Delete `apps/` directory (dead scaffold, empty test folders)
- [ ] Delete `automation/` stubs (4 comment-only files)
- [ ] Delete `customer_experience/` stubs (4 comment-only files)
- [ ] Delete `docs/DISASTER_RECOVERY.md` stub
- [ ] Delete `security/` stubs (4 comment-only files — rebuild properly in Phase C)
- [ ] Delete `operations/` stub (1 comment-only file — rebuild in Phase C)
- [ ] Delete `email_system/` stubs (3 .py + 5 .html comment-only files)
- [ ] Remove `domains` app from `INSTALLED_APPS` (models empty, re-add when ready)
- [ ] Add `CSRF_TRUSTED_ORIGINS` to prod settings
- [ ] Run `manage.py check --deploy` against prod settings, fix all warnings
- [ ] Verify `.env.example` has all required env vars documented
- [ ] Confirm no secrets committed to git

### Acceptance Criteria

- All stub files removed
- `manage.py check --deploy` passes (or warnings documented with justification)
- All existing tests still pass
- Clean git history (single commit: `chore: remove stub files, harden prod settings`)

---

## Phase 1 — Webhook Async Refactor + Idempotency (~3-4 hours)

**Goal:** Stripe event processing is idempotent and async per Stripe best practices.

### Why This Matters

Current webhook handler processes synchronously inside the HTTP request. Stripe says:
- Events can arrive **out of order**
- Events may be delivered **more than once**
- Handlers should be **asynchronous** (return 2xx immediately, process in background)

### Tasks

- [ ] Refactor `PaymentEvent` to act as an **inbox table**:
  - Add `status` field: `received` → `processing` → `processed` / `failed`
  - Insert FIRST with `get_or_create(stripe_event_id=event.id)`, THEN process
  - Duplicate = return 200 immediately (no-op)
- [ ] Wire Celery app properly (`config/celery.py`)
- [ ] Create `orders/tasks.py` with `process_stripe_event` Celery task
- [ ] Webhook view: verify signature → insert event → enqueue task → return 200
- [ ] Add idempotency keys on outbound Stripe API calls:
  - `create_checkout_session`: key = `f"checkout-{user.pk}-{plan.slug}-{timestamp_bucket}"`
  - `billing_portal.Session.create`: key = `f"portal-{user.pk}-{timestamp_bucket}"`
- [ ] Add tests:
  - Duplicate event ID is safe no-op
  - Invalid signature returns 400
  - Out-of-order events don't corrupt subscription state
  - Celery task processes event and updates models correctly

### Acceptance Criteria

- Webhook returns 2xx in <200ms (no synchronous Stripe API calls in handler)
- Duplicate webhook deliveries are safe no-ops
- Subscription state updates correctly via background task
- PaymentEvent has full audit trail (status + timestamps)

---

## Phase B — API Hardening (~2-3 hours)

**Goal:** Production-grade REST API with docs, auth options, and rate limiting.

### Tasks

- [ ] Install `drf-spectacular` → OpenAPI schema + Swagger UI at `/api/schema/swagger-ui/`
- [ ] Install `djangorestframework-simplejwt` → JWT auth at `/api/token/` + `/api/token/refresh/`
- [ ] Configure DRF throttles in settings:
  - Anonymous: 100/hour
  - Authenticated: 1000/hour
  - Ticket creation: 10/hour per user
- [ ] Add `DEFAULT_VERSIONING_CLASS` to DRF settings
- [ ] Add tests for rate limiting and JWT token flow

### New Packages

```
drf-spectacular>=0.28.0
djangorestframework-simplejwt>=5.4.0
```

### Acceptance Criteria

- Swagger UI accessible at `/api/schema/swagger-ui/`
- JWT auth works for API endpoints
- Rate limiting enforced
- Existing session auth still works for browser clients

---

## Phase 2 — Fulfillment Tracking (NEW — from research) (~3-4 hours)

**Goal:** Bridge the gap between "customer pays" and "customer gets the service."

### Why This Matters

Currently there's no way to track: "Customer bought Professional plan → they want a VPS →
someone needs to create it → it's done." This is the provisioning layer.

### Tasks

- [ ] Create `provisioning/` Django app with models:
  - `Order` (user, service_type, plan FK, requested_params JSON, status, created/updated)
  - `ProvisioningJob` (order FK, status state machine, logs, attempts, worker)
  - `VPSInstance` (order FK, vmid, node, ip_address, status, credentials_delivered)
- [ ] Order status choices: `pending` → `in_progress` → `completed` / `failed` / `cancelled`
- [ ] ProvisioningJob status: `queued` → `running` → `needs_info` → `complete` / `failed`
- [ ] Admin UI for operators to manage orders and jobs
- [ ] Dashboard shows user's orders and their status
- [ ] Link support tickets to orders (optional FK on Ticket)
- [ ] Entitlements mapping: plan tier → allowed service types and limits
- [ ] Add tests for order creation and status transitions

### Acceptance Criteria

- Customer can request a service from dashboard
- Admin can see/manage all orders and update status
- Order status visible on customer dashboard
- Audit trail on status changes

---

## Phase C — Security Middleware (~3 hours)

**Goal:** Real security hardening replacing the empty stubs.

### Tasks

- [ ] Install `django-axes` → brute-force login protection
- [ ] Install `django-csp` → Content Security Policy headers
- [ ] Implement structured logging (stdlib `logging.config.dictConfig` or `django-structlog`)
- [ ] Install `django-health-check` → production health endpoint (DB, Redis, Celery, disk)
- [ ] Install `django-simple-history` → audit trail on Subscription, Ticket, User
- [ ] Configure HSTS rollout (start with low max-age, document preload plan)

### New Packages

```
django-axes>=6.0
django-csp>=4.0
django-health-check>=3.18
django-simple-history>=3.7
```

### Acceptance Criteria

- Failed login attempts trigger lockout after N attempts
- CSP headers present on responses (start in Report-Only mode)
- Health endpoint checks DB + cache connectivity
- Model changes tracked with history

---

## Phase D — Email System (~3 hours)

**Goal:** Transactional emails work via Celery background tasks.

### Tasks

- [ ] Wire Celery app (`config/celery.py` — if not done in Phase 1)
- [ ] Build real email templates (HTML):
  - Welcome email (after registration)
  - Order confirmation (after checkout)
  - Ticket notification (new reply)
  - Service expiry warning
- [ ] Create Celery tasks in `email_system/tasks.py`:
  - `send_welcome_email(user_id)`
  - `send_order_confirmation(order_id)`
  - `send_ticket_notification(ticket_id, message_id)`
- [ ] Connect signals/hooks to trigger emails:
  - allauth `user_signed_up` signal → welcome email
  - Ticket message created → notification email
  - Webhook subscription activated → confirmation email
- [ ] Local dev: use Django console backend (already configured)
- [ ] Document `MAILGUN_API_KEY` + `MAILGUN_SENDER_DOMAIN` for prod

### Acceptance Criteria

- Emails trigger on correct events
- Console backend shows emails in dev
- Celery tasks are retryable on failure
- Templates are branded and responsive

---

## Phase E — Test Coverage Push (~2 hours)

**Goal:** Close remaining coverage gaps to 93%+.

### Tasks

- [ ] `orders/views.py` (70% → 90%+): mock Stripe webhook signatures, test checkout flow
- [ ] `tickets/admin.py` (56% → 85%+): test admin save_formset staff-reply logic
- [ ] `seed_plans` management command (0% → 80%+): `call_command('seed_plans')` test
- [ ] New provisioning app: comprehensive model + view tests
- [ ] Celery tasks: test with `CELERY_TASK_ALWAYS_EAGER=True`

### Acceptance Criteria

- Overall coverage ≥ 93%
- No critical path untested
- CI enforces coverage threshold

---

## Phase 3 — Proxmox VPS Provisioning MVP (dedicated session)

**Goal:** Automated VPS provisioning for the VPS product line.

### Tasks

- [ ] Create Cloud-Init VM templates on Proxmox
- [ ] Create Proxmox API token (least-privilege, `pveum`)
- [ ] Implement Proxmox API client in `provisioning/proxmox.py`
- [ ] Celery task: clone template → configure (CPU/RAM/disk/SSH keys) → start VM
- [ ] Update `VPSInstance` model with VMID, IP, status
- [ ] Rollback: failed provisioning cleans up or marks for manual cleanup
- [ ] Dashboard shows VPS status (running/stopped/provisioning)
- [ ] Document Proxmox env vars

### Environment Variables (new)

```
PROXMOX_API_URL=https://pve-host:8006
PROXMOX_TOKEN_ID=user@pam!token-name
PROXMOX_TOKEN_SECRET=xxxx-xxxx-xxxx
PROXMOX_VERIFY_SSL=true
PROXMOX_TEMPLATE_VMID=9000
PROXMOX_DEFAULT_NODE=pve
PROXMOX_DEFAULT_STORAGE=local-lvm
```

### Acceptance Criteria

- VPS creation triggered by order status change
- VM cloned from template with correct resources
- Customer notified when VPS is ready
- Failed provisioning doesn't leave orphan VMs

---

## Phase F — Database & Deploy Prep (dedicated session)

**Goal:** Production-ready infrastructure.

### Tasks

- [ ] Switch from SQLite to PostgreSQL (change one env var)
- [ ] Create `docker-compose.yml` (Django + Postgres + Redis + Celery worker)
- [ ] Run `manage.py check --deploy` clean
- [ ] Add `collectstatic` to deploy step
- [ ] Document reverse proxy setup (Nginx/Caddy + TLS)
- [ ] Backup strategy: pg_dump + media, automated schedule
- [ ] Restore drill: prove you can recover from backup

### Acceptance Criteria

- App runs in Docker with all services
- Backup + restore tested
- Deploy checklist documented

---

## Phase G — Django Upgrade Path (dedicated session)

**Goal:** Get off Django 4.2 before EOL.

### Tasks

- [ ] Django 4.2 → 5.0 (fix `re_path` deprecations, middleware changes)
- [ ] Django 5.0 → 5.2 LTS (stable target, allauth 65.14.3 supports it)
- [ ] redis 5.2.1 → 7.x (connection pool API changes, test Celery)
- [ ] Consider `dj-stripe` migration (replace hand-rolled Stripe models)

### Acceptance Criteria

- All tests pass on new Django version
- No deprecation warnings
- CI matrix updated

---

## Phase 4 — Production Ops & Compliance (dedicated session)

**Goal:** Operational maturity and compliance baseline.

### Tasks

- [ ] Sentry integration verified (test error → alert)
- [ ] Prometheus metrics endpoint + Grafana dashboards
- [ ] GDPR incident response plan (72-hour notification requirement)
- [ ] Data retention policy documented
- [ ] User data export/deletion capability
- [ ] PCI documentation (hosted payment surfaces, SAQ scope)
- [ ] Security review cadence and patch management process

### Acceptance Criteria

- Errors tracked in Sentry
- Alerts fire on symptoms (latency/errors/availability)
- Compliance docs exist and are actionable
- Backup restore drill completed and documented

---

## Future — OSS Integrations (when ready)

These are major integrations to pursue after the core platform is solid:

- **Chatwoot** — live chat widget + omnichannel support (see docs/OSS_STACK.md)
- **HestiaCP** — web hosting control panel via API (see docs/OSS_STACK.md)
- **Rasa** — AI chatbot for order intake workflows (see docs/OSS_STACK.md)
- **Domain registration** — registrar API integration (Cloudflare/Namecheap)
- **SSL automation** — ACME/Let's Encrypt integration

---

## Quick Reference: Priority Order

```
Phase 0  ─── Clean house + prod hardening          → ~2 hours
Phase 1  ─── Webhook async + idempotency            → ~3-4 hours
Phase B  ─── API hardening (OpenAPI, JWT, throttles) → ~2-3 hours
Phase 2  ─── Fulfillment tracking (Order/Job models) → ~3-4 hours
Phase C  ─── Security middleware (axes, CSP, logging) → ~3 hours
Phase D  ─── Email system (Celery tasks, templates)   → ~3 hours
Phase E  ─── Test coverage push (→ 93%+)              → ~2 hours
Phase 3  ─── Proxmox VPS provisioning MVP             → dedicated session
Phase F  ─── Database + deploy prep (Docker, Postgres) → dedicated session
Phase G  ─── Django upgrade (4.2 → 5.2 LTS)           → dedicated session
Phase 4  ─── Ops maturity + compliance                 → dedicated session
```
