# Generated by Django 2.1 on 2018-11-14 20:36

from django.db import migrations


# def parent_instrument_to_data_getter(apps, schema_editor):
#     Condition = apps.get_model("django_input_collection", "Condition")
#     for id, parent_id in Condition.objects.values_list("id", "parent_instrument"):
#         Condition.objects.filter(id=id).update(data_getter="instrument:%d" % (parent_id,))


class Migration(migrations.Migration):
    dependencies = [
        ("django_input_collection", "0002_condition_data_getter"),
    ]

    operations = [
        # migrations.RunPython(parent_instrument_to_data_getter, migrations.RunPython.noop),
    ]
