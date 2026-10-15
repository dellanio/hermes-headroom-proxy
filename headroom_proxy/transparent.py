"""Profile-scoped integration at Hermes' Anthropic builder and terminal hook.

No global HTTP/subprocess patch, credential replacement, or executable replacement.
"""
from urllib.parse import urlsplit
import shlex


def require_proxy(manager):
    manager.ensure()
    if not manager.diagnostic()['destinations']['claude-cli']['upstream_verified']:
        raise RuntimeError('Selected Claude route requires verified Headroom Anthropic upstream')


def native_builder(original, manager, active):
    def build(*args, **kwargs):
        # Construct against the REAL endpoint first: OAuth headers and SDK auth style
        # must never be classified as third-party x-api-key authentication.
        client = original(*args, **kwargs)
        base = kwargs.get('base_url', args[1] if len(args) > 1 else None)
        if not active() or urlsplit(base or 'https://api.anthropic.com').hostname != 'api.anthropic.com':
            return client
        def route(request):
            if not active():
                return
            require_proxy(manager)  # raises before network; never fallback direct
            if request.url.host != 'api.anthropic.com':
                raise RuntimeError('Unexpected native Anthropic destination')
            target = urlsplit(manager.settings.url)
            request.url = request.url.copy_with(scheme='http', host=target.hostname, port=target.port)
            request.headers['host'] = target.netloc
        client._client.event_hooks.setdefault('request', []).append(route)
        return client
    return build


def terminal_directive(args, manager):
    command = args.get('command', '')
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        if 'claude' in command:
            return {'action': 'block', 'message': 'Cannot safely parse selected Claude command'}
        return None
    # Exact executable tokens only; textual prompts containing 'claude' are not rewritten.
    lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|()\n')
    lexer.whitespace = ' \t\r'
    lexer.whitespace_split = True
    tokens = list(lexer)
    executables = []
    position = True
    for t in tokens:
        if t in ('&&', '||', ';', '|', '&', '(', '\n'):
            position = True
            continue
        if position and t.replace('\\', '/').rsplit('/', 1)[-1].lower() in ('claude', 'claude.exe', 'claude.cmd'):
            executables.append(t)
        if position and ('=' in t or t in ('env', 'command', 'exec')):
            if 'claude' in tokens:
                return {'action': 'block', 'message': 'Use plain claude; executable/env overrides are not safely routable'}
        position = False
    if not executables:
        return None
    if any(t != 'claude' for t in executables):
        return {'action': 'block', 'message': 'Selected Claude absolute/alternate executable requires plain claude for scoped routing'}
    try:
        import os
        from .routing import launch_environment
        from dataclasses import replace
        launch_environment(replace(manager.settings, claude_cli=True), 'claude-cli', '', os.environ)
        require_proxy(manager)
    except Exception:
        return {'action': 'block', 'message': 'Selected Claude route unavailable or billing/endpoint override; direct fallback prohibited'}
    # A shell function intercepts command positions without reparsing/requoting user's
    # arguments. `command` bypasses the function, so no recursive wrap occurs.
    url = shlex.quote(manager.settings.url)
    prefix = ('claude() { ANTHROPIC_BASE_URL=' + url + ' ENABLE_TOOL_SEARCH=true command claude "$@"; }; ')
    return {'action': 'modify', 'args': dict(args, command=prefix + command)}


def install_native(manager, enabled):
    if not enabled:
        return lambda: None
    from agent import anthropic_adapter
    from hermes_constants import get_hermes_home
    from pathlib import Path
    home = Path(get_hermes_home()).resolve()
    state = {'enabled': True}
    def active():
        return state['enabled'] and Path(get_hermes_home()).resolve() == home
    original = anthropic_adapter.build_anthropic_client
    wrapped = native_builder(original, manager, active)
    anthropic_adapter.build_anthropic_client = wrapped
    def undo():
        state['enabled'] = False
        if anthropic_adapter.build_anthropic_client is wrapped:
            anthropic_adapter.build_anthropic_client = original
    return undo
