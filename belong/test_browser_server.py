import os
from pathlib import Path
import socket
import sys
import tempfile
from unittest.mock import patch
from urllib.request import urlopen

from django.test import SimpleTestCase

from scripts import browser_server as server


class ManagedBrowserServerTests(SimpleTestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.checkout = self.root / 'test'
        self.checkout.mkdir()
        login = self.checkout / 'accounts/login'
        login.mkdir(parents=True)
        (login / 'index.html').write_text('Ready')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        for name, value in [('ADDRESS', ('127.0.0.1', port)), ('URL', f'http://127.0.0.1:{port}')]:
            replacement = patch.object(server, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)
        command = patch.object(server, 'command', return_value=[sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'])
        command.start()
        self.addCleanup(command.stop)
        self.addCleanup(server.stop, self.root, self.checkout)

    def test_owned_server_can_be_stopped_and_replaced(self):
        server.launch(self.root, self.checkout, dict(os.environ), 'first-commit')
        first = server.read_state(server.runtime(self.root) / 'browser-test.json')
        self.assertTrue(server.owned(first, self.checkout))
        self.assertTrue(server.serves_port(first['pid']))
        self.assertTrue(server.stop(self.root, self.checkout))
        server.launch(self.root, self.checkout, dict(os.environ), 'second-commit')
        second = server.read_state(server.runtime(self.root) / 'browser-test.json')
        self.assertNotEqual(first['pid'], second['pid'])
        with urlopen(server.URL + '/accounts/login/') as response:
            self.assertEqual(response.read(), b'Ready')
        self.assertEqual(second['commit'], 'second-commit')

    def test_unknown_listener_is_not_killed_even_with_stale_pid_state(self):
        state = {'pid': os.getpid(), 'identity': server.identity(os.getpid()), 'commit': 'stale'}
        server.write_state(server.runtime(self.root) / 'browser-test.json', state)
        with socket.socket() as sock:
            sock.bind(server.ADDRESS)
            sock.listen()
            with patch.object(server.os, 'kill') as kill, patch.object(server.signal, 'pidfd_send_signal') as pinned_signal:
                self.assertFalse(server.stop(self.root, self.checkout))
                with self.assertRaisesMessage(ValueError, 'unknown process'):
                    server.require_free_port()
                kill.assert_not_called()
                pinned_signal.assert_not_called()
            self.assertEqual(sock.getsockname(), server.ADDRESS)

    def test_reused_pid_start_time_is_not_trusted(self):
        server.launch(self.root, self.checkout, dict(os.environ), 'preview')
        path = server.runtime(self.root) / 'browser-test.json'
        original = server.read_state(path)
        stale = {**original, 'identity': {**original['identity'], 'started': '0'}}
        server.write_state(path, stale)
        with patch.object(server.os, 'kill') as kill, patch.object(server.signal, 'pidfd_send_signal') as pinned_signal:
            self.assertFalse(server.stop(self.root, self.checkout))
            kill.assert_not_called()
            pinned_signal.assert_not_called()
        server.write_state(path, original)  # Restore genuine state for cleanup.

    def test_failed_startup_leaves_no_pid_state(self):
        with patch.object(server, 'command', return_value=[sys.executable, '-c', 'raise SystemExit(1)']):
            with self.assertRaisesMessage(ValueError, 'startup'):
                server.launch(self.root, self.checkout, dict(os.environ), 'failed')
        self.assertIsNone(server.read_state(server.runtime(self.root) / 'browser-test.json'))

    def test_http_readiness_failure_stops_child_and_removes_state(self):
        (self.checkout / 'accounts/login/index.html').unlink()
        (self.checkout / 'accounts/login').rmdir()
        with self.assertRaisesMessage(ValueError, 'did not become ready'):
            server.launch(self.root, self.checkout, dict(os.environ), 'failed', timeout=0.5)
        self.assertIsNone(server.read_state(server.runtime(self.root) / 'browser-test.json'))
        server.require_free_port()
