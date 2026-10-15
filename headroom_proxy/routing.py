"""Explicit child-only env routing, never a global SDK/HTTP monkeypatch."""


def launch_environment(settings, provider, model, environ):
    env = dict(environ)
    if provider == 'claude-cli':
        if not settings.claude_cli:
            raise ValueError('Claude CLI routing is disabled; opt in with claude_cli')
        # This launcher is deliberately SUBSCRIPTION ONLY. Never fabricate an API key.
        blocked = ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'CLAUDE_CODE_USE_BEDROCK',
                   'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY')
        if any(env.get(k) for k in blocked):
            raise ValueError('Subscription launcher refuses API-key/token/cloud billing overrides')
        key, url = 'ANTHROPIC_BASE_URL', settings.url
        env.setdefault('ENABLE_TOOL_SEARCH', 'true')
    else:
        if provider not in ('openai', 'anthropic') or provider not in settings.providers:
            raise ValueError('Provider not selected or unsupported; openai-codex OAuth is disabled')
        if settings.models and model not in settings.models:
            raise ValueError('Model is not selected')
        credential = 'OPENAI_API_KEY' if provider == 'openai' else 'ANTHROPIC_API_KEY'
        if not env.get(credential):
            raise ValueError('Existing provider API key required; dummy credentials are forbidden')
        key = 'OPENAI_BASE_URL' if provider == 'openai' else 'ANTHROPIC_BASE_URL'
        url = settings.url + ('/v1' if provider == 'openai' else '')
    if env.get(key) and env[key].rstrip('/') != url:
        raise ValueError('Existing custom endpoint conflicts; no implicit upstream rewrite')
    env[key] = url
    return env
