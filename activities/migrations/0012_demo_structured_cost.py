"""Populate authored fixture amounts only; never parse user cost-display prose."""
from decimal import Decimal
from importlib import import_module

from django.db import migrations
from django.utils.text import slugify


AMOUNTS = {
    'sailing-on-weekends': ('free', 'Free (see details)', '0'),
    'chill-overwatch-2': ('free', '', '0'),
    'need-help-moving': ('free', '', '0'),
    'co-ed-softball-league': ('paid', '$60', '60'),
    'firefighter-flashover-training': ('paid', '$100', '100'),
    'wednesday-night-paddle': ('paid', '$10 (see details)', '10'),
    'stroll-the-street-manayunk': ('free', '', '0'),
}


def populate_demo_amounts(apps, schema_editor):
    definitions = import_module('activities.migrations.0009_demo_response_semantics').DEMO_RESPONSES
    Activity = apps.get_model('activities', 'Activity')
    Record = apps.get_model('activities', 'DemoSeedRecord')
    alias = schema_editor.connection.alias if schema_editor else 'default'
    records = Record.objects.using(alias)
    for slug, (kind, display, amount) in AMOUNTS.items():
        organizer = definitions[f'activity:{slug}'][0]
        record = records.filter(key=f'activity:{slug}', content_type__app_label='activities', content_type__model='activity').first()
        owner = records.filter(key=f'user:{slugify(organizer)}', content_type__app_label='auth', content_type__model='user').first()
        if record and owner:
            Activity.objects.using(alias).filter(pk=record.object_id, host_id=owner.object_id,
                cost_type=kind, cost_display=display, cost_amount__isnull=True).update(cost_amount=Decimal(amount))


class Migration(migrations.Migration):
    dependencies = [('activities', '0011_structured_cost')]
    operations = [migrations.RunPython(populate_demo_amounts, migrations.RunPython.noop)]
