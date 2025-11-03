from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("designer_portfolio", "0003_usersubscription_acquisition_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WebAuthnCredential",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("credential_id", models.BinaryField(unique=True)),
                ("public_key", models.BinaryField()),
                ("sign_count", models.PositiveBigIntegerField(default=0)),
                ("transports", models.JSONField(blank=True, default=list)),
                ("nickname", models.CharField(blank=True, max_length=150)),
                ("attestation_format", models.CharField(blank=True, max_length=50)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="webauthn_credentials",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "WebAuthn Credential",
                "verbose_name_plural": "WebAuthn Credentials",
            },
        ),
    ]
