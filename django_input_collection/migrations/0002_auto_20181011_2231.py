# Generated by Django 2.1 on 2018-10-11 22:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('django_input_collection', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='responsepolicy',
            options={'verbose_name_plural': 'Response policies'},
        ),
        migrations.AlterField(
            model_name='case',
            name='match_data',
            field=models.CharField(blank=True, max_length=512, null=True),
        ),
        migrations.AlterField(
            model_name='conditiongroup',
            name='cases',
            field=models.ManyToManyField(blank=True, to='django_input_collection.Case'),
        ),
    ]