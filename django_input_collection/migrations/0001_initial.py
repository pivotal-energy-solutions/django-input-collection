# Generated by Django 2.1 on 2018-10-01 20:10

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import swapper


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CollectedInput',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('data', models.CharField(max_length=512)),
            ],
            options={
                'swappable': swapper.swappable_setting('django_input_collection', 'CollectedInput'),
            },
        ),
        migrations.CreateModel(
            name='Case',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('nickname', models.CharField(blank=True, max_length=100, null=True, unique=True)),
                ('match_type', models.CharField(choices=[('any', 'Any input allowed'), ('none', 'No input allowed'), ('all-suggested', 'All suggested'), ('one-suggested', 'At least one suggested'), ('all-custom', 'All custom'), ('one-custom', 'At least one custom'), ('match', 'Input matches this data'), ('mismatch', "Input doesn't match this data"), ('contains', 'Input contains this data'), ('not-contains', 'Input does not contain this data')], default=None, max_length=20, null=True)),
                ('match_data', models.CharField(max_length=512)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CollectionGroup',
            fields=[
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('id', models.CharField(max_length=100, primary_key=True, serialize=False)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CollectionInstrument',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('order', models.IntegerField(default=0)),
                ('text', models.TextField()),
                ('description', models.TextField(blank=True)),
                ('help', models.TextField(blank=True)),
            ],
            options={
                'ordering': ('order', 'pk'),
            },
        ),
        migrations.CreateModel(
            name='CollectionInstrumentType',
            fields=[
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('id', models.CharField(max_length=100, primary_key=True, serialize=False)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CollectionRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('max_instrument_inputs_per_user', models.PositiveIntegerField(blank=True, null=True)),
                ('max_instrument_inputs', models.PositiveIntegerField(blank=True, null=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Condition',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ConditionGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('nickname', models.CharField(blank=True, max_length=100, null=True, unique=True)),
                ('requirement_type', models.CharField(choices=[('all-pass', 'All cases must pass'), ('one-pass', 'At least one case must pass'), ('all-fail', 'All cases must fail')], default=True, max_length=20)),
                ('cases', models.ManyToManyField(to='django_input_collection.Case')),
                ('child_groups', models.ManyToManyField(blank=True, related_name='parent_groups', to='django_input_collection.ConditionGroup')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Measure',
            fields=[
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('id', models.CharField(max_length=100, primary_key=True, serialize=False)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ResponsePolicy',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('nickname', models.CharField(max_length=100, null=True)),
                ('is_singleton', models.BooleanField(default=False)),
                ('restrict', models.BooleanField()),
                ('multiple', models.BooleanField()),
                ('required', models.BooleanField()),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SuggestedResponse',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('data', models.CharField(max_length=512)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='condition',
            name='condition_group',
            field=models.ForeignKey(limit_choices_to={'parent_groups': None}, on_delete=django.db.models.deletion.CASCADE, to='django_input_collection.ConditionGroup'),
        ),
        migrations.AddField(
            model_name='condition',
            name='instrument',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conditions', to='django_input_collection.CollectionInstrument'),
        ),
        migrations.AddField(
            model_name='condition',
            name='parent_instrument',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='child_conditions', to='django_input_collection.CollectionInstrument'),
        ),
        migrations.AddField(
            model_name='collectioninstrument',
            name='collection_request',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='django_input_collection.CollectionRequest'),
        ),
        migrations.AddField(
            model_name='collectioninstrument',
            name='group',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='django_input_collection.CollectionGroup'),
        ),
        migrations.AddField(
            model_name='collectioninstrument',
            name='measure',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='django_input_collection.Measure'),
        ),
        migrations.AddField(
            model_name='collectioninstrument',
            name='response_policy',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='django_input_collection.ResponsePolicy'),
        ),
        migrations.AddField(
            model_name='collectioninstrument',
            name='suggested_responses',
            field=models.ManyToManyField(to='django_input_collection.SuggestedResponse'),
        ),
        migrations.AddField(
            model_name='collectioninstrument',
            name='type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='django_input_collection.CollectionInstrumentType'),
        ),
        migrations.AddField(
            model_name='collectedinput',
            name='collection_request',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='collectedinput_set', to='django_input_collection.CollectionRequest'),
        ),
        migrations.AddField(
            model_name='collectedinput',
            name='instrument',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='collectedinput_set', to='django_input_collection.CollectionInstrument'),
        ),
        migrations.AddField(
            model_name='collectedinput',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
    ]