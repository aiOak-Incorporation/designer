# redym_portfolio/apps.py
from django.apps import AppConfig

class SerializerMethodField(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "redym_portfolio"

    def ready(self):
        import redym_portfolio.signals
