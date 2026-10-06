from django.db import migrations, models


def backfill_and_check(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Profile = apps.get_model('social', 'UserProfile')
    seen = set()
    for user in User.objects.all().iterator():
        email = user.email.strip().lower()
        if email and email in seen:
            raise RuntimeError('Duplicate legacy email addresses prevent canonical email uniqueness. Resolve duplicates explicitly before migrating; no user data was changed.')
        if email:
            seen.add(email)
    for user in User.objects.all().iterator():
        user.email = user.email.strip().lower()
        user.save(update_fields=['email'])
        name = f'{user.first_name} {user.last_name}'.strip() or user.username
        profile, _ = Profile.objects.get_or_create(user_id=user.pk, defaults={'display_name': name, 'legacy_access': True})
        if not profile.display_name:
            profile.display_name = name
            profile.save(update_fields=['display_name'])


class Migration(migrations.Migration):
    dependencies = [('social', '0004_userprofile_account_type_userprofile_display_name_and_more'), ('auth', '0012_alter_user_first_name_max_length')]
    operations = [
        migrations.AlterField(model_name='userprofile', name='legacy_access', field=models.BooleanField(default=False)),
        migrations.RunPython(backfill_and_check, migrations.RunPython.noop),
        # Keep auth.User's stable PK and all relationships. Empty legacy emails remain valid.
        migrations.RunSQL('CREATE UNIQUE INDEX belong_user_email_unique ON auth_user (LOWER(email)) WHERE email <> \'\'', 'DROP INDEX belong_user_email_unique'),
    ]
