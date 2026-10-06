import hashlib

from django.contrib.sessions.backends.db import SessionStore
from django.db import migrations
from django.utils import timezone


def scrub_tokens(apps, schema_editor):
    Session = apps.get_model('sessions', 'Session')
    Invitation = apps.get_model('groups', 'GroupInvitation')
    store = SessionStore()
    for session in Session.objects.all().iterator():
        data = store.decode(session.session_data)
        if 'group_invitation' not in data:
            continue
        token = data.pop('group_invitation')
        if isinstance(token, str):
            invitation = Invitation.objects.filter(token_digest=hashlib.sha256(token.encode()).hexdigest(), status='pending', expires_at__gt=timezone.now()).first()
            if invitation:
                data['pending_group_invitation'] = invitation.pk
        session.session_data = store.encode(data)
        session.save(update_fields=['session_data'])


class Migration(migrations.Migration):
    dependencies = [('social', '0005_canonical_email'), ('groups', '0004_group_default_activity_image_group_image'), ('sessions', '0001_initial')]
    operations = [migrations.RunPython(scrub_tokens, migrations.RunPython.noop)]
