"""Safe, dependency-free Headroom lifecycle and explicit routing primitives."""
from dataclasses import dataclass
import json
import os
import re
import socket
import subprocess
import threading
import time
import urllib.request


def is_process_descendant(pid, parent):
    """Verify Windows venv/uv redirector ancestry, without importing psutil."""
    if os.name != 'nt' or type(pid) is not int or type(parent) is not int:
        return False
    import ctypes
    from ctypes import wintypes
    class Entry(ctypes.Structure):
        _fields_ = [('size',wintypes.DWORD),('usage',wintypes.DWORD),('pid',wintypes.DWORD),
                    ('heap',ctypes.c_size_t),('module',wintypes.DWORD),('threads',wintypes.DWORD),
                    ('parent',wintypes.DWORD),('priority',wintypes.LONG),('flags',wintypes.DWORD),
                    ('exe',wintypes.WCHAR*260)]
    kernel=ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    kernel.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
    kernel.Process32NextW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    snapshot=kernel.CreateToolhelp32Snapshot(2,0)
    if snapshot == ctypes.c_void_p(-1).value:
        return False
    parents={}
    try:
        entry=Entry();entry.size=ctypes.sizeof(entry)
        ok=kernel.Process32FirstW(snapshot,ctypes.byref(entry))
        while ok:
            parents[entry.pid]=entry.parent
            ok=kernel.Process32NextW(snapshot,ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    seen=set()
    while pid in parents and pid not in seen:
        seen.add(pid);pid=parents[pid]
        if pid == parent:
            return True
    return False


class ProxyManager:
    """Never adopt/stop an external process; never alter a shared proxy's config."""
    def __init__(self, settings, probe=None):
        self.settings = settings
        self._probe = probe or self._health
        self._lock = threading.RLock()
        self._process = None
        self._state = 'idle'
        self._error = None
        self._thread = None
        self._stderr_tail = ''
        self._stderr_thread = None
        self._exit_code = None

    def _drain_stderr(self, stream):
        # Drain continuously: never let a full pipe deadlock proxy startup.
        try:
            while True:
                chunk = stream.readline(8193)
                if not isinstance(chunk, bytes) or not chunk:
                    break
                if len(chunk) > 8192:
                    # Discard an overlong whole line, never expose split credentials.
                    while chunk and not chunk.endswith(b'\n'):
                        chunk = stream.readline(8193)
                    continue
                text = chunk.decode('utf-8', 'replace')
                text = re.sub(r'(?im)^.*(?:authorization|api[_-]?key|token|password|secret|cookie).*$','[REDACTED]',text)
                for key, value in os.environ.items():
                    if re.search(r'KEY|TOKEN|PASSWORD|SECRET|COOKIE', key, re.I) and len(value) >= 6:
                        text = text.replace(value, '[REDACTED]')
                self._stderr_tail = (self._stderr_tail + text)[-4096:]
        finally:
            stream.close()

    def _health(self):
        # Do not use a corporate/system HTTP proxy for loopback health checks.
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(self.settings.url + '/health', timeout=1) as response:
                return json.loads(response.read(262144))
        except Exception:
            with socket.socket() as sock:
                sock.settimeout(0.3)
                if sock.connect_ex(('127.0.0.1', self.settings.port)) == 0:
                    return {'service': 'unknown'}
            return None

    def status(self):
        with self._lock:
            return {'state': self._state, 'url': self.settings.url, 'error': self._error,
                    'owns_process': self._process is not None,
                    'hermes_auto_routing': self.settings.native_anthropic or self.settings.auto_claude_cli, 'stderr_tail': self._stderr_tail,
                    'exit_code': self._exit_code}

    def read_json(self, path, payload=None):
        if path not in ('/stats', '/v1/retrieve'):
            raise ValueError('unsupported local endpoint')
        diagnostic = self.diagnostic()
        if not any(d.get('upstream_verified') for d in diagnostic['destinations'].values()):
            raise ValueError('Headroom identity/upstream not verified')
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(self.settings.url + path, data=data,
            headers={'Content-Type': 'application/json'})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=15) as response:
            raw = response.read(8388609)
            if len(raw) > 8388608:
                raise ValueError('local response exceeds size limit')
            return json.loads(raw)

    def diagnostic(self):
        health = self._probe()
        config = health.get('config', {}) if isinstance(health, dict) else {}
        healthy = isinstance(health, dict) and health.get('service') == 'headroom-proxy' and health.get('status') == 'healthy'
        def verified(provider):
            key = provider + '_api_url'
            upstream = config.get(key)
            return healthy and ((key in config and upstream is None and config.get('backend') == provider) or
                upstream in ('https://api.' + provider + '.com', 'https://api.' + provider + '.com/v1'))
        return dict(self.status(), destinations={
            'claude-cli': {'supported': True, 'enabled': self.settings.claude_cli or self.settings.auto_claude_cli,
                           'upstream_verified': verified('anthropic'), 'routing': 'ordinary terminal hook when auto_claude_cli enabled; explicit launcher otherwise'},
            'openai': {'supported': True, 'enabled': 'openai' in self.settings.providers,
                       'upstream_verified': verified('openai'), 'routing': 'explicit API-key child only'},
            'anthropic': {'supported': True, 'enabled': 'anthropic' in self.settings.providers,
                          'upstream_verified': verified('anthropic'), 'routing': 'explicit API-key child only'},
            'openai-codex': {'supported': False, 'reason': 'No verified native Hermes OAuth transport seam'},
            'hermes-native-claude': {'supported': True, 'enabled': self.settings.native_anthropic, 'routing': 'new native clients; original OAuth identity, request-hook redirect'}},
            advanced={'config_reference': self.settings.config_reference, 'external_read_only': self._state != 'owned'},
            failure_policy=self.settings.failure_policy)

    def start_background(self):
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self.ensure, name='headroom-proxy-start', daemon=True)
                self._thread.start()

    def ensure(self):
        with self._lock:
            if not self.settings.autostart:
                self._state = 'disabled'
                return self.status()
            if self._process is not None and self._process.poll() is None:
                return self.status()
            self._process = None
            try:
                health = self._probe()
            except Exception as exc:
                self._state = 'error'
                self._error = type(exc).__name__
                return self.status()
            if health is not None:
                self._state = ('external' if isinstance(health, dict) and
                               health.get('service') == 'headroom-proxy' and
                               health.get('status') == 'healthy' else 'conflict')
                return self.status()
            self._state = 'starting'
            self._error = None
            try:
                # No file logging, memory, telemetry, subscription poller or model downloads.
                executable = self.settings.executable
                name = os.path.basename(executable.replace('\\', '/')).lower()
                prefix = [executable, '-m', 'headroom.cli'] if name in ('python','python3','python.exe','python3.exe') else [executable]
                command = prefix + ['proxy', '--host', '127.0.0.1',
                           '--port', str(self.settings.port), '--stateless', '--no-telemetry',
                           '--no-subscription-tracking', '--disable-kompress', '--lossless',
                           '--no-embedding-server', '--mode', 'cache']
                flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                # Hermes PM pins its own CPython dependency generation on PYTHONPATH.
                # The external uv runtime must resolve its own ABI-compatible packages.
                child_env = dict(os.environ, HEADROOM_BEACON='off', DO_NOT_TRACK='1',
                                 PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
                for key in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONUSERBASE', 'VIRTUAL_ENV'):
                    child_env.pop(key, None)
                self._process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=flags,
                    env=child_env)
                self._stderr_tail = ''
                self._exit_code = None
                self._stderr_thread = threading.Thread(target=self._drain_stderr,
                    args=(self._process.stderr,), daemon=True)
                self._stderr_thread.start()
                deadline = time.monotonic() + self.settings.startup_timeout
                while time.monotonic() < deadline:
                    if self._process.poll() is not None:
                        self._exit_code = self._process.poll()
                        self._stderr_thread.join(timeout=1)
                        raise RuntimeError('child exited')
                    health = self._probe()
                    # Health PID, when available, must identify OUR child (bind-race guard).
                    if isinstance(health, dict) and health.get('service') == 'headroom-proxy' and health.get('status') == 'healthy':
                        pid = health.get('config', {}).get('pid')
                        if pid is not None and pid != self._process.pid and not is_process_descendant(pid,self._process.pid):
                            raise RuntimeError('port ownership changed')
                        self._state = 'owned'
                        return self.status()
                    time.sleep(0.1)
                raise TimeoutError('startup deadline')
            except Exception as exc:
                self.close()
                self._state = 'error'
                self._error = type(exc).__name__
                if str(exc) in ('child exited', 'port ownership changed', 'startup deadline'):
                    self._error += ': ' + str(exc)
                return self.status()

    def close(self):
        with self._lock:
            process, self._process = self._process, None
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            if self._state == 'owned':
                self._state = 'stopped'


@dataclass(frozen=True)
class Settings:
    autostart: bool = True
    port: int = 8787
    executable: str = 'headroom'
    providers: tuple = ()
    models: tuple = ()
    claude_cli: bool = False
    auto_claude_cli: bool = False
    native_anthropic: bool = False
    startup_timeout: float = 45.0
    failure_policy: str = 'closed'
    config_reference: str = ''

    def __post_init__(self):
        if self.failure_policy not in ('closed', 'warn-direct'):
            raise ValueError('failure_policy must be closed or warn-direct')
        if not isinstance(self.config_reference, str):
            raise ValueError('config_reference must be a string')
        if any(type(value) is not bool for value in (self.autostart, self.claude_cli, self.auto_claude_cli, self.native_anthropic)):
            raise ValueError('autostart and claude_cli must be booleans')
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError('port must be an integer 1..65535')
        if not isinstance(self.executable, str) or not self.executable.strip():
            raise ValueError('executable must name the Headroom executable')
        if not isinstance(self.providers, (tuple, list)) or any(p not in ('openai', 'anthropic') for p in self.providers):
            raise ValueError('Only explicit API-key openai/anthropic launches supported; OAuth, custom and other providers disabled')
        if not isinstance(self.models, (tuple, list)) or any(not isinstance(m, str) or not m for m in self.models):
            raise ValueError('models must be a list of exact model IDs; empty means all selected provider models')
        if isinstance(self.startup_timeout, bool) or not isinstance(self.startup_timeout, (float, int)) or not 1 <= self.startup_timeout <= 120:
            raise ValueError('startup_timeout must be 1..120 seconds')

    @property
    def url(self):
        return f'http://127.0.0.1:{self.port}'
