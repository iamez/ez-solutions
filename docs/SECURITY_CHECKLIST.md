# EZ Solutions — Security Checklist

> Generated: February 18, 2026
> Sources: Django deployment checklist, OWASP cheat sheets, Stripe webhook security,
> PCI SSC guidance, ChatGPT deep research (docs/ez-solutions-research.md)

---

## How to Use This Checklist

- [ ] = Not done yet
- [x] = Completed
- Items marked **(BLOCKING)** must be done before any public deployment
- Items marked **(RECOMMENDED)** should be done before production traffic
- Items marked **(FUTURE)** can wait until the feature they protect is built

Run `python manage.py check --deploy --settings=config.settings.prod` regularly.

---

## 1. Environment & Secrets

- [x] `SECRET_KEY` loaded from env var (not in code) **(BLOCKING)**
- [x] `.env` is in `.gitignore` **(BLOCKING)**
- [x] `.env.example` exists with placeholder values
- [ ] Separate Stripe test vs live keys in different environments **(BLOCKING)**
- [ ] All secrets documented in `.env.example` with descriptions
- [ ] Proxmox API tokens use least-privilege (not root) **(FUTURE)**
- [ ] Secret rotation plan documented (what to rotate, how often)
- [ ] No secrets in git history (run `git log --all -p | grep -i "sk_live\|password"`)

---

## 2. Django Production Settings

- [x] `DEBUG = False` in `config/settings/prod.py` **(BLOCKING)**
- [x] `ALLOWED_HOSTS` set correctly **(BLOCKING)**
- [x] `SecurityMiddleware` enabled in middleware stack
- [x] `SECURE_SSL_REDIRECT = True` in prod
- [x] `SECURE_HSTS_SECONDS = 31536000` in prod
- [x] `SECURE_HSTS_INCLUDE_SUBDOMAINS = True` in prod
- [x] `SECURE_HSTS_PRELOAD = True` in prod
- [x] `SECURE_CONTENT_TYPE_NOSNIFF = True` in prod
- [x] `SESSION_COOKIE_SECURE = True` in prod
- [x] `CSRF_COOKIE_SECURE = True` in prod
- [x] `X_FRAME_OPTIONS = "DENY"` in prod
- [ ] `CSRF_TRUSTED_ORIGINS` configured for real domains **(BLOCKING for prod)**
- [ ] `manage.py check --deploy` passes against prod settings **(BLOCKING)**
- [ ] `SECURE_PROXY_SSL_HEADER` set if behind reverse proxy **(RECOMMENDED)**
- [ ] `SESSION_COOKIE_HTTPONLY = True` (Django default, verify not overridden)
- [ ] `CSRF_COOKIE_HTTPONLY = True` (consider enabling)

---

## 3. Authentication & Access Control

- [x] Custom User model with email-only auth (no username)
- [x] `django-allauth` configured for registration/login
- [x] Password validators enabled (similarity, minimum length, common, numeric)
- [x] Email verification configured (`ACCOUNT_EMAIL_VERIFICATION`)
- [ ] Email verification set to `"mandatory"` for paid services **(RECOMMENDED)**
- [ ] Account enumeration prevention enabled in allauth **(RECOMMENDED)**
- [ ] Admin protected: MFA for all staff accounts **(RECOMMENDED)**
- [ ] Admin access restricted to VPN/IP allowlist **(RECOMMENDED)**
- [ ] Rate limiting on login endpoint **(RECOMMENDED)** — use `django-axes`
- [ ] Rate limiting on password reset endpoint **(RECOMMENDED)**
- [ ] Least-privilege staff accounts (no shared admin) **(BLOCKING)**
- [ ] Session timeout configured (e.g., 12 hours inactive)
- [ ] `ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"` in prod

---

## 4. Stripe & Billing Security

- [x] Webhook signature verification using raw `request.body` **(BLOCKING)**
- [x] `PaymentEvent` stores `stripe_event_id` (unique) for idempotency
- [x] CSRF exempt on webhook endpoint (required for Stripe POST)
- [ ] Webhook processing is idempotent: duplicate event = safe no-op **(BLOCKING)**
- [ ] Webhook handler returns 2xx quickly (async processing via Celery) **(RECOMMENDED)**
- [ ] `PaymentEvent` acts as inbox table: insert FIRST, process SECOND **(RECOMMENDED)**
- [ ] Idempotency keys on outbound Stripe API calls **(RECOMMENDED)**
- [ ] Stripe test mode verified end-to-end before going live **(BLOCKING)**
- [ ] `STRIPE_WEBHOOK_SECRET` set in prod (not empty string) **(BLOCKING)**
- [ ] All card data handled by Stripe-hosted surfaces only (Checkout + Portal)
- [ ] No custom card input forms (reduces PCI scope to SAQ A)
- [ ] Stripe Dashboard webhook endpoint configured for prod URL

---

## 5. CSRF & XSS Protection

- [x] `CsrfViewMiddleware` enabled in middleware stack
- [x] `{% csrf_token %}` used in all POST forms (templates)
- [x] Django templates auto-escape enabled (default)
- [ ] No misuse of `|safe` or `mark_safe()` in templates **(RECOMMENDED)**
- [ ] CSRF token attached to AJAX requests from dashboard **(RECOMMENDED)**
- [ ] CSP headers implemented via `django-csp` **(RECOMMENDED)**
  - [ ] Start in `Content-Security-Policy-Report-Only` mode
  - [ ] Tighten policy iteratively based on reports
  - [ ] Eventually enforce strict CSP

---

## 6. Security Headers

- [x] `X-Frame-Options: DENY` (clickjacking protection)
- [x] `X-Content-Type-Options: nosniff`
- [x] HSTS enabled with 1-year max-age
- [ ] CSP header configured **(RECOMMENDED)** — see django-csp
- [ ] `Referrer-Policy: strict-origin-when-cross-origin` **(RECOMMENDED)**
- [ ] `Permissions-Policy` header configured (disable unused browser features)
- [ ] HSTS preload submitted only after thorough testing (IRREVERSIBLE)

---

## 7. API Security

- [x] DRF `SessionAuthentication` for browser clients
- [x] `IsAuthenticatedOrReadOnly` as default permission
- [ ] JWT auth added for external API clients **(Phase B)**
- [ ] Rate limiting configured per endpoint **(Phase B)**
  - [ ] Anonymous: 100 requests/hour
  - [ ] Authenticated: 1000 requests/hour
  - [ ] Ticket creation: 10/hour per user
- [ ] API versioning enforced (`/api/v1/`)
- [ ] Input validation on all API endpoints (serializer-level)
- [ ] No sensitive data in API error responses

---

## 8. Logging & Monitoring

- [ ] Log authentication failures **(RECOMMENDED)**
- [ ] Log authorization failures (403s) **(RECOMMENDED)**
- [ ] Log input validation failures **(RECOMMENDED)**
- [ ] Logs do NOT contain secrets, passwords, or full card numbers
- [ ] Logs protected from tampering (append-only or centralized)
- [ ] Sentry configured with `SENTRY_DSN` env var **(RECOMMENDED)**
- [ ] Alerts are symptom-based (latency, error rate, availability)
- [ ] Alert routing configured (who gets paged, for what)
- [ ] Health check endpoint verifies DB + Redis + Celery connectivity

---

## 9. Infrastructure & Network

- [ ] HTTPS enforced end-to-end (reverse proxy + Django) **(BLOCKING)**
- [ ] Reverse proxy (Nginx/Caddy) terminates TLS **(BLOCKING)**
- [ ] Reverse proxy validates `Host` header
- [ ] Proxmox management network isolated from customer VPS networks **(FUTURE)**
- [ ] Proxmox firewall enabled and configured **(FUTURE)**
- [ ] Cloud-Init templates used for VPS (no password-based provisioning) **(FUTURE)**
- [ ] SSH key-only access to all servers **(RECOMMENDED)**

---

## 10. Data Protection & GDPR

- [ ] Data minimization: don't store what you don't need **(RECOMMENDED)**
- [ ] User data export capability (GDPR right of access) **(FUTURE)**
- [ ] User data deletion/anonymization capability (GDPR right to erasure) **(FUTURE)**
- [ ] Data retention policy documented **(RECOMMENDED)**
- [ ] Backup + restore tested (prove RTO/RPO) **(RECOMMENDED)**
- [ ] GDPR incident response plan documented **(RECOMMENDED)**
  - [ ] 72-hour notification to supervisory authority
  - [ ] Who does what, who to contact
  - [ ] Evidence collection procedure
- [ ] Privacy policy page exists and is linked from signup **(BLOCKING for prod)**
- [ ] Cookie consent mechanism if using analytics cookies **(BLOCKING for EU)**

---

## 11. Dependency Management

- [x] `pip-audit` runs in CI (detects vulnerable dependencies)
- [x] `bandit` runs in CI (static security analysis)
- [x] Dependabot configured for weekly updates
- [x] CodeQL scanning on push + weekly schedule
- [ ] Dependencies reviewed before version bumps (breaking changes)
- [ ] Django patches applied within 1 week of security release **(RECOMMENDED)**
- [ ] Major version upgrades tested in branch before merging

---

## 12. Backup & Recovery

- [ ] Database backup automated (pg_dump schedule) **(RECOMMENDED)**
- [ ] Media files backed up **(RECOMMENDED)**
- [ ] Backup tested: restore from backup to clean environment **(RECOMMENDED)**
- [ ] Recovery Time Objective (RTO) defined and documented
- [ ] Recovery Point Objective (RPO) defined and documented
- [ ] Backup encryption at rest **(RECOMMENDED)**
- [ ] Backup stored off-site (not only on Proxmox)

---

## Quick Wins (do these first)

1. Run `manage.py check --deploy --settings=config.settings.prod`
2. Add `CSRF_TRUSTED_ORIGINS` to prod settings
3. Set `SENTRY_DSN` env var
4. Install `django-axes` for brute-force protection
5. Verify no secrets in git history
