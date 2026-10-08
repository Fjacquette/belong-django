"""Independent occurrence copying, private draft authority and publication safety."""
from copy import deepcopy
from datetime import timedelta

from django.test import TestCase, Client, SimpleTestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from belong.test_helpers import create_legacy_user
from groups.models import Group, GroupMembership
from .models import (Activity, ActivityDraft, ActivityResponse, ActivityInvitation,
    ActivitySeries, Announcement, RegistrationTarget, FreeReservationPool,
    ActivityNotificationEvent, OngoingOpportunity, DatePoll)
from .drafts import COPY_FIELDS, copy_values, DraftForm
from .participation_config import make_config
from .participation import cancel_activity


class DraftTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.host = create_legacy_user('clone-host')
        cls.viewer = create_legacy_user('clone-viewer')
        cls.other = create_legacy_user('clone-other')
        cls.co = create_legacy_user('clone-co')
        cls.group = Group.objects.create(owner=cls.host, name='Hiking')
        GroupMembership.objects.create(group=cls.group, user=cls.co, role='organizer')
        cls.series = ActivitySeries.objects.create(owner=cls.host, group=cls.group, title='Usual hikes', description='Defaults changed later')
        cls.source = Activity.objects.create(host=cls.host, group=cls.group, series=cls.series,
            title='Past trail hike', description='Meet together', starts_at=timezone.now()-timedelta(days=3),
            ends_at=timezone.now()-timedelta(days=3, hours=-2), post_until=timezone.now()-timedelta(days=2),
            location_name='Trailhead', location_instructions='Bring water', location_gps='40.0, -75.0',
            invite_group_members=True, audience='everyone', cost_type='free', capacity=2,
            available_responses=['committed','question'])
        ActivityResponse.objects.create(activity=cls.source, user=cls.viewer, status='committed', note='Historic note')
        ActivityInvitation.objects.create(activity=cls.source, user=cls.viewer, invited_by=cls.host)
        Announcement.objects.create(activity=cls.source, author=cls.host, body='Old weather')

    def setUp(self):
        self.client.force_login(self.host)

    def clone(self, source=None):
        response = self.client.post(reverse('activities:clone', args=[(source or self.source).pk]))
        self.assertEqual(response.status_code, 302)
        return ActivityDraft.objects.latest('pk')

    def payload(self, draft, **changes):
        # Submit browser-selectable values, never internal config or derived terms.
        data = deepcopy(draft.values)
        data.pop('participation_config', None)
        data.pop('interests', None)
        for key in ['group', 'series', 'category', 'header_image', 'organizer_image', 'capacity', 'cost_amount', 'starts_at', 'ends_at', 'post_until']:
            if data.get(key) is None:
                data[key] = ''
        data = {key: '' if value is None else value for key,value in data.items()}
        data.update(revision=draft.revision, action='publish', starts_at=(timezone.now()+timedelta(days=3)).strftime('%Y-%m-%dT%H:%M'))
        data.update(changes)
        return data

    def test_clone_allowlist_and_source_history_are_unchanged(self):
        before = Activity.objects.values().get(pk=self.source.pk)
        response = list(ActivityResponse.objects.values())
        invitations = list(ActivityInvitation.objects.values())
        updates = list(Announcement.objects.values())
        draft = self.clone()
        self.assertEqual(Activity.objects.count(), 1)
        self.assertEqual(draft.source_id, self.source.pk)
        for name in ('starts_at','ends_at','post_until'):
            self.assertIsNone(draft.values[name])
        self.assertEqual(draft.values['location_instructions'], 'Bring water')
        self.assertEqual((draft.values['group'],draft.values['series']), (self.group.pk,self.series.pk))
        self.assertFalse(draft.values['invite_group_members'])
        self.assertFalse({'host','status','cancelled_at','cancelled_by','is_personal_invitation','created_at','ongoing_opportunity'} & set(COPY_FIELDS))
        self.assertEqual(Activity.objects.values().get(pk=self.source.pk), before)
        self.assertEqual(list(ActivityResponse.objects.values()), response)
        self.assertEqual(list(ActivityInvitation.objects.values()), invitations)
        self.assertEqual(list(Announcement.objects.values()), updates)

    def test_draft_is_private_and_not_an_activity_or_notification_target(self):
        draft = self.clone()
        self.assertContains(self.client.get(reverse('activities:draft',args=[draft.pk])), 'Only you can see')
        for user in (self.viewer,self.other,self.co):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse('activities:draft',args=[draft.pk])).status_code,404)
            self.assertEqual(self.client.post(reverse('activities:draft',args=[draft.pk]),self.payload(draft)).status_code,404)
        self.assertFalse(ActivityNotificationEvent.objects.exists())
        self.assertEqual(Activity.objects.count(),1)
        self.assertNotContains(self.client.get(reverse('activities:history')), 'Your private drafts')

    def test_clone_requires_access_organizer_post_and_csrf(self):
        url=reverse('activities:clone',args=[self.source.pk])
        self.assertEqual(self.client.get(url).status_code,405)
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.host)
        self.assertEqual(csrf.post(url).status_code,403)
        for user in (self.viewer,self.other):
            self.client.force_login(user);self.assertEqual(self.client.post(url).status_code,404)
        self.client.force_login(self.co);draft=self.clone()
        self.assertEqual(draft.creator_id,self.co.pk)
        self.source.audience='friends';self.source.save()
        self.assertEqual(self.client.post(url).status_code,404)
        self.assertNotContains(self.client.get(reverse('activities:history')), self.source.get_absolute_url())

    def test_history_filters_permission_time_and_retains_search_pagination(self):
        future=Activity.objects.create(host=self.host,title='Future outing',description='Later',starts_at=timezone.now()+timedelta(days=2))
        outsider=Activity.objects.create(host=self.other,title='Other past',description='Before',starts_at=timezone.now()-timedelta(days=1))
        page=self.client.get(reverse('activities:history'))
        self.assertContains(page,self.source.title);self.assertNotContains(page,future.title);self.assertNotContains(page,outsider.title)
        for n in range(21):
            Activity.objects.create(host=self.host,title=f'Past {n}',description='Old',starts_at=timezone.now()-timedelta(days=n+4))
        page=self.client.get(reverse('activities:history'),{'q':'Past'})
        self.assertContains(page,'?q=Past&amp;page=2')
        self.assertNotContains(self.client.get(reverse('activities:history'),{'q':'Absent'}), self.source.title)

    def test_save_then_publish_edit_logistics_and_replay_is_idempotent(self):
        draft=self.clone();url=reverse('activities:draft',args=[draft.pk])
        data=self.payload(draft,title='New trail hike',location_name='New trailhead',action='save')
        self.assertRedirects(self.client.post(url,data),url)
        self.assertEqual(Activity.objects.count(),1)
        draft.refresh_from_db();self.assertEqual(draft.revision,2)
        page=self.client.get(url);self.assertContains(page,'New trailhead')
        self.assertContains(page, data['starts_at'])
        data=self.payload(draft,action='publish')
        response=self.client.post(url,data);draft.refresh_from_db()
        new=draft.published_activity
        self.assertRedirects(response,new.get_absolute_url())
        self.assertEqual((new.group_id,new.series_id),(self.group.pk,self.series.pk))
        self.assertEqual((new.location_name,new.capacity),('New trailhead',2))
        self.assertFalse(new.invite_group_members)
        self.assertFalse(new.responses.exists());self.assertFalse(new.direct_invitations.exists());self.assertFalse(new.email_invitations.exists());self.assertFalse(new.announcements.exists())
        self.assertFalse(ActivityNotificationEvent.objects.filter(activity=new).exists())
        self.assertEqual(new.host_id,self.host.pk)
        self.assertNotEqual(new.pk,self.source.pk)
        self.client.post(url,data);self.client.post(url,{**data,'action':'save','title':'Stale'})
        self.assertEqual(Activity.objects.count(),2)
        new.refresh_from_db();self.assertEqual(new.title,'New trail hike')
        self.assertContains(self.client.get(reverse('activities:index'),{'q':'New trail hike'}),'New trail hike')

    def test_publish_validation_stale_save_and_untrusted_internal_fields(self):
        draft=self.clone();url=reverse('activities:draft',args=[draft.pk])
        for changes in ({'starts_at':''},{'starts_at':'2000-01-01T10:00'}, {'ends_at':'2000-01-01T09:00'}, {'group':999999}, {'series':999999}, {'capacity':'0'}, {'audience':'group'}, {'location_gps':'bad'}):
            self.assertEqual(self.client.post(url,self.payload(draft,**changes)).status_code,200)
            self.assertEqual(Activity.objects.count(),1)
        saved=self.payload(draft,action='save');self.client.post(url,saved)
        self.assertContains(self.client.post(url,saved),'changed in another tab')
        draft.refresh_from_db()
        data=self.payload(draft,status='cancelled',host=self.other.pk,participation_config='fake',is_personal_invitation=True,ongoing_opportunity=999)
        self.client.post(url,data);draft.refresh_from_db();new=draft.published_activity
        self.assertEqual((new.status,new.host_id,new.is_personal_invitation,new.ongoing_opportunity_id),('active',self.host.pk,False,None))

    def test_group_series_authority_rechecked_and_defaults_not_reapplied(self):
        draft=self.clone()
        self.series.title='Changed Series';self.series.description='Different description';self.series.save()
        form=DraftForm(self.payload(draft),draft=draft,user=self.host)
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.cleaned_data['description'],'Meet together')
        unrelated=ActivitySeries.objects.create(owner=self.host,title='No Group',description='Not grouped')
        form=DraftForm(self.payload(draft,series=unrelated.pk),draft=draft,user=self.host)
        self.assertFalse(form.is_valid());self.assertIn('series',form.errors)
        self.client.force_login(self.co);co_draft=self.clone()
        membership=GroupMembership.objects.get(group=self.group,user=self.co);membership.status='blocked';membership.role='member';membership.save()
        form=DraftForm(self.payload(co_draft),draft=co_draft,user=self.co)
        self.assertFalse(form.is_valid());self.assertIn('group',form.errors)
        form=DraftForm(self.payload(co_draft,group='',series=''),draft=co_draft,user=self.co)
        self.assertTrue(form.is_valid(),form.errors)

    def test_cancelled_source_clones_active_new_occurrence_and_history_survives(self):
        cancel_activity(self.source.pk,self.host,'Trail flooded')
        before=Activity.objects.values().get(pk=self.source.pk)
        draft=self.clone();self.client.post(reverse('activities:draft',args=[draft.pk]),self.payload(draft))
        draft.refresh_from_db();new=draft.published_activity
        self.assertFalse(new.is_cancelled);self.assertIsNone(new.cancelled_at);self.assertEqual(new.cancellation_reason,'')
        self.assertEqual(Activity.objects.values().get(pk=self.source.pk),before)
        self.assertEqual(self.source.responses.get().note,'Historic note')
        self.assertContains(self.client.get(reverse('activities:history')),'Cancelled')

    def test_explicit_group_invite_choice_and_scheduled_configuration(self):
        # Source fixture starts legacy; do not mutate its configuration authority.
        scheduled=Activity.objects.create(host=self.host,group=self.group,title='Scheduled hike',description='Walk',cost_type='free',participation_config=make_config('scheduled',version=2))
        draft=self.clone(scheduled)
        self.client.post(reverse('activities:draft',args=[draft.pk]),self.payload(draft,invite_group_members=True))
        draft.refresh_from_db();new=draft.published_activity
        self.assertTrue(new.invite_group_members);self.assertEqual(new.participation_config,scheduled.participation_config)
        self.assertFalse(new.direct_invitations.exists());self.assertFalse(new.email_invitations.exists())

    def test_registration_and_ongoing_create_fresh_pools_without_history(self):
        for pattern,version in [('ongoing',4),('registration',5)]:
            source=Activity.objects.create(host=self.host,title=pattern,description='Free',cost_type='free',participation_config=make_config(pattern,version=version))
            if pattern=='ongoing':
                OngoingOpportunity.objects.create(activity=source,capacity=3)
            else:
                target=RegistrationTarget.objects.create(activity=source,capacity=3,amount=0,admission='request',allocation='claim')
                pool=FreeReservationPool.objects.create(target=target,capacity=3,waitlist_enabled=True)
                FreeReservationPool.objects.filter(pk=pool.pk).update(capacity=4)
            draft=self.clone(source)
            self.client.post(reverse('activities:draft',args=[draft.pk]),self.payload(draft))
            draft.refresh_from_db();self.assertIsNotNone(draft.published_activity_id)
            new=draft.published_activity
            self.assertIsNone(new.capacity)
            if pattern=='ongoing':
                self.assertEqual(OngoingOpportunity.objects.get(activity=new).capacity,3)
            else:
                self.assertEqual(new.registration_target.capacity,4)
                self.assertTrue(new.registration_target.reservation_pool.waitlist_enabled)
                self.assertFalse(new.registration_target.requests.exists())

    def test_poll_clone_requires_new_dates_and_copies_no_votes_or_finalization(self):
        from .polls import create_poll
        source=Activity.objects.create(host=self.host,title='Planning',description='Dates',cost_type='free',participation_config=make_config('planning',version=3))
        create_poll(source,[timezone.now()+timedelta(days=n) for n in (3,4,5)])
        draft=self.clone(source);url=reverse('activities:draft',args=[draft.pk])
        self.assertEqual(self.client.post(url,self.payload(draft,starts_at='')).status_code,200)
        self.assertEqual(DatePoll.objects.count(),1)
        dates={f'poll_date_{n}':(timezone.now()+timedelta(days=n+10)).strftime('%Y-%m-%dT%H:%M') for n in (1,2,3)}
        response=self.client.post(url,self.payload(draft,starts_at='',**dates))
        self.assertEqual(response.status_code,302)
        draft.refresh_from_db();self.assertTrue(draft.published_activity.is_date_planning)
        self.assertEqual(DatePoll.objects.count(),2)


    def test_artwork_is_snapshot_and_publish_does_not_apply_new_group_default(self):
        from io import BytesIO
        from PIL import Image
        from media_assets.models import ImageAsset
        output=BytesIO();Image.new('RGB',(20,20),'purple').save(output,format='PNG')
        artwork=ImageAsset.objects.create(name='New default',purpose='activity_header',data=output.getvalue(),size=len(output.getvalue()),content_type='image/png')
        draft=self.clone()
        self.group.default_activity_image=artwork;self.group.save()
        self.client.post(reverse('activities:draft',args=[draft.pk]),self.payload(draft))
        draft.refresh_from_db();self.assertIsNone(draft.published_activity.header_image_id)
        self.source.header_image=artwork;self.source.save()
        draft=self.clone();self.assertEqual(draft.values['header_image'],str(artwork.pk))
        self.client.post(reverse('activities:draft',args=[draft.pk]),self.payload(draft))
        draft.refresh_from_db();self.assertEqual(draft.published_activity.header_image_id,artwork.pk)

    def test_publication_requires_csrf_and_verification_and_retains_audience(self):
        draft=self.clone();url=reverse('activities:draft',args=[draft.pk])
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.host)
        self.assertEqual(csrf.post(url,self.payload(draft)).status_code,403)
        self.host.profile.legacy_access=False;self.host.profile.save()
        self.assertRedirects(self.client.post(url,self.payload(draft)),reverse('verification_status'))
        self.host.profile.legacy_access=True;self.host.profile.save()
        self.client.post(url,self.payload(draft,title='Private new hike',audience='friends',invite_group_members=True))
        draft.refresh_from_db();new=draft.published_activity
        self.client.force_login(self.co)
        self.assertEqual(self.client.get(new.get_absolute_url()).status_code,404)
        self.assertNotContains(self.client.get(reverse('activities:index'),{'q':new.title}),new.get_absolute_url())

    def test_paid_copy_stays_eligibility_only_and_no_legacy_interested_is_created(self):
        source=Activity.objects.create(host=self.host,title='Paid metadata',description='No payments',cost_type='paid',cost_amount='25.00',participation_config=make_config('registration',version=5))
        RegistrationTarget.objects.create(activity=source,amount='25.00',capacity=12,admission='open',allocation='claim')
        draft=self.clone(source);self.client.post(reverse('activities:draft',args=[draft.pk]),self.payload(draft))
        draft.refresh_from_db();new=draft.published_activity
        self.assertEqual(new.registration_target.amount,source.registration_target.amount)
        self.assertFalse(new.registration_target.requests.exists())
        self.assertContains(self.client.get(new.get_absolute_url()),'Payments are unavailable')
        self.source.available_responses=['interested'];self.source.save()
        draft=self.clone();self.assertEqual(draft.values['available_responses'],['more'])
        self.source.refresh_from_db();self.assertEqual(self.source.available_responses,['interested'])


class DraftPublicationRaceTests(SimpleTestCase):
    def test_file_backed_duplicate_publish_and_save_publish_races(self):
        import os
        from pathlib import Path
        import subprocess
        import sys
        import tempfile
        script = r'''
import os,django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','belong.settings');django.setup()
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta
from django.db import close_old_connections
from django.core.management import call_command
from django.test import RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage
from django.utils import timezone
from belong.test_helpers import create_legacy_user
from activities.models import Activity,ActivityDraft,ActivityNotificationEvent
from activities.drafts import copy_values,edit
call_command('migrate',verbosity=0)
u=create_legacy_user('clone-race')
s=Activity.objects.create(host=u,title='Race source',description='Trail',cost_type='free')
def request(draft,data):
 r=RequestFactory().post('/activity-drafts/'+str(draft.pk)+'/',data);r.user=u;r.session={};r._messages=FallbackStorage(r)
 return edit(r,draft.pk)
def race(draft,actions):
 barrier=Barrier(len(actions))
 def run(data):
  close_old_connections()
  try:barrier.wait(timeout=10);return request(draft,data).status_code
  finally:close_old_connections()
 with ThreadPoolExecutor(max_workers=len(actions)) as pool:return list(pool.map(run,actions))
for n in range(3):
 d=ActivityDraft.objects.create(creator=u,source=s,source_title=s.title,values=copy_values(s,u))
 data={k:('' if v is None else v) for k,v in d.values.items() if k not in ('participation_config','interests')}
 data.update(action='publish',revision=1,starts_at=(timezone.now()+timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'))
 before=Activity.objects.count();race(d,[data,data,data]);d.refresh_from_db()
 assert d.published_activity_id and Activity.objects.count()==before+1
 d=ActivityDraft.objects.create(creator=u,source=s,source_title=s.title,values=copy_values(s,u))
 before=Activity.objects.count();race(d,[data,{**data,'action':'save','title':'Saved race'}]);d.refresh_from_db()
 assert Activity.objects.count()<=before+1
 if not d.published_at:
  current={k:('' if v is None else v) for k,v in d.values.items() if k not in ('participation_config','interests')}
  current.update(action='publish',revision=d.revision)
  assert request(d,current).status_code==302
 assert Activity.objects.count()==before+1
assert ActivityNotificationEvent.objects.count()==0
print('Draft publication races passed')
'''
        with tempfile.TemporaryDirectory() as root:
            env=os.environ.copy();env.update(BELONG_ENV='test',DJANGO_DB_PATH=str(Path(root)/'draft-race.sqlite3'),EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
            result=subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,text=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('Draft publication races passed',result.stdout)


class DraftMigrationTests(TransactionTestCase):
    def test_additive_draft_migration_retains_all_prior_activity_and_response_facts(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        executor=MigrationExecutor(connection);leaves=executor.loader.graph.leaf_nodes();old=[('activities','0028_alter_activitynotificationevent_kind_and_more')]
        try:
            executor.migrate(old);apps=executor.loader.project_state(old).apps
            user=apps.get_model('auth','User').objects.create(username='clone-migration')
            activity=apps.get_model('activities','Activity').objects.create(host_id=user.pk,title='Historic',description='Retain',status='cancelled',cancellation_reason='Past',available_responses=['interested','committed'])
            apps.get_model('activities','ActivityResponse').objects.create(activity_id=activity.pk,user_id=user.pk,status='interested',note='Historical note')
            apps.get_model('activities','Announcement').objects.create(activity_id=activity.pk,author_id=user.pk,body='Retain update')
            names=['Activity','ActivityResponse','Announcement'];before={name:list(apps.get_model('activities',name).objects.values()) for name in names}
            MigrationExecutor(connection).migrate(leaves)
            from django.apps import apps as current
            for name,rows in before.items():self.assertEqual(list(current.get_model('activities',name).objects.values()),rows,name)
            self.assertFalse(ActivityDraft.objects.exists())
        finally:MigrationExecutor(connection).migrate(leaves)
