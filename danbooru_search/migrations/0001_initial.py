# Generated by Django 5.1.6 on 2025-02-11 17:04

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CommonWord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('word', models.CharField(max_length=100, unique=True)),
                ('category', models.CharField(choices=[('english', 'English'), ('japanese', 'Japanese'), ('proper_noun', 'Proper Noun'), ('custom', 'Custom Addition')], max_length=50)),
                ('added_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='UpdateStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_tags', models.IntegerField(default=0)),
                ('processed_tags', models.IntegerField(default=0)),
                ('current_page', models.IntegerField(default=0)),
                ('start_time', models.DateTimeField(null=True)),
                ('last_backup', models.DateTimeField(null=True)),
                ('is_updating', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True)),
                ('post_count', models.IntegerField()),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('last_update_page', models.IntegerField(default=0)),
            ],
            options={
                'indexes': [models.Index(fields=['name'], name='danbooru_se_name_c72f77_idx'), models.Index(fields=['-post_count'], name='danbooru_se_post_co_cf2f0e_idx')],
            },
        ),
    ]
