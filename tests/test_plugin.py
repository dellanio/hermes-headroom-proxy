import json
import unittest
from unittest.mock import Mock, patch
import headroom_proxy

class PluginTests(unittest.TestCase):
    def context(self, **settings):
        ctx=Mock()
        ctx.get_config.side_effect=lambda key,default=None:settings.get(key,default)
        return ctx

    def test_native_registration_defers_start_and_uses_unload(self):
        ctx=self.context()
        with patch('headroom_proxy.ProxyManager') as cls:
            headroom_proxy.register(ctx)
            cls.return_value.start_background.assert_called_once()
            ctx.on_unload.assert_called_once_with(cls.return_value.close)
            self.assertEqual(ctx.register_hook.call_args.args[0], 'on_session_start')
            self.assertEqual(ctx.register_tool.call_args.kwargs['name'], 'headroom_proxy_status')
            ctx.register_middleware.assert_not_called()

    def test_disabled_config_never_starts(self):
        ctx=self.context(autostart=False)
        with patch('headroom_proxy.ProxyManager') as cls:
            headroom_proxy.register(ctx)
            cls.return_value.start_background.assert_not_called()
            ctx.register_hook.call_args.args[1](session_id='mock')
            cls.return_value.start_background.assert_not_called()

    def test_status_is_read_only_json(self):
        ctx=self.context(autostart=False)
        with patch('headroom_proxy.ProxyManager') as cls:
            cls.return_value.status.return_value={'state':'disabled'}
            headroom_proxy.register(ctx)
            tool=ctx.register_tool.call_args.kwargs['handler']
            self.assertEqual(json.loads(tool({})), {'state':'disabled'})
            ctx.set_config.assert_not_called()

    def test_operational_and_retrieval_tools_registered(self):
        ctx=self.context(autostart=False)
        with patch('headroom_proxy.ProxyManager'):
            headroom_proxy.register(ctx)
        names={call.kwargs['name'] for call in ctx.register_tool.call_args_list}
        self.assertTrue({'headroom_proxy_control','headroom_proxy_stats','headroom_proxy_retrieve','headroom_proxy_status'} <= names)

    def test_slash_command_diagnose_dispatches(self):
        ctx=self.context(autostart=False)
        with patch('headroom_proxy.ProxyManager') as cls:
            cls.return_value.diagnostic.return_value={'hermes_auto_routing':False,'destinations':{}}
            headroom_proxy.register(ctx)
            command=ctx.register_command.call_args.args[1]
            self.assertIn('destinations',json.loads(command('diagnose')))
            cls.return_value.diagnostic.assert_called_once()

    def test_native_cli_command_is_registered(self):
        with patch('headroom_proxy.ProxyManager'):
            ctx=self.context(autostart=False)
            headroom_proxy.register(ctx)
            self.assertEqual(ctx.register_cli_command.call_args.kwargs['name'], 'headroom-proxy')
