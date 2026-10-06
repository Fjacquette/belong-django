import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings

from belong.environment import CONFIG_KEYS, config_bool, read_local_config
from media_assets.images import normalized_avatar


class ConfigurationSecurityTests(SimpleTestCase):
    def test_missing_environment_fails_closed_and_invalid_environment_names_key(self):
        env = {k: v for k, v in os.environ.items() if k not in CONFIG_KEYS}
        env['DJANGO_SECRET_KEY'] = 'isolated-settings-test-only-key'
        code = "from unittest.mock import patch\nwith patch('belong.environment.read_local_config', return_value={}):\n import belong.settings as s\n assert not s.DEBUG and not s.ALLOW_LEGACY_ACCOUNTS\n"
        result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        env['BELONG_ENV'] = 'typo'
        result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('BELONG_ENV', result.stderr)

    def test_mail_and_legacy_settings_round_trip_and_errors_name_key_not_value(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / '.env.local'
            path.write_text('DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend\nDJANGO_DEFAULT_FROM_EMAIL="Belong <noreply@example.com>"\nBELONG_ALLOW_LEGACY_ACCOUNTS=false\n')
            config = read_local_config(path)
            self.assertEqual(config['DJANGO_DEFAULT_FROM_EMAIL'], 'Belong <noreply@example.com>')
            self.assertFalse(config_bool(config['BELONG_ALLOW_LEGACY_ACCOUNTS'], key='BELONG_ALLOW_LEGACY_ACCOUNTS'))
            for value in ['DJANGO_SECRET_KEY secret-value', 'UNKNOWN_KEY=secret-value', 'DJANGO_DEFAULT_FROM_EMAIL="secret-value', 'DJANGO_DEFAULT_FROM_EMAIL=secret value']:
                path.write_text(value)
                with self.assertRaises(ValueError) as error:
                    read_local_config(path)
                self.assertIn(value.split('=')[0].split()[0], str(error.exception))
                self.assertNotIn('secret-value', str(error.exception))
        with self.assertRaisesRegex(ValueError, 'BELONG_ALLOW_LEGACY_ACCOUNTS'):
            config_bool('typo', key='BELONG_ALLOW_LEGACY_ACCOUNTS')

    def test_large_avatar_rejected_before_verify_or_decode(self):
        source = MagicMock()
        source.width, source.height = 5001, 5000
        with patch('media_assets.images.Image.open') as opened:
            opened.return_value.__enter__.return_value = source
            with self.assertRaisesRegex(ValidationError, '25 million pixels'):
                normalized_avatar(SimpleUploadedFile('large.png', b'compressed-image'))
        source.verify.assert_not_called()
        source.load.assert_not_called()

    def test_file_backed_sqlite_concurrent_proof_consumption_is_one_time(self):
        # Shared-cache in-memory SQLite raises SQLITE_LOCKED rather than honoring
        # busy_timeout. Exercise the supported file-backed runtime in isolation.
        with tempfile.TemporaryDirectory() as root:
            env = {**os.environ, 'DJANGO_SETTINGS_MODULE': 'belong.settings', 'DJANGO_DB_PATH': str(Path(root)/'concurrency.sqlite3')}
            code = '''
import django
django.setup()
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connections
from django.utils import timezone
from belong.email_verification import confirm_email, digest
from social.models import EmailVerification
call_command('migrate', verbosity=0)
assert connections['default'].settings_dict['OPTIONS']['transaction_mode'] == 'IMMEDIATE'
u = get_user_model().objects.create_user('concurrent-proof', email='concurrent@example.com')
u.profile.email_verified_at = timezone.now()
u.profile.pending_email = u.email
u.profile.save(update_fields=['pending_email', 'email_verified_at'])
EmailVerification.objects.create(user=u, email=u.email, token_digest=digest('isolated-proof'), expires_at=timezone.now()+timedelta(hours=1))
barrier = Barrier(2)
def consume(_):
    barrier.wait(timeout=10)
    try:
        confirm_email('isolated-proof')
        return 'confirmed'
    except ValidationError:
        return 'already-used'
    finally:
        connections.close_all()
with ThreadPoolExecutor(max_workers=2) as pool:
    outcomes = list(pool.map(consume, range(2)))
assert sorted(outcomes) == ['already-used', 'confirmed'], outcomes
'''
            result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=40)
            self.assertEqual(result.returncode, 0, result.stderr)


class ProvisioningSecurityTests(TestCase):
    @override_settings(ALLOW_LEGACY_ACCOUNTS=True)
    def test_new_users_never_gain_legacy_access_by_username(self):
        for name in ['ordinary-name', 'u_opaque-name']:
            user = get_user_model().objects.create_user(name)
            self.assertFalse(user.profile.legacy_access)
            self.assertFalse(user.profile.can_use_belong)
