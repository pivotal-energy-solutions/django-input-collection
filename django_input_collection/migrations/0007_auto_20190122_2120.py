# Generated by Django 2.1.4 on 2019-01-22 21:20
from django.conf import settings
from django.db import migrations, models

from django_input_collection.models import get_boundsuggestedresponse_model


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.INPUT_BOUNDSUGGESTEDRESPONSE_MODEL),
        ("django_input_collection", "0006_auto_20190122_2117"),
    ]

    operations = [
        migrations.AddField(
            model_name="collectioninstrument",
            name="suggested_responses_new",
            field=models.ManyToManyField(
                blank=True,
                related_name="collectioninstrument_new",
                through=get_boundsuggestedresponse_model(),
                to="django_input_collection.SuggestedResponse",
            ),
        ),
        migrations.RemoveField(
            model_name="collectioninstrument",
            name="suggested_responses",
        ),
        migrations.RenameField(
            model_name="collectioninstrument",
            old_name="suggested_responses_new",
            new_name="suggested_responses",
        ),
        migrations.AlterField(
            model_name="collectioninstrument",
            name="suggested_responses",
            field=models.ManyToManyField(
                blank=True,
                through=get_boundsuggestedresponse_model(),
                to="django_input_collection.SuggestedResponse",
            ),
        ),
    ]
