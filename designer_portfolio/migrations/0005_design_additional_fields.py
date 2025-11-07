from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("designer_portfolio", "0004_webauthncredential"),
    ]

    operations = [
        migrations.AddField(
            model_name="design",
            name="category",
            field=models.CharField(blank=True, default="", max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="design",
            name="target_market",
            field=models.CharField(blank=True, default="", max_length=50),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="design",
            name="featured",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="design",
            name="fabric_type",
            field=models.CharField(blank=True, default="", max_length=200),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="design",
            name="fabric_weight",
            field=models.CharField(blank=True, default="", max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="design",
            name="design_notes",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
    ]
