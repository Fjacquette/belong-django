from datetime import timedelta

from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from belong.test_helpers import create_legacy_user
from groups.models import Group, GroupMembership
from .models import (Activity, ActivityInvitation, ActivityResponse, Announcement,
                     ActivityNotificationDelivery, ActivityNotificationEvent)
from .notifications import queue_event, deliver_event
from .participation import locked_activity


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', BELONG_PUBLIC_ORIGIN='https://belong.example')
class ContextualActivityEmailTests(TestCase):
    def setUp(self):
        self.host = create_legacy_user('email-host', email='email-host@example.invalid')
        self.user = create_legacy_user('email-hiker', email='email-hiker@example.invalid')
        for user in [self.host, self.user]:
            user.profile.email_verified_at = timezone.now()
            user.profile.save(update_fields=['email_verified_at'])
        self.group = Group.objects.create(owner=self.host, name='Hikers', access='open')
        self.activity = Activity.objects.create(host=self.host, group=self.group, title='Creek hike',
            starts_at=timezone.now()+timedelta(days=2), cost_type='free', available_responses=['more', 'committed', 'question', 'declined'])
        self.url = reverse('activities:enable_activity_email', args=[self.activity.pk])
        self.next = '/?q=Creek&when=tomorrow&when=weekend&cost=free&page=2'
        self.client.force_login(self.user)

    def response(self, status='committed'):
        return ActivityResponse.objects.create(activity=self.activity, user=self.user, status=status, note='Keep this note')

    def enable(self, *, htmx=False, variant='detail', destination=None):
        return self.client.post(self.url, {'variant':variant, 'next': self.next if destination is None else destination},
            **({'HTTP_HX_REQUEST':'true'} if htmx else {}))

    def test_default_off_visit_and_invitation_alone_do_not_prompt_or_consent(self):
        self.assertFalse(self.user.profile.activity_email_enabled)
        ActivityInvitation.objects.create(activity=self.activity, user=self.user, invited_by=self.host)
        for url in [self.activity.get_absolute_url(), reverse('activities:index')]:
            self.assertNotContains(self.client.get(url), 'Turn on Activity emails')
        self.assertEqual(self.enable().status_code, 404)
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.activity_email_enabled)

    def test_eligible_saved_responses_including_historical_prompt_on_details_and_discover(self):
        for status in ['committed','more','question','interested','vote']:
            with self.subTest(status=status):
                self.response(status)
                for url in [self.activity.get_absolute_url(), reverse('activities:index')]:
                    page = self.client.get(url)
                    self.assertContains(page, 'Turn on Activity emails')
                    self.assertContains(page, 'for all Activities you participate in')
                ActivityResponse.objects.all().delete()
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.activity_email_enabled)

    def test_response_htmx_detail_and_card_and_nojs_show_prompt_without_automatic_consent(self):
        for variant, htmx in [('detail', True), ('card', True), ('detail', False), ('card', False)]:
            with self.subTest(variant=variant, htmx=htmx):
                ActivityResponse.objects.all().delete()
                result = self.client.post(reverse('activities:respond', args=[self.activity.pk]),
                    {'status':'committed','variant':variant,'next':self.activity.get_absolute_url() if variant=='detail' else '/?q=Creek'},
                    **({'HTTP_HX_REQUEST':'true'} if htmx else {}))
                if not htmx:
                    self.assertEqual(result.status_code,302)
                    result = self.client.get(result.url)
                self.assertContains(result, 'Turn on Activity emails')
                if htmx and variant=='card':
                    self.assertContains(result, 'id="activity-email-opt-in" aria-live="polite" hx-swap-oob="outerHTML"')
                self.user.profile.refresh_from_db()
                self.assertFalse(self.user.profile.activity_email_enabled)

    def test_decline_removal_cancellation_and_already_enabled_suppress_prompt(self):
        response = self.response('declined')
        for stage in ['declined','removed','cancelled','enabled']:
            with self.subTest(stage=stage):
                if stage=='removed':
                    response.delete()
                elif stage=='cancelled':
                    response=self.response()
                    self.activity.status='cancelled'; self.activity.save()
                elif stage=='enabled':
                    self.activity.status='active'; self.activity.save()
                    self.user.profile.activity_email_enabled=True; self.user.profile.save()
                self.assertNotContains(self.client.get(self.activity.get_absolute_url()), 'Turn on Activity emails')
                self.assertNotContains(self.client.get('/?q=Creek'), 'Turn on Activity emails')
                if stage!='enabled':
                    self.assertEqual(self.enable().status_code,404)

    def test_enable_idempotent_global_consent_no_other_side_effects(self):
        self.response()
        ActivityInvitation.objects.create(activity=self.activity,user=self.user,invited_by=self.host)
        snapshots = {model: list(model.objects.values()) for model in [Activity,ActivityResponse,ActivityInvitation,Group,GroupMembership]}
        for _ in range(2):
            self.assertRedirects(self.enable(), self.next, fetch_redirect_response=False)
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.activity_email_enabled)
        for model,before in snapshots.items():
            self.assertEqual(list(model.objects.values()), before)
        self.assertFalse(ActivityNotificationEvent.objects.exists())
        self.assertFalse(ActivityNotificationDelivery.objects.exists())
        self.assertEqual(len(mail.outbox),0)
        self.assertNotContains(self.client.get(self.activity.get_absolute_url()), 'Turn on Activity emails')

    def test_htmx_enable_replaces_detail_or_offer_without_navigation(self):
        self.response()
        result=self.enable(htmx=True)
        self.assertContains(result, 'id="participation-'+str(self.activity.pk)+'"')
        self.assertContains(result, 'You: Count me in')
        self.assertNotContains(result, 'Turn on Activity emails')
        self.assertContains(result, 'emails are on for Activities you participate in')
        result=self.enable(htmx=True,variant='card')
        self.assertContains(result, 'id="activity-email-opt-in"')
        self.assertNotIn('HX-Redirect', result)
        self.assertContains(result, 'emails are on for Activities you participate in')

    def test_csrf_post_only_authenticated_verified_and_valid_email(self):
        self.response()
        self.assertEqual(self.client.get(self.url).status_code,405)
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.user)
        self.assertEqual(csrf.post(self.url,{'variant':'detail'}).status_code,403)
        self.client.logout();self.assertEqual(self.enable().status_code,302)
        self.client.force_login(self.user)
        self.user.profile.email_verified_at=None;self.user.profile.save()
        self.assertNotContains(self.client.get(self.activity.get_absolute_url()), 'Turn on Activity emails')
        self.assertEqual(self.enable().status_code,404)
        self.user.profile.email_verified_at=timezone.now();self.user.profile.save()
        self.user.email='';self.user.save()
        self.assertEqual(self.enable().status_code,404)

    def test_visibility_and_safe_return(self):
        self.response()
        self.assertRedirects(self.enable(destination='https://evil.example/'), self.activity.get_absolute_url(), fetch_redirect_response=False)
        self.activity.audience='private';self.activity.save()
        self.assertEqual(self.enable().status_code,404)

    def test_account_settings_optout_suppresses_future_notice(self):
        self.response();self.enable()
        self.client.post(reverse('account_settings'), {'action':'notifications'})
        self.user.profile.refresh_from_db();self.assertFalse(self.user.profile.activity_email_enabled)
        with locked_activity(self.activity.pk) as activity:
            announcement=Announcement.objects.create(activity=activity,author=self.host,body='New trailhead')
            event=queue_event(activity,self.host,'update',announcement=announcement)
        deliver_event(event.pk)
        self.assertEqual(event.deliveries.get().reason,'recipient_opted_out')
        self.assertEqual(len(mail.outbox),0)

    def test_poll_votes_and_declines_do_not_prompt_but_confirmed_attendance_does(self):
        from .polls import create_poll, finalize_poll, submit_answers, confirmation_for
        from .participation import change_response
        from .participation_config import make_config
        self.activity=Activity.objects.create(host=self.host,title='Poll hike',cost_type='free',
            participation_config=make_config('planning',version=3))
        poll=create_poll(self.activity,[timezone.now()+timedelta(days=n) for n in [3,4,5]])
        submit_answers(self.activity.pk,self.user,{f'option_{o.pk}':'yes' for o in poll.options.all()})
        self.assertNotContains(self.client.get(self.activity.get_absolute_url()),'Turn on Activity emails')
        finalize_poll(self.activity.pk,self.host,poll.options.first().pk)
        self.activity.refresh_from_db()
        round=confirmation_for(self.activity)
        change_response(self.activity.pk,self.user,action='decline_attendance',confirmation_round=str(round.pk))
        self.assertNotContains(self.client.get(self.activity.get_absolute_url()),'Turn on Activity emails')
        change_response(self.activity.pk,self.user,action='confirm_attendance',confirmation_round=str(round.pk))
        self.assertContains(self.client.get(self.activity.get_absolute_url()),'Turn on Activity emails')

    def test_ongoing_pending_request_is_not_recipient_but_enrollment_is(self):
        from .enrollment import request_place, decide_request, withdraw_request
        from .models import OngoingOpportunity
        from .participation_config import make_config
        activity=Activity.objects.create(host=self.host,title='Weekly hikes',cost_type='free',
            participation_config=make_config('ongoing',version=4))
        opportunity=OngoingOpportunity.objects.create(activity=activity,capacity=2)
        request_place(activity.pk,self.user)
        self.assertNotContains(self.client.get(activity.get_absolute_url()),'Turn on Activity emails')
        application=opportunity.requests.get(user=self.user)
        decide_request(activity.pk,self.host,application.pk,'approved')
        self.assertContains(self.client.get(activity.get_absolute_url()),'Turn on Activity emails')
        withdraw_request(activity.pk,self.user,application.pk)
        self.assertNotContains(self.client.get(activity.get_absolute_url()),'Turn on Activity emails')

    def test_htmx_decline_and_removal_clear_card_offer(self):
        self.response()
        for route, data in [('respond', {'status':'declined'}), ('leave', {})]:
            result=self.client.post(reverse('activities:'+route,args=[self.activity.pk]),
                {**data,'variant':'card','next':self.next}, HTTP_HX_REQUEST='true')
            self.assertContains(result,'id="activity-email-opt-in" aria-live="polite" hidden hx-swap-oob="outerHTML"')
            self.assertNotContains(result,'Turn on Activity emails')

    def test_enabling_affects_future_events_but_never_expands_old_snapshot(self):
        self.response()
        def event(body):
            with locked_activity(self.activity.pk) as activity:
                announcement=Announcement.objects.create(activity=activity,author=self.host,body=body)
                return queue_event(activity,self.host,'update',announcement=announcement)
        old=event('Before consent')
        self.enable()
        deliver_event(old.pk)
        self.assertEqual(old.deliveries.get().status,'skipped')
        self.assertEqual(len(mail.outbox),0)
        new=event('After consent');deliver_event(new.pk)
        self.assertEqual(new.deliveries.get().status,'sent')
        self.assertEqual(len(mail.outbox),1)
