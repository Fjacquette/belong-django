from copy import deepcopy
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from belong.test_helpers import create_legacy_user
from .forms import ActivityForm, ActivitySeriesForm
from .models import Activity, ActivitySeries, ActivityResponse, ActivityInvitation, Announcement, ActivityNotificationEvent, ActivityNotificationDelivery
from .participation_config import PATTERNS, make_config, validate_config
from .participation import change_response
from .series import occurrence_initial


class ParticipationConfigurationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.host=create_legacy_user('config-host')
        cls.user=create_legacy_user('config-viewer')
        cls.other=create_legacy_user('config-other')

    def setUp(self):
        self.client.force_login(self.user)

    def activity(self, **kwargs):
        defaults={'host':self.host,'title':'Configured opportunity','description':'A useful description.'}
        defaults.update(kwargs)
        return Activity.objects.create(**defaults)

    def form_data(self, **kwargs):
        data={'title':'New opportunity','description':'Details','location_type':'tbd','audience':'everyone','cost_type':'free'}
        data.update(kwargs)
        return data

    def test_all_seven_patterns_have_explicit_version_and_safe_navigation_defaults(self):
        self.assertEqual(set(PATTERNS),{'scheduled','immediate','planning','ongoing','registration','inquiry','none'})
        for pattern in PATTERNS:
            with self.subTest(pattern=pattern):
                config=make_config(pattern)
                self.assertEqual(config,{'version':1,'pattern':pattern,'actions':['view_details']})
                a=self.activity(participation_config=config)
                a.full_clean()
                self.assertEqual(a.active_responses(),[])
                self.assertEqual(change_response(a.pk,self.user,'committed'),'No response is required for this activity.')
        self.assertFalse(ActivityResponse.objects.exists())

    def test_action_ids_versions_and_payload_shapes_are_validated(self):
        for value in [{},[],False,'none',{'version':True,'pattern':'none','actions':['view_details']},
                      {'version':2,'pattern':'none','actions':['view_details']},
                      {'version':1,'pattern':'unknown','actions':['view_details']},
                      {'version':1,'pattern':'none','actions':['view_details','view_details']},
                      {'version':1,'pattern':'none','actions':[]},
                      {'version':1,'pattern':'none','actions':['view_details'],'extra':True},
                      {'version':1,'pattern':'none','actions':{'view_details':True}}]:
            with self.subTest(value=value),self.assertRaises(ValidationError):validate_config(value)
        for pattern, (_,planned) in PATTERNS.items():
            for action in [*planned,'interested','willing','question','vote','pay','notify_future_outings']:
                with self.subTest(pattern=pattern,action=action),self.assertRaises(ValidationError):
                    make_config(pattern,actions=['view_details',action])
        validate_config(None)
        validate_config(make_config('none',actions=['view_details','open_external']))

    def test_legacy_choices_empty_default_and_historical_read_path_unchanged(self):
        a=self.activity(available_responses=['question','interested','committed'])
        ActivityInvitation.objects.create(activity=a,user=self.user,invited_by=self.host)
        saved=ActivityResponse.objects.create(activity=a,user=self.user,status='interested',note='Retain historical note')
        before=ActivityResponse.objects.values().get(pk=saved.pk)
        self.assertEqual(a.active_responses(),['question','committed'])
        self.assertEqual(self.activity().active_responses(),['more'])
        page=self.client.get(a.get_absolute_url())
        self.assertContains(page,'Interested (historical)')
        self.assertEqual([o['value'] for o in page.context['join_context']['response_options']],['committed','declined','question'])
        self.assertEqual(ActivityResponse.objects.values().get(pk=saved.pk),before)
        self.assertContains(self.client.get('/?q=Configured'),'Past response')

    def test_creator_default_stays_legacy_and_only_ready_pattern_is_selectable(self):
        form=ActivityForm(user=self.host)
        self.assertEqual(form.initial['participation_pattern'],'')
        self.assertEqual([value for value, label in form.fields['participation_pattern'].choices], ['', 'scheduled', 'immediate', 'none', 'planning'])
        legacy=ActivityForm(data=self.form_data(),user=self.host)
        self.assertTrue(legacy.is_valid(),legacy.errors)
        a=legacy.save(commit=False);a.host=self.host;a.save()
        self.assertIsNone(a.participation_config);self.assertEqual(a.available_responses,['more'])
        for pattern in set(PATTERNS)-{'none', 'scheduled', 'immediate', 'planning'}:
            forged=ActivityForm(data=self.form_data(participation_pattern=pattern),user=self.host)
            self.assertFalse(forged.is_valid());self.assertIn('participation_pattern',forged.errors)

    def test_create_no_response_ignores_legacy_checkboxes_and_forged_config_fields(self):
        self.client.force_login(self.host)
        response=self.client.post(reverse('activities:create'),self.form_data(participation_pattern='none',available_responses=['committed','question'],participation_config='{"pattern":"registration"}',action1_label='Open opportunity',action1_url='https://example.invalid/opportunity'))
        a=Activity.objects.latest('pk')
        self.assertRedirects(response,a.get_absolute_url())
        self.assertEqual(a.participation_config,make_config('none',actions=['view_details','open_external']))
        self.assertEqual(a.available_responses,[])
        self.assertFalse(ActivityResponse.objects.exists())

    def test_no_response_navigation_details_and_invited_card_never_create_response(self):
        a=self.activity(participation_config=make_config('none',actions=['view_details','open_external']),action1_label='External opportunity',action1_url='https://example.invalid/opportunity')
        ActivityInvitation.objects.create(activity=a,user=self.user,invited_by=self.host)
        for viewer in [self.user,self.other]:
            self.client.force_login(viewer)
            card=self.client.get('/?q=Configured&audience=everyone&audience=friends')
            self.assertContains(card,'>See details</a>')
            self.assertNotContains(card,'See details / RSVP')
            self.assertNotContains(card,'name="status"')
            detail=self.client.get(a.get_absolute_url())
            self.assertContains(detail,'No response required.')
            self.assertContains(detail,'href="https://example.invalid/opportunity"')
            self.assertNotContains(detail,'No response yet')
            self.assertNotContains(detail,'name="status"')
            self.assertNotContains(detail,'Remove response')
        self.assertFalse(ActivityResponse.objects.exists())

    def test_crafted_join_respond_remove_htmx_and_fallback_cannot_mutate_navigation_only(self):
        a=self.activity(participation_config=make_config('none'))
        ActivityInvitation.objects.create(activity=a,user=self.user,invited_by=self.host)
        for route in ['join','respond','leave']:
            for status in ['committed','declined','question','vote','more','interested']:
                for htmx in [False,True]:
                    result=self.client.post(reverse('activities:'+route,args=[a.pk]),{'status':status,'variant':'card','next':'/?q=Configured&audience=everyone&audience=friends'},**({'HTTP_HX_REQUEST':'true'} if htmx else {}))
                    self.assertIn(result.status_code,[200,302])
                    self.assertFalse(ActivityResponse.objects.exists())
                    if result.status_code==302:self.assertEqual(result.url,'/?q=Configured&audience=everyone&audience=friends')

    def test_existing_activity_config_cannot_change_even_without_responses(self):
        for config in [None,make_config('none')]:
            a=self.activity(participation_config=config)
            a.participation_config=make_config('planning')
            with self.assertRaises(ValidationError):a.full_clean()
            with self.assertRaises(ValidationError):a.save()
            a.refresh_from_db();self.assertEqual(a.participation_config,config)
        old=self.activity(available_responses=['interested','question'])
        form=ActivityForm(data=self.form_data(participation_pattern='none'),instance=old,user=self.host)
        self.assertFalse(form.is_valid());self.assertIn('__all__',form.errors)
        old.refresh_from_db();self.assertEqual(old.available_responses,['interested','question'])

    def test_configured_history_is_read_only_and_cancelled_footer_retains_it(self):
        # Defensive read path if a future migration/direct DB operator adds historical evidence.
        a=self.activity(participation_config=make_config('none'))
        saved=ActivityResponse.objects.create(activity=a,user=self.user,status='interested',note='History')
        before=ActivityResponse.objects.values().get(pk=saved.pk)
        self.assertContains(self.client.get(a.get_absolute_url()),'Interested (historical)')
        card = self.client.get('/?q=Configured')
        self.assertContains(card, 'View response for')
        self.assertNotContains(card, 'Edit response')
        self.client.post(reverse('activities:leave',args=[a.pk]))
        self.assertEqual(ActivityResponse.objects.values().get(pk=saved.pk),before)
        a.status='cancelled';a.save(update_fields=['status'])
        self.assertContains(self.client.get('/?q=Configured'),'>Cancelled</a>')
        self.assertEqual(ActivityResponse.objects.values().get(pk=saved.pk),before)

    def test_external_action_requires_capability_and_valid_http_url_without_affecting_legacy(self):
        a=self.activity(participation_config=make_config('none'),action1_label='External opportunity',action1_url='https://example.invalid/opportunity')
        self.assertNotContains(self.client.get(a.get_absolute_url()),'href="https://example.invalid/opportunity"')
        b=self.activity(participation_config=make_config('none',actions=['view_details','open_external']),action2_label='Broken link',action2_url='javascript:alert(1)')
        self.assertNotContains(self.client.get(b.get_absolute_url()),'Broken link')
        legacy=self.activity(action1_label='External opportunity',action1_url='https://example.invalid/opportunity')
        self.assertContains(self.client.get(legacy.get_absolute_url()),'href="https://example.invalid/opportunity"')

    def test_series_copies_all_configurations_deeply_without_rewriting_legacy_json(self):
        for pattern in PATTERNS:
            series=ActivitySeries.objects.create(owner=self.host,title='Defaults',description='Future opportunities',participation_config=make_config(pattern),available_responses=['interested','vote'])
            initial=occurrence_initial(series)
            self.assertEqual(initial['participation_config'],series.participation_config)
            self.assertEqual(initial['available_responses'],[])
            initial['participation_config']['actions'].append('open_external')
            self.assertEqual(series.participation_config['actions'],['view_details'])
            series.refresh_from_db();self.assertEqual(series.available_responses,['interested','vote'])

    def test_series_edit_defaults_and_create_occurrence_leave_siblings_unchanged(self):
        self.client.force_login(self.host)
        series=ActivitySeries.objects.create(owner=self.host,title='Legacy defaults',description='Future activities',available_responses=['interested','committed'])
        old=self.activity(series=series,available_responses=['interested','committed'])
        before=Activity.objects.values().get(pk=old.pk)
        data=self.form_data(participation_pattern='none',cadence='flexible')
        self.assertEqual(self.client.post(reverse('activities:series_edit',args=[series.pk]),data).status_code,302)
        series.refresh_from_db()
        self.assertEqual(series.participation_config,make_config('none'))
        self.assertEqual(series.available_responses,['interested','committed'])
        copied=occurrence_initial(series)
        data={k:('' if value is None else value) for k,value in copied.items() if k!='participation_config'}
        self.assertEqual(self.client.post(reverse('activities:create')+f'?series={series.pk}',data).status_code,302)
        created=Activity.objects.latest('pk')
        self.assertEqual(created.participation_config,series.participation_config)
        self.assertEqual(created.available_responses,[])
        self.assertEqual(Activity.objects.values().get(pk=old.pk),before)
        series.participation_config=None;series.save()
        created.refresh_from_db();self.assertEqual(created.participation_config,make_config('none'))

    def test_no_response_series_form_saves_real_empty_choices(self):
        form=ActivitySeriesForm(data=self.form_data(participation_pattern='none',cadence='flexible'),user=self.host)
        self.assertTrue(form.is_valid(),form.errors)
        series=form.save(commit=False);series.owner=self.host;series.save()
        self.assertEqual(series.available_responses,[])
        self.assertEqual(series.participation_config,make_config('none'))

    def test_admin_cannot_create_or_reassign_responses_to_navigation_only_activity(self):
        from .admin import ActivityResponseAdminForm
        legacy = self.activity()
        configured = self.activity(participation_config=make_config('none'))
        response = ActivityResponse.objects.create(activity=legacy, user=self.user, status='committed')
        data = {'activity': configured.pk, 'user': self.user.pk, 'status': 'committed', 'note': ''}
        self.assertFalse(ActivityResponseAdminForm(data=data).is_valid())
        self.assertFalse(ActivityResponseAdminForm(data=data, instance=response).is_valid())
        history = ActivityResponse.objects.create(activity=configured, user=self.other, status='question')
        historical_data = {'activity': configured.pk, 'user': self.other.pk, 'status': 'question', 'note': 'Historical note'}
        self.assertTrue(ActivityResponseAdminForm(data=historical_data, instance=history).is_valid())
        self.assertFalse(ActivityResponseAdminForm(data={**historical_data, 'user': self.host.pk}, instance=history).is_valid())

    def test_null_is_the_only_legacy_sentinel_and_invalid_config_fails_closed(self):
        a=self.activity()
        Activity.objects.filter(pk=a.pk).update(participation_config={})
        a.refresh_from_db();self.assertFalse(a.uses_legacy_participation)
        self.assertEqual(a.active_responses(),[])
        self.assertFalse(a.offers_external_actions)
        self.assertFalse(change_response(a.pk,self.user,'committed')=='')
        self.assertFalse(ActivityResponse.objects.exists())


class ParticipationConfigurationMigrationTests(TransactionTestCase):
    def test_additive_migration_preserves_all_prior_fields_and_does_not_infer_patterns(self):
        executor=MigrationExecutor(connection);leaves=executor.loader.graph.leaf_nodes()
        old=[('activities','0023_announcement_submission_key_and_more')]
        try:
            executor.migrate(old);apps=executor.loader.project_state(old).apps
            user=apps.get_model('auth','User').objects.create(username='config-migration')
            series=apps.get_model('activities','ActivitySeries').objects.create(owner_id=user.pk,title='Scheduled title',description='Legacy',available_responses=['interested','vote'])
            a=apps.get_model('activities','Activity').objects.create(host_id=user.pk,series_id=series.pk,title='Paid registration',description='Legacy',cost_type='paid',cost_amount=25,available_responses=['interested','question'])
            response=apps.get_model('activities','ActivityResponse').objects.create(activity_id=a.pk,user_id=user.pk,status='interested',note='Retain')
            invitation=apps.get_model('activities','ActivityInvitation').objects.create(activity_id=a.pk,user_id=user.pk,invited_by_id=user.pk)
            announcement=apps.get_model('activities','Announcement').objects.create(activity_id=a.pk,author_id=user.pk,body='Keep update')
            event=apps.get_model('activities','ActivityNotificationEvent').objects.create(activity_id=a.pk,actor_id=user.pk,announcement_id=announcement.pk,kind='update')
            delivery=apps.get_model('activities','ActivityNotificationDelivery').objects.create(event_id=event.pk,recipient_id=user.pk,recipient_hash='0'*64,status='sent',attempts=1)
            snapshots={name:list(apps.get_model('activities',name).objects.values()) for name in ['Activity','ActivitySeries','ActivityResponse','ActivityInvitation','Announcement','ActivityNotificationEvent','ActivityNotificationDelivery']}
            MigrationExecutor(connection).migrate(leaves)
            from django.apps import apps as current
            for name, rows in snapshots.items():
                actual=list(current.get_model('activities',name).objects.values(*rows[0].keys()))
                self.assertEqual(actual,rows,name)
            self.assertIsNone(Activity.objects.get(pk=a.pk).participation_config)
            self.assertIsNone(ActivitySeries.objects.get(pk=series.pk).participation_config)
        finally:MigrationExecutor(connection).migrate(leaves)
