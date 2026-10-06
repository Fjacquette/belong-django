from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class AccountMigrationTests(TransactionTestCase):
    def test_existing_users_keep_ids_relationships_and_real_or_empty_emails(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        previous = [('social', '0003_alter_userprofile_last_active_at')]
        executor.migrate(previous)
        try:
            apps = executor.loader.project_state(previous).apps
            User = apps.get_model('auth', 'User')
            Profile = apps.get_model('social', 'UserProfile')
            Friendship = apps.get_model('social', 'Friendship')
            a = User.objects.create(username='existing', first_name='Visible', last_name='Name', email='Existing@EXAMPLE.com')
            b = User.objects.create(username='demo-without-email', email='')
            orphan = User.objects.create(username='imported-without-profile', email='')
            Profile.objects.create(user_id=a.pk, status_text='Keep status')
            Profile.objects.create(user_id=b.pk)
            friendship = Friendship.objects.create(user_a_id=a.pk, user_b_id=b.pk)
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            apps = executor.loader.project_state(latest).apps
            User = apps.get_model('auth', 'User'); Profile = apps.get_model('social', 'UserProfile')
            self.assertEqual(User.objects.get(pk=a.pk).email, 'existing@example.com')
            self.assertEqual(User.objects.get(pk=b.pk).email, '')
            profile = Profile.objects.get(user_id=a.pk)
            self.assertEqual((profile.display_name, profile.status_text), ('Visible Name', 'Keep status'))
            self.assertTrue(profile.legacy_access)
            self.assertIsNone(profile.email_verified_at)
            self.assertEqual(Profile.objects.get(user_id=b.pk).display_name, 'demo-without-email')
            self.assertTrue(Profile.objects.get(user_id=orphan.pk).legacy_access)
            pair = apps.get_model('social', 'Friendship').objects.get(pk=friendship.pk)
            self.assertEqual((pair.user_a_id, pair.user_b_id), (a.pk, b.pk))
        finally:
            MigrationExecutor(connection).migrate(latest)

    def test_raw_invitation_sessions_are_scrubbed_to_nonsecret_reference(self):
        from datetime import timedelta
        import hashlib
        from django.contrib.sessions.backends.db import SessionStore
        from django.utils import timezone
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        previous = [('social', '0005_canonical_email'), ('groups', '0004_group_default_activity_image_group_image'), ('sessions', '0001_initial')]
        executor.migrate(previous)
        try:
            apps = executor.loader.project_state(previous).apps
            owner = apps.get_model('auth', 'User').objects.create(username='session-migration-owner')
            group = apps.get_model('groups', 'Group').objects.create(name='Keep invitation', owner_id=owner.pk)
            token = 'legacy-session-test-only-token'
            invitation = apps.get_model('groups', 'GroupInvitation').objects.create(group_id=group.pk, inviter_id=owner.pk, email='invited@example.com', token_digest=hashlib.sha256(token.encode()).hexdigest(), expires_at=timezone.now()+timedelta(hours=1))
            store = SessionStore()
            Session = apps.get_model('sessions', 'Session')
            Session.objects.create(session_key='a'*32, session_data=store.encode({'group_invitation': token, 'other_state': 'preserved'}), expire_date=timezone.now()+timedelta(days=1))
            Session.objects.create(session_key='b'*32, session_data=store.encode({'group_invitation': 'invalid-token'}), expire_date=timezone.now()+timedelta(days=1))
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            Session = executor.loader.project_state(latest).apps.get_model('sessions', 'Session')
            data = store.decode(Session.objects.get(pk='a'*32).session_data)
            self.assertEqual(data, {'pending_group_invitation': invitation.pk, 'other_state': 'preserved'})
            self.assertNotIn('group_invitation', store.decode(Session.objects.get(pk='b'*32).session_data))
        finally:
            MigrationExecutor(connection).migrate(latest)

    def test_email_controls_backfill_retained_deliveries_and_preserve_profiles(self):
        from datetime import timedelta
        import hashlib
        from django.utils import timezone
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        previous = [('social', '0008_seed_interests'), ('groups', '0005_group_interests')]
        executor.migrate(previous)
        try:
            apps = executor.loader.project_state(previous).apps
            user = apps.get_model('auth', 'User').objects.create(username='old-mail-owner', email='old-owner@example.com')
            apps.get_model('social', 'UserProfile').objects.create(user_id=user.pk, display_name='Keep identity', status_text='Keep state')
            group = apps.get_model('groups', 'Group').objects.create(name='Keep group', owner_id=user.pk)
            sent = timezone.now()
            apps.get_model('groups', 'GroupInvitation').objects.create(group_id=group.pk, inviter_id=user.pk, email='OLD-INVITEE@EXAMPLE.COM', token_digest='retained-digest', expires_at=sent+timedelta(days=7), status='revoked')
            apps.get_model('social', 'EmailVerification').objects.create(user_id=user.pk, email=user.email, token_digest='old-proof-digest', created_at=sent, expires_at=sent+timedelta(hours=24))
            executor = MigrationExecutor(connection); executor.migrate(latest)
            apps = executor.loader.project_state(latest).apps
            profile = apps.get_model('social', 'UserProfile').objects.get(user_id=user.pk)
            self.assertEqual((profile.display_name, profile.status_text, profile.outbound_mail_suspended), ('Keep identity', 'Keep state', False))
            Attempt = apps.get_model('social', 'OutboundEmailAttempt')
            invite = Attempt.objects.get(kind='invitation')
            self.assertEqual((invite.actor_id, invite.group_reference, invite.outcome, invite.created_at), (user.pk, group.pk, 'sent', sent))
            self.assertEqual(invite.recipient_hash, hashlib.sha256(b'old-invitee@example.com').hexdigest())
            self.assertEqual(Attempt.objects.get(kind='verification').created_at, sent)
            self.assertTrue(apps.get_model('social', 'EmailControlLock').objects.filter(pk=1).exists())
        finally:
            MigrationExecutor(connection).migrate(latest)
