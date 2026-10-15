"""Opt-in bounded real process smoke. Never starts/stops or reconfigures port 8787."""
import os
import socket
import unittest
from headroom_proxy.core import Settings, ProxyManager, is_process_descendant

@unittest.skipUnless(os.environ.get('HEADROOM_TEST_EXECUTABLE'), 'Set HEADROOM_TEST_EXECUTABLE for real smoke')
class RealProxyTests(unittest.TestCase):
    def test_real_proxy_health_and_owned_cleanup(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port=sock.getsockname()[1]
        self.assertNotEqual(port,8787)
        manager=ProxyManager(Settings(port=port, executable=os.environ['HEADROOM_TEST_EXECUTABLE'],startup_timeout=60))
        try:
            result=manager.ensure()
            self.assertEqual(result['state'],'owned',result)
            health=manager._probe()
            self.assertEqual(health['service'],'headroom-proxy')
            self.assertTrue(health['config']['pid'] == manager._process.pid or is_process_descendant(health['config']['pid'],manager._process.pid))
            print(f'REAL_PROXY port={port} version={health.get("version")} service={health["service"]} status={health["status"]}')
        finally:
            process=manager._process
            manager.close()
        self.assertIsNotNone(process.poll())
        self.assertIsNone(manager._probe())
