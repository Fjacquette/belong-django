"""Repair only tracked sample responses left at the former Interested default."""
from importlib import import_module

from django.db import migrations
from django.utils.text import slugify


def reconcile_demo_responses(apps, schema_editor):
    definitions = import_module('activities.migrations.0009_demo_response_semantics').DEMO_RESPONSES
    alias = schema_editor.connection.alias if schema_editor else 'default'
    Record = apps.get_model('activities', 'DemoSeedRecord')
    Activity = apps.get_model('activities', 'Activity')
    Response = apps.get_model('activities', 'ActivityResponse')
    User = apps.get_model('auth', 'User')
    records = Record.objects.using(alias)
    demo = records.filter(key='user:demo', content_type__app_label='auth', content_type__model='user').first()
    if not demo or not User.objects.using(alias).filter(pk=demo.object_id, username='belong_demo').exists():
        return
    for key, (organizer, choices) in definitions.items():
        if 'interested' in choices:
            continue
        activity_record = records.filter(key=key, content_type__app_label='activities', content_type__model='activity').first()
        owner = records.filter(key=f'user:{slugify(organizer)}', content_type__app_label='auth', content_type__model='user').first()
        response_record = records.filter(key=f"response:{key.split(':', 1)[1]}:demo", content_type__app_label='activities', content_type__model='activityresponse').first()
        if not activity_record or not owner or not response_record:
            continue
        activity = Activity.objects.using(alias).filter(pk=activity_record.object_id, host_id=owner.object_id).first()
        # Changed choices/ownership, other users, untracked rows and non-default
        # statuses are custom data. Only the known stale fixture state qualifies.
        if activity and activity.available_responses == choices:
            Response.objects.using(alias).filter(
                pk=response_record.object_id, activity_id=activity.pk,
                user_id=demo.object_id, status='interested',
            ).update(status=choices[0])


class Migration(migrations.Migration):
    dependencies = [('activities', '0009_demo_response_semantics')]
    operations = [migrations.RunPython(reconcile_demo_responses, migrations.RunPython.noop)]
