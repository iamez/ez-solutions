# email_system/email_config.py
"""
Email Configuration for Tech-IT Solutions
Supports multiple email backends and providers
"""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)

# Add to settings.py:
"""
# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@techitsolutions.com')
SUPPORT_EMAIL = os.environ.get('SUPPORT_EMAIL', 'support@techitsolutions.com')
BILLING_EMAIL = os.environ.get('BILLING_EMAIL', 'billing@techitsolutions.com')

# Celery Configuration for async emails
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
"""

class EmailService:
    """
    Centralized email service for sending various types of emails
    """
    
    @staticmethod
    def send_email(
        subject,
        template_name,
        context,
        recipient_list,
        from_email=None,
        cc=None,
        bcc=None,
        attachments=None
    ):
        """
        Send HTML email with text fallback
        
        Args:
            subject: Email subject line
            template_name: Template path (without .html)
            context: Dictionary of template variables
            recipient_list: List of recipient email addresses
            from_email: Sender email (defaults to DEFAULT_FROM_EMAIL)
            cc: List of CC recipients
            bcc: List of BCC recipients
            attachments: List of (filename, content, mimetype) tuples
        """
        try:
            # Render HTML email
            html_message = render_to_string(f'emails/{template_name}.html', context)
            text_message = strip_tags(html_message)
            
            # Create email
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_message,
                from_email=from_email or settings.DEFAULT_FROM_EMAIL,
                to=recipient_list,
                cc=cc,
                bcc=bcc
            )
            
            email.attach_alternative(html_message, "text/html")
            
            # Add attachments
            if attachments:
                for filename, content, mimetype in attachments:
                    email.attach(filename, content, mimetype)
            
            # Send email
            email.send(fail_silently=False)
            logger.info(f"Email sent: {subject} to {recipient_list}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False
    
    @staticmethod
    def send_welcome_email(user):
        """Send welcome email to new users"""
        context = {
            'user': user,
            'login_url': f"{settings.SITE_URL}/login/",
            'dashboard_url': f"{settings.SITE_URL}/dashboard/",
            'support_email': settings.SUPPORT_EMAIL,
        }
        
        return EmailService.send_email(
            subject='Welcome to Tech-IT Solutions!',
            template_name='welcome',
            context=context,
            recipient_list=[user.email]
        )
    
    @staticmethod
    def send_order_confirmation(order):
        """Send order confirmation email"""
        context = {
            'order': order,
            'user': order.user,
            'items': order.items.all(),
            'total': order.total_amount,
            'order_url': f"{settings.SITE_URL}/orders/{order.id}/",
            'support_email': settings.SUPPORT_EMAIL,
        }
        
        return EmailService.send_email(
            subject=f'Order Confirmation #{order.id}',
            template_name='order_confirmation',
            context=context,
            recipient_list=[order.user.email]
        )
    
    @staticmethod
    def send_invoice(invoice):
        """Send invoice email with PDF attachment"""
        from io import BytesIO
        from .invoice_generator import generate_invoice_pdf
        
        # Generate PDF
        pdf_buffer = BytesIO()
        generate_invoice_pdf(invoice, pdf_buffer)
        pdf_buffer.seek(0)
        
        context = {
            'invoice': invoice,
            'user': invoice.order.user,
            'order': invoice.order,
            'invoice_url': f"{settings.SITE_URL}/invoices/{invoice.id}/",
            'billing_email': settings.BILLING_EMAIL,
        }
        
        attachments = [
            (f'invoice_{invoice.invoice_number}.pdf', pdf_buffer.read(), 'application/pdf')
        ]
        
        return EmailService.send_email(
            subject=f'Invoice {invoice.invoice_number}',
            template_name='invoice',
            context=context,
            recipient_list=[invoice.order.user.email],
            attachments=attachments
        )
    
    @staticmethod
    def send_password_reset(user, reset_token):
        """Send password reset email"""
        context = {
            'user': user,
            'reset_url': f"{settings.SITE_URL}/reset-password/{reset_token}/",
            'expiry_hours': 24,
            'support_email': settings.SUPPORT_EMAIL,
        }
        
        return EmailService.send_email(
            subject='Password Reset Request',
            template_name='password_reset',
            context=context,
            recipient_list=[user.email]
        )
    
    @staticmethod
    def send_ticket_notification(ticket, is_new=True):
        """Send support ticket notification"""
        action = "created" if is_new else "updated"
        
        context = {
            'ticket': ticket,
            'user': ticket.user,
            'action': action,
            'ticket_url': f"{settings.SITE_URL}/tickets/{ticket.id}/",
            'support_email': settings.SUPPORT_EMAIL,
        }
        
        # Send to customer
        EmailService.send_email(
            subject=f'Support Ticket #{ticket.id} {action.title()}',
            template_name='ticket_notification',
            context=context,
            recipient_list=[ticket.user.email]
        )
        
        # Send to support team
        context['is_staff_notification'] = True
        EmailService.send_email(
            subject=f'[SUPPORT] Ticket #{ticket.id} {action.title()}',
            template_name='ticket_notification_staff',
            context=context,
            recipient_list=[settings.SUPPORT_EMAIL]
        )
    
    @staticmethod
    def send_service_expiry_warning(service, days_until_expiry):
        """Send service expiration warning"""
        context = {
            'service': service,
            'user': service.user,
            'days': days_until_expiry,
            'renewal_url': f"{settings.SITE_URL}/services/{service.id}/renew/",
            'billing_email': settings.BILLING_EMAIL,
        }
        
        return EmailService.send_email(
            subject=f'Service Expiring in {days_until_expiry} Days',
            template_name='service_expiry_warning',
            context=context,
            recipient_list=[service.user.email]
        )
    
    @staticmethod
    def send_payment_receipt(payment):
        """Send payment receipt"""
        context = {
            'payment': payment,
            'user': payment.order.user,
            'order': payment.order,
            'receipt_url': f"{settings.SITE_URL}/receipts/{payment.id}/",
            'billing_email': settings.BILLING_EMAIL,
        }
        
        return EmailService.send_email(
            subject=f'Payment Receipt - {payment.payment_id}',
            template_name='payment_receipt',
            context=context,
            recipient_list=[payment.order.user.email]
        )
    
    @staticmethod
    def send_marketing_email(subject, template_name, context, recipient_list):
        """Send marketing/promotional email"""
        context['unsubscribe_url'] = f"{settings.SITE_URL}/unsubscribe/"
        
        return EmailService.send_email(
            subject=subject,
            template_name=f'marketing/{template_name}',
            context=context,
            recipient_list=recipient_list,
            bcc=[settings.SUPPORT_EMAIL]  # BCC to track sent emails
        )
