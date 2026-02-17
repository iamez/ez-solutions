# customer_experience/onboarding/onboarding_system.py
"""
User Onboarding System
Guides new users through setup with email sequences and in-app tours
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from email_system.email_config import EmailService

User = get_user_model()


class OnboardingStep(models.Model):
    """Onboarding step definition"""
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    order = models.IntegerField(default=0)
    
    # Step configuration
    is_required = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Email configuration
    send_email = models.BooleanField(default=False)
    email_template = models.CharField(max_length=100, blank=True)
    email_delay_hours = models.IntegerField(default=0, help_text="Send email X hours after previous step")
    
    # In-app tour
    tour_element_id = models.CharField(max_length=100, blank=True, help_text="DOM element ID for tour highlight")
    tour_content = models.TextField(blank=True, help_text="Tour step content")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return self.name


class UserOnboarding(models.Model):
    """Track user's onboarding progress"""
    
    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('skipped', 'Skipped'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='onboarding')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')
    current_step = models.ForeignKey(OnboardingStep, on_delete=models.SET_NULL, null=True, blank=True)
    
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Progress tracking
    completion_percentage = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = "User Onboarding"
        verbose_name_plural = "User Onboardings"
    
    def __str__(self):
        return f"{self.user.email} - {self.status}"
    
    def start_onboarding(self):
        """Start the onboarding process"""
        self.status = 'in_progress'
        self.started_at = timezone.now()
        self.current_step = OnboardingStep.objects.filter(is_active=True).first()
        self.save()
        
        # Send welcome email
        EmailService.send_welcome_email(self.user)
    
    def complete_step(self, step):
        """Mark a step as completed"""
        UserOnboardingProgress.objects.update_or_create(
            user_onboarding=self,
            step=step,
            defaults={
                'status': 'completed',
                'completed_at': timezone.now()
            }
        )
        
        # Update progress percentage
        self.update_progress()
        
        # Move to next step
        self.move_to_next_step()
    
    def skip_step(self, step):
        """Skip a step"""
        UserOnboardingProgress.objects.update_or_create(
            user_onboarding=self,
            step=step,
            defaults={
                'status': 'skipped',
                'completed_at': timezone.now()
            }
        )
        
        self.update_progress()
        self.move_to_next_step()
    
    def move_to_next_step(self):
        """Move to the next onboarding step"""
        if not self.current_step:
            return
        
        next_step = OnboardingStep.objects.filter(
            is_active=True,
            order__gt=self.current_step.order
        ).first()
        
        if next_step:
            self.current_step = next_step
            self.save()
            
            # Schedule email if configured
            if next_step.send_email:
                from celery import shared_task
                send_onboarding_email.apply_async(
                    args=[self.user.id, next_step.id],
                    countdown=next_step.email_delay_hours * 3600
                )
        else:
            # No more steps, mark as completed
            self.complete_onboarding()
    
    def complete_onboarding(self):
        """Complete the entire onboarding"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.completion_percentage = 100
        self.save()
        
        # Send completion email
        EmailService.send_email(
            subject='Welcome to Tech-IT Solutions - You\'re All Set!',
            template_name='onboarding/completion',
            context={'user': self.user},
            recipient_list=[self.user.email]
        )
    
    def update_progress(self):
        """Update completion percentage"""
        total_steps = OnboardingStep.objects.filter(is_active=True).count()
        completed_steps = self.progress.filter(status='completed').count()
        
        if total_steps > 0:
            self.completion_percentage = int((completed_steps / total_steps) * 100)
            self.save(update_fields=['completion_percentage'])
    
    def get_incomplete_steps(self):
        """Get list of incomplete steps"""
        completed_step_ids = self.progress.filter(
            status__in=['completed', 'skipped']
        ).values_list('step_id', flat=True)
        
        return OnboardingStep.objects.filter(
            is_active=True
        ).exclude(id__in=completed_step_ids)


class UserOnboardingProgress(models.Model):
    """Individual step progress"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('skipped', 'Skipped'),
    ]
    
    user_onboarding = models.ForeignKey(UserOnboarding, on_delete=models.CASCADE, related_name='progress')
    step = models.ForeignKey(OnboardingStep, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Track user actions
    attempts = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['user_onboarding', 'step']
        ordering = ['step__order']
    
    def __str__(self):
        return f"{self.user_onboarding.user.email} - {self.step.name}"


# Celery task for sending onboarding emails
from celery import shared_task

@shared_task
def send_onboarding_email(user_id, step_id):
    """Send onboarding email for a specific step"""
    try:
        user = User.objects.get(id=user_id)
        step = OnboardingStep.objects.get(id=step_id)
        
        if step.send_email and step.email_template:
            context = {
                'user': user,
                'step': step,
            }
            
            EmailService.send_email(
                subject=f'Next Step: {step.name}',
                template_name=f'onboarding/{step.email_template}',
                context=context,
                recipient_list=[user.email]
            )
    except (User.DoesNotExist, OnboardingStep.DoesNotExist):
        pass


# Onboarding utilities
class OnboardingManager:
    """Manage onboarding operations"""
    
    @staticmethod
    def initialize_onboarding(user):
        """Initialize onboarding for a new user"""
        onboarding, created = UserOnboarding.objects.get_or_create(user=user)
        
        if created:
            onboarding.start_onboarding()
        
        return onboarding
    
    @staticmethod
    def check_step_completion(user, step_slug):
        """Check if user completed a specific step"""
        try:
            onboarding = UserOnboarding.objects.get(user=user)
            step = OnboardingStep.objects.get(slug=step_slug)
            progress = UserOnboardingProgress.objects.get(
                user_onboarding=onboarding,
                step=step
            )
            return progress.status == 'completed'
        except (UserOnboarding.DoesNotExist, OnboardingStep.DoesNotExist, UserOnboardingProgress.DoesNotExist):
            return False
    
    @staticmethod
    def get_onboarding_checklist(user):
        """Get onboarding checklist for user"""
        try:
            onboarding = UserOnboarding.objects.get(user=user)
            steps = OnboardingStep.objects.filter(is_active=True)
            
            checklist = []
            for step in steps:
                try:
                    progress = UserOnboardingProgress.objects.get(
                        user_onboarding=onboarding,
                        step=step
                    )
                    status = progress.status
                except UserOnboardingProgress.DoesNotExist:
                    status = 'pending'
                
                checklist.append({
                    'step': step,
                    'status': status,
                    'is_current': step == onboarding.current_step
                })
            
            return checklist
        except UserOnboarding.DoesNotExist:
            return []


# Default onboarding steps
DEFAULT_ONBOARDING_STEPS = [
    {
        'name': 'Complete Your Profile',
        'slug': 'complete-profile',
        'description': 'Add your name, company, and contact information',
        'order': 1,
        'is_required': True,
        'send_email': False,
        'tour_element_id': 'profile-menu',
        'tour_content': 'Click here to complete your profile and personalize your account.'
    },
    {
        'name': 'Browse Services',
        'slug': 'browse-services',
        'description': 'Explore our hosting, VPS, and domain services',
        'order': 2,
        'is_required': False,
        'send_email': True,
        'email_template': 'browse_services',
        'email_delay_hours': 24,
        'tour_element_id': 'services-menu',
        'tour_content': 'Browse our services to find the perfect solution for your needs.'
    },
    {
        'name': 'Create Your First Order',
        'slug': 'first-order',
        'description': 'Select a service and complete your first order',
        'order': 3,
        'is_required': False,
        'send_email': True,
        'email_template': 'first_order',
        'email_delay_hours': 48,
        'tour_element_id': 'order-button',
        'tour_content': 'Ready to get started? Create your first order here.'
    },
    {
        'name': 'Setup Your Service',
        'slug': 'setup-service',
        'description': 'Configure and activate your new service',
        'order': 4,
        'is_required': False,
        'send_email': True,
        'email_template': 'setup_service',
        'email_delay_hours': 1,
    },
    {
        'name': 'Explore Support Options',
        'slug': 'explore-support',
        'description': 'Learn about our support channels and knowledge base',
        'order': 5,
        'is_required': False,
        'send_email': True,
        'email_template': 'explore_support',
        'email_delay_hours': 72,
        'tour_element_id': 'support-menu',
        'tour_content': 'Need help? Access our support resources and create tickets here.'
    },
]
