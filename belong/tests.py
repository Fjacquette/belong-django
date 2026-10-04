import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

from django.test import SimpleTestCase

from .environment import config_bool, read_local_config
from scripts.local_env import (
    database_path,
    git_output,
    initialize_local_config,
    local_environment,
    refresh_test,
    start,
    test_checkout as browser_checkout,
)


class LocalConfigurationTests(SimpleTestCase):
    def test_reads_quoted_values_and_comments_without_shell_expansion(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env.local"
            path.write_text(
                '# Local settings\nBELONG_ENV=test\nDJANGO_DEBUG=false # comment\n'
                'DJANGO_DB_PATH="data/browser test.sqlite3"\n'
                'DJANGO_SECRET_KEY="literal-$HOME-$(whoami)"\n'
            )
            config = read_local_config(path)
            self.assertEqual(config["BELONG_ENV"], "test")
            self.assertFalse(config_bool(config["DJANGO_DEBUG"]))
            self.assertEqual(config["DJANGO_DB_PATH"], "data/browser test.sqlite3")
            self.assertEqual(config["DJANGO_SECRET_KEY"], "literal-$HOME-$(whoami)")

    def test_invalid_configuration_fails_without_echoing_secret_values(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env.local"
            for line in ("UNKNOWN=private-value", 'DJANGO_SECRET_KEY="private-value'):
                with self.subTest(line=line):
                    path.write_text(line)
                    with self.assertRaises(ValueError) as error:
                        read_local_config(path)
                    self.assertNotIn("private-value", str(error.exception))
        with self.assertRaises(ValueError):
            config_bool("maybe")

    def test_bootstrap_preserves_existing_config_database_and_key(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            initialize_local_config(root, "dev")
            (root / "db.sqlite3").write_bytes(b"persistent local data")
            files = [root / name for name in (".env.local", ".django-secret-key", "db.sqlite3")]
            original = [path.read_bytes() for path in files]
            initialize_local_config(root, "dev")
            self.assertEqual([path.read_bytes() for path in files], original)
            for path in files[:2]:
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_launcher_isolates_test_from_inherited_dev_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checkout = root / "test"
            checkout.mkdir()
            initialize_local_config(root, "dev")
            initialize_local_config(checkout, "test")
            with patch.dict(os.environ, {
                "BELONG_ENV": "dev", "DJANGO_DB_PATH": str(root / "db.sqlite3"),
                "DJANGO_SECRET_KEY": "inherited-dev-key", "VIRTUAL_ENV": "dev-venv",
                "UV_PROJECT_ENVIRONMENT": "dev-venv", "DJANGO_SETTINGS_MODULE": "other.settings",
            }):
                env = local_environment(checkout, "test")
            self.assertEqual(env["BELONG_ENV"], "test")
            self.assertNotIn("DJANGO_SECRET_KEY", env)
            self.assertNotIn("VIRTUAL_ENV", env)
            self.assertNotIn("UV_PROJECT_ENVIRONMENT", env)
            self.assertEqual(env["DJANGO_SETTINGS_MODULE"], "belong.settings")
            self.assertNotEqual(database_path(root, {}), database_path(checkout, env))
            self.assertNotEqual(
                (root / ".django-secret-key").read_bytes(),
                (checkout / ".django-secret-key").read_bytes(),
            )

    def test_settings_load_local_file_and_allow_process_overrides(self):
        source = Path(__file__).with_name("settings.py").read_text()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            package = root / "belong"
            package.mkdir()
            settings = package / "settings.py"
            settings.write_text(source)
            initialize_local_config(root, "test")

            def load(env):
                with patch.dict(os.environ, env, clear=True):
                    spec = importlib.util.spec_from_file_location("belong.config_validation", settings)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    return module

            local = load({})
            self.assertEqual(local.ENVIRONMENT, "test")
            self.assertTrue(local.DEBUG)
            self.assertEqual(local.DATABASES["default"]["NAME"], root / "db.sqlite3")
            self.assertIn("127.0.0.1", local.ALLOWED_HOSTS)
            overridden = load({
                "BELONG_ENV": "dev", "DJANGO_DEBUG": "false",
                "DJANGO_ALLOWED_HOSTS": "localhost, example.invalid",
                "DJANGO_DB_PATH": "data/dev.sqlite3", "DJANGO_SECRET_KEY": "validation-key",
            })
            self.assertFalse(overridden.DEBUG)
            self.assertEqual(overridden.ALLOWED_HOSTS, ["localhost", "example.invalid"])
            self.assertEqual(overridden.DATABASES["default"]["NAME"], root / "data/dev.sqlite3")
            self.assertEqual(overridden.SECRET_KEY, "validation-key")
            self.assertNotEqual(local.SESSION_COOKIE_NAME, overridden.SESSION_COOKIE_NAME)
            self.assertNotEqual(local.CSRF_COOKIE_NAME, overridden.CSRF_COOKIE_NAME)


class BrowserWorktreeTests(SimpleTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.origin = root / "origin"
        self.repo = root / "dev"
        self.origin.mkdir()
        self.git(self.origin, "init", "-b", "master")
        self.git(self.origin, "config", "user.name", "Local Test")
        self.git(self.origin, "config", "user.email", "test@example.invalid")
        (self.origin / ".gitignore").write_text(".worktrees/\n.env.local\n.django-secret-key\n*.sqlite3\n")
        (self.origin / "source.txt").write_text("initial master\n")
        self.git(self.origin, "add", ".")
        self.git(self.origin, "commit", "-m", "Initial master")
        self.git(root, "clone", str(self.origin), str(self.repo))
        self.git(self.repo, "switch", "-c", "feature-under-development")

    def git(self, root, *args):
        return subprocess.run(
            ["git", *args], cwd=root, check=True, capture_output=True, text=True
        ).stdout.strip()

    def advance_master(self):
        (self.origin / "source.txt").write_text("updated master\n")
        self.git(self.origin, "commit", "-am", "Update master")

    def test_refresh_updates_only_test_and_preserves_persistent_local_files(self):
        refresh_test(self.repo)
        checkout = browser_checkout(self.repo)
        (checkout / "db.sqlite3").write_bytes(b"persistent browser data")
        local_files = [checkout / name for name in (".env.local", ".django-secret-key", "db.sqlite3")]
        original = [path.read_bytes() for path in local_files]
        dev_head = git_output(self.repo, "rev-parse", "HEAD")
        (self.repo / "source.txt").write_text("unfinished dev work\n")
        self.advance_master()

        refresh_test(self.repo)

        self.assertEqual(git_output(checkout, "rev-parse", "HEAD"), git_output(self.origin, "rev-parse", "HEAD"))
        self.assertEqual(git_output(checkout, "rev-parse", "@{upstream}"), git_output(checkout, "rev-parse", "HEAD"))
        self.assertEqual(git_output(self.repo, "rev-parse", "HEAD"), dev_head)
        self.assertEqual(git_output(self.repo, "branch", "--show-current"), "feature-under-development")
        self.assertEqual((self.repo / "source.txt").read_text(), "unfinished dev work\n")
        self.assertEqual([path.read_bytes() for path in local_files], original)

    def test_refresh_refuses_to_overwrite_test_source_changes(self):
        refresh_test(self.repo)
        checkout = browser_checkout(self.repo)
        (checkout / "source.txt").write_text("unsaved test work\n")
        head = git_output(checkout, "rev-parse", "HEAD")
        self.advance_master()

        with self.assertRaisesMessage(ValueError, "source changes"):
            refresh_test(self.repo)

        self.assertEqual(git_output(checkout, "rev-parse", "HEAD"), head)
        self.assertEqual((checkout / "source.txt").read_text(), "unsaved test work\n")

    def test_refresh_refuses_to_discard_local_test_commits(self):
        refresh_test(self.repo)
        checkout = browser_checkout(self.repo)
        self.git(checkout, "config", "user.name", "Local Test")
        self.git(checkout, "config", "user.email", "test@example.invalid")
        (checkout / "source.txt").write_text("committed test work\n")
        self.git(checkout, "commit", "-am", "Local test work")
        head = git_output(checkout, "rev-parse", "HEAD")

        with self.assertRaisesMessage(ValueError, "local commits"):
            refresh_test(self.repo)

        self.assertEqual(git_output(checkout, "rev-parse", "HEAD"), head)

    def test_refresh_preserves_ignored_local_file_if_master_starts_tracking_it(self):
        refresh_test(self.repo)
        checkout = browser_checkout(self.repo)
        path = checkout / ".env.local"
        original = path.read_bytes()
        head = git_output(checkout, "rev-parse", "HEAD")
        (self.origin / ".env.local").write_text("BELONG_ENV=unexpected\n")
        self.git(self.origin, "add", "-f", ".env.local")
        self.git(self.origin, "commit", "-m", "Conflicting tracked config")

        with self.assertRaises(subprocess.CalledProcessError):
            refresh_test(self.repo)

        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(git_output(checkout, "rev-parse", "HEAD"), head)

    def test_launchers_reject_shared_database_before_running_django(self):
        refresh_test(self.repo)
        initialize_local_config(self.repo, "dev")
        checkout = browser_checkout(self.repo)
        shared_db = self.repo / "db.sqlite3"
        shared_db.write_bytes(b"preserve this data")
        (checkout / ".env.local").write_text(
            f'BELONG_ENV=test\nDJANGO_DB_PATH="{shared_db}"\n'
        )
        for environment in ("dev", "test"):
            with self.subTest(environment=environment):
                with self.assertRaisesMessage(ValueError, "separate database"):
                    start(self.repo, environment)
                self.assertEqual(shared_db.read_bytes(), b"preserve this data")
