import os
import re
import subprocess
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.admin.models import LogEntry
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, ActivityEmailInvitation, ActivityInvitation, ActivityResponse
from groups.models import Group, GroupInvitation, GroupMembership
from groups.invitations import digest
from social.models import AccountEmailProof, BetaAdmission, OutboundEmailAttempt
from .account_email import complete_signup, request_account_email
from .beta_admission import ERROR, issue_code, revoke


@override_settings(BETA_MODE=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', BELONG_PUBLIC_ORIGIN='http://testserver')
class BetaAdmissionTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser('beta-admin',email='admin@example.invalid',password='Admin-only-817!')
        self.admin.profile.email_verified_at=timezone.now();self.admin.profile.save()
        self.email='hiker@example.invalid'
        self.admission,self.code=issue_code(self.email,self.admin)
        self.request=RequestFactory().post('/',REMOTE_ADDR='192.0.2.77')
        self.request.session={}
        self.data={'display_name':'Hiker','account_type':'individual','password1':'Test-hiker-817!','password2':'Test-hiker-817!'}

    def signup(self, **data):
        return self.client.post(reverse('signup'),{'email':self.email,'beta_code':self.code,**data})

    def token(self):
        return re.search('/accounts/setup/([^/]+)/',mail.outbox[-1].body).group(1)

    def proof(self, admission=None, email=None):
        token='proof-'+str(AccountEmailProof.objects.count())
        proof=AccountEmailProof.objects.create(email=email or self.email,purpose='signup',token_digest=digest(token),
            beta_admission=admission,expires_at=timezone.now()+timedelta(hours=1))
        return proof,token

    def test_enabled_signup_copy_missing_invalid_and_email_mismatch_are_safe(self):
        page=self.client.get(reverse('signup'))
        self.assertContains(page,'invitation-only beta');self.assertContains(page,'Beta invitation code')
        self.assertContains(self.signup(beta_code=''),'This field is required')
        for data in [{'beta_code':'invalid'},{'email':'wrong@example.invalid'}]:
            result=self.signup(**data)
            self.assertContains(result,ERROR)
            self.assertNotContains(result,self.code)
            self.assertNotContains(result,'admin@example.invalid')
        self.assertEqual(len(mail.outbox),0)
        self.assertEqual(get_user_model().objects.count(),1)

    def test_expired_revoked_and_used_share_error_and_never_mint_proof(self):
        for state in ['expired','revoked','used']:
            with self.subTest(state=state):
                self.admission.expires_at=timezone.now()-timedelta(seconds=1) if state=='expired' else timezone.now()+timedelta(days=1)
                self.admission.revoked_at=timezone.now() if state=='revoked' else None
                self.admission.redeemed_at=timezone.now() if state=='used' else None
                self.admission.save()
                OutboundEmailAttempt.objects.all().delete()
                self.assertContains(self.signup(),ERROR)
                self.assertFalse(AccountEmailProof.objects.exists())
                self.assertEqual(len(mail.outbox),0)

    def test_email_proof_required_and_redemption_at_success_not_request_or_bad_form(self):
        self.assertRedirects(self.signup(),reverse('account_email_requested'))
        self.admission.refresh_from_db();self.assertIsNone(self.admission.redeemed_at)
        self.assertEqual(get_user_model().objects.count(),1)
        token=self.token()
        self.assertEqual(AccountEmailProof.objects.get().beta_admission,self.admission)
        self.assertContains(self.client.post(reverse('complete_signup',args=[token]),{}),'This field is required')
        self.assertRedirects(self.client.post(reverse('complete_signup',args=[token]),self.data),reverse('account_interests'))
        user=get_user_model().objects.get(email=self.email)
        self.assertTrue(user.profile.email_verified_at);self.assertFalse(user.profile.activity_email_enabled)
        self.assertFalse(user.is_staff);self.assertFalse(user.is_superuser)
        self.admission.refresh_from_db();self.assertEqual(self.admission.redeemed_by,user)
        self.assertContains(self.client.post(reverse('complete_signup',args=[token]),self.data),'already used')
        self.assertEqual(get_user_model().objects.filter(email=self.email).count(),1)
        self.assertFalse(GroupMembership.objects.exists());self.assertFalse(ActivityInvitation.objects.exists())

    def test_code_cannot_substitute_for_verification_or_be_retrieved(self):
        result=self.client.post(reverse('complete_signup',args=[self.code]),self.data)
        self.assertContains(result,'expired or was already used')
        row=BetaAdmission.objects.values().get()
        self.assertNotIn(self.code,str(row));self.assertEqual(len(row['verifier']),64)
        self.assertNotEqual(row['verifier'],digest(self.code))

    @override_settings(BETA_MODE=False)
    def test_disabled_mode_ordinary_signup_and_history_untouched(self):
        self.assertNotContains(self.client.get(reverse('signup')),'Beta invitation code')
        self.assertRedirects(self.signup(beta_code=''),reverse('account_email_requested'))
        token=self.token();self.client.post(reverse('complete_signup',args=[token]),self.data)
        self.admission.refresh_from_db();self.assertIsNone(self.admission.redeemed_at)
        self.assertIsNone(AccountEmailProof.objects.get().beta_admission)

    def test_old_or_alternate_signup_proof_cannot_bypass_current_gate(self):
        proof,token=self.proof()
        self.assertContains(self.client.post(reverse('complete_signup',args=[token]),self.data),ERROR)
        self.assertFalse(get_user_model().objects.filter(email=self.email).exists())
        self.assertRedirects(self.client.post(reverse('complete_signup',args=[token]),{**self.data,'beta_code':self.code}),reverse('account_interests'))

    def test_unknown_recovery_and_provisional_verification_cannot_mint_ungated_signup(self):
        self.client.post(reverse('password_reset'),{'email':self.email})
        self.assertFalse(AccountEmailProof.objects.exists())
        user=get_user_model().objects.create_user('provisional',email=self.email,password='Old-only-817!')
        self.client.force_login(user)
        self.client.post(reverse('verification_status'),{'email':self.email})
        self.assertFalse(AccountEmailProof.objects.exists())
        OutboundEmailAttempt.objects.all().delete()
        self.client.post(reverse('verification_status'),{'email':self.email,'beta_code':self.code})
        token=self.token();complete_signup(self.request,token,self.data)
        self.admission.refresh_from_db();self.assertEqual(self.admission.redeemed_by_id,user.pk)

    def test_existing_login_recovery_and_email_verification_remain_available(self):
        self.assertRedirects(self.client.post(reverse('login'),{'username':self.admin.email,'password':'Admin-only-817!'}),reverse('activities:index'))
        self.client.logout()
        self.client.post(reverse('password_reset'),{'email':self.admin.email})
        self.assertEqual(AccountEmailProof.objects.get().purpose,'recovery')
        self.admission.refresh_from_db();self.assertIsNone(self.admission.redeemed_at)

    def test_revocation_expiry_and_failed_transaction_between_request_and_completion(self):
        proof,token=self.proof(self.admission)
        revoke(BetaAdmission.objects.filter(pk=self.admission.pk),self.admin)
        with self.assertRaisesMessage(ValidationError,ERROR):complete_signup(self.request,token,self.data)
        self.admission.revoked_at=None;self.admission.save()
        with patch('belong.beta_admission.redeem',side_effect=ValidationError('Simulated failure')):
            with self.assertRaises(ValidationError):complete_signup(self.request,token,self.data)
        self.assertFalse(get_user_model().objects.filter(email=self.email).exists())
        proof.refresh_from_db();self.assertIsNone(proof.used_at)
        self.admission.refresh_from_db();self.assertIsNone(self.admission.redeemed_at)
        complete_signup(self.request,token,self.data)

    def test_get_and_csrf_do_not_consume_code(self):
        csrf=Client(enforce_csrf_checks=True)
        self.assertEqual(csrf.post(reverse('signup'),{'email':self.email,'beta_code':self.code}).status_code,403)
        self.client.get(reverse('signup'))
        self.admission.refresh_from_db();self.assertIsNone(self.admission.redeemed_at)

    def test_invitation_bridges_bound_and_keep_only_original_rights(self):
        for kind in ['group','activity']:
            with self.subTest(kind=kind):
                email=kind+'@example.invalid'
                group=Group.objects.create(owner=self.admin,name='Private hiking details',access='private')
                activity=Activity.objects.create(host=self.admin,group=group,title='Private outing',audience='everyone')
                model=GroupInvitation if kind=='group' else ActivityEmailInvitation
                kwargs={'group':group} if kind=='group' else {'activity':activity}
                invitation=model.objects.create(**kwargs,inviter=self.admin,email=email,token_digest=digest(kind+'-token'),expires_at=timezone.now()+timedelta(days=2))
                client=Client()
                route=reverse('groups:invitation' if kind=='group' else 'activities:email_invitation',args=[kind+'-token'])
                self.assertEqual(client.post(route,{'auth':'signup'}).status_code,302)
                page=client.get(reverse('signup'));self.assertContains(page,'no separate code is needed')
                self.assertNotContains(page,'name="beta_code"')
                self.assertContains(client.post(reverse('signup'),{'email':'wrong@example.invalid'}),'Use the invited email address')
                client.post(reverse('signup'),{'email':email})
                token=self.token()
                # Complete in another browser: admission is bound to the emailed proof.
                other=Client();other.post(reverse('complete_signup',args=[token]),self.data)
                user=get_user_model().objects.get(email=email)
                self.assertTrue(user.profile.email_verified_at)
                admission=BetaAdmission.objects.get(email=email);self.assertEqual(admission.kind,kind)
                self.assertEqual(admission.redeemed_by,user)
                self.assertFalse(ActivityResponse.objects.filter(user=user).exists())
                self.assertFalse(user.is_staff)
                if kind=='group':
                    self.assertTrue(GroupMembership.objects.filter(user=user,group=group,status='active').exists())
                    self.assertFalse(ActivityInvitation.objects.filter(user=user).exists())
                else:
                    self.assertTrue(ActivityInvitation.objects.filter(user=user,activity=activity).exists())
                    self.assertFalse(GroupMembership.objects.filter(user=user).exists())
                # Existing consented session continuation still grants only invitation rights.
                client.force_login(user)
                client.get(reverse('login'))
                pending=reverse('groups:pending_invitation' if kind=='group' else 'activities:pending_email_invitation')
                client.post(pending)
                if kind=='group':self.assertTrue(GroupMembership.objects.filter(user=user,group=group,status='active').exists())
                else:
                    self.assertTrue(ActivityInvitation.objects.filter(user=user,activity=activity).exists())
                    self.assertFalse(GroupMembership.objects.filter(user=user).exists())

    def test_bridge_revoked_reissued_cancelled_or_unauthorized_after_proof_blocks_creation(self):
        group=Group.objects.create(owner=self.admin,name='Walkers',access='open')
        invitation=GroupInvitation.objects.create(group=group,inviter=self.admin,email=self.email,
            token_digest=digest('bridge'),expires_at=timezone.now()+timedelta(days=2))
        self.request.session={'pending_group_invitation':invitation.pk}
        request_account_email(self.request,self.email,'signup')
        token=self.token()
        for state in ['revoked','reissued','unauthorized']:
            with self.subTest(state=state):
                invitation.status='revoked' if state=='revoked' else 'pending'
                invitation.token_digest=digest('rotated') if state=='reissued' else digest('bridge');invitation.save()
                self.admin.profile.outbound_mail_suspended=state=='unauthorized';self.admin.profile.save()
                with self.assertRaisesMessage(ValidationError,ERROR):complete_signup(self.request,token,self.data)
                self.assertFalse(get_user_model().objects.filter(email=self.email).exists())

    def test_admin_issue_once_readonly_and_revoke_without_secret_logs(self):
        self.client.force_login(self.admin)
        response=self.client.post(reverse('admin:social_betaadmission_add'),{'email':'new@example.invalid','_save':'Save'})
        self.assertEqual(response.status_code,200)
        token=response.context['code'];admission=response.context['admission']
        self.assertIn('no-store',response['Cache-Control'])
        self.assertContains(response,token)
        self.assertNotIn(token,str(list(LogEntry.objects.values())))
        page=self.client.get(reverse('admin:social_betaadmission_change',args=[admission.pk]))
        self.assertNotContains(page,token)
        self.assertNotContains(page,admission.verifier)
        self.client.post(reverse('admin:social_betaadmission_changelist'),{'action':'revoke_selected','_selected_action':[admission.pk]})
        admission.refresh_from_db();self.assertTrue(admission.revoked_at)
        self.assertFalse(self.client.get(reverse('admin:social_betaadmission_change',args=[admission.pk])).context['has_delete_permission'])

    def test_private_activity_bridge_grants_account_but_not_audience_or_rsvp(self):
        activity=Activity.objects.create(host=self.admin,title='Private meeting',audience='friends')
        invitation=ActivityEmailInvitation.objects.create(activity=activity,inviter=self.admin,email=self.email,
            token_digest=digest('private-bridge'),expires_at=timezone.now()+timedelta(days=1))
        self.client.post(reverse('activities:email_invitation',args=['private-bridge']),{'auth':'signup'})
        self.client.post(reverse('signup'),{'email':self.email})
        self.client.post(reverse('complete_signup',args=[self.token()]),self.data)
        user=get_user_model().objects.get(email=self.email)
        self.assertEqual(self.client.get(activity.get_absolute_url()).status_code,404)
        self.assertFalse(ActivityInvitation.objects.filter(user=user).exists())
        self.assertFalse(ActivityResponse.objects.filter(user=user).exists())
        invitation.refresh_from_db();self.assertEqual(invitation.status,'pending')
        self.assertEqual(BetaAdmission.objects.get(kind='activity').redeemed_by,user)

    def test_invalid_codes_use_existing_rate_controls_and_arbitrary_context_is_rejected(self):
        session=self.client.session
        session['pending_group_invitation']=99999
        session['pending_activity_invitation']=True
        session.save()
        self.signup(beta_code='invalid')
        attempt=OutboundEmailAttempt.objects.get()
        self.assertEqual(attempt.reason,'beta_admission_required')
        self.assertNotIn(self.code,str(list(OutboundEmailAttempt.objects.values())))
        self.assertFalse(AccountEmailProof.objects.exists())
        self.signup(beta_code='invalid')
        self.assertEqual(OutboundEmailAttempt.objects.filter(reason='address_cooldown').count(),1)

    def test_disabling_after_issuance_does_not_require_or_redeem_code(self):
        proof,token=self.proof()
        with override_settings(BETA_MODE=False):complete_signup(self.request,token,self.data)
        self.admission.refresh_from_db();self.assertIsNone(self.admission.redeemed_at)

    def test_regular_user_cannot_issue_or_revoke_codes(self):
        from django.core.exceptions import PermissionDenied
        user=get_user_model().objects.create_user('ordinary',email='ordinary@example.invalid')
        with self.assertRaises(PermissionDenied):issue_code('new@example.invalid',user)
        with self.assertRaises(PermissionDenied):revoke(BetaAdmission.objects.all(),user)
        self.admission.refresh_from_db();self.assertIsNone(self.admission.revoked_at)

    def test_key_rotation_cannot_reissue_consumed_invitation_admission(self):
        from .beta_admission import resolve
        from .email_controls import lock_controls
        from django.db import transaction
        group=Group.objects.create(owner=self.admin,name='Walkers',access='open')
        invitation=GroupInvitation.objects.create(group=group,inviter=self.admin,email=self.email,
            token_digest=digest('rotation-bridge'),expires_at=timezone.now()+timedelta(days=1))
        self.request.session={'pending_group_invitation':invitation.pk}
        with transaction.atomic():
            lock_controls();admission=resolve(self.request,self.email)
        proof,token=self.proof(admission)
        complete_signup(self.request,token,self.data)
        with override_settings(SECRET_KEY='Rotated-test-key'):
            with transaction.atomic():
                lock_controls()
                with self.assertRaisesMessage(ValidationError,ERROR):resolve(self.request,self.email)
        self.assertEqual(BetaAdmission.objects.filter(kind='group').count(),1)


class BetaRedemptionRaceTests(SimpleTestCase):
    def test_file_backed_concurrent_redemption_has_one_creation(self):
        with tempfile.TemporaryDirectory() as root:
            env={**os.environ,'DJANGO_SETTINGS_MODULE':'belong.settings','BELONG_ENV':'test','BELONG_BETA_MODE':'true',
                 'DJANGO_DB_PATH':str(Path(root)/'beta.sqlite3')}
            script=r'''
import django
django.setup()
from concurrent.futures import ThreadPoolExecutor
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.db import close_old_connections
from django.utils import timezone
from datetime import timedelta
from social.models import AccountEmailProof, BetaAdmission
from belong.beta_admission import issue_code
from belong.account_email import complete_signup
from belong.email_verification import digest
from django.core.exceptions import ValidationError
call_command('migrate', verbosity=0)
admin=get_user_model().objects.create_superuser('admin',email='admin@example.invalid',password='Only-test-817!')
for run in range(3):
    email=f'race{run}@example.invalid'
    admission,code=issue_code(email,admin)
    for i in range(2):
        AccountEmailProof.objects.create(email=email,purpose='signup',beta_admission=admission,
            token_digest=digest(f'{run}-{i}'),expires_at=timezone.now()+timedelta(hours=1))
    def finish(i):
        close_old_connections()
        request=RequestFactory().post('/',REMOTE_ADDR=f'192.0.2.{run+1}');request.session={}
        try:
            complete_signup(request,f'{run}-{i}',{'display_name':'Hiker','account_type':'individual','password1':'Only-test-817!'})
            return 'created'
        except ValidationError:return 'rejected'
        finally:close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(finish,range(2)))
    assert sorted(results)==['created','rejected'],results
    assert get_user_model().objects.filter(email=email).count()==1
    admission.refresh_from_db();assert admission.redeemed_at and admission.redeemed_by_id
print('Three serialized beta redemption races passed')
'''
            result=subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,text=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)


class BetaConfigurationTests(SimpleTestCase):
    def test_production_requires_explicit_mode_and_parses_boolean(self):
        env={**os.environ,'BELONG_ENV':'production','DJANGO_SECRET_KEY':'isolated-test-only-secret'}
        env.pop('BELONG_BETA_MODE',None)
        script="import belong.settings as s; print(s.BETA_MODE)"
        result=subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertIn('Set BELONG_BETA_MODE explicitly',result.stderr)
        for value,expected in [('true','True'),('false','False')]:
            result=subprocess.run([sys.executable,'-c',script],env={**env,'BELONG_BETA_MODE':value},capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.strip(),expected)
