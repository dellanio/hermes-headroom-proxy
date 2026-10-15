import argparse
import unittest
from unittest.mock import Mock, patch
from headroom_proxy.core import Settings
from headroom_proxy.cli import execute

class FailureTests(unittest.TestCase):
    def test_explicit_warn_direct_keeps_original_environment(self):
        manager=Mock();manager.ensure.return_value={'state':'error'}
        args=argparse.Namespace(action='claude',model='',child_args=['--','--version'])
        with patch('headroom_proxy.cli.shutil.which',return_value='claude.exe'), patch('headroom_proxy.cli.subprocess.run') as run, patch('headroom_proxy.cli.os.environ',{}):
            run.return_value.returncode=0
            self.assertEqual(execute(args,Settings(claude_cli=True,failure_policy='warn-direct'),manager),0)
            self.assertNotIn('ANTHROPIC_BASE_URL',run.call_args.kwargs['env'])

    def test_ccr_retrieval_returns_original_and_expiry(self):
        from headroom_proxy.operations import retrieve
        manager=Mock();manager.read_json.return_value={'original_content':'hello','original_tokens':1,'secret':'hidden'}
        self.assertEqual(retrieve(manager,{'hash':'abcdef'}),{'original_content':'hello','original_tokens':1,'tool_name':None})
        manager.read_json.assert_called_once_with('/v1/retrieve',{'hash':'abcdef'})
        self.assertIn('error',retrieve(manager,{'hash':'../invalid'}))
