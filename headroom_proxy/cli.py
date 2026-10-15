"""Standalone/native Hermes CLI. Does not change persistent client settings."""
import argparse
import json
import os
import shutil
import subprocess
from .core import ProxyManager, Settings
from .routing import launch_environment


def configure_parser(parser):
    parser.add_argument('action', choices=['status','start','stop','diagnose','stats','advanced','claude','run-api'])
    parser.add_argument('--provider', choices=['openai','anthropic'])
    parser.add_argument('--model', default='')
    parser.add_argument('child_args', nargs=argparse.REMAINDER)


def execute(args, settings=None, manager=None):
    settings = settings or Settings()
    manager = manager or ProxyManager(settings)
    if args.action in ('start','stop','diagnose','stats','advanced'):
        if args.action == 'start':
            result = manager.ensure()
        elif args.action == 'stop':
            manager.close()
            result = manager.status()
        elif args.action == 'diagnose':
            result = manager.diagnostic()
        elif args.action == 'stats':
            from .operations import local_stats
            result = local_stats(manager)
        else:
            result = {'config_reference': settings.config_reference,
                      'dashboard': settings.url,
                      'note': 'Reference only; use Headroom CLI/dashboard for advanced config. Shared external service is read-only.'}
        print(json.dumps(result))
        return 0
    if args.action == 'status':
        print(json.dumps(manager.status()))
        return 0
    provider = 'claude-cli' if args.action == 'claude' else args.provider
    env = launch_environment(settings, provider, args.model, os.environ)
    state = manager.ensure()
    if state['state'] not in ('owned','external'):
        if settings.failure_policy != 'warn-direct':
            raise ValueError('Proxy not ready; no child launched')
        import sys
        print('WARNING: Headroom unavailable; explicit warn-direct policy bypasses proxy/compression/privacy controls for this child.', file=sys.stderr)
        env = dict(os.environ)
    else:
        health = manager._probe()
        config = health.get('config', {}) if isinstance(health, dict) else {}
        upstream_key = 'openai_api_url' if provider == 'openai' else 'anthropic_api_url'
        expected = 'https://api.openai.com' if provider == 'openai' else 'https://api.anthropic.com'
        upstream = config.get(upstream_key)
        implicit_default = upstream_key in config and upstream is None and config.get('backend') == 'anthropic'
        if not implicit_default and str(upstream or '').rstrip('/') not in (expected, expected+'/v1'):
            raise ValueError('Proxy upstream not verified as first-party; refusing credential forwarding')
    child = list(args.child_args)
    if child[:1] == ['--']:
        child.pop(0)
    if provider == 'claude-cli':
        binary = shutil.which('claude')
        if not binary:
            raise ValueError('Claude CLI is not installed')
        child.insert(0,binary)
        print('Claude: custom BASE_URL disables Remote Control on 2.1.196+; 1M tier is not forced.')
    elif not child:
        raise ValueError('run-api requires an explicit client command after --')
    # No dummy credential, persistent settings edit, global environment mutation or shell.
    return subprocess.run(child, env=env, check=False).returncode


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', help='Explicit local JSON settings file, not a Hermes profile')
    configure_parser(parser)
    args=parser.parse_args(argv)
    settings=Settings()
    if args.settings:
        with open(args.settings, encoding='utf-8') as handle:
            settings=Settings(**json.load(handle))
    manager=ProxyManager(settings)
    try:
        return execute(args, settings, manager)
    except (ValueError, OSError) as exc:
        # Do not echo subprocess exceptions or a command that might contain secrets.
        parser.exit(2, f'{type(exc).__name__}: launch refused; check selected settings, credentials, endpoint and proxy health.\n')
    finally:
        manager.close()

if __name__ == '__main__':
    raise SystemExit(main())
