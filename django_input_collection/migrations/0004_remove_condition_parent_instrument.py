# -*- coding: utf-8 -*-
# Generated by Django 2.1 on 2018-11-14 21:41

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("django_input_collection", "0003_auto_20181114_2036"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="condition",
            name="parent_instrument",
        ),
    ]
