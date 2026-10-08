from django.contrib.admin.sites import AdminSite
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.urls import reverse

from belong.test_helpers import create_legacy_user
from .admin import ActivityResponseAdmin
from .forms import ActivityForm, ActivitySeriesForm
from .models import Activity, ActivityInvitation, ActivityResponse, ActivitySeries
from .series import occurrence_initial


class ResponseFooterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.host = create_legacy_user('footer-host')
        cls.user = create_legacy_user('footer-user')
        cls.activity = Activity.objects.create(host=cls.host, title='A shared activity',
            description='A full description belongs here.', available_responses=['more', 'question', 'committed', 'vote', 'declined'])

    def setUp(self):
        self.client.force_login(self.user)

    def card(self):
        return self.client.get('/?q=shared&audience=everyone&audience=friends')

    def post(self, status, *, variant='card', htmx=True):
        headers = {'HTTP_HX_REQUEST': 'true'} if htmx else {}
        return self.client.post(reverse('activities:respond', args=[self.activity.pk]),
            {'status': status, 'variant': variant, 'next': '/?q=shared&audience=everyone&audience=friends'}, **headers)

    def bands(self, response):
        html = response.content.decode()
        band4 = html.split('activity-card__band-4', 1)[1].split('activity-card__band-5', 1)[0]
        band5 = html.split('activity-card__band-5', 1)[1].split('</section>', 1)[0]
        self.assertIn(self.activity.description, band4)
        self.assertNotIn('card-current-response', html)
        self.assertNotIn('You:', band4)
        self.assertNotIn('Saved response:', band4)
        return band5

    def test_same_ordinary_card_before_and_after_response_navigation_never_mutates(self):
        self.assertIn('See details / RSVP', self.bands(self.card()))
        result = self.post('committed')
        self.assertIn('Going / Edit response', self.bands(result))
        before = ActivityResponse.objects.values().get(user=self.user)
        self.assertIn('Going / Edit response', self.bands(self.card()))
        self.assertContains(self.client.get(self.activity.get_absolute_url()), 'aria-pressed="true"')
        self.assertEqual(ActivityResponse.objects.values().get(user=self.user), before)

    def test_all_ordinary_saved_statuses_have_accurate_footer_and_full_accessible_state(self):
        for status, concise, full in [('committed', 'Going', 'Count me in'), ('declined', "Can't make it", 'Cannot make it'),
                ('question', 'Have a question', 'I have a question'), ('more', 'Tell me more', 'Tell me more'),
                ('vote', 'Vote on details', 'Vote on details'), ('interested', 'Past response', 'Interested (historical)')]:
            with self.subTest(status=status):
                ActivityResponse.objects.update_or_create(activity=self.activity, user=self.user, defaults={'status': status})
                before = ActivityResponse.objects.values().get(user=self.user)
                response = self.card()
                footer = self.bands(response)
                from html import escape
                self.assertIn(escape(concise)+' / Edit response', footer)
                self.assertIn('Saved response: '+full, footer)
                self.assertNotIn('See details / RSVP', footer)
                self.assertNotIn('name="status"', footer)
                self.assertEqual(ActivityResponse.objects.values().get(user=self.user), before)

    def test_invited_unmatched_state_has_footer_disclosure_both_rsvps_and_details(self):
        ActivityInvitation.objects.create(activity=self.activity, user=self.user, invited_by=self.host)
        for status in ['question', 'more', 'vote', 'interested']:
            with self.subTest(status=status):
                ActivityResponse.objects.update_or_create(activity=self.activity, user=self.user, defaults={'status': status})
                footer = self.bands(self.card())
                self.assertIn('card-response-menu', footer)
                self.assertIn('Saved response:', footer)
                self.assertIn('value="committed" aria-pressed="false"', footer)
                self.assertIn('value="declined" aria-pressed="false"', footer)
                self.assertIn('Edit response in Details', footer)
                changed = self.post('committed')
                self.assertNotIn('card-response-menu', self.bands(changed))
                self.assertContains(changed, 'value="committed" aria-pressed="true"')

    def test_invited_unmatched_disclosure_honors_full_capacity(self):
        ActivityInvitation.objects.create(activity=self.activity, user=self.user, invited_by=self.host)
        ActivityResponse.objects.create(activity=self.activity, user=self.host, status='committed')
        saved = ActivityResponse.objects.create(activity=self.activity, user=self.user, status='vote', note='Keep')
        self.activity.capacity = 1; self.activity.save()
        self.assertContains(self.card(), 'aria-label="I&#x27;m coming · Full"')
        self.post('committed'); saved.refresh_from_db()
        self.assertEqual((saved.status, saved.note), ('vote', 'Keep'))
        self.post('declined'); saved.refresh_from_db(); self.assertEqual(saved.status, 'declined')

    def test_cancelled_footer_links_to_saved_state_and_preserves_history(self):
        ActivityResponse.objects.create(activity=self.activity, user=self.user, status='interested', note='History')
        self.activity.status = 'cancelled'; self.activity.save()
        before = ActivityResponse.objects.values().get(user=self.user)
        footer = self.bands(self.card())
        self.assertIn('>Cancelled</a>', footer)
        self.assertIn('Saved response: Interested (historical)', footer)
        self.assertNotIn('name="status"', footer)
        self.assertContains(self.client.get(self.activity.get_absolute_url()), 'You: Interested (historical)')
        self.post('committed')
        self.client.post(reverse('activities:leave', args=[self.activity.pk]))
        self.assertEqual(ActivityResponse.objects.values().get(user=self.user), before)

    def test_details_preserves_current_creator_order_and_only_invitees_extend_it(self):
        self.activity.available_responses = ['vote', 'interested', 'question', 'more']; self.activity.save()
        ActivityResponse.objects.create(activity=self.activity, user=self.user, status='question')
        page = self.client.get(self.activity.get_absolute_url())
        self.assertEqual([option['value'] for option in page.context['join_context']['response_options']], ['vote', 'question', 'more'])
        self.assertContains(page, 'value="question" aria-pressed="true"')
        self.assertNotContains(page, 'value="interested"')
        self.assertNotContains(page, 'See details')
        self.assertNotContains(page, 'value="committed"')
        ActivityInvitation.objects.create(activity=self.activity, user=self.user, invited_by=self.host)
        page = self.client.get(self.activity.get_absolute_url())
        self.assertEqual([option['value'] for option in page.context['join_context']['response_options']],
                         ['committed', 'declined', 'vote', 'question', 'more'])

    def test_retired_response_rejected_without_creating_or_changing_history(self):
        self.activity.available_responses = ['interested', 'question']; self.activity.save()
        self.post('interested'); self.assertFalse(ActivityResponse.objects.exists())
        saved = ActivityResponse.objects.create(activity=self.activity, user=self.user, status='interested', note='Keep history')
        before = ActivityResponse.objects.values().get(pk=saved.pk)
        self.post('interested')
        self.assertEqual(ActivityResponse.objects.values().get(pk=saved.pk), before)
        self.assertIn('Past response / Edit response', self.bands(self.card()))
        self.post('question', variant='detail'); saved.refresh_from_db(); self.assertEqual(saved.status, 'question')
        self.client.post(reverse('activities:leave', args=[self.activity.pk]))
        self.assertFalse(ActivityResponse.objects.filter(pk=saved.pk).exists())

    def test_legacy_only_configuration_has_no_current_choice_or_implicit_commitment(self):
        self.activity.available_responses = ['interested']; self.activity.save()
        self.assertEqual(self.activity.active_responses(), [])
        page = self.client.get(self.activity.get_absolute_url())
        self.assertContains(page, 'No response choices available')
        self.client.post(reverse('activities:join', args=[self.activity.pk]))
        self.assertFalse(ActivityResponse.objects.exists())
        self.activity.refresh_from_db(); self.assertEqual(self.activity.available_responses, ['interested'])

    def test_activity_series_and_model_defaults_never_select_interested(self):
        for cls in [ActivityForm, ActivitySeriesForm]:
            form = cls(user=self.host)
            self.assertEqual(form['available_responses'].value(), ['more'])
            self.assertNotIn('interested', dict(form.fields['available_responses'].choices))
            form = cls({'title': 'A new activity', 'description': 'Together', 'cost_type': 'unknown',
                        'audience': 'everyone', 'location_type': 'tbd', 'available_responses': ['interested']}, user=self.host)
            self.assertFalse(form.is_valid()); self.assertIn('available_responses', form.errors)
        activity = Activity.objects.create(host=self.host, title='New default')
        self.assertEqual(activity.active_responses(), ['more'])
        self.assertEqual(ActivityResponse.objects.create(activity=activity, user=self.user).status, 'more')

    def test_legacy_series_occurrence_copies_current_choices_without_rewriting_series(self):
        for old, expected in [(['interested'], ['more']), (['vote', 'interested', 'question'], ['vote', 'question'])]:
            series = ActivitySeries.objects.create(owner=self.host, title='Old Series', available_responses=old)
            initial = occurrence_initial(series)
            self.assertEqual(initial['available_responses'], expected)
            self.assertEqual(ActivitySeriesForm(instance=series, user=self.host)['available_responses'].value(), expected)
            series.refresh_from_db(); self.assertEqual(series.available_responses, old)
        self.assertEqual(ActivityForm(instance=self.activity, user=self.host)['available_responses'].value(), self.activity.available_responses)

    def test_admin_new_responses_exclude_interested_but_legacy_read_edit_is_safe(self):
        admin = ActivityResponseAdmin(ActivityResponse, AdminSite())
        request = RequestFactory().get('/admin/'); request.user = self.host
        form = admin.get_form(request)()
        self.assertNotIn('interested', dict(form.fields['status'].choices))
        saved = ActivityResponse.objects.create(activity=self.activity, user=self.user, status='interested')
        form = admin.get_form(request, saved)(instance=saved)
        self.assertEqual(dict(form.fields['status'].choices)['interested'], 'Interested (historical)')

    def test_non_js_edit_state_preserves_repeated_discover_filters(self):
        destination = '/?q=shared&audience=everyone&audience=friends'
        self.assertRedirects(self.post('question', htmx=False), destination)
        self.assertIn('Have a question / Edit response', self.bands(self.card()))
        ActivityInvitation.objects.create(activity=self.activity, user=self.user, invited_by=self.host)
        self.assertRedirects(self.post('declined', htmx=False), destination)
        self.assertContains(self.card(), 'value="declined" aria-pressed="true"')


class RetiredResponseMigrationTests(TransactionTestCase):
    def test_default_and_label_migration_preserves_all_response_and_configuration_values(self):
        executor = MigrationExecutor(connection)
        targets = executor.loader.graph.leaf_nodes()
        before = [('activities', '0021_groupjoinoffer')]
        try:
            executor.migrate(before)
            apps = executor.loader.project_state(before).apps
            User = apps.get_model('auth', 'User'); ActivityOld = apps.get_model('activities', 'Activity')
            ResponseOld = apps.get_model('activities', 'ActivityResponse'); SeriesOld = apps.get_model('activities', 'ActivitySeries')
            user = User.objects.create(username='legacy-migration')
            series = SeriesOld.objects.create(owner_id=user.pk, title='Keep Series', available_responses=['interested', 'vote'])
            activity = ActivityOld.objects.create(host_id=user.pk, series_id=series.pk, title='Keep occurrence', available_responses=['interested', 'question'])
            response = ResponseOld.objects.create(user_id=user.pk, activity_id=activity.pk, status='interested', note='Do not convert me')
            snapshot = ResponseOld.objects.values().get(pk=response.pk)
            executor = MigrationExecutor(connection); executor.migrate(targets)
            self.assertEqual(ActivityResponse.objects.values().get(pk=response.pk), snapshot)
            self.assertEqual(Activity.objects.get(pk=activity.pk).available_responses, ['interested', 'question'])
            self.assertEqual(ActivitySeries.objects.get(pk=series.pk).available_responses, ['interested', 'vote'])
        finally:
            MigrationExecutor(connection).migrate(targets)
