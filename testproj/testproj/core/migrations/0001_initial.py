# Generated by Django 2.1 on 2018-10-01 20:10

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('django_input_collection', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PoliticalRally',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=50)),
                ('location', models.CharField(max_length=50)),
                ('time', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='RallyPoll',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_time', models.DateTimeField(auto_now=True)),
                ('end_time', models.DateTimeField(blank=True, null=True)),
                ('collection_request', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='django_input_collection.CollectionRequest')),
                ('rally', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.PoliticalRally')),
            ],
        ),
        migrations.CreateModel(
            name='Survey',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=50)),
                ('start_time', models.DateTimeField(auto_now=True)),
                ('end_time', models.DateTimeField(blank=True, null=True)),
                ('collection_request', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='django_input_collection.CollectionRequest')),
            ],
        ),
        migrations.AddField(
            model_name='politicalrally',
            name='collection_requests',
            field=models.ManyToManyField(through='core.RallyPoll', to='django_input_collection.CollectionRequest'),
        ),
    ]
