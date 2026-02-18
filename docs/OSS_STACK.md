# EZ Solutions — Open-Source Stack Map

> Generated: February 18, 2026
> Purpose: Track every OSS tool we plan to use, how it fits, and when to adopt it.

---

## Overview

EZ Solutions follows an **integration-first strategy**: Django is the brain (accounts, billing,
entitlements, fulfillment tracking), and proven OSS tools handle the heavy lifting for
chat, hosting, monitoring, and infrastructure. We don't rebuild what's already solved.

---

## Layer 1 — Python Packages (inside Django, pip install)

### Already Installed & Working

| Package | Version | What it does for us | License |
|---------|---------|-------------------|---------|
| **django-allauth** | 65.14.3 | Login, signup, email verification, password reset, social login, MFA-ready | MIT |
| **djangorestframework** | 3.15.2 | REST API framework (`/api/v1/*` endpoints) | BSD |
| **stripe** | 11.5.0 | Stripe API client (Checkout, Portal, webhooks) | MIT |
| **celery** | 5.4.0 | Background task queue (webhooks, email, provisioning) | BSD |
| **django-celery-beat** | 2.8.1 | Periodic task scheduler (cron-like) | BSD |
| **redis** | 5.2.1 | Redis client (Celery broker + cache) | MIT |
| **django-cors-headers** | 4.9.0 | CORS handling for API | MIT |
| **django-anymail** | 14.0 | Email backend abstraction (Mailgun, SES, etc.) | BSD |
| **whitenoise** | 6.9.0 | Static file serving without nginx | MIT |
| **sentry-sdk** | 2.53.0 | Error tracking and monitoring | MIT |
| **Pillow** | 12.1.1 | Image processing | HPND |
| **django-storages** | 1.14.6 | S3-compatible file storage | BSD |
| **gunicorn** | 23.0.0 | Production WSGI server | MIT |
| **psycopg2-binary** | 2.9.11 | PostgreSQL adapter | LGPL |

### Already Installed (Dev/Testing)

| Package | Version | What it does | License |
|---------|---------|-------------|---------|
| **pytest** + **pytest-django** | 9.0.2 / 4.12.0 | Test framework | MIT |
| **pytest-cov** | 7.0.0 | Coverage reporting | MIT |
| **ruff** | 0.15.1 | Linter + formatter (replaces flake8/isort) | MIT |
| **black** | 26.1.0 | Code formatter | MIT |
| **bandit** | 1.9.3 | Security static analysis | Apache 2.0 |
| **pip-audit** | 2.10.0 | Dependency vulnerability scanner | Apache 2.0 |
| **pre-commit** | 4.5.1 | Git hook manager | MIT |
| **django-debug-toolbar** | 6.2.0 | Dev debugging UI | BSD |
| **factory-boy** | 3.3.3 | Test fixtures | MIT |
| **faker** | 40.4.0 | Fake data generation | MIT |

### To Add — Phase B (API Hardening)

| Package | Stars | What it does | License | Priority |
|---------|-------|-------------|---------|----------|
| **drf-spectacular** | 2.2k | Auto-generates OpenAPI/Swagger docs from DRF views. Gives us instant API docs at `/api/schema/swagger-ui/` | BSD | High |
| **djangorestframework-simplejwt** | 4k | JWT token auth for mobile/SPA/external API clients. Adds `/api/token/` + `/api/token/refresh/` | MIT | High |

### To Add — Phase C (Security)

| Package | Stars | What it does | License | Priority |
|---------|-------|-------------|---------|----------|
| **django-axes** | 1.6k | Brute-force login protection. Blocks IPs after N failed attempts. Drop-in middleware | MIT | High |
| **django-csp** | 550 | Content Security Policy headers via middleware. Prevents XSS. Start in Report-Only mode | BSD | High |
| **django-health-check** | 1.2k | Production health endpoints. Checks DB, Redis, Celery, storage, disk space | MIT | High |
| **django-simple-history** | 2.2k | Audit trail on models. Tracks every change to Subscription, Ticket, User. Creates `_history` tables | BSD | Medium |

### Optional — Future

| Package | Stars | What it does | License | When |
|---------|-------|-------------|---------|------|
| **dj-stripe** | 1.8k | Auto-syncs ALL Stripe objects to Django models. Replaces our hand-rolled orders models. Major upgrade path | MIT | Phase G or later |
| **django-structlog** | 400 | Structured JSON logging with request IDs & user context | MIT | Phase C alt |
| **django-cachalot** | 1.2k | Automatic ORM query caching with Redis auto-invalidation | BSD | Phase F |
| **django-import-export** | 2.9k | CSV/Excel import/export in Django admin | BSD | When needed |

---

## Layer 2 — Self-Hosted Services (run alongside Django on Proxmox)

### Customer Support & Live Chat

#### Chatwoot (RECOMMENDED)
- **What:** Open-source omnichannel customer support platform with live chat widget
- **Stars:** 22k+ | **License:** MIT
- **URL:** https://github.com/chatwoot/chatwoot
- **Stack:** Ruby on Rails + Vue.js + PostgreSQL + Redis
- **Features:**
  - Live chat widget (embed in Django templates via `<script>` tag)
  - Omnichannel: email, WhatsApp, Telegram, Facebook, Twitter
  - AI agent ("Captain") for automated responses
  - Built-in help center / knowledge base
  - Canned responses, automation rules, SLA tracking
- **Integration pattern:**
  - Run as a separate Docker service on Proxmox
  - Embed chat widget in `templates/base.html`
  - Optional: webhook from Chatwoot → Django to auto-create tickets
  - Optional: SSO so portal login = Chatwoot login
- **When:** After core platform is stable (post-Phase 4)

#### Zammad (ALTERNATIVE)
- **What:** Open-source helpdesk / ticketing system
- **Stars:** 4.5k+ | **License:** AGPL-3.0
- **URL:** https://github.com/zammad/zammad
- **Stack:** Ruby on Rails + PostgreSQL
- **Features:** Mature ITSM workflows, multi-channel, knowledge base
- **Caveat:** AGPL license — if you modify and distribute, you must share source.
  Self-hosting as a separate service is fine.
- **When:** Consider if Chatwoot doesn't fit

### Web Hosting Control Panels

> These are NOT Django libraries. They are separate services that manage hosting resources.
> Your Django app calls their APIs to provision accounts.

#### HestiaCP (RECOMMENDED for shared hosting)
- **What:** Web hosting control panel (websites, email, DNS, databases, SSL)
- **Stars:** 3.5k+ | **License:** GPL-3.0
- **URL:** https://github.com/hestiacp/hestiacp
- **Features:**
  - Apache/Nginx web server management
  - Mail server (Exim + Dovecot)
  - DNS server (Bind)
  - Database management (MySQL/PostgreSQL)
  - Let's Encrypt SSL auto-provisioning
  - User/account management with quotas
- **Integration pattern:**
  - Install on a dedicated server/VM on Proxmox
  - Django Celery task calls HestiaCP CLI or API to:
    - Create hosting account when customer orders "website hosting"
    - Set quotas based on plan tier
    - Provision SSL certificate
  - Customer dashboard shows hosting account details
- **When:** When ready to offer website hosting product

#### ISPConfig (ALTERNATIVE for multi-server)
- **What:** Multi-server hosting management
- **Stars:** N/A (established project) | **License:** BSD
- **URL:** https://www.ispconfig.org/
- **When:** If scaling beyond one hosting server

#### CyberPanel (ALTERNATIVE for performance)
- **What:** OpenLiteSpeed-based hosting control (faster for WordPress)
- **Stars:** 2k+ | **License:** GPL-3.0
- **URL:** https://cyberpanel.net/
- **When:** If WordPress hosting is a major product line

### Monitoring & Observability

#### Prometheus + Grafana (RECOMMENDED)
- **What:** Metrics collection + dashboarding + alerting
- **Stars:** 56k + 65k | **License:** Apache 2.0
- **URLs:** https://github.com/prometheus/prometheus / https://github.com/grafana/grafana
- **Integration pattern:**
  - Run on Proxmox
  - Prometheus scrapes Django metrics endpoint (django-prometheus or custom)
  - Prometheus scrapes Proxmox node_exporter
  - Grafana shows dashboards + fires alerts
  - Alertmanager handles routing/deduplication
- **Note:** You already have real Prometheus/alert configs in
  `ai_instructions_copilot_instructions_readme/` (prometheus.yml, alert_rules.yml, alertmanager.yml)
- **When:** Phase 4

#### Sentry (ALREADY IN REQUIREMENTS)
- **What:** Error tracking and performance monitoring
- **License:** BSL (self-hosted available) / Free SaaS tier
- **Integration:** `sentry-sdk` already installed. Just set `SENTRY_DSN` env var
- **When:** Phase 0 (just configure the env var)

### Infrastructure

#### PostgreSQL (ALREADY IN REQUIREMENTS)
- **What:** Production database
- **License:** PostgreSQL License (permissive)
- **Current:** Using SQLite for dev. Switch to Postgres by changing env vars
- **When:** Phase F

#### Redis (ALREADY IN REQUIREMENTS)
- **What:** Celery broker + cache + session store
- **License:** BSD
- **When:** Phase 1 (needed for Celery)

#### Mailpit (FOR DEV)
- **What:** Local SMTP server with web UI — see every email your app sends
- **Stars:** 6k+ | **License:** MIT
- **URL:** https://github.com/axllent/mailpit
- **Integration:** Run locally, point Django `EMAIL_HOST` at it
- **When:** Phase D (email system development)

### AI & Automation

#### Rasa (OPTIONAL — FUTURE)
- **What:** Open-source conversational AI framework
- **Stars:** 19k+ | **License:** Apache 2.0
- **URL:** https://github.com/RasaHQ/rasa
- **Use case:** Deterministic "order intake" chatbot workflows. Customer says
  "I need a VPS" → bot collects specs → creates order in Django
- **When:** After Chatwoot integration is stable

---

## Layer 3 — External Services (not self-hosted)

| Service | Free Tier | What it does | Required? |
|---------|-----------|-------------|-----------|
| **Stripe** | 2.9% + 30¢/txn | Payment processing, subscriptions, invoices | Yes |
| **Mailgun** | 5k emails/month | Transactional email delivery | Yes (prod) |
| **Cloudflare** | Generous free tier | DNS, CDN, DDoS protection, registrar | Optional |
| **GitHub** | Free for private repos | Source control, CI/CD, code scanning | Yes |
| **Sentry** | 5k events/month free | Error tracking (or self-host) | Recommended |

---

## Decision Matrix: Build vs. Integrate vs. Skip

| Capability | Build ourselves? | Integrate OSS? | Skip for MVP? |
|-----------|-----------------|----------------|---------------|
| Customer accounts + auth | **Build** (Django + allauth) | — | — |
| Billing + subscriptions | **Build** (Django + Stripe) | dj-stripe later | — |
| Service catalog + pricing | **Build** (Django models) | — | — |
| Order/fulfillment tracking | **Build** (Django provisioning app) | — | — |
| VPS provisioning | **Build** (Proxmox API client) | — | — |
| Support tickets | **Build** (Django tickets app) | — | — |
| Live chat | — | **Chatwoot** | Skip MVP |
| Website hosting mgmt | — | **HestiaCP** | Skip MVP |
| Email delivery | — | **Mailgun** | — |
| Monitoring dashboards | — | **Prometheus + Grafana** | — |
| Error tracking | — | **Sentry** | — |
| SSL certificate mgmt | — | Let's Encrypt (HestiaCP handles it) | Skip MVP |
| Domain registration | — | Registrar API (Cloudflare/Namecheap) | **Skip MVP** |
| AI chatbot | — | Rasa (far future) | **Skip MVP** |
| Hosting control panel | — | **HestiaCP** | Skip MVP |

---

## Licensing Summary

| License | Packages/Tools | Can we use commercially? |
|---------|---------------|------------------------|
| MIT | allauth, stripe, celery, Chatwoot, simplejwt, axes, Mailpit | Yes, freely |
| BSD | DRF, black, anymail, whitenoise, django-csp, ISPConfig | Yes, freely |
| Apache 2.0 | bandit, pip-audit, Prometheus, Grafana, Rasa | Yes, freely |
| LGPL | psycopg2 | Yes (linking is fine) |
| GPL-3.0 | HestiaCP, CyberPanel | Yes if self-hosted as separate service (not embedding in our code) |
| AGPL-3.0 | Zammad | Yes if self-hosted as separate service. Careful if modifying + distributing. |
| BSL | Sentry (self-hosted) | Free SaaS tier; self-host requires BSL terms review |

**Bottom line:** All recommended tools are safe for commercial use when self-hosted as
separate services. The only caution is AGPL (Zammad) if you modify and redistribute.
