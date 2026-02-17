# Tech-IT Solutions - Testing Guide

## 🧪 Testing Suite Overview

Complete testing infrastructure for your Django SaaS platform.

---

## 📦 Test Files Included

1. **test_users.py** - User authentication, registration, profiles
2. **test_services.py** - Service management, pricing
3. **test_orders.py** - Orders, billing, payments
4. **test_domains.py** - Domain management (create this)
5. **test_tickets.py** - Support system (create this)
6. **test_api.py** - API endpoints (create this)

---

## 🚀 Quick Start

### Run All Tests

```bash
# Run all tests
python manage.py test

# Run with verbose output
python manage.py test --verbosity=2

# Run tests in parallel (faster)
python manage.py test --parallel

# Run specific app tests
python manage.py test apps.users
python manage.py test apps.services
python manage.py test apps.orders
```

### Run Specific Tests

```bash
# Run specific test class
python manage.py test apps.users.tests.UserRegistrationTests

# Run specific test method
python manage.py test apps.users.tests.UserRegistrationTests.test_successful_registration

# Run tests matching pattern
python manage.py test --pattern="test_*login*"
```

---

## 📊 Test Coverage

### Install Coverage Tool

```bash
pip install coverage
```

### Run Tests with Coverage

```bash
# Run tests and measure coverage
coverage run --source='.' manage.py test

# Generate coverage report
coverage report

# Generate HTML coverage report
coverage html

# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Coverage Goals
- ✅ **80%+** overall coverage
- ✅ **90%+** for critical paths (auth, payments)
- ✅ **100%** for security-sensitive code

---

## 🏗️ Test Structure

### Directory Structure

```
apps/
├── users/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_models.py
│   │   ├── test_views.py
│   │   ├── test_forms.py
│   │   └── test_api.py
├── services/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_models.py
│   │   └── test_views.py
└── orders/
    ├── tests/
        ├── __init__.py
        ├── test_models.py
        └── test_views.py
```

### Creating Test Files

1. Create `tests` directory in your app
2. Create `__init__.py` to make it a package
3. Create test files: `test_*.py`

---

## 🔧 Test Configuration

### settings.py for Testing

```python
# In config/settings.py or create config/test_settings.py

if 'test' in sys.argv:
    # Use faster password hasher for tests
    PASSWORD_HASHERS = [
        'django.contrib.auth.hashers.MD5PasswordHasher',
    ]
    
    # Use in-memory SQLite for faster tests
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }
    
    # Disable migrations for faster tests
    class DisableMigrations:
        def __contains__(self, item):
            return True
        def __getitem__(self, item):
            return None
    
    MIGRATION_MODULES = DisableMigrations()
    
    # Disable Celery tasks during tests
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
```

---

## 📝 Writing Good Tests

### Test Naming Convention

```python
class TestClassName(TestCase):
    def test_what_it_does_when_condition(self):
        # Arrange
        # Act
        # Assert
        pass
```

### Example Test Template

```python
from django.test import TestCase, Client
from django.urls import reverse

class MyFeatureTests(TestCase):
    def setUp(self):
        """Run before each test"""
        self.client = Client()
        # Create test data
    
    def tearDown(self):
        """Run after each test"""
        # Clean up if needed
        pass
    
    def test_feature_works_correctly(self):
        """Test description"""
        # Arrange - Set up test data
        data = {'key': 'value'}
        
        # Act - Perform the action
        response = self.client.post(reverse('my-url'), data)
        
        # Assert - Verify the result
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'expected text')
```

---

## 🎯 Test Types

### 1. Unit Tests
Test individual functions and methods in isolation.

```python
class UserModelTests(TestCase):
    def test_user_creation(self):
        user = User.objects.create_user(
            username='test',
            email='test@example.com',
            password='TestPass123!'
        )
        self.assertEqual(user.email, 'test@example.com')
```

### 2. Integration Tests
Test multiple components working together.

```python
class OrderProcessingTests(TestCase):
    def test_order_creates_invoice(self):
        # Create order
        order = Order.objects.create(...)
        
        # Check invoice was created
        self.assertTrue(
            Invoice.objects.filter(order=order).exists()
        )
```

### 3. Functional Tests
Test complete user workflows.

```python
class UserRegistrationFlowTests(TestCase):
    def test_complete_registration_flow(self):
        # Visit registration page
        response = self.client.get(reverse('register'))
        
        # Fill form and submit
        response = self.client.post(reverse('register'), {
            'email': 'new@example.com',
            'password1': 'TestPass123!',
            'password2': 'TestPass123!',
        })
        
        # Check redirected to dashboard
        self.assertRedirects(response, reverse('dashboard'))
        
        # Check user can login
        login = self.client.login(
            username='new@example.com',
            password='TestPass123!'
        )
        self.assertTrue(login)
```

---

## 🔍 Testing Best Practices

### 1. Test Independence
Each test should be independent and not rely on other tests.

```python
# ❌ Bad - Tests depend on order
class BadTests(TestCase):
    def test_1_create_user(self):
        self.user = User.objects.create(...)
    
    def test_2_user_login(self):
        # Depends on test_1
        self.client.login(username=self.user.email, ...)

# ✅ Good - Each test is independent
class GoodTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(...)
    
    def test_user_login(self):
        self.client.login(username=self.user.email, ...)
```

### 2. Use Fixtures for Complex Data

Create `fixtures.py`:

```python
from django.contrib.auth import get_user_model

User = get_user_model()

def create_test_user(**kwargs):
    defaults = {
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'TestPass123!'
    }
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)

def create_test_service(**kwargs):
    defaults = {
        'name': 'Test Service',
        'slug': 'test-service',
        'price': 9.99
    }
    defaults.update(kwargs)
    return Service.objects.create(**defaults)
```

Use in tests:

```python
from .fixtures import create_test_user, create_test_service

class MyTests(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.service = create_test_service()
```

### 3. Test Edge Cases

```python
def test_password_validation_edge_cases(self):
    # Empty password
    with self.assertRaises(ValueError):
        User.objects.create_user(username='test', password='')
    
    # Too short password
    # Special characters
    # Unicode characters
    # etc.
```

### 4. Mock External Services

```python
from unittest.mock import patch, Mock

class PaymentTests(TestCase):
    @patch('stripe.Charge.create')
    def test_stripe_payment(self, mock_stripe):
        # Mock Stripe response
        mock_stripe.return_value = Mock(
            id='ch_123',
            status='succeeded'
        )
        
        # Test payment processing
        result = process_payment(100, 'tok_123')
        
        # Verify Stripe was called correctly
        mock_stripe.assert_called_once()
        self.assertTrue(result.success)
```

---

## 🔄 Continuous Integration

### GitHub Actions Configuration

Create `.github/workflows/tests.yml`:

```yaml
name: Django Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Run tests
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db
      run: |
        python manage.py test --verbosity=2
    
    - name: Generate coverage report
      run: |
        coverage run --source='.' manage.py test
        coverage report
        coverage html
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### GitLab CI Configuration

Create `.gitlab-ci.yml`:

```yaml
image: python:3.11

services:
  - postgres:14

variables:
  POSTGRES_DB: test_db
  POSTGRES_USER: postgres
  POSTGRES_PASSWORD: postgres
  DATABASE_URL: postgresql://postgres:postgres@postgres:5432/test_db

stages:
  - test
  - coverage

before_script:
  - pip install -r requirements.txt

test:
  stage: test
  script:
    - python manage.py test --verbosity=2
  coverage: '/TOTAL.*\s+(\d+%)$/'

coverage:
  stage: coverage
  script:
    - coverage run --source='.' manage.py test
    - coverage report
    - coverage html
  artifacts:
    paths:
      - htmlcov/
```

---

## 🎭 Test Data Management

### Using Factory Boy

```bash
pip install factory-boy
```

Create `factories.py`:

```python
import factory
from factory.django import DjangoModelFactory
from apps.users.models import User
from apps.services.models import Service

class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
    
    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.LazyAttribute(lambda o: f'{o.username}@example.com')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')

class ServiceFactory(DjangoModelFactory):
    class Meta:
        model = Service
    
    name = factory.Faker('word')
    slug = factory.LazyAttribute(lambda o: o.name.lower())
    price = factory.Faker('pydecimal', left_digits=2, right_digits=2, positive=True)
```

Use in tests:

```python
from .factories import UserFactory, ServiceFactory

class OrderTests(TestCase):
    def test_order_creation(self):
        user = UserFactory()
        service = ServiceFactory()
        order = Order.objects.create(user=user, service=service)
        self.assertIsNotNone(order)
```

---

## 📈 Performance Testing

### Load Testing with Locust

```bash
pip install locust
```

Create `locustfile.py`:

```python
from locust import HttpUser, task, between

class WebsiteUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)
    def view_homepage(self):
        self.client.get("/")
    
    @task(2)
    def view_services(self):
        self.client.get("/services/")
    
    @task(1)
    def login(self):
        self.client.post("/users/login/", {
            "username": "test@example.com",
            "password": "TestPass123!"
        })
```

Run load test:

```bash
locust -f locustfile.py --host=http://localhost:8000
# Open http://localhost:8089 to control the test
```

---

## 🐛 Debugging Tests

### Run Tests with PDB

```python
def test_something(self):
    # Add breakpoint
    import pdb; pdb.set_trace()
    
    # Or use Python 3.7+
    breakpoint()
    
    result = some_function()
    self.assertEqual(result, expected)
```

### View Test Database

```python
# In test method
from django.test.utils import setup_test_environment
setup_test_environment()

# Now you can inspect the database
User.objects.all()
```

### Verbose Test Output

```bash
# Show full error messages
python manage.py test --verbosity=2 --debug-mode

# Keep test database after run
python manage.py test --keepdb
```

---

## ✅ Testing Checklist

Before deploying:

- [ ] All tests pass
- [ ] Coverage > 80%
- [ ] No security vulnerabilities
- [ ] Performance tests pass
- [ ] API tests pass
- [ ] Integration tests pass
- [ ] Manual testing of critical flows
- [ ] Browser compatibility tested
- [ ] Mobile responsiveness tested

---

## 📚 Resources

- **Django Testing**: https://docs.djangoproject.com/en/stable/topics/testing/
- **Coverage.py**: https://coverage.readthedocs.io/
- **Factory Boy**: https://factoryboy.readthedocs.io/
- **Locust**: https://docs.locust.io/

---

## 🎯 Next Steps

1. ✅ Copy test files to your project
2. ✅ Run all tests: `python manage.py test`
3. ✅ Check coverage: `coverage run manage.py test && coverage report`
4. ✅ Set up CI/CD with GitHub Actions or GitLab CI
5. ✅ Add pre-commit hooks to run tests
6. ✅ Create test data fixtures
7. ✅ Write tests for new features

Happy testing! 🧪
