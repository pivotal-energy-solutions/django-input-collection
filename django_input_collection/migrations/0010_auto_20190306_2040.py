# Generated by Django 2.1.4 on 2019-03-06 20:40

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("django_input_collection", "0009_group_to_segment"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="collectioninstrument",
            options={"ordering": ("segment_id", "group_id", "order", "pk")},
        ),
    ]
