from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import User


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
