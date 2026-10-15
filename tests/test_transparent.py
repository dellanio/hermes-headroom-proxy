import unittest
from unittest.mock import Mock
from headroom_proxy import transparent

class RoutingTests(unittest.TestCase):
    def test_native_keeps_identity_but_routes_each_request(self):
        manager = Mock()
        from headroom_proxy.core import Settings
        manager.settings = Settings()
        manager.diagnostic.return_value = {'destinations': {'claude-cli': {'upstream_verified': True}}}
        client = Mock()
        client._client.event_hooks = {'request': []}
        original = Mock(return_value=client)
        builder = transparent.native_builder(original, manager, lambda: True)
        self.assertIs(builder('existing-oauth', 'https://api.anthropic.com'), client)
        original.assert_called_once_with('existing-oauth', 'https://api.anthropic.com')
        import httpx
        request = httpx.Request('POST', 'https://api.anthropic.com/v1/messages?beta=true', headers={'authorization':'Bearer existing-oauth'})
        client._client.event_hooks['request'][0](request)
        self.assertEqual(str(request.url), 'http://127.0.0.1:8787/v1/messages?beta=true')
        self.assertEqual(request.headers['authorization'], 'Bearer existing-oauth')

    def test_terminal_preserves_literal_command_and_uses_hook_directive(self):
        manager = Mock()
        from headroom_proxy.core import Settings
        manager.settings = Settings()
        manager.diagnostic.return_value = {'destinations': {'claude-cli': {'upstream_verified': True}}}
        args = {'command': 'cd "a b" && claude -p "say \\"hello\\""', 'timeout': 30}
        result = transparent.terminal_directive(args, manager)
        self.assertEqual(result['action'], 'modify')
        self.assertTrue(result['args']['command'].endswith(args['command']))
        self.assertIn('command claude "$@"', result['args']['command'])
        self.assertEqual(result['args']['timeout'], 30)

    def test_prompt_text_is_not_an_executable(self):
        self.assertIsNone(transparent.terminal_directive({'command': 'echo claude'}, Mock()))

    def test_selected_native_request_fails_closed_before_network(self):
        import httpx
        from headroom_proxy.core import Settings
        manager = Mock(settings=Settings())
        manager.ensure.side_effect = RuntimeError('unavailable')
        client = Mock()
        client._client.event_hooks = {'request': []}
        transparent.native_builder(Mock(return_value=client), manager, lambda: True)('oauth', 'https://api.anthropic.com')
        request = httpx.Request('POST', 'https://api.anthropic.com/v1/messages')
        with self.assertRaises(RuntimeError):
            client._client.event_hooks['request'][0](request)
        self.assertEqual(request.url.host, 'api.anthropic.com')

    def test_other_profile_and_other_provider_are_unchanged(self):
        for active, url in ((False, 'https://api.anthropic.com'), (True, 'https://other.example')):
            manager = Mock()
            client = Mock()
            client._client.event_hooks = {'request': []}
            result = transparent.native_builder(Mock(return_value=client), manager, lambda: active)('credential', url)
            self.assertIs(result, client)
            self.assertEqual(client._client.event_hooks['request'], [])
            manager.ensure.assert_not_called()

    def test_terminal_unavailable_is_blocked_and_bypass_is_refused(self):
        from headroom_proxy.core import Settings
        manager = Mock(settings=Settings())
        manager.ensure.side_effect = RuntimeError('unavailable')
        for command in ('claude -p hi', 'command claude -p hi', 'env X=y claude -p hi', 'C:/bin/claude.exe -p hi'):
            self.assertEqual(transparent.terminal_directive({'command': command}, manager)['action'], 'block')

    def test_newline_command_position_is_routed(self):
        from headroom_proxy.core import Settings
        manager = Mock(settings=Settings())
        manager.diagnostic.return_value = {'destinations': {'claude-cli': {'upstream_verified': True}}}
        result = transparent.terminal_directive({'command': 'pwd\nclaude -p "space quoted"'}, manager)
        self.assertIsNotNone(result)
        self.assertEqual(result['action'], 'modify')

if __name__ == '__main__': unittest.main()
