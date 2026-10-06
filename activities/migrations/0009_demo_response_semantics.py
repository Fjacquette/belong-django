from django.db import migrations


# Frozen fixture choices: soft interest for ongoing/planning opportunities;
# commitment for joining a game, helping, league enrollment or scheduled training.
DEMO_RESPONSES = {
    'activity:sailing-on-weekends': ('Jonas Grumby', ['interested', 'more']),
    'activity:chill-overwatch-2': ('Frank Jacquette', ['committed', 'question']),
    'activity:hersheypark-trip': ('Carol Brady', ['interested', 'vote', 'question']),
    'activity:need-help-moving': ('Greg Brady', ['committed', 'more']),
    'activity:co-ed-softball-league': ('Phoenixville Y', ['committed', 'declined']),
    'activity:greg-is-bored': ('Greg Brady', ['interested', 'vote']),
    'activity:firefighter-flashover-training': ('Chester County EMS', ['committed', 'question']),
    'activity:wednesday-night-paddle': ('Take It Outdoors Adventures', ['committed', 'question']),
    'activity:stroll-the-street-manayunk': ('Neighborhood Collective', ['interested', 'more']),
}


def update_demo_responses(apps, schema_editor):
    from django.utils.text import slugify
    Activity = apps.get_model('activities', 'Activity')
    Record = apps.get_model('activities', 'DemoSeedRecord')
    alias = schema_editor.connection.alias if schema_editor else 'default'
    records = Record.objects.using(alias)
    for key, (organizer, choices) in DEMO_RESPONSES.items():
        record = records.filter(key=key, content_type__app_label='activities', content_type__model='activity').first()
        owner = records.filter(key=f'user:{slugify(organizer)}', content_type__model='user').first()
        if not record or not owner:
            continue
        activity = Activity.objects.using(alias).filter(pk=record.object_id, host_id=owner.object_id).first()
        if not activity:
            continue
        # Refresh only the old generic defaults or the one former seeded pair.
        # Creator customizations and response records are deliberately untouched.
        if activity.available_responses in [[], ['interested', 'committed'], ['interested', 'committed', 'question']]:
            Activity.objects.using(alias).filter(pk=activity.pk).update(available_responses=choices)


class Migration(migrations.Migration):
    dependencies = [('activities', '0008_activity_group')]
    operations = [migrations.RunPython(update_demo_responses, migrations.RunPython.noop)]
