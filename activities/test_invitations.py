from django.test import TestCase, Client
from html import escape
from django.urls import reverse
from belong.test_helpers import create_legacy_user
from groups.models import Group, GroupMembership
from social.models import Friendship
from .models import Activity, ActivityResponse, ActivityInvitation, ActivitySeries
from .forms import ActivityForm, ActivitySeriesForm
from .series import occurrence_initial


class ActivityInvitationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.host = create_legacy_user('invite-host')
        cls.viewer = create_legacy_user('invite-viewer')
        cls.other = create_legacy_user('invite-other')
        cls.co = create_legacy_user('invite-co')
        cls.group = Group.objects.create(owner=cls.host, name='Hikers')
        GroupMembership.objects.create(group=cls.group,user=cls.viewer)
        GroupMembership.objects.create(group=cls.group,user=cls.co,role='organizer')
        Friendship.make_pair(cls.host,cls.other)
        cls.activity = Activity.objects.create(host=cls.host,group=cls.group,title='Hike',description='Together',available_responses=['question','interested'])

    def setUp(self):
        self.client.force_login(self.viewer)

    def invite(self, user=None):
        return ActivityInvitation.objects.create(activity=self.activity,user=user or self.viewer,invited_by=self.host)

    def post(self, status, **extra):
        return self.client.post(reverse('activities:respond',args=[self.activity.pk]), {'status':status,'variant':'card',**extra}, HTTP_HX_REQUEST='true')

    def manage(self, **data):
        self.client.force_login(self.host)
        return self.client.post(reverse('activities:manage_invitations',args=[self.activity.pk]),data)

    def card(self):
        return self.client.get(reverse('activities:index'))

    def test_same_activity_has_one_discovery_link_or_two_invited_answers(self):
        ordinary=self.card()
        self.assertContains(ordinary,'See details / RSVP')
        self.assertNotContains(ordinary,'name="status"')
        self.assertFalse(ActivityResponse.objects.exists())
        self.invite()
        invited=self.card()
        self.assertContains(invited,escape("I'm coming"))
        self.assertContains(invited,escape("Can't make it"))
        self.assertNotContains(invited,'See details / RSVP')
        self.assertContains(invited,'name="status"',count=2)
        self.assertNotContains(invited,'card-response__optional')
        self.assertNotContains(invited,'ui-response--confirmed')

    def test_group_link_needs_explicit_flag_and_current_active_membership(self):
        self.assertContains(self.card(),'See details / RSVP')
        self.activity.invite_group_members=True;self.activity.save()
        self.assertContains(self.card(),escape("I'm coming"))
        ActivityResponse.objects.create(activity=self.activity,user=self.viewer,status='committed',note='History')
        before=ActivityResponse.objects.values().get(user=self.viewer)
        for status in ['pending','blocked']:
            GroupMembership.objects.filter(user=self.viewer).update(status=status)
            self.assertContains(self.card(),'See details / RSVP')
            self.assertContains(self.card(),'You: Count me in')
        GroupMembership.objects.filter(user=self.viewer).delete()
        self.assertContains(self.card(),'See details / RSVP')
        self.assertEqual(ActivityResponse.objects.values().get(user=self.viewer),before)

    def test_direct_invitation_survives_group_loss_but_removal_keeps_response(self):
        invitation=self.invite()
        self.post('declined')
        before=ActivityResponse.objects.values().get(user=self.viewer)
        GroupMembership.objects.filter(user=self.viewer).delete()
        self.assertContains(self.card(),escape("Can't make it"))
        invitation.delete()
        self.assertContains(self.card(),'See details / RSVP')
        self.assertContains(self.card(),'You: Cannot make it')
        self.assertEqual(ActivityResponse.objects.values().get(user=self.viewer),before)

    def test_invitation_does_not_override_visibility_or_legacy_boolean(self):
        self.activity.is_personal_invitation=True;self.activity.save()
        self.assertContains(self.card(),'See details / RSVP')
        self.invite()
        self.activity.audience='friends';self.activity.save()
        self.assertNotContains(self.card(),self.activity.title)
        self.assertEqual(self.client.get(reverse('activities:detail',args=[self.activity.pk])).status_code,404)
        self.assertEqual(self.post('committed').status_code,404)
        self.assertFalse(ActivityResponse.objects.exists())

    def test_invitation_does_not_gate_ordinary_creator_responses(self):
        self.post('interested')
        self.assertEqual(ActivityResponse.objects.get(user=self.viewer).status,'interested')
        self.assertContains(self.card(),'You: Interested')
        self.post('committed')
        self.assertEqual(ActivityResponse.objects.get(user=self.viewer).status,'interested')

    def test_invited_answers_extend_vocabulary_and_details_match(self):
        self.invite()
        for status,label in [('committed',escape("I'm coming")),('declined',escape("Can't make it"))]:
            result=self.post(status)
            self.assertEqual(ActivityResponse.objects.get(user=self.viewer).status,status)
            self.assertContains(result,f'value="{status}" aria-pressed="true"')
            self.assertNotContains(result,'ui-response--confirmed')
            detail=self.client.get(reverse('activities:detail',args=[self.activity.pk]))
            self.assertContains(detail,'You’re invited')
            self.assertContains(detail,f'You: {label}')
            self.assertContains(detail,'I have a question')
            self.assertContains(detail,'Interested')
        self.post('declined')
        self.assertFalse(ActivityResponse.objects.exists())

    def test_selected_invited_rsvp_is_not_repeated_in_card_body(self):
        self.invite()
        for status in ['committed', 'declined']:
            with self.subTest(status=status):
                fragment = self.post(status)
                for result in [fragment, self.card()]:
                    self.assertContains(result, f'value="{status}" aria-pressed="true"')
                    self.assertNotContains(result, 'card-current-response')

    def test_card_body_keeps_responses_without_a_selected_direct_choice(self):
        invitation = self.invite()
        for invited in [True, False]:
            if not invited:
                invitation.delete()
            for status, label in [('interested', 'Interested'), ('question', 'I have a question'),
                                  ('committed', 'Count me in'), ('declined', 'Cannot make it')]:
                if invited and status in ['committed', 'declined']:
                    continue
                with self.subTest(invited=invited, status=status):
                    ActivityResponse.objects.update_or_create(
                        activity=self.activity, user=self.viewer, defaults={'status': status})
                    card = self.card()
                    self.assertContains(card, 'card-current-response', count=1)
                    self.assertContains(card, f'aria-label="You: {label}"')
                    self.assertContains(card, f'>You: {label}</p>')

    def test_cancelled_invited_rsvp_remains_visible_in_card_body(self):
        self.invite()
        self.activity.status = 'cancelled'
        self.activity.save()
        for status, label in [('committed', 'Count me in'), ('declined', 'Cannot make it')]:
            with self.subTest(status=status):
                ActivityResponse.objects.update_or_create(
                    activity=self.activity, user=self.viewer, defaults={'status': status})
                card = self.card()
                self.assertContains(card, 'Cancelled')
                self.assertNotContains(card, 'name="status"')
                self.assertContains(card, f'>You: {label}</p>')

    def test_full_capacity_rejects_invited_commitment_retaining_previous_response(self):
        self.invite();self.activity.capacity=1;self.activity.save()
        ActivityResponse.objects.create(activity=self.activity,user=self.other,status='committed')
        ActivityResponse.objects.create(activity=self.activity,user=self.viewer,status='interested',note='Keep')
        before=ActivityResponse.objects.values().get(user=self.viewer)
        self.post('committed')
        self.assertEqual(ActivityResponse.objects.values().get(user=self.viewer),before)
        self.post('declined')
        self.assertEqual(ActivityResponse.objects.get(user=self.viewer).status,'declined')
        self.client.post(reverse('activities:join',args=[self.activity.pk]))
        self.assertEqual(ActivityResponse.objects.get(user=self.viewer).status,'declined')
        ActivityResponse.objects.filter(user=self.other).delete()
        self.post('committed')
        self.assertEqual(ActivityResponse.objects.get(user=self.viewer).status,'committed')
        self.post('committed')
        self.assertFalse(ActivityResponse.objects.filter(user=self.viewer).exists())

    def test_cancelled_invitation_freezes_history(self):
        self.invite();self.post('committed')
        before=list(ActivityResponse.objects.values())
        self.activity.status='cancelled';self.activity.save()
        self.assertContains(self.card(),'Cancelled')
        self.assertNotContains(self.card(),'name="status"')
        for status in ['declined','committed']:
            self.post(status)
        self.client.post(reverse('activities:leave',args=[self.activity.pk]))
        self.assertEqual(list(ActivityResponse.objects.values()),before)

    def test_management_relationship_choices_authority_and_history(self):
        url=reverse('activities:manage_invitations',args=[self.activity.pk])
        self.assertEqual(self.client.post(url,{'action':'group','invite_group_members':'on'}).status_code,404)
        self.assertEqual(self.manage(action='add',invitee=self.other.pk).status_code,302)
        self.assertEqual(self.manage(action='add',invitee=self.other.pk).status_code,302)
        self.assertEqual(ActivityInvitation.objects.count(),1)
        outsider=create_legacy_user('not-related')
        self.assertEqual(self.manage(action='add',invitee=outsider.pk).status_code,200)
        self.assertFalse(ActivityInvitation.objects.filter(user=outsider).exists())
        self.assertEqual(self.manage(action='group',invite_group_members='on').status_code,302)
        self.activity.refresh_from_db();self.assertTrue(self.activity.invite_group_members)
        self.client.force_login(self.co)
        self.assertEqual(self.client.post(url,{'action':'add','invitee':self.viewer.pk}).status_code,302)
        response=ActivityResponse.objects.create(activity=self.activity,user=self.other,status='interested')
        invitation=ActivityInvitation.objects.get(user=self.other)
        self.manage(action='remove',invitation=invitation.pk)
        self.assertTrue(ActivityResponse.objects.filter(pk=response.pk).exists())
        self.assertEqual(self.manage(action='remove',invitation='bogus').status_code,404)

    def test_management_post_csrf_and_scoped_removal(self):
        self.client.force_login(self.host)
        url=reverse('activities:manage_invitations',args=[self.activity.pk])
        self.assertEqual(self.client.get(url).status_code,405)
        secure=Client(enforce_csrf_checks=True);secure.force_login(self.host)
        self.assertEqual(secure.post(url,{'action':'add','invitee':self.other.pk}).status_code,403)
        other=Activity.objects.create(host=self.host,title='Other',description='Other')
        invitation=ActivityInvitation.objects.create(activity=other,user=self.other,invited_by=self.host)
        self.assertEqual(self.manage(action='remove',invitation=invitation.pk).status_code,404)
        self.assertTrue(ActivityInvitation.objects.filter(pk=invitation.pk).exists())

    def test_group_creation_and_series_copy_keep_explicit_choice(self):
        self.assertTrue(ActivityForm(user=self.host,context_group=self.group)['invite_group_members'].value())
        self.assertFalse(ActivityForm(user=self.host)['invite_group_members'].value())
        self.assertTrue(ActivitySeriesForm(user=self.host,context_group=self.group)['invite_group_members'].value())
        for enabled in [True,False]:
            series=ActivitySeries.objects.create(owner=self.host,group=self.group,title='Weekly',description='Together',invite_group_members=enabled)
            initial=occurrence_initial(series)
            form=ActivityForm(user=self.host,context_group=self.group,context_series=series,initial=initial)
            self.assertEqual(form['invite_group_members'].value(),enabled)
            data={'title':'Next','description':'Together','audience':'everyone','location_type':'tbd','cost_type':'unknown'}
            if enabled:data['invite_group_members']='on'
            form=ActivityForm(data,user=self.host,context_group=self.group,context_series=series,initial=initial)
            self.assertTrue(form.is_valid(),form.errors)
            obj=form.save(commit=False);obj.host=self.host;obj.save()
            self.assertEqual(obj.invite_group_members,enabled)
            self.assertEqual(obj.active_responses(),['interested'])
        invalid=ActivityForm({**data,'invite_group_members':'on'},user=self.host)
        self.assertFalse(invalid.is_valid())

    def test_ordinary_default_and_historical_interested_remain_valid(self):
        activity=Activity.objects.create(host=self.host,title='Default',description='Together')
        self.assertEqual(activity.active_responses(),['interested'])
        self.assertEqual(ActivityForm(user=self.host)['available_responses'].value(),['interested'])
        self.assertEqual(ActivitySeriesForm(user=self.host)['available_responses'].value(),['interested'])
        response=ActivityResponse.objects.create(activity=activity,user=self.viewer,status='interested')
        self.client.get(reverse('activities:detail',args=[activity.pk]))
        response.refresh_from_db();self.assertEqual(response.status,'interested')

    def test_invitation_discovery_query_count_is_bounded(self):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection
        for n in range(6):
            a=Activity.objects.create(host=self.host,group=self.group,title=f'Another {n}',description='Together',invite_group_members=True)
            ActivityInvitation.objects.create(activity=a,user=self.viewer,invited_by=self.host)
        with CaptureQueriesContext(connection) as queries:
            self.card()
        invitation_selects=[q['sql'] for q in queries if 'activities_activityinvitation' in q['sql']]
        self.assertEqual(len(invitation_selects),1)
