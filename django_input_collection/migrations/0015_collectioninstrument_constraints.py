from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_input_collection", "0014_collectioninstrument_context"),
    ]

    operations = [
        migrations.AddField(
            model_name="collectioninstrument",
            name="constraints",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
