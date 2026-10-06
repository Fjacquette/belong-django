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
