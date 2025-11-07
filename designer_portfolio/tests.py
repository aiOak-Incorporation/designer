import shutil
import tempfile

from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from .models import DesignerProfile, UserSubscription, Design, DesignImage


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
class DesignManagementTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_root = tempfile.mkdtemp(prefix="designer-tests-")
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self) -> None:
        self.password = "SecretPass123!"
        self.user = User.objects.create_user(
            username="creative-user",
            email="creative@example.com",
            password=self.password,
            is_active=True,
        )
        self.client.login(username=self.user.username, password=self.password)

    def _png_file(self, name="image.png"):
        return SimpleUploadedFile(name, b"\x89PNG\r\n\x1a\n\x00\x00\x00fake", content_type="image/png")

    def _jpg_file(self, name="cover.jpg"):
        return SimpleUploadedFile(name, b"\xff\xd8\xff\xdb\x00\x84fake", content_type="image/jpeg")

    def _pdf_file(self, name="techpack.pdf"):
        return SimpleUploadedFile(name, b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n", content_type="application/pdf")

    def _xlsx_file(self, name="updates.xlsx"):
        return SimpleUploadedFile(name, b"PK\x03\x04fake-xlsx", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    def test_create_design_with_related_files(self):
        cover = self._jpg_file()
        gallery_image = self._png_file("gallery.png")
        techpack = self._pdf_file()

        response = self.client.post(
            reverse("designer_design_create"),
            {
                "title": "Ocean Breeze",
                "season": "Spring",
                "year": str(timezone.now().year),
                "description": "Flowy summer dress inspired by ocean waves.",
                "category": "dresses",
                "target_market": "womens",
                "fabric_type": "Cotton",
                "fabric_weight": "Lightweight",
                "color_palette": "Turquoise, White",
                "size_range": "XS-XL",
                "target_price": "199.99",
                "technical_notes": "Dry clean only",
                "published": "true",
                "featured": "true",
                "cover_image": cover,
                "additional_images": [gallery_image],
                "techpack_file": techpack,
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 302)

        design = Design.objects.get(title="Ocean Breeze")
        self.assertTrue(design.slug)
        self.assertTrue(design.published)
        self.assertTrue(design.is_featured)
        self.assertEqual(design.category, "dresses")
        self.assertEqual(design.target_market, "womens")
        self.assertEqual(design.fabric_details, "Cotton")
        self.assertEqual(design.fabric_weight, "Lightweight")
        self.assertEqual(design.color_palette, "Turquoise, White")
        self.assertEqual(str(design.target_price), "199.99")
        self.assertEqual(design.production_notes, "Dry clean only")
        self.assertTrue(design.techpack_pdf.name.endswith("techpack.pdf"))
        self.assertEqual(design.images.count(), 1)

    def test_edit_design_updates_fields_and_files(self):
        design = Design.objects.create(
            designer=self.user,
            title="Sunset Dress",
            slug="sunset-dress",
            season="Summer",
            year=timezone.now().year,
            description="Original description",
            category="dresses",
            target_market="womens",
            fabric_details="Linen",
            size_range="S-L",
            published=False,
        )

        DesignImage.objects.create(design=design, image=self._png_file("initial.png"), order=0)

        response = self.client.post(
            reverse("designer_design_edit", args=[design.id]),
            {
                "title": "Sunset Dress Deluxe",
                "category": "dresses",
                "target_market": "womens",
                "description": "Updated and refined description.",
                "season": "Fall",
                "year": str(timezone.now().year + 1),
                "fabric_type": "Silk",
                "fabric_weight": "Medium",
                "color_palette": "Orange, Gold",
                "size_range": "S-XL",
                "target_price": "249.50",
                "technical_notes": "Updated notes",
                "is_public": "true",
                "is_featured": "true",
                "cover_image": self._jpg_file("new-cover.jpg"),
                "tech_pack_excel": self._xlsx_file(),
                "additional_images": [self._png_file("added.png")],
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 302)

        design.refresh_from_db()
        self.assertEqual(design.title, "Sunset Dress Deluxe")
        self.assertEqual(design.season, "Fall")
        self.assertEqual(design.year, timezone.now().year + 1)
        self.assertEqual(design.fabric_details, "Silk")
        self.assertEqual(design.fabric_weight, "Medium")
        self.assertEqual(design.size_range, "S-XL")
        self.assertEqual(str(design.target_price), "249.50")
        self.assertEqual(design.production_notes, "Updated notes")
        self.assertTrue(design.published)
        self.assertTrue(design.is_featured)
        self.assertTrue(design.cover_image.name.endswith("new-cover.jpg"))
        self.assertTrue(design.techpack_excel.name.endswith("updates.xlsx"))
        self.assertEqual(design.images.count(), 2)

    def test_delete_design_removes_records(self):
        design = Design.objects.create(
            designer=self.user,
            title="Delete Me",
            slug="delete-me",
            season="Winter",
            year=timezone.now().year,
        )
        DesignImage.objects.create(design=design, image=self._png_file("to-delete.png"), order=0)

        response = self.client.post(reverse("designer_design_delete", args=[design.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Design.objects.filter(pk=design.id).exists())
        self.assertEqual(DesignImage.objects.filter(design=design).count(), 0)

    def test_design_detail_api_returns_expected_payload(self):
        design = Design.objects.create(
            designer=self.user,
            title="API Design",
            slug="api-design",
            season="Spring",
            year=timezone.now().year,
            description="For API test",
            category="tops",
            target_market="womens",
            fabric_details="Cotton",
            fabric_weight="Light",
            color_palette="Blue, White",
            size_range="XS-L",
            target_price="149.00",
            production_notes="Handle with care",
            published=True,
            is_featured=True,
        )
        DesignImage.objects.create(design=design, image=self._png_file("api.png"), order=0)

        response = self.client.get(reverse("designer_design_detail_api", args=[design.id]))
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        data = payload["design"]
        self.assertEqual(data["title"], "API Design")
        self.assertEqual(data["category"], "tops")
        self.assertEqual(data["target_market"], "womens")
        self.assertEqual(data["season"], "Spring")
        self.assertEqual(data["description"], "For API test")
        self.assertTrue(data["published"])
        self.assertTrue(data["is_featured"])
        self.assertEqual(len(data["images"]), 1)
