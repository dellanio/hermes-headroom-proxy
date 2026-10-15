"""Opt-in native Hermes loader validation in a non-profile isolated home."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

@unittest.skipUnless(os.environ.get('HERMES_TEST_SOURCE'), 'Set HERMES_TEST_SOURCE for native contract test')
class NativeContractTests(unittest.TestCase):
    def test_native_manifest_settings_and_inprocess_loader(self):
        sys.path.insert(0,os.environ['HERMES_TEST_SOURCE'])
        from hermes_cli.plugins_manifest import parse_manifest_file
        from hermes_cli.plugins import PluginManager
        from hermes_cli.plugins_settings import plugin_settings_fields
        directory=Path(__file__).resolve().parents[1]/'headroom_proxy'
        manifest=parse_manifest_file(directory/'plugin.yaml',directory,'user','')
        self.assertIsNotNone(manifest)
        cfg={'plugins':{'entries':{'headroom_proxy':{'settings':{'autostart':False}}}}}
        with patch('hermes_cli.config.load_config_readonly',return_value=cfg), patch('hermes_cli.config.load_config',return_value=cfg):
            fields=plugin_settings_fields('headroom_proxy',directory)
            self.assertEqual(next(x for x in fields if x['key']=='autostart')['value'],False)
            manager=PluginManager(scope_key=os.environ['HERMES_HOME'])
            try:
                with patch.object(manager,'_runs_in_plugin_host',return_value=False):
                    manager._load_plugin(manifest)
                loaded=manager._plugins['headroom_proxy']
                self.assertIsNone(loaded.error)
                self.assertIn('on_session_start',manager._hooks)
                self.assertIn('headroom_proxy_status',manager._plugin_tool_names)
                self.assertFalse(manager._middleware)
                print('NATIVE_HERMES manifest/settings/in-process user loader/unload: PASS; host isolation not exercised')
            finally:
                manager.unload()
