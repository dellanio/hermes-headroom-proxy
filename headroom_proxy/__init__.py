"""Hermes user plugin entry point. Importing this module has no side effects."""
import atexit
import json
from .core import ProxyManager, Settings

DEFAULTS = {'autostart': True, 'port': 8787, 'executable': 'headroom',
            'providers': (), 'models': (), 'claude_cli': False, 'startup_timeout': 45.0,
            'failure_policy': 'closed', 'config_reference': '',
            'auto_claude_cli': False, 'native_anthropic': False}


def register(ctx):
    settings = Settings(**{key: ctx.get_config(key, default) for key, default in DEFAULTS.items()})
    manager = ProxyManager(settings)

    def start(**_):
        if settings.autostart:
            manager.start_background()

    def status(args=None, **_):
        return json.dumps(manager.status())

    def setup(parser):
        from .cli import configure_parser
        configure_parser(parser)

    def command(args):
        from .cli import execute
        return execute(args, settings=settings, manager=manager)

    from .operations import local_stats, retrieve

    def control(args, **_):
        try:
            action = args.get('action', 'diagnose')
            if action == 'start':
                return json.dumps(manager.ensure())
            if action == 'stop':
                manager.close()
                return json.dumps(manager.status())
            if action == 'diagnose':
                return json.dumps(manager.diagnostic())
            return json.dumps({'error': 'Unsupported operation'})
        except Exception as exc:
            return json.dumps({'error': type(exc).__name__})

    def stats(args=None, **_):
        try:
            return json.dumps(local_stats(manager))
        except Exception as exc:
            return json.dumps({'error': type(exc).__name__})

    for name, description, properties, handler in (
        ('headroom_proxy_control', 'Start/status diagnostics or stop ONLY the proxy owned by this plugin host; external services never stopped.',
         {'action': {'type':'string','enum':['start','stop','diagnose']}}, control),
        ('headroom_proxy_stats', 'Read allowlisted local Headroom counters; not proof of routing by this session.', {}, stats),
        ('headroom_proxy_retrieve', 'Retrieve complete original CCR content by bare hex hash. Expired hashes require original command rerun.',
         {'hash': {'type':'string'}}, lambda args, **_: json.dumps(retrieve(manager,args)))):
        ctx.register_tool(name=name, toolset='headroom_proxy', description=description,
            schema={'name':name, 'description':description,
                    'parameters':{'type':'object','properties':properties,'additionalProperties':False}},
            handler=handler)

    from .transparent import install_native, terminal_directive
    undo_native = install_native(manager, settings.native_anthropic)
    if settings.native_anthropic:
        ctx.on_unload(undo_native)
    if settings.auto_claude_cli:
        def route_terminal(tool_name='', args=None, **_):
            if tool_name == 'terminal' and isinstance(args, dict):
                return terminal_directive(args, manager)
        ctx.register_hook('pre_tool_call', route_terminal)
    ctx.register_hook('on_session_start', start)
    ctx.register_tool(name='headroom_proxy_status', toolset='headroom_proxy',
        description='Read Headroom lifecycle and configured automatic routing state.',
        schema={'name':'headroom_proxy_status',
                'description':'Read Headroom status; no credentials, writes, or provider switching.',
                'parameters':{'type':'object','properties':{},'additionalProperties':False}},
        handler=status)
    def slash(raw_args='', **_):
        action = str(raw_args).strip() or 'status'
        if action == 'status':
            return status()
        if action == 'stats':
            return stats()
        return control({'action':action})

    ctx.register_command('headroom-proxy', slash,
                         description='Headroom: status, diagnose, stats, start, stop (owned only)')
    ctx.register_cli_command(name='headroom-proxy', help='Headroom status and explicit Claude launcher',
                             setup_fn=setup, handler_fn=command)
    ctx.on_unload(manager.close)
    atexit.register(manager.close)
    start()
