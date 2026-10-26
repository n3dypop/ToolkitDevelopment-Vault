"""Regression tests use disposable fixtures and never access real agent settings."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parent


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


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
        self.engine = os.environ.get('VAULT_SYNC_ENGINE', 'pwsh' if os.name == 'nt' else 'sh')
        self.cli_fixture()

    def command(self, mode='Check', workspace_root=None, dry_run=False, repo=None):
        scripts = (repo or self.repo) / 'scripts'
        if self.engine == 'pwsh':
            command = ['pwsh', '-NoProfile', '-File', str(scripts / 'sync-agents.ps1')]
        else:
            command = ['sh', str(scripts / 'sync-agents.sh')]
        command += ['-Mode', mode]
        if workspace_root is not None:
            command += ['-WorkspaceRoot', str(workspace_root)]
        if dry_run:
            command += ['-DryRun']
        return command

    def run_sync(self, mode, **kwargs):
        environment = kwargs.pop('environment', None)
        result = subprocess.run(self.command(mode, **kwargs), cwd=self.root,
                                capture_output=True, env=environment)
        if result.returncode:
            raise ValueError(result.stderr.decode(errors='replace'))
        return result

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
        self.cli_fixture(other)
        with self.assertRaises(ValueError):
            self.run_sync('Check', workspace_root=self.repo)
        with self.assertRaises(ValueError):
            self.run_sync('RepoToWorkspace', repo=other)
        self.run_sync('RepoToWorkspace', repo=other, workspace_root=self.workspace)
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

    def injected_command(self, name, text):
        if self.engine != 'sh':
            self.skipTest('POSIX command fault injection')
        directory = self.root / 'fake-bin'
        directory.mkdir()
        program = directory / name
        program.write_text('#!/bin/sh\n' + text, encoding='utf-8')
        program.chmod(0o755)
        environment = os.environ.copy()
        environment['PATH'] = str(directory) + os.pathsep + environment['PATH']
        return environment

    def test_failed_atomic_replace_keeps_destination_and_backup(self):
        old = b'# Old\n'
        self.copy.write_bytes(old)
        environment = self.injected_command('mv', 'exit 1\n')
        with self.assertRaises(ValueError):
            self.run_sync('RepoToWorkspace', environment=environment)
        self.assertEqual(old, self.copy.read_bytes())
        self.assertEqual([old], [p.read_bytes() for p in self.workspace.glob('*.bak')])
        self.assertEqual([], list(self.workspace.glob('.agents-sync.*')))

    def test_concurrent_edit_is_rejected(self):
        self.copy.write_bytes(b'# Before\n')
        environment = self.injected_command('cp', """
"$VAULT_TEST_REAL_CP" "$@" || exit 1
for argument do last=$argument; done
case $last in */replacement) printf '# Concurrent edit\\n' > "$VAULT_TEST_DESTINATION" ;; esac
""")
        environment['VAULT_TEST_REAL_CP'] = shutil.which('cp')
        environment['VAULT_TEST_DESTINATION'] = str(self.copy)
        with self.assertRaises(ValueError):
            self.run_sync('RepoToWorkspace', environment=environment)
        self.assertEqual(b'# Concurrent edit\n', self.copy.read_bytes())
        self.assertEqual([], list(self.workspace.glob('*.bak')))

    def test_directory_destination_is_rejected(self):
        self.copy.mkdir()
        with self.assertRaises(ValueError):
            self.run_sync('RepoToWorkspace')
        self.assertTrue(self.copy.is_dir())
        self.assertEqual([], list(self.copy.iterdir()))

    @unittest.skipIf(os.name == 'nt', 'POSIX permission semantics')
    def test_destination_permissions_are_preserved(self):
        if self.engine != 'sh':
            self.skipTest('POSIX shell permission preservation')
        self.copy.write_bytes(b'# Old\n')
        self.copy.chmod(0o600)
        self.run_sync('RepoToWorkspace')
        self.assertEqual(0o600, self.copy.stat().st_mode & 0o777)

    def cli_fixture(self, repo=None):
        scripts = (repo or self.repo) / 'scripts'
        scripts.mkdir(exist_ok=True)
        for name in ('sync-agents.sh', 'sync-agents.ps1'):
            shutil.copy2(SCRIPTS / name, scripts / name)
        return scripts

    def test_cli_from_unrelated_working_directory(self):
        self.assertNotEqual(0, subprocess.run(self.command(), cwd=self.root, capture_output=True).returncode)
        self.run_sync('RepoToWorkspace')
        self.assertEqual(self.data, self.copy.read_bytes())
        self.assertEqual(0, subprocess.run(self.command(), cwd=self.root, capture_output=True).returncode)

    def test_missing_workspace_is_not_created(self):
        absent = self.root / 'missing workspace'
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.run_sync('RepoToWorkspace', workspace_root=absent)
        self.assertFalse(absent.exists())
        self.assertEqual(before, self.snapshot())

    def test_sync_does_not_invoke_python(self):
        directory = self.root / 'no-python'
        directory.mkdir()
        marker = self.root / 'python-was-called'
        for name in ('python', 'python3', 'py'):
            if os.name == 'nt':
                program = directory / (name + '.cmd')
                program.write_text('@echo called > "%VAULT_TEST_MARKER%"\n@exit /b 99\n')
            else:
                program = directory / name
                program.write_text('#!/bin/sh\nprintf called > "$VAULT_TEST_MARKER"\nexit 99\n')
                program.chmod(0o755)
        environment = os.environ.copy()
        environment['PATH'] = str(directory) + os.pathsep + environment['PATH']
        environment['VAULT_TEST_MARKER'] = str(marker)
        self.run_sync('RepoToWorkspace', environment=environment)
        self.run_sync('Check', environment=environment)
        self.assertFalse(marker.exists())
        self.assertEqual(self.data, self.copy.read_bytes())

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            self.run_sync('UnknownMode')
        self.assertFalse(self.copy.exists())


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
