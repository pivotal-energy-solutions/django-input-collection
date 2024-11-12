# Generated by Django 2.1.7 on 2019-03-05 17:59

from django.db import migrations, models
import django.db.models.deletion


# def forwards__group_to_segment(apps, schema_editor):
#     CollectionInstrument = apps.get_model("django_input_collection", "CollectionInstrument")
#     CollectionInstrument.objects.update(segment=models.F("group"), group=None)
#
#
# def backwards__segment_to_group(apps, schema_editor):
#     CollectionInstrument = apps.get_model("django_input_collection", "CollectionInstrument")
#     CollectionInstrument.objects.update(group=models.F("segment"), segment=None)


class Migration(migrations.Migration):
    dependencies = [
        ("django_input_collection", "0008_auto_20190206_1901"),
    ]

    operations = [
        migrations.AddField(
            model_name="collectioninstrument",
            name="segment",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="segment_instruments",
                to="django_input_collection.CollectionGroup",
            ),
        ),
        migrations.AlterField(
            model_name="collectioninstrument",
            name="group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="group_instruments",
                to="django_input_collection.CollectionGroup",
            ),
        ),
        # Data migration
        # migrations.RunPython(forwards__group_to_segment, backwards__segment_to_group),
    ]
