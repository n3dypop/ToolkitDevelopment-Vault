"""Regression tests use disposable fixtures and never access real agent settings."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


sync = module('vault_sync', 'sync-agents.py')
checker = module('vault_check', 'check-vault.py')


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='vault tests ')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.workspace = self.root / 'Toolkit'
        self.repo = self.workspace / 'vault with spaces'
        self.repo.mkdir(parents=True)
        self.canonical = self.repo / 'AGENTS.md'
        self.copy = self.workspace / 'AGENTS.md'
        self.data = '# 指針\n\n変更範囲を守る。\n'.encode()
        self.canonical.write_bytes(self.data)

    def run_sync(self, mode, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            sync.synchronize(self.repo, mode, **kwargs)

    def snapshot(self):
        return {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_check_missing_and_drift_are_read_only(self):
        for initial in (None, b'# Different\n'):
            if initial is not None:
                self.copy.write_bytes(initial)
            before = self.snapshot()
            with self.assertRaises(ValueError):
                self.run_sync('Check')
            self.assertEqual(before, self.snapshot())

    def test_create_check_and_repeat_do_not_make_backups(self):
        self.run_sync('RepoToWorkspace')
        self.run_sync('Check')
        self.assertEqual(self.copy.read_bytes(), self.data)
        before = self.copy.stat().st_mtime_ns
        self.run_sync('RepoToWorkspace')
        self.assertEqual(before, self.copy.stat().st_mtime_ns)
        self.assertEqual([], list(self.root.rglob('*.bak')))

    def test_reverse_sync_preserves_exact_previous_bytes(self):
        edited = b'\xef\xbb\xbf# Edited\r\n'
        self.copy.write_bytes(edited)
        self.run_sync('WorkspaceToRepo')
        self.assertEqual(edited, self.canonical.read_bytes())
        backups = list(self.repo.glob('*.bak'))
        self.assertEqual(1, len(backups))
        self.assertEqual(self.data, backups[0].read_bytes())
        self.run_sync('Check')

    def test_overwrite_creates_distinct_backups(self):
        self.copy.write_bytes(b'# Old\n')
        self.run_sync('RepoToWorkspace')
        self.canonical.write_bytes(b'# New\n')
        self.run_sync('RepoToWorkspace')
        contents = {p.read_bytes() for p in self.workspace.glob('*.bak')}
        self.assertEqual({b'# Old\n', self.data}, contents)

    def test_dry_run_does_not_write_or_create(self):
        for initial in (None, b'# Old\n'):
            if initial is not None:
                self.copy.write_bytes(initial)
            before = self.snapshot()
            self.run_sync('RepoToWorkspace', dry_run=True)
            self.assertEqual(before, self.snapshot())

    def test_unrelated_parent_and_settings_are_untouched(self):
        outside = self.root / 'AGENTS.md'
        outside.write_bytes(b'# Unrelated\n')
        self.run_sync('RepoToWorkspace')
        self.assertEqual(b'# Unrelated\n', outside.read_bytes())
        self.assertFalse((self.root / '.codex').exists())

    def test_ambiguous_location_requires_explicit_root(self):
        other = self.root / 'Elsewhere'
        other.mkdir()
        (other / 'AGENTS.md').write_bytes(self.data)
        with self.assertRaises(ValueError):
            self.run_sync('Check', workspace_root=self.repo)
        with self.assertRaises(ValueError):
            sync.synchronize(other, 'RepoToWorkspace')
        with contextlib.redirect_stdout(io.StringIO()):
            sync.synchronize(other, 'RepoToWorkspace', self.workspace)
        self.assertEqual(self.data, self.copy.read_bytes())

    def test_invalid_destination_and_source_are_not_overwritten(self):
        for data in (b'', b'\xff', b'# Bad\x00\n'):
            with self.subTest(data=data):
                self.copy.write_bytes(data)
                with self.assertRaises(ValueError):
                    self.run_sync('RepoToWorkspace')
                self.assertEqual(data, self.copy.read_bytes())
                with self.assertRaises(ValueError):
                    self.run_sync('WorkspaceToRepo')
                self.assertEqual(self.data, self.canonical.read_bytes())

    def test_hardlink_is_rejected(self):
        os.link(self.canonical, self.copy)
        with self.assertRaises(ValueError):
            self.run_sync('RepoToWorkspace')
        self.assertEqual(self.data, self.copy.read_bytes())

    def test_symlink_is_rejected(self):
        try:
            self.copy.symlink_to(self.canonical)
        except OSError:
            self.skipTest('Symlink creation is unavailable on this host')
        with self.assertRaises(ValueError):
            self.run_sync('RepoToWorkspace')
        self.assertTrue(self.copy.is_symlink())

    def test_failed_atomic_replace_keeps_destination_and_backup(self):
        old = b'# Old\n'
        self.copy.write_bytes(old)
        with mock.patch.object(sync.os, 'replace', side_effect=OSError('injected failure')):
            with self.assertRaises(OSError):
                self.run_sync('RepoToWorkspace')
        self.assertEqual(old, self.copy.read_bytes())
        self.assertEqual([old], [p.read_bytes() for p in self.workspace.glob('*.bak')])
        self.assertEqual([], list(self.workspace.glob('.AGENTS.md.sync-*')))

    def test_concurrent_edit_is_rejected(self):
        self.copy.write_bytes(b'# Another edit\n')
        with self.assertRaises(ValueError):
            sync.replace_file(self.copy, self.data, b'# Stale snapshot\n')
        self.assertEqual(b'# Another edit\n', self.copy.read_bytes())
        self.assertEqual([], list(self.workspace.glob('*.bak')))

    @unittest.skipIf(os.name == 'nt', 'POSIX permission semantics')
    def test_destination_permissions_are_preserved(self):
        self.copy.write_bytes(b'# Old\n')
        self.copy.chmod(0o600)
        self.run_sync('RepoToWorkspace')
        self.assertEqual(0o600, self.copy.stat().st_mode & 0o777)

    def cli_fixture(self):
        scripts = self.repo / 'scripts'
        scripts.mkdir()
        for name in ('sync-agents.py', 'sync-agents.sh', 'sync-agents.ps1'):
            shutil.copy2(SCRIPTS / name, scripts / name)
        return scripts

    def test_cli_from_unrelated_working_directory(self):
        scripts = self.cli_fixture()
        command = [sys.executable, str(scripts / 'sync-agents.py')]
        self.assertNotEqual(0, subprocess.run(command, cwd=self.root, capture_output=True).returncode)
        result = subprocess.run(command + ['--mode', 'RepoToWorkspace'], cwd=self.root, capture_output=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(self.data, self.copy.read_bytes())
        self.assertEqual(0, subprocess.run(command, cwd=self.root, capture_output=True).returncode)

    @unittest.skipIf(os.name == 'nt', 'POSIX shell wrapper')
    def test_shell_wrapper(self):
        scripts = self.cli_fixture()
        result = subprocess.run(['sh', str(scripts / 'sync-agents.sh'), '--mode', 'RepoToWorkspace'],
                                cwd=self.root, capture_output=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(self.data, self.copy.read_bytes())

    @unittest.skipUnless(shutil.which('pwsh'), 'PowerShell 7 is not installed')
    def test_powershell_wrapper_success_and_failure(self):
        scripts = self.cli_fixture()
        command = ['pwsh', '-NoProfile', '-File', str(scripts / 'sync-agents.ps1')]
        self.assertNotEqual(0, subprocess.run(command, cwd=self.root, capture_output=True).returncode)
        result = subprocess.run(command + ['-Mode', 'RepoToWorkspace'], cwd=self.root, capture_output=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(self.data, self.copy.read_bytes())


class MarkdownTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / 'HOME.md').write_text('# Home\n', encoding='utf-8')

    def errors(self):
        return checker.inspect_markdown(self.root)[1]

    def test_fences_do_not_count_headings_or_example_links(self):
        (self.root / 'HOME.md').write_text('# Home\n\n````md\n# Example\n```\n[example](missing.md)\n````\n', encoding='utf-8')
        self.assertEqual([], self.errors())

    def test_broken_link_and_escaped_target_are_detected(self):
        (self.root / 'HOME.md').write_text('# Home\n\n[missing](missing.md)\n[escape](../outside.md)\n', encoding='utf-8')
        errors = self.errors()
        self.assertTrue(any('broken link' in item for item in errors))
        self.assertTrue(any('escapes vault' in item for item in errors))

    def test_active_document_must_be_reachable(self):
        (self.root / 'guide.md').write_text('---\nstatus: active\n---\n# Guide\n', encoding='utf-8')
        self.assertTrue(any('unreachable' in item for item in self.errors()))
        (self.root / 'HOME.md').write_text('# Home\n\n[Guide](guide.md)\n', encoding='utf-8')
        self.assertEqual([], self.errors())

    def test_paths_whitespace_and_unclosed_fence_are_reported_without_contents(self):
        windows = 'Q:' + chr(92) + 'example'
        (self.root / 'HOME.md').write_text('# Home  \n\n/Users/example/file\n' + windows + '\n```\n', encoding='utf-8')
        errors = self.errors()
        self.assertEqual(4, len(errors))
        self.assertFalse(any('/Users/example/file' in item or windows in item for item in errors))


if __name__ == '__main__':
    unittest.main()
