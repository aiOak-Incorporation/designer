from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("designer_portfolio", "0002_designerprofile_portfolio_template"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersubscription",
            name="acquisition_source",
            field=models.CharField(max_length=100, blank=True, null=True),
        ),
        migrations.AddField(
            model_name="usersubscription",
            name="acquisition_medium",
            field=models.CharField(max_length=100, blank=True, null=True),
        ),
        migrations.AddField(
            model_name="usersubscription",
            name="acquisition_campaign",
            field=models.CharField(max_length=150, blank=True, null=True),
        ),
        migrations.AddField(
            model_name="usersubscription",
            name="acquisition_content",
            field=models.CharField(max_length=150, blank=True, null=True),
        ),
        migrations.AddField(
            model_name="usersubscription",
            name="acquisition_term",
            field=models.CharField(max_length=150, blank=True, null=True),
        ),
        migrations.AddField(
            model_name="usersubscription",
            name="acquisition_landing_page",
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="usersubscription",
            name="acquisition_initial_referrer",
            field=models.URLField(blank=True, null=True),
        ),
    ]
