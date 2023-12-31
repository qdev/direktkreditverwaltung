# Generated by Django 3.0.8 on 2020-07-26 17:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dkapp', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contact',
            name='bank_name',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AlterField(
            model_name='contact',
            name='bic',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AlterField(
            model_name='contact',
            name='email',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AlterField(
            model_name='contact',
            name='iban',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AlterField(
            model_name='contact',
            name='phone',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AlterField(
            model_name='contact',
            name='remark',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AlterField(
            model_name='contract',
            name='category',
            field=models.CharField(choices=[('Privat', 'Privat'), ('Syndikat', 'Syndikat'), ('Dritte', 'Dritte')], max_length=200),
        ),
        migrations.AlterField(
            model_name='contract',
            name='comment',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AlterField(
            model_name='contractversion',
            name='duration_months',
            field=models.IntegerField(blank=True),
        ),
        migrations.AlterField(
            model_name='contractversion',
            name='cancellation_months',
            field=models.IntegerField(blank=True),
        ),
        migrations.AlterField(
            model_name='contractversion',
            name='interest_type',
            field=models.CharField(choices=[('Auszahlen', 'Auszahlen'), ('ohne Zinseszins', 'ohne Zinseszins'), ('mit Zinseszins', 'mit Zinseszins')], max_length=200),
        ),
    ]
