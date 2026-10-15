"""Allowlisted local operational data; no raw diagnostic payloads."""
import re
import urllib.error


def retrieve(manager, args):
    key = args.get('hash', '')
    if not isinstance(key, str) or not re.fullmatch(r'[0-9a-fA-F]{6,128}', key):
        return {'error': 'A bare hexadecimal CCR hash (6..128 characters) is required'}
    try:
        data = manager.read_json('/v1/retrieve', {'hash': key})
        return {k: data.get(k) for k in ('original_content','original_tokens','tool_name')}
    except urllib.error.HTTPError as exc:
        return {'error': 'Content expired or absent; re-run original command' if exc.code == 404 else 'Retrieval HTTP error', 'status': exc.code}
    except Exception as exc:
        return {'error': 'Retrieval unavailable', 'type': type(exc).__name__}


def local_stats(manager):
    data = manager.read_json('/stats')
    allowed = {'requests': ('total','cached','rate_limited','failed'),
               'tokens': ('input','output','saved','proxy_compression_saved','savings_percent')}
    return {section: {key: data.get(section, {}).get(key) for key in keys
                      if isinstance(data.get(section, {}).get(key), (int,float))}
            for section,keys in allowed.items()}
