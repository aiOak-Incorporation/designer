from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.core import mail

from .models import DesignerProfile, UserSubscription, DesignerConversation, DesignerMessage


TEST_STORAGE_BACKENDS = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    STORAGES=TEST_STORAGE_BACKENDS,
)
class LoginFlowTests(TestCase):
    def setUp(self) -> None:
        self.password = "TestPass123!"
        self.user = User.objects.create_user(
            username="designer1",
            email="designer1@example.com",
            password=self.password,
            is_active=True,
        )

    def test_login_with_username_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.user.username, "password": self.password},
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers.get("Location"), reverse("designer_dashboard"))

    def test_login_with_email_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.user.email, "password": self.password},
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers.get("Location"), reverse("designer_dashboard"))

    @override_settings(REMEMBER_ME_SESSION_AGE=3600)
    def test_remember_me_sets_persistent_session(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": self.user.username,
                "password": self.password,
                "remember_me": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        session = self.client.session
        # Should NOT expire at browser close when remember me is set
        self.assertFalse(session.get_expire_at_browser_close())
        # Should be close to configured REMEMBER_ME_SESSION_AGE (>= 1 hour)
        self.assertGreaterEqual(session.get_expiry_age(), 3590)

    def test_without_remember_me_expires_on_browser_close(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.user.username, "password": self.password},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        session = self.client.session
        # Should expire at browser close when remember me is not set
        self.assertTrue(session.get_expire_at_browser_close())

    def test_login_creates_required_related_records(self):
        self.assertFalse(DesignerProfile.objects.filter(user=self.user).exists())
        self.assertFalse(UserSubscription.objects.filter(user=self.user).exists())

        response = self.client.post(
            reverse("login"),
            {"username": self.user.username, "password": self.password, "remember_me": "on"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        self.assertTrue(DesignerProfile.objects.filter(user=self.user).exists())
        self.assertTrue(UserSubscription.objects.filter(user=self.user).exists())


@override_settings(
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    STORAGES=TEST_STORAGE_BACKENDS,
)
class PasswordResetFlowTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="sleepy-designer",
            email="sleepy@example.com",
            password="unused",
            is_active=False,
        )
        # Simulate legacy account without required relations
        DesignerProfile.objects.filter(user=self.user).delete()
        UserSubscription.objects.filter(user=self.user).delete()
        self.user.set_unusable_password()
        self.user.is_active = False
        self.user.save(update_fields=["password", "is_active"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_by_username_reactivates_and_bootstraps(self):
        mail.outbox.clear()

        response = self.client.post(
            reverse("password_reset"),
            {"email": self.user.username},
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("password_reset_done"))

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertTrue(DesignerProfile.objects.filter(user=self.user).exists())
        self.assertTrue(UserSubscription.objects.filter(user=self.user).exists())

        # At least one email should have been queued and one must be the reset email
        self.assertGreaterEqual(len(mail.outbox), 1)
        self.assertTrue(
            any("reset" in (message.subject or "").lower() for message in mail.outbox),
            "Expected a password reset email to be sent",
        )
        self.assertTrue(
            any("sleepy@example.com" in (message.to or []) for message in mail.outbox),
            "Expected emails to include the designer's address",
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_falls_back_to_contact_email(self):
        mail.outbox.clear()
        fallback_email = "sleepy-contact@example.com"

        # Ensure the user record has no email but the profile exposes a contact address
        self.user.email = ""
        self.user.save(update_fields=["email"])
        DesignerProfile.objects.create(user=self.user, contact_email=fallback_email)

        response = self.client.post(
            reverse("password_reset"),
            {"email": self.user.username},
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("password_reset_done"))

        self.assertTrue(
            any(fallback_email in (message.to or []) for message in mail.outbox),
            "Expected the reset email to use the profile contact address when user.email is empty",
        )


@override_settings(
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    STORAGES=TEST_STORAGE_BACKENDS,
)
class MessengerViewTests(TestCase):
    def setUp(self) -> None:
        self.password = "StrongPass123!"
        self.sender = User.objects.create_user(
            username="primary-designer",
            email="primary@example.com",
            password=self.password,
            is_active=True,
        )
        self.recipient = User.objects.create_user(
            username="secondary-designer",
            email="secondary@example.com",
            password=self.password,
            is_active=True,
        )
        DesignerProfile.objects.create(user=self.sender)
        DesignerProfile.objects.create(user=self.recipient)

    def test_login_required_for_messenger(self):
        response = self.client.get(reverse("designer_messenger"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_non_designer_redirected_from_messenger(self):
        outsider = User.objects.create_user(
            username="outsider",
            email="outsider@example.com",
            password=self.password,
            is_active=True,
        )
        self.client.login(username="outsider", password=self.password)

        # Emulate a legacy account that has not been provisioned as a designer
        DesignerProfile.objects.filter(user=outsider).delete()

        response = self.client.get(reverse("designer_messenger"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("designer_dashboard"))

    def test_get_with_parameter_bootstraps_conversation(self):
        self.client.login(username=self.sender.username, password=self.password)
        self.assertEqual(DesignerConversation.objects.count(), 0)

        response = self.client.get(f"{reverse('designer_messenger')}?with={self.recipient.username}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DesignerConversation.objects.count(), 1)

    def test_post_creates_message_and_conversation(self):
        self.client.login(username=self.sender.username, password=self.password)
        post_data = {
            "recipient": str(self.recipient.pk),
            "message": "Hello from the dedicated messenger.",
        }

        response = self.client.post(reverse("designer_messenger"), post_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("designer_messenger")))

        conversation = DesignerConversation.objects.get(
            participant_a_id=min(self.sender.pk, self.recipient.pk),
            participant_b_id=max(self.sender.pk, self.recipient.pk),
        )
        self.assertEqual(conversation.messages.count(), 1)

        message = conversation.messages.first()
        self.assertEqual(message.content, post_data["message"])
        self.assertEqual(message.sender, self.sender)

    def test_thread_marks_partner_messages_as_read(self):
        conversation = DesignerConversation.get_or_create_between(self.sender, self.recipient)[0]
        DesignerMessage.objects.create(
            conversation=conversation,
            sender=self.recipient,
            content="Incoming message that should be marked read.",
        )

        self.client.login(username=self.sender.username, password=self.password)
        response = self.client.get(f"{reverse('designer_messenger')}?conversation={conversation.pk}")
        self.assertEqual(response.status_code, 200)

        message = conversation.messages.first()
        message.refresh_from_db()
        self.assertIsNotNone(message.read_at)
