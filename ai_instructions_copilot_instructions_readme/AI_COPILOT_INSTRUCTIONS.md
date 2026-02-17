# AI Copilot Instructions: Tech Solutions SaaS Platform

## Project Overview
You are building a comprehensive tech solutions platform called **Tech-IT Solutions** that offers:
- Web hosting
- VPS hosting
- Domain name buying/renting/reselling
- Web development services
- Data/SQL consulting
- Linux support
- IT consulting
- SSL certificates
- Email hosting
- Website monitoring
- Backup solutions
- Security services

**Key Constraint:** No cPanel or admin tools available. Everything must be custom-built.

---

## Tech Stack
- **Backend:** Python 3.10+
- **Framework:** Django 4.2+
- **Frontend:** HTML5 + Django Templates (initially), upgrade to React/Vue if needed
- **Database:** PostgreSQL
- **Payment Processing:** Stripe API
- **Hosting:** DigitalOcean, Render, or Railway
- **Additional Tools:** Celery for async tasks, Redis for caching

---

## Phase 1: Foundation (Weeks 1-2)

### Project Setup
1. Create Django project structure with proper organization
2. Set up PostgreSQL database
3. Configure environment variables (.env file)
4. Initialize git repository
5. Set up static files and media handling

### Core Models to Create
```
User (Custom User model extending Django's User)
  - email, password, created_date, subscription_tier, balance

Service (Hosting plans, VPS types, etc.)
  - name, type, price, renewal_period, description, specs

Order (Customer purchases)
  - user, service, order_date, expiry_date, status, price_paid

Invoice
  - user, order, amount, due_date, paid_date, stripe_payment_id

Domain
  - name, owner, registrar, expiry_date, auto_renew, price

ServiceTicket (For support/consulting requests)
  - user, subject, description, status, assigned_to, created_date
```

### Authentication System
- Custom user registration and login
- Email verification on signup
- Password reset functionality
- Role-based access (admin, customer, support staff)
- JWT tokens or sessions for API

---

## Phase 2: Customer Dashboard (Weeks 2-3)

### User-Facing Features
1. **Dashboard Home**
   - Active services/orders
   - Upcoming renewals
   - Account balance
   - Quick stats

2. **Services Management**
   - Browse available hosting/VPS plans
   - View service specifications and pricing
   - Purchase services (with Stripe integration)
   - Manage active services

3. **Orders & Billing**
   - View all orders/invoices
   - Download invoices as PDF
   - Billing history
   - Auto-renewal settings

4. **Domain Management**
   - View owned domains
   - Domain renewal
   - DNS management interface (basic)
   - WHOIS info

5. **Support/Tickets**
   - Create support tickets
   - View ticket history
   - Chat/messages with support
   - Upload attachments

---

## Phase 3: Admin Dashboard (Weeks 3-4)

### Admin-Only Features
1. **Customer Management**
   - Search/filter customers
   - View customer details
   - Manually adjust balances
   - Suspend accounts

2. **Service Management**
   - Create/edit/delete service offerings
   - Manage pricing and specs
   - Track inventory (if limited slots)

3. **Orders & Revenue**
   - View all orders
   - Process manual orders
   - Revenue analytics (daily/monthly/yearly)
   - Refund management

4. **Ticket Management**
   - View all support tickets
   - Assign tickets to staff
   - Add internal notes
   - Close tickets

5. **Monitoring & Reports**
   - Total revenue
   - Customer acquisition rate
   - Active subscriptions
   - Churn rate
   - Export reports

---

## Phase 4: Payment Integration (Week 4)

### Stripe Integration
1. Create Stripe account and get API keys
2. Set up webhook handlers for payment events
3. Implement checkout flow:
   - Customer selects service
   - Creates Stripe payment session
   - Validates payment
   - Auto-provisions service upon success
4. Handle payment failures and retries
5. Implement subscription management (recurring payments if needed)

---

## Phase 5: Core Features & Polish (Weeks 5+)

### Features to Build
1. **Email Notifications**
   - Order confirmation emails
   - Renewal reminders
   - Payment receipts
   - Support ticket updates

2. **API Endpoint** (for developers/integrations)
   - List available services
   - Get pricing
   - Create orders (programmatically)
   - Check order status

3. **Analytics & Logging**
   - Track user actions
   - Monitor API usage
   - Error logging
   - Performance metrics

4. **Security**
   - CSRF protection
   - SQL injection prevention (Django handles this)
   - Rate limiting on endpoints
   - HTTPS enforcement
   - Secure password hashing (Django handles this)

---

## Code Generation Guidelines

### When Generating Code:
1. **Always use Django best practices**
   - Models should inherit from `models.Model`
   - Use Django ORM (not raw SQL unless necessary)
   - Leverage Django's built-in security features
   - Follow MVT (Model-View-Template) pattern

2. **Organize files properly**
   ```
   project/
   ├── manage.py
   ├── project/
   │   ├── settings.py (configuration)
   │   ├── urls.py (routing)
   │   └── wsgi.py
   ├── apps/
   │   ├── users/ (authentication, profiles)
   │   ├── services/ (hosting plans, VPS)
   │   ├── orders/ (purchases, billing)
   │   ├── domains/ (domain management)
   │   ├── tickets/ (support system)
   │   └── api/ (REST endpoints)
   ├── templates/
   ├── static/
   └── requirements.txt
   ```

3. **Database Queries**
   - Use `.select_related()` and `.prefetch_related()` for optimization
   - Index frequently queried fields
   - Use querysets efficiently

4. **API Endpoints** (REST style)
   - Use Django REST Framework if building extensive API
   - Consistent URL patterns: `/api/v1/services/`, `/api/v1/orders/`
   - Return JSON with proper status codes
   - Implement pagination for list endpoints

5. **Frontend HTML**
   - Use Bootstrap 5 for responsive design
   - Keep templates DRY (reuse base templates)
   - Use Django template tags for dynamic content
   - Minimal JavaScript (vanilla JS or HTMX for interactivity)

6. **Error Handling**
   - Try-catch blocks around external API calls
   - Graceful error messages to users
   - Log all errors properly
   - Don't expose sensitive errors to frontend

---

## Testing Guidelines

### Unit Tests
- Test each model's methods
- Test API endpoints
- Test payment flow (mock Stripe)

### Integration Tests
- Test complete user flow (signup → purchase → receipt)
- Test admin actions
- Test email sending

### Run tests with:
```bash
python manage.py test
```

---

## Deployment Checklist

Before going live:
- [ ] Set `DEBUG = False` in production
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Use environment variables for secrets
- [ ] Set up PostgreSQL (production database)
- [ ] Configure static/media files serving
- [ ] Set up email service (SendGrid, AWS SES, etc.)
- [ ] Test payment processing in live mode
- [ ] Set up logging and monitoring
- [ ] SSL certificate configured
- [ ] Database backups automated
- [ ] Run security checks: `python manage.py check --deploy`

---

## Common Tasks

### When User Asks For:

**"Add a new service type"**
- Create model fields
- Add admin form
- Create template to display it
- Update pricing logic if needed

**"Add email notifications"**
- Create email templates folder
- Use Django's `send_mail()` or Celery async
- Set up email service credentials

**"Create a report"**
- Query relevant data from database
- Aggregate with Python
- Generate PDF or CSV
- Make it downloadable

**"Add a new admin feature"**
- Create the view/logic
- Add template
- Add navigation link
- Protect with permission decorators

---

## Performance Tips

1. Use caching for frequently accessed data
2. Optimize database queries (select_related, prefetch_related)
3. Compress static files
4. Use CDN for images/assets
5. Implement rate limiting
6. Consider Celery for long-running tasks

---

## Communication Style

- Ask clarifying questions if requirements are ambiguous
- Suggest best practices and security improvements
- Provide code that's production-ready
- Include comments for complex logic
- Structure responses clearly with code blocks

---

## Priority Order

1. **Must Have (MVP):** Auth, services listing, basic purchase, admin dashboard
2. **Should Have:** Email notifications, orders history, invoicing
3. **Nice to Have:** Analytics, API, advanced reporting, integrations

Build in this order to get to market fastest.
