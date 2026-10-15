import unittest
from headroom_proxy.core import Settings
import headroom_proxy.routing as routing

class RoutingTests(unittest.TestCase):
    def test_claude_opt_in_preserves_oauth_and_parent_environment(self):
        original={'CLAUDE_CODE_OAUTH_TOKEN':'private','PATH':'bin'}
        result=routing.launch_environment(Settings(claude_cli=True), 'claude-cli', '', original)
        self.assertEqual(result['CLAUDE_CODE_OAUTH_TOKEN'], 'private')
        self.assertNotIn('ANTHROPIC_API_KEY', result)
        self.assertEqual(result['ANTHROPIC_BASE_URL'], 'http://127.0.0.1:8787')
        self.assertEqual(result['ENABLE_TOOL_SEARCH'], 'true')
        self.assertNotIn('ANTHROPIC_BASE_URL', original)

    def test_subscription_launcher_refuses_billing_override(self):
        for key in ('ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','CLAUDE_CODE_USE_VERTEX','CLAUDE_CODE_USE_BEDROCK','CLAUDE_CODE_USE_FOUNDRY'):
            with self.assertRaises(ValueError):
                routing.launch_environment(Settings(claude_cli=True), 'claude-cli', '', {key:'private'})

    def test_unselected_provider_or_model_denied(self):
        for provider,model in [('openai-codex','gpt'),('openai','denied'),('anthropic','allowed'),('claude-cli','')]:
            with self.assertRaises(ValueError):
                routing.launch_environment(Settings(providers=['openai'],models=['allowed']), provider,model,{'OPENAI_API_KEY':'private'})

    def test_api_key_clients_require_real_existing_key(self):
        for provider,key,url in [('openai','OPENAI_API_KEY','http://127.0.0.1:8787/v1'),('anthropic','ANTHROPIC_API_KEY','http://127.0.0.1:8787')]:
            s=Settings(providers=[provider])
            with self.assertRaises(ValueError):
                routing.launch_environment(s,provider,'model',{})
            env=routing.launch_environment(s,provider,'model',{key:'private'})
            self.assertEqual(env[key],'private')
            self.assertEqual(env['OPENAI_BASE_URL' if provider=='openai' else 'ANTHROPIC_BASE_URL'],url)

    def test_conflicting_existing_endpoint_refused(self):
        with self.assertRaises(ValueError):
            routing.launch_environment(Settings(claude_cli=True),'claude-cli','',{'ANTHROPIC_BASE_URL':'https://other.example'})
