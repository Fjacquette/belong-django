from django.db import migrations

DEMO_METADATA = {'Sailing on weekends!': ('free', '39.267,-76.798'),
 'Chill Overwatch 2': ('free', ''),
 'Hersheypark trip': ('paid', '40.288,-76.656'),
 'Need help moving': ('free', '40.121,-75.339'),
 'Co-ed softball league': ('paid', '40.130,-75.514'),
 'Greg is bored': ('unknown', '40.028,-75.174'),
 'Firefighter flashover training': ('paid', '39.962,-75.606'),
 'Wednesday night paddle': ('paid', '40.248,-75.649'),
 'Stroll the Street - Manayunk': ('free', '40.028,-75.225')}


def enrich_demo(apps, schema_editor):
    Activity = apps.get_model("activities", "Activity")
    Record = apps.get_model("activities", "DemoSeedRecord")
    for record in Record.objects.filter(content_type__app_label="activities", content_type__model="activity", key__startswith="activity:"):
        activity = Activity.objects.filter(pk=record.object_id).first()
        if activity is None or activity.title not in DEMO_METADATA:
            continue
        cost, gps = DEMO_METADATA[activity.title]
        changes = {}
        if activity.cost_type == "unknown":
            changes["cost_type"] = cost
        if not activity.location_gps and gps:
            changes["location_gps"] = gps
        if changes:
            Activity.objects.filter(pk=activity.pk).update(**changes)


class Migration(migrations.Migration):
    dependencies = [("activities", "0006_activity_cost_type_alter_activityresponse_status_and_more")]
    operations = [migrations.RunPython(enrich_demo, migrations.RunPython.noop)]
