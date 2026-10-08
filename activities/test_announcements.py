from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from belong.test_helpers import create_legacy_user
from groups.models import Group, GroupMembership
from .models import Activity, ActivityResponse, ActivitySeries, Announcement


class AnnouncementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.host = create_legacy_user('update-host')
        cls.member = create_legacy_user('update-member')
        cls.co = create_legacy_user('update-co')
        cls.outsider = create_legacy_user('update-outsider')
        cls.declined = create_legacy_user('update-declined')
        cls.pending = create_legacy_user('update-pending')
        cls.blocked = create_legacy_user('update-blocked')
        cls.group = Group.objects.create(owner=cls.host, name='Hikers', access='closed')
        for user, status, role in [(cls.member, 'active', 'member'), (cls.co, 'active', 'organizer'),
                                   (cls.pending, 'pending', 'member'), (cls.blocked, 'blocked', 'member')]:
            GroupMembership.objects.create(group=cls.group, user=user, status=status, role=role)
        cls.series = ActivitySeries.objects.create(owner=cls.host, group=cls.group, title='Hikes', description='Together')
        cls.activity = Activity.objects.create(host=cls.host, group=cls.group, series=cls.series,
                                              title='Saturday', description='Hike', available_responses=['committed','interested','question'])
        cls.sibling = Activity.objects.create(host=cls.host, group=cls.group, series=cls.series, title='Sunday', description='Hike')
        ActivityResponse.objects.create(activity=cls.activity, user=cls.member, status='committed', note='History')
        ActivityResponse.objects.create(activity=cls.activity, user=cls.outsider, status='question')
        ActivityResponse.objects.create(activity=cls.activity, user=cls.declined, status='declined')

    def post(self, context, user, body='Weather update'):
        self.client.force_login(user)
        scope = 'groups' if isinstance(context, Group) else 'activities'
        url = reverse(scope+':announce', args=[context.pk])
        token = self.client.get(url).context['form'].initial.get('submission_token', '') if context.can_organize(user) else ''
        return self.client.post(url, {'body': body, 'submission_token': token})

    def page(self, context, user):
        self.client.force_login(user)
        scope = 'groups' if isinstance(context, Group) else 'activities'
        return self.client.get(reverse(scope+':detail', args=[context.pk]))

    def test_organizer_authorization_for_both_scopes(self):
        for context in [self.activity, self.group]:
            scope = 'groups' if context == self.group else 'activities'
            url = reverse(scope+':announce', args=[context.pk])
            for user in [self.member, self.outsider, self.pending, self.blocked]:
                self.client.force_login(user)
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.post(context, user).status_code, 404)
            for user in [self.host, self.co]:
                self.assertEqual(self.post(context, user).status_code, 302)
        self.assertEqual(Announcement.objects.count(), 4)

    def test_no_staff_override_or_unrelated_group_privilege(self):
        self.outsider.is_staff = True; self.outsider.save()
        self.activity.group = None; self.activity.series = None; self.activity.save()
        for user in [self.co, self.outsider]:
            self.assertEqual(self.post(self.activity, user).status_code, 404)
        self.assertEqual(self.post(self.activity, self.host).status_code, 302)

    def test_occurrence_audience_includes_proto_intent_without_group_gate(self):
        self.post(self.activity, self.co)
        update = Announcement.objects.get()
        self.assertEqual(set(update.recipients.values_list('pk', flat=True)), {self.member.pk, self.outsider.pk})
        for user in [self.member, self.outsider, self.host, self.co]:
            self.assertContains(self.page(self.activity, user), 'Weather update')
        for user in [self.declined, self.pending, self.blocked]:
            self.assertNotContains(self.page(self.activity, user), 'Weather update')
        self.assertNotContains(self.page(self.sibling, self.member), 'Weather update')
        self.assertNotContains(self.page(self.group, self.member), 'Weather update')
        self.assertNotContains(self.page(self.activity, self.outsider), 'Post an update')

    def test_group_audience_is_active_members_plus_owner(self):
        self.post(self.group, self.host)
        update = Announcement.objects.get()
        self.assertEqual(set(update.recipients.values_list('pk', flat=True)), {self.host.pk,self.member.pk,self.co.pk})
        for user in [self.host, self.member, self.co]:
            self.assertContains(self.page(self.group, user), 'Weather update')
        for user in [self.outsider, self.pending, self.blocked]:
            self.assertNotContains(self.page(self.group, user), 'Weather update')
        self.assertNotContains(self.page(self.activity, self.member), 'Weather update')

    def test_delivery_snapshot_does_not_add_later_members_or_responders(self):
        self.post(self.group, self.host, 'Earlier group update')
        self.post(self.activity, self.host, 'Earlier hike update')
        GroupMembership.objects.create(group=self.group, user=self.declined)
        ActivityResponse.objects.filter(user=self.declined).update(status='interested')
        self.assertNotContains(self.page(self.group, self.declined), 'Earlier group update')
        self.assertNotContains(self.page(self.activity, self.declined), 'Earlier hike update')
        self.post(self.group, self.host, 'New group update')
        self.post(self.activity, self.host, 'New hike update')
        self.assertContains(self.page(self.group, self.declined), 'New group update')
        self.assertContains(self.page(self.activity, self.declined), 'New hike update')

    def test_response_removal_decline_and_membership_revocation_hide_updates(self):
        self.post(self.activity, self.host)
        self.post(self.group, self.host)
        ActivityResponse.objects.filter(user=self.member).update(status='declined')
        self.assertNotContains(self.page(self.activity, self.member), 'Weather update')
        ActivityResponse.objects.filter(user=self.outsider).delete()
        self.assertNotContains(self.page(self.activity, self.outsider), 'Weather update')
        GroupMembership.objects.filter(user=self.member).update(status='blocked')
        self.assertNotContains(self.page(self.group, self.member), 'Weather update')
        GroupMembership.objects.filter(user=self.member).delete()
        self.assertNotContains(self.page(self.group, self.member), 'Weather update')
        self.assertEqual(Announcement.objects.count(), 2)

    def test_visibility_revocation_overrides_stored_recipient(self):
        self.post(self.activity, self.host)
        self.activity.audience = 'friends'; self.activity.save()
        self.assertEqual(self.page(self.activity, self.outsider).status_code, 404)
        self.group.access = 'private'; self.group.save()
        self.assertEqual(self.page(self.group, self.outsider).status_code, 404)
        self.assertContains(self.page(self.activity, self.host), 'Weather update')
        # Organizer management works when participant visibility excludes the co-organizer.
        self.client.force_login(self.co)
        self.assertContains(self.client.get(reverse('activities:roster', args=[self.activity.pk])), 'Weather update')

    def test_cancelled_updates_preserve_all_participation_and_other_context(self):
        self.activity.status='cancelled'; self.activity.save()
        before = list(ActivityResponse.objects.values())
        sibling = Activity.objects.values().get(pk=self.sibling.pk)
        group = Group.objects.values().get(pk=self.group.pk)
        series = ActivitySeries.objects.values().get(pk=self.series.pk)
        self.assertEqual(self.post(self.activity, self.host, 'After cancellation').status_code, 302)
        self.assertContains(self.page(self.activity, self.member), 'After cancellation')
        self.assertEqual(list(ActivityResponse.objects.values()), before)
        self.assertEqual(Activity.objects.values().get(pk=self.sibling.pk), sibling)
        self.assertEqual(Group.objects.values().get(pk=self.group.pk), group)
        self.assertEqual(ActivitySeries.objects.values().get(pk=self.series.pk), series)

    def test_context_constraint_rejects_neither_or_both(self):
        for kwargs in [{}, {'activity':self.activity,'group':self.group}]:
            update = Announcement(author=self.host, body='Invalid', **kwargs)
            with self.assertRaises(ValidationError):
                update.clean()
            with self.assertRaises(IntegrityError), transaction.atomic():
                update.save()

    def test_form_is_bounded_plain_text_and_ignores_crafted_fields(self):
        for body in ['', '   ', 'x'*2001]:
            self.assertEqual(self.post(self.activity, self.host, body).status_code, 200)
        self.assertFalse(Announcement.objects.exists())
        self.client.force_login(self.host)
        self.client.post(reverse('activities:announce', args=[self.activity.pk]), {
            'submission_token': self.client.get(reverse('activities:announce', args=[self.activity.pk])).context['form'].initial['submission_token'],
            'body':'<script>alert(1)</script>\nWeather update', 'group':self.group.pk, 'author':self.outsider.pk,
            'recipients':[self.blocked.pk]})
        update = Announcement.objects.get()
        self.assertEqual(update.author, self.host)
        self.assertIsNone(update.group_id)
        self.assertNotIn(self.blocked, update.recipients.all())
        page = self.page(self.activity, self.member)
        self.assertContains(page, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(page, '<script>alert(1)</script>')

    def test_post_csrf_login_and_compose_get_does_not_mutate(self):
        for scope, context in [('activities',self.activity),('groups',self.group)]:
            url=reverse(scope+':announce', args=[context.pk])
            self.client.logout()
            self.assertEqual(self.client.post(url,{'body':'Anonymous'}).status_code,302)
            secure=Client(enforce_csrf_checks=True); secure.force_login(self.host)
            self.assertEqual(secure.post(url,{'body':'No CSRF'}).status_code,403)
            self.client.force_login(self.host)
            self.assertContains(self.client.get(url), 'Post update')
            self.assertNotContains(self.client.get(url), 'aria-label="Create"')
            self.assertEqual(self.client.delete(url).status_code,405)
        self.assertFalse(Announcement.objects.exists())

    def test_demoted_organizer_loses_posting_and_read_management_access(self):
        self.post(self.group, self.host)
        self.post(self.activity, self.host)
        GroupMembership.objects.filter(user=self.co).update(role='member')
        self.assertEqual(self.post(self.activity, self.co).status_code,404)
        self.assertEqual(self.post(self.group, self.co).status_code,404)
        self.assertNotContains(self.page(self.activity, self.co),'Weather update')
        self.assertContains(self.page(self.group, self.co),'Weather update')

    def test_updates_are_paginated_in_context(self):
        self.client.force_login(self.host)
        for n in range(21):
            Announcement.objects.create(activity=self.activity,author=self.host,body=f'Update number {n}')
        page = self.page(self.activity,self.host)
        self.assertEqual(len(page.context['announcements']),20)
        self.assertContains(page, 'Older updates')
        second=self.client.get(reverse('activities:detail',args=[self.activity.pk]),{'updates_page':2})
        self.assertEqual(len(second.context['announcements']),1)
        self.assertContains(second,'Update number 0')
