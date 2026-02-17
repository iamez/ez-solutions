# Tech-IT Solutions - Monitoring & Alerting Setup Guide

## 🎯 Overview

This guide will help you set up a complete monitoring and alerting system for your Django SaaS platform. You'll get:

✅ **Real-time health checks** - Know instantly when something breaks  
✅ **System metrics** - CPU, memory, disk, network monitoring  
✅ **Application metrics** - Request rates, response times, errors  
✅ **Database monitoring** - Connection pools, slow queries  
✅ **Alerting** - Email, Slack, PagerDuty notifications  
✅ **Uptime monitoring** - External checks for your site  

## 📊 Monitoring Stack

### Core Components

1. **Prometheus** - Metrics collection and storage
2. **Grafana** - Visualization dashboards
3. **Alertmanager** - Alert routing and notifications
4. **Node Exporter** - System metrics
5. **PostgreSQL Exporter** - Database metrics
6. **Sentry** - Error tracking and debugging
7. **UptimeRobot** - External uptime monitoring

---

## 🚀 Quick Start (15 minutes)

### Step 1: Install Required Packages

```bash
# Install Python packages
pip install psutil django-health-check sentry-sdk

# Update requirements.txt
pip freeze > requirements.txt

# Install monitoring tools (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y prometheus grafana alertmanager

# Install exporters
sudo apt-get install -y prometheus-node-exporter
```

### Step 2: Configure Django Health Checks

Add to `config/urls.py`:

```python
from health_checks import (
    HealthCheckView,
    DetailedHealthCheckView,
    ReadinessCheckView,
    LivenessCheckView,
    MetricsView
)

urlpatterns = [
    # ... your existing URLs
    
    # Health check endpoints
    path('health/', HealthCheckView.as_view(), name='health'),
    path('health/detailed/', DetailedHealthCheckView.as_view(), name='health-detailed'),
    path('health/ready/', ReadinessCheckView.as_view(), name='readiness'),
    path('health/live/', LivenessCheckView.as_view(), name='liveness'),
    path('health/metrics/', MetricsView.as_view(), name='metrics'),
]
```

### Step 3: Add Monitoring Middleware

Add to `config/settings.py`:

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    # Add monitoring middleware
    'monitoring_middleware.MonitoringMiddleware',
    'monitoring_middleware.SecurityMonitoringMiddleware',
    'monitoring_middleware.PerformanceMonitoringMiddleware',
]

# Configure logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': '/var/log/django/monitoring.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'monitoring': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

### Step 4: Test Health Checks

```bash
# Start your Django server
python manage.py runserver

# Test endpoints (in another terminal)
curl http://localhost:8000/health/
curl http://localhost:8000/health/detailed/
curl http://localhost:8000/health/metrics/
```

You should see:
- `/health/` → "OK"
- `/health/detailed/` → JSON with system status
- `/health/metrics/` → Prometheus metrics

---

## 📈 Full Monitoring Setup

### 1. Prometheus Setup

```bash
# Copy configuration
sudo cp prometheus.yml /etc/prometheus/prometheus.yml
sudo cp alert_rules.yml /etc/prometheus/alert_rules.yml

# Set permissions
sudo chown prometheus:prometheus /etc/prometheus/*.yml

# Restart Prometheus
sudo systemctl restart prometheus
sudo systemctl enable prometheus

# Verify it's running
curl http://localhost:9090
```

### 2. Alertmanager Setup

```bash
# Copy configuration
sudo cp alertmanager.yml /etc/alertmanager/alertmanager.yml

# Update email credentials in the file
sudo nano /etc/alertmanager/alertmanager.yml

# Restart Alertmanager
sudo systemctl restart alertmanager
sudo systemctl enable alertmanager

# Verify it's running
curl http://localhost:9093
```

### 3. Node Exporter (System Metrics)

```bash
# Should already be running after installation
sudo systemctl status prometheus-node-exporter

# If not, start it
sudo systemctl start prometheus-node-exporter
sudo systemctl enable prometheus-node-exporter

# Test metrics
curl http://localhost:9100/metrics
```

### 4. PostgreSQL Exporter

```bash
# Install
wget https://github.com/prometheus-community/postgres_exporter/releases/download/v0.12.0/postgres_exporter-0.12.0.linux-amd64.tar.gz
tar xvfz postgres_exporter-*.tar.gz
sudo mv postgres_exporter-*/postgres_exporter /usr/local/bin/

# Configure
export DATA_SOURCE_NAME="postgresql://username:password@localhost:5432/techit_db?sslmode=disable"

# Create systemd service
sudo nano /etc/systemd/system/postgres_exporter.service
```

Add this content:

```ini
[Unit]
Description=PostgreSQL Exporter
After=network.target

[Service]
Type=simple
User=postgres
Environment=DATA_SOURCE_NAME=postgresql://username:password@localhost:5432/techit_db?sslmode=disable
ExecStart=/usr/local/bin/postgres_exporter
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Start service
sudo systemctl daemon-reload
sudo systemctl start postgres_exporter
sudo systemctl enable postgres_exporter
```

### 5. Grafana Setup

```bash
# Start Grafana
sudo systemctl start grafana-server
sudo systemctl enable grafana-server

# Access Grafana
# Open browser: http://localhost:3000
# Default login: admin/admin
```

**Configure Grafana:**

1. Add Prometheus data source:
   - Go to Configuration → Data Sources
   - Add Prometheus
   - URL: `http://localhost:9090`
   - Save & Test

2. Import dashboards:
   - Go to Create → Import
   - Import these dashboard IDs:
     - **1860** - Node Exporter Full
     - **9628** - PostgreSQL Database
     - **12124** - Django Application

3. Create custom dashboard for your app:
   - Add panels for:
     - Request rate
     - Response time
     - Error rate
     - Active users
     - Database connections

---

## 🔔 Alert Configuration

### Email Alerts

Update `alertmanager.yml` with your SMTP settings:

```yaml
global:
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'alerts@techit-solutions.com'
  smtp_auth_username: 'alerts@techit-solutions.com'
  smtp_auth_password: 'your-app-password-here'
```

**For Gmail:**
1. Enable 2FA on your Google account
2. Generate an App Password
3. Use that password in the config

### Slack Alerts

1. Create a Slack webhook:
   - Go to https://api.slack.com/apps
   - Create new app
   - Enable Incoming Webhooks
   - Copy webhook URL

2. Add to `alertmanager.yml`:

```yaml
slack_configs:
  - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
    channel: '#alerts'
```

### PagerDuty Integration

1. Get your PagerDuty integration key
2. Add to `alertmanager.yml`:

```yaml
pagerduty_configs:
  - service_key: 'YOUR_PAGERDUTY_KEY'
```

---

## 🔍 Sentry Error Tracking

### Setup Sentry

```bash
pip install sentry-sdk
```

Add to `config/settings.py`:

```python
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn="YOUR_SENTRY_DSN",
    integrations=[DjangoIntegration()],
    traces_sample_rate=1.0,
    send_default_pii=True,
    environment="production",
)
```

Get your DSN from: https://sentry.io

---

## 🌐 External Uptime Monitoring

### Option 1: UptimeRobot (Free)

1. Sign up at https://uptimerobot.com
2. Add monitors:
   - **HTTP Monitor**: https://yourdomain.com/health/
   - Check interval: 5 minutes
   - Alert contacts: Your email/SMS

### Option 2: Pingdom

1. Sign up at https://www.pingdom.com
2. Add uptime check for your domain
3. Configure alert contacts

### Option 3: StatusCake (Free)

1. Sign up at https://www.statuscake.com
2. Add uptime test
3. Set up alert emails

---

## 🧪 Testing Your Monitoring

### 1. Test Health Checks

```bash
# Basic health
curl http://localhost:8000/health/

# Detailed status
curl http://localhost:8000/health/detailed/ | jq

# Metrics
curl http://localhost:8000/health/metrics/
```

### 2. Test Alerts

```bash
# Simulate high CPU
stress --cpu 8 --timeout 300s

# Simulate high memory
stress --vm 2 --vm-bytes 1G --timeout 300s

# Watch alerts fire
curl http://localhost:9093/api/v2/alerts
```

### 3. Test Error Tracking

Create a test view:

```python
def test_error(request):
    division_by_zero = 1 / 0
    return HttpResponse("This won't execute")
```

Visit the URL and check Sentry for the error.

---

## 📊 Important Metrics to Monitor

### Application Metrics
- Request rate (requests/second)
- Response time (95th percentile)
- Error rate (5xx errors)
- Active sessions
- Background job queue length

### System Metrics
- CPU usage
- Memory usage
- Disk usage
- Network I/O
- Load average

### Database Metrics
- Active connections
- Connection pool usage
- Slow queries (> 1 second)
- Database size
- Query rate

### Business Metrics
- New user registrations
- Active subscriptions
- Revenue (daily/monthly)
- Service activations
- Support ticket volume

---

## 🎯 Alert Thresholds

### Critical Alerts (Immediate Action)
- Application down > 1 minute
- Database down > 30 seconds
- Disk usage > 95%
- 5xx error rate > 10%
- SSL certificate expired

### Warning Alerts (Check Soon)
- CPU usage > 85% for 5 minutes
- Memory usage > 85% for 5 minutes
- Disk usage > 85%
- Response time > 2 seconds
- 5xx error rate > 5%
- SSL certificate expiring < 30 days

---

## 📱 Mobile Monitoring

### Prometheus Mobile App
- iOS: "Prometheus Monitor"
- Android: "Prometheus"
- View metrics and alerts on the go

### PagerDuty Mobile App
- iOS/Android: "PagerDuty"
- Receive critical alerts
- Acknowledge and resolve incidents

---

## 🔧 Maintenance Commands

```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Check Alertmanager status
curl http://localhost:9093/api/v2/status

# View active alerts
curl http://localhost:9093/api/v2/alerts

# Silence an alert
curl -X POST http://localhost:9093/api/v2/silences \
  -H "Content-Type: application/json" \
  -d '{"matchers":[{"name":"alertname","value":"HighCPUUsage"}],"startsAt":"2025-01-01T00:00:00Z","endsAt":"2025-01-01T01:00:00Z","createdBy":"admin","comment":"Maintenance window"}'

# Check log files
sudo tail -f /var/log/django/monitoring.log
sudo tail -f /var/log/prometheus/prometheus.log
```

---

## 📚 Dashboards to Create

### 1. Overview Dashboard
- System health status
- Request rate
- Error rate
- Active users
- Response time

### 2. System Dashboard
- CPU usage
- Memory usage
- Disk I/O
- Network traffic

### 3. Application Dashboard
- Request rate by endpoint
- Slow requests
- Error breakdown
- Database query performance

### 4. Business Dashboard
- New signups (daily)
- Active subscriptions
- Revenue metrics
- Service usage

---

## 🚨 Incident Response

When an alert fires:

1. **Acknowledge** the alert in PagerDuty/Slack
2. **Check** the Grafana dashboard for context
3. **Review** recent logs for errors
4. **Take action** based on the alert type
5. **Document** the incident and resolution
6. **Follow up** with a post-mortem if needed

---

## 💡 Best Practices

1. ✅ **Start simple** - Begin with basic health checks
2. ✅ **Add gradually** - Don't overwhelm yourself
3. ✅ **Test alerts** - Ensure notifications work
4. ✅ **Review weekly** - Check metrics and trends
5. ✅ **Update thresholds** - Adjust based on experience
6. ✅ **Document incidents** - Learn from failures
7. ✅ **Automate remediation** - For common issues

---

## 🆘 Troubleshooting

### Prometheus not scraping metrics
```bash
# Check if endpoint is accessible
curl http://localhost:8000/health/metrics/

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq

# Check Prometheus logs
sudo journalctl -u prometheus -f
```

### Alerts not firing
```bash
# Check alert rules are loaded
curl http://localhost:9090/api/v1/rules | jq

# Check Alertmanager configuration
amtool check-config /etc/alertmanager/alertmanager.yml

# Test alert routing
amtool config routes show
```

### High false positive rate
- Adjust alert thresholds in `alert_rules.yml`
- Increase `for` duration before alert fires
- Add inhibition rules to suppress cascading alerts

---

## 📞 Next Steps

1. ✅ Set up basic health checks (Done above)
2. ✅ Install and configure Prometheus
3. ✅ Set up Grafana dashboards
4. ✅ Configure email/Slack alerts
5. ✅ Set up external uptime monitoring
6. ✅ Install Sentry for error tracking
7. ✅ Create runbooks for common incidents
8. ✅ Test the entire monitoring stack

---

## 🎓 Learning Resources

- **Prometheus**: https://prometheus.io/docs/
- **Grafana**: https://grafana.com/docs/
- **Sentry**: https://docs.sentry.io/
- **Django Logging**: https://docs.djangoproject.com/en/stable/topics/logging/

---

You now have enterprise-grade monitoring! 🎉

Your system will:
- ✅ Alert you immediately when things break
- ✅ Show you exactly what's wrong
- ✅ Track performance over time
- ✅ Help prevent issues before they happen

Happy monitoring! 🚀
