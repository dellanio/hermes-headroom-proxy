import argparse
import unittest
from unittest.mock import Mock, patch
from headroom_proxy.core import Settings
import headroom_proxy.cli as cli

class CliTests(unittest.TestCase):
    def parse(self, args):
        p=argparse.ArgumentParser()
        cli.configure_parser(p)
        return p.parse_args(args)

    def test_status_does_not_spawn(self):
        m=Mock(); m.status.return_value={'state':'idle'}
        with patch('builtins.print'):
            self.assertEqual(cli.execute(self.parse(['status']), Settings(), m),0)
        m.ensure.assert_not_called()

    def test_disabled_claude_refused_before_proxy_or_child(self):
        m=Mock()
        with patch.object(cli.subprocess,'run') as run:
            with self.assertRaises(ValueError):
                cli.execute(self.parse(['claude','--','--version']),Settings(),m)
            run.assert_not_called(); m.ensure.assert_not_called()

    def test_claude_child_only_env_and_argument_boundaries(self):
        m=Mock(); m.ensure.return_value={'state':'external'}
        m._probe.return_value={'config':{'anthropic_api_url':'https://api.anthropic.com'}}
        with patch.object(cli.subprocess,'run') as run, patch.object(cli.shutil,'which',return_value='claude.exe'), patch.dict(cli.os.environ, {}, clear=True):
            run.return_value.returncode=0
            self.assertEqual(cli.execute(self.parse(['claude','--','--version']),Settings(claude_cli=True),m),0)
            self.assertEqual(run.call_args.args[0], ['claude.exe','--version'])
            self.assertNotIn('ANTHROPIC_API_KEY', run.call_args.kwargs['env'])
            self.assertFalse(run.call_args.kwargs.get('shell',False))

    def test_proxy_none_upstream_means_verified_builtin_default(self):
        m=Mock();m.ensure.return_value={'state':'external'}
        m._probe.return_value={'config':{'anthropic_api_url':None,'backend':'anthropic'}}
        with patch.object(cli.subprocess,'run') as run, patch.object(cli.shutil,'which',return_value='claude.exe'),patch.dict(cli.os.environ,{},clear=True):
            run.return_value.returncode=0
            self.assertEqual(cli.execute(self.parse(['claude','--','--version']),Settings(claude_cli=True),m),0)

    def test_custom_upstream_refused(self):
        m=Mock(); m.ensure.return_value={'state':'external'}
        m._probe.return_value={'config':{'anthropic_api_url':'https://other.example'}}
        with patch.object(cli.subprocess,'run') as run, patch.dict(cli.os.environ,{},clear=True):
            with self.assertRaises(ValueError):
                cli.execute(self.parse(['claude']),Settings(claude_cli=True),m)
            run.assert_not_called()
