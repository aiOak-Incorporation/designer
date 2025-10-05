# redym_portfolio/signals.py
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings


@receiver(post_save, sender=User)
def notify_designer_on_approval(sender, instance, created, **kwargs):
    """
    When an admin activates a user account, send them an approval email.
    """
    if not created and instance.is_active:  # not a new signup, but updated
        send_mail(
            subject="Your Redym Designer Account Has Been Approved 🎉",
            message=(
                f"Hello {instance.username},\n\n"
                "Good news! Your designer account has been approved. "
                "You can now log in and upload your designs + techpacks.\n\n"
                "Login here: https://redym.aioak.co/login\n\n"
                "Best,\nTeam Redym"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[instance.email],
            fail_silently=True,
        )
