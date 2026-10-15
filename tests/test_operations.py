import unittest
from headroom_proxy.core import Settings, ProxyManager

class OperationsTests(unittest.TestCase):
    def test_probe_failure_is_redacted_and_nonfatal(self):
        def fail():
            raise PermissionError('secret-do-not-return')
        report=ProxyManager(Settings(),probe=fail).ensure()
        self.assertEqual(report['state'],'error')
        self.assertEqual(report['error'],'PermissionError')
        self.assertNotIn('secret-do-not-return',str(report))

    def test_diagnostic_exposes_capabilities_not_credentials(self):
        manager=ProxyManager(Settings(), probe=lambda:{'service':'headroom-proxy','status':'healthy','config':{'anthropic_api_url':None,'backend':'anthropic','secret':'DO-NOT-RETURN'}})
        report=manager.diagnostic()
        self.assertFalse(report['destinations']['openai-codex']['supported'])
        self.assertTrue(report['destinations']['hermes-native-claude']['supported'])
        self.assertFalse(report['destinations']['hermes-native-claude']['enabled'])
        self.assertTrue(report['destinations']['claude-cli']['upstream_verified'])
        self.assertNotIn('DO-NOT-RETURN',str(report))
