import unittest
from unittest.mock import Mock, patch
from headroom_proxy.core import Settings
import headroom_proxy.core as core

class LifecycleTests(unittest.TestCase):
    def test_autostart_disabled_never_probes_or_spawns(self):
        probe=Mock()
        m=core.ProxyManager(Settings(autostart=False), probe=probe)
        self.assertEqual(m.ensure()['state'], 'disabled')
        probe.assert_not_called()

    def test_reuses_verified_headroom_without_ownership(self):
        with patch.object(core.subprocess, 'Popen') as popen:
            m=core.ProxyManager(Settings(), probe=lambda: {'service':'headroom-proxy','status':'healthy'})
            self.assertEqual(m.ensure()['state'], 'external')
            m.close()
            popen.assert_not_called()

    def test_unknown_port_occupant_never_spawned_or_killed(self):
        with patch.object(core.subprocess, 'Popen') as popen:
            m=core.ProxyManager(Settings(), probe=lambda: {'service':'other'})
            self.assertEqual(m.ensure()['state'], 'conflict')
            m.close()
            popen.assert_not_called()

    def test_owned_process_started_once_and_only_it_is_closed(self):
        probes=iter([None, {'service':'headroom-proxy','status':'healthy'}])
        process=Mock(); process.poll.return_value=None
        with patch.object(core.subprocess, 'Popen', return_value=process) as popen:
            m=core.ProxyManager(Settings(), probe=lambda: next(probes))
            self.assertEqual(m.ensure()['state'], 'owned')
            self.assertEqual(m.ensure()['state'], 'owned')
            self.assertEqual(popen.call_count, 1)
            self.assertIn('--stateless', popen.call_args.args[0])
            m.close()
            process.terminate.assert_called_once()

    def test_timeout_cleans_only_owned_process(self):
        process=Mock(); process.poll.return_value=None
        with patch.object(core.subprocess, 'Popen', return_value=process), patch.object(core.time, 'monotonic', side_effect=[0,0,2]):
            m=core.ProxyManager(Settings(startup_timeout=1), probe=lambda: None)
            self.assertEqual(m.ensure()['state'], 'error')
            process.terminate.assert_called_once()

    def test_python_runtime_avoids_windows_launcher_pid_indirection(self):
        probes=iter([None, {'service':'headroom-proxy','status':'healthy'}])
        process=Mock(); process.poll.return_value=None
        with patch.object(core.subprocess, 'Popen', return_value=process) as popen:
            m=core.ProxyManager(Settings(executable='C:/runtime/python.exe'),probe=lambda:next(probes))
            self.assertEqual(m.ensure()['state'],'owned')
            self.assertEqual(popen.call_args.args[0][:4],['C:/runtime/python.exe','-m','headroom.cli','proxy'])
            self.assertEqual(popen.call_args.kwargs['env']['HEADROOM_BEACON'],'off')
            m.close()

    def test_health_pid_may_be_a_verified_windows_child(self):
        probes=iter([None, {'service':'headroom-proxy','status':'healthy','config':{'pid':99}}])
        process=Mock(); process.poll.return_value=None
        with patch.object(core.subprocess,'Popen',return_value=process), patch.object(core,'is_process_descendant',return_value=True) as descendant:
            m=core.ProxyManager(Settings(),probe=lambda:next(probes))
            self.assertEqual(m.ensure()['state'],'owned')
            descendant.assert_called_once_with(99,process.pid)
            m.close()

    def test_external_runtime_does_not_inherit_hermes_pythonpath(self):
        probes=iter([None, {'service':'headroom-proxy','status':'healthy'}])
        process=Mock(); process.poll.return_value=None
        with patch.dict(core.os.environ, {'PYTHONPATH':'hermes-cp314-packages','PYTHONHOME':'hermes-runtime'}), patch.object(core.subprocess,'Popen',return_value=process) as popen:
            m=core.ProxyManager(Settings(executable='C:/runtime/python.exe'),probe=lambda:next(probes))
            self.assertEqual(m.ensure()['state'],'owned')
            self.assertNotIn('PYTHONPATH', popen.call_args.kwargs['env'])
            self.assertNotIn('PYTHONHOME', popen.call_args.kwargs['env'])
            m.close()

    def test_child_failure_preserves_sanitized_stderr(self):
        import io
        process=Mock(); process.poll.return_value=1
        process.stderr=io.BytesIO(b'ModuleNotFoundError: missing package\nAuthorization: Bearer secret-value\n')
        with patch.object(core.subprocess,'Popen',return_value=process):
            m=core.ProxyManager(Settings(),probe=lambda:None)
            result=m.ensure()
            self.assertIn('ModuleNotFoundError', result['stderr_tail'])
            self.assertNotIn('secret-value', str(result))
            self.assertEqual(result['exit_code'],1)

    def test_executable_failure_is_redacted(self):
        with patch.object(core.subprocess, 'Popen', side_effect=OSError('sensitive text')):
            m=core.ProxyManager(Settings(), probe=lambda:None)
            self.assertEqual(m.ensure()['state'],'error')
            self.assertNotIn('sensitive', str(m.status()))
