#!/bin/bash
# Tech-IT Solutions - Monitoring & Testing Setup Script
# This script automates the setup of monitoring and testing infrastructure

set -e  # Exit on error

echo "========================================"
echo "Tech-IT Solutions Setup"
echo "Monitoring & Testing Infrastructure"
echo "========================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root for system packages
if [ "$EUID" -ne 0 ] && [ "$1" != "--no-system" ]; then 
    echo -e "${YELLOW}Some steps require root privileges.${NC}"
    echo "Run with sudo for full setup, or use --no-system flag to skip system packages"
    echo ""
fi

# Function to print status
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

# ==========================================
# PART 1: Python Dependencies
# ==========================================
echo "Step 1: Installing Python dependencies..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    print_info "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install Python packages
print_info "Installing Python packages..."
pip install --upgrade pip > /dev/null 2>&1
pip install psutil django-health-check sentry-sdk coverage factory-boy locust > /dev/null 2>&1
print_status "Python dependencies installed"

# ==========================================
# PART 2: Create Directory Structure
# ==========================================
echo ""
echo "Step 2: Creating directory structure..."

# Create log directory
if [ ! -d "/var/log/django" ]; then
    if [ "$EUID" -eq 0 ]; then
        mkdir -p /var/log/django
        chmod 755 /var/log/django
        print_status "Created /var/log/django"
    else
        print_info "Skipping /var/log/django (requires root)"
    fi
fi

# Create test directories
mkdir -p apps/users/tests
mkdir -p apps/services/tests
mkdir -p apps/orders/tests
mkdir -p apps/domains/tests
mkdir -p apps/tickets/tests
mkdir -p apps/api/tests
print_status "Test directories created"

# ==========================================
# PART 3: Copy Files
# ==========================================
echo ""
echo "Step 3: Setting up monitoring files..."

# Copy health check module
if [ -f "health_checks.py" ]; then
    cp health_checks.py config/
    print_status "Health checks module installed"
fi

# Copy middleware
if [ -f "monitoring_middleware.py" ]; then
    cp monitoring_middleware.py config/
    print_status "Monitoring middleware installed"
fi

# Copy test files
if [ -f "test_users.py" ]; then
    cp test_users.py apps/users/tests/
    print_status "User tests installed"
fi

if [ -f "test_services.py" ]; then
    cp test_services.py apps/services/tests/
    print_status "Service tests installed"
fi

if [ -f "test_orders.py" ]; then
    cp test_orders.py apps/orders/tests/
    print_status "Order tests installed"
fi

# ==========================================
# PART 4: System Packages (Optional)
# ==========================================
if [ "$1" != "--no-system" ]; then
    echo ""
    echo "Step 4: Installing monitoring tools..."
    
    if [ "$EUID" -eq 0 ]; then
        # Detect OS
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            OS=$NAME
        fi
        
        if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
            print_info "Installing on Debian/Ubuntu..."
            
            # Update package list
            apt-get update -qq > /dev/null 2>&1
            
            # Install Prometheus
            apt-get install -y prometheus > /dev/null 2>&1
            print_status "Prometheus installed"
            
            # Install Grafana
            apt-get install -y grafana > /dev/null 2>&1
            print_status "Grafana installed"
            
            # Install Alertmanager
            apt-get install -y prometheus-alertmanager > /dev/null 2>&1
            print_status "Alertmanager installed"
            
            # Install Node Exporter
            apt-get install -y prometheus-node-exporter > /dev/null 2>&1
            print_status "Node Exporter installed"
            
            # Copy configuration files
            if [ -f "prometheus.yml" ]; then
                cp prometheus.yml /etc/prometheus/
                chown prometheus:prometheus /etc/prometheus/prometheus.yml
                print_status "Prometheus configured"
            fi
            
            if [ -f "alert_rules.yml" ]; then
                cp alert_rules.yml /etc/prometheus/
                chown prometheus:prometheus /etc/prometheus/alert_rules.yml
                print_status "Alert rules configured"
            fi
            
            if [ -f "alertmanager.yml" ]; then
                cp alertmanager.yml /etc/alertmanager/
                chown prometheus:prometheus /etc/alertmanager/alertmanager.yml
                print_status "Alertmanager configured"
            fi
            
            # Enable and start services
            systemctl enable prometheus > /dev/null 2>&1
            systemctl restart prometheus > /dev/null 2>&1
            print_status "Prometheus started"
            
            systemctl enable grafana-server > /dev/null 2>&1
            systemctl restart grafana-server > /dev/null 2>&1
            print_status "Grafana started"
            
            systemctl enable prometheus-alertmanager > /dev/null 2>&1
            systemctl restart prometheus-alertmanager > /dev/null 2>&1
            print_status "Alertmanager started"
            
        else
            print_error "Unsupported OS for automatic installation"
            print_info "Please install manually: Prometheus, Grafana, Alertmanager"
        fi
    else
        print_info "Skipping system packages (not root)"
        print_info "Run with sudo for full installation"
    fi
else
    print_info "Skipping system packages (--no-system flag)"
fi

# ==========================================
# PART 5: Django Configuration
# ==========================================
echo ""
echo "Step 5: Updating Django settings..."

# Check if settings.py exists
if [ -f "config/settings.py" ]; then
    # Backup settings
    cp config/settings.py config/settings.py.backup
    print_status "Settings backed up to config/settings.py.backup"
    
    print_info "Please manually update config/settings.py with:"
    echo "  1. Add monitoring middleware to MIDDLEWARE"
    echo "  2. Add health check URLs to config/urls.py"
    echo "  3. Configure LOGGING settings"
    echo ""
    print_info "See MONITORING_GUIDE.md for detailed instructions"
fi

# ==========================================
# PART 6: Run Tests
# ==========================================
echo ""
echo "Step 6: Running tests..."

# Run Django tests
print_info "Running test suite..."
python manage.py test --verbosity=0 > /dev/null 2>&1 && \
    print_status "All tests passed!" || \
    print_error "Some tests failed. Run 'python manage.py test' for details"

# Check test coverage
print_info "Checking test coverage..."
coverage run --source='.' manage.py test > /dev/null 2>&1
coverage report > coverage_report.txt
COVERAGE=$(grep "TOTAL" coverage_report.txt | awk '{print $4}' | sed 's/%//')
echo -e "  Coverage: ${COVERAGE}%"

if [ ${COVERAGE%.*} -ge 80 ]; then
    print_status "Coverage goal met (≥80%)"
else
    print_error "Coverage below 80% (current: ${COVERAGE}%)"
fi

# ==========================================
# PART 7: Verify Installation
# ==========================================
echo ""
echo "Step 7: Verifying installation..."

# Check if services are running
check_service() {
    if systemctl is-active --quiet $1 2>/dev/null; then
        print_status "$1 is running"
        return 0
    else
        print_error "$1 is not running"
        return 1
    fi
}

if [ "$EUID" -eq 0 ] && [ "$1" != "--no-system" ]; then
    check_service prometheus
    check_service grafana-server
    check_service prometheus-alertmanager
    check_service prometheus-node-exporter
else
    print_info "Skipping service checks (not root)"
fi

# ==========================================
# PART 8: Summary
# ==========================================
echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""

print_status "Monitoring and testing infrastructure is ready!"
echo ""

echo "📊 Access Points:"
echo "  • Health Check: http://localhost:8000/health/"
echo "  • Detailed Health: http://localhost:8000/health/detailed/"
echo "  • Metrics: http://localhost:8000/health/metrics/"

if [ "$EUID" -eq 0 ] && [ "$1" != "--no-system" ]; then
    echo "  • Prometheus: http://localhost:9090"
    echo "  • Grafana: http://localhost:3000 (admin/admin)"
    echo "  • Alertmanager: http://localhost:9093"
fi

echo ""
echo "📚 Next Steps:"
echo "  1. Review MONITORING_GUIDE.md for detailed setup"
echo "  2. Review TESTING_GUIDE.md for testing best practices"
echo "  3. Configure Alertmanager email settings in /etc/alertmanager/alertmanager.yml"
echo "  4. Set up Grafana dashboards"
echo "  5. Configure external uptime monitoring (UptimeRobot, Pingdom, etc.)"
echo ""

echo "🧪 Testing Commands:"
echo "  • Run tests: python manage.py test"
echo "  • Check coverage: coverage run manage.py test && coverage report"
echo "  • Generate HTML report: coverage html"
echo ""

echo "🚀 Start Development Server:"
echo "  python manage.py runserver"
echo ""

print_status "Setup script completed successfully!"
