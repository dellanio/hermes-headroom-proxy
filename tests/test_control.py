import argparse
import unittest
from unittest.mock import Mock, patch
from headroom_proxy.core import Settings
from headroom_proxy.cli import execute

class ControlTests(unittest.TestCase):
    def test_stop_uses_only_current_manager(self):
        manager=Mock()
        manager.status.return_value={'owns_process':False}
        self.assertEqual(execute(argparse.Namespace(action='stop'),Settings(),manager),0)
        manager.close.assert_called_once()
        manager.ensure.assert_not_called()

    def test_stats_allowlist_redacts_arbitrary_payload(self):
        from headroom_proxy.operations import local_stats
        manager=Mock()
        manager.read_json.return_value={'requests':{'total':9,'secret':'hidden'},'tokens':{'saved':3},'secret':'hidden'}
        self.assertEqual(local_stats(manager),{'requests':{'total':9},'tokens':{'saved':3}})
