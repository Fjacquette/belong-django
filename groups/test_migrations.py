from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class AccessMigrationTests(TransactionTestCase):
    def test_provisional_configurations_map_without_losing_group_context(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        previous = [('groups', '0001_initial')]
        executor.migrate(previous)
        try:
            apps = executor.loader.project_state(previous + [('activities', '0008_activity_group')]).apps
            Group = apps.get_model('groups', 'Group')
            Membership = apps.get_model('groups', 'GroupMembership')
            Activity = apps.get_model('activities', 'Activity')
            Response = apps.get_model('activities', 'ActivityResponse')
            User = apps.get_model('auth', 'User')
            user = User.objects.create(username='migration-owner')
            pending_user = User.objects.create(username='migration-pending')
            expected = {}
            for visibility in ['public', 'unlisted', 'private']:
                for policy in ['open', 'approval', 'invite']:
                    group = Group.objects.create(name=f'{visibility} {policy}', description='Keep context', owner_id=user.pk, visibility=visibility, join_policy=policy)
                    Membership.objects.create(group=group, user_id=user.pk, role='organizer', status='active')
                    Membership.objects.create(group=group, user_id=pending_user.pk, status='pending')
                    activity = Activity.objects.create(title=group.name, description='Keep opportunity', host_id=user.pk, group_id=group.pk)
                    Response.objects.create(activity=activity, user_id=pending_user.pk, status='interested')
                    mode = 'private' if visibility == 'private' else 'unlisted' if visibility == 'unlisted' else 'private' if policy == 'invite' else 'open' if policy == 'open' else 'closed'
                    expected[group.pk] = (group.name, mode)
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            apps = executor.loader.project_state(latest).apps
            Group = apps.get_model('groups', 'Group')
            Membership = apps.get_model('groups', 'GroupMembership')
            Activity = apps.get_model('activities', 'Activity')
            Response = apps.get_model('activities', 'ActivityResponse')
            for pk, (name, mode) in expected.items():
                group = Group.objects.get(pk=pk)
                self.assertEqual((group.name, group.description, group.owner_id, group.access), (name, 'Keep context', user.pk, mode))
                self.assertTrue(Membership.objects.filter(group_id=pk, user_id=user.pk, role='organizer', status='active').exists())
                self.assertTrue(Membership.objects.filter(group_id=pk, user_id=pending_user.pk, status='pending').exists())
                activity = Activity.objects.get(group_id=pk)
                self.assertEqual(activity.description, 'Keep opportunity')
                self.assertTrue(Response.objects.filter(activity=activity, user_id=pending_user.pk, status='interested').exists())
        finally:
            MigrationExecutor(connection).migrate(latest)
