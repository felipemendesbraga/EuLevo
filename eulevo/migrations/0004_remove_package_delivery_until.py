# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2017-01-19 12:20
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('eulevo', '0003_auto_20161214_1620'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='package',
            name='delivery_until',
        ),
    ]
