"""Nonblocking radio playback with explicit dependency discovery and mpv IPC.

YouTube audio is resolved before playback. Passing its live audio manifest
straight to mpv avoids the hook's EDL seek path, which can fail on live HLS.
"""
from collections import deque
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlparse

DEFAULT_STREAM_URL = 'https://www.youtube.com/watch?v=tRsQsTMvPNg'


def find_executable(name):
    """Also find Homebrew/pipx tools when launched with a minimal GUI PATH."""
    found = shutil.which(name)
    if found:
        return found
    for directory in ('/opt/homebrew/bin', '/usr/local/bin',
                      os.path.expanduser('~/.local/bin'),
                      '/opt/homebrew/opt/{}/bin'.format(name),
                      '/usr/local/opt/{}/bin'.format(name)):
        candidate = os.path.join(directory, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _is_youtube(url):
    host = (urlparse(url).hostname or '').lower()
    return host in ('youtu.be', 'youtube.com', 'www.youtube.com',
                    'm.youtube.com', 'music.youtube.com')


class AudioPlayer:
    def __init__(self, stream_url=DEFAULT_STREAM_URL, initial_volume=80, enabled=True):
        self.stream_url = stream_url
        self.volume = max(0, min(100, int(initial_volume)))
        self.enabled = enabled
        self.is_paused = False
        self.is_muted = self.volume == 0
        self.is_connected = False
        self.is_buffering = bool(enabled)
        self.status = 'connecting' if enabled else 'disabled'
        self.error_message = None
        self.current_title = 'Claude FM · music for thinking and building'
        self.diagnostics = deque(maxlen=24)
        self.audio_params = None
        self.audio_output = None
        self.audio_codec = None
        self.audio_driver = None
        self.playback_position = None
        self._previous_volume = self.volume
        self._ready = False
        self._cache_paused = False
        self._requested_pause = None
        self._buffer = b''
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._cleanup_lock = threading.Lock()
        self._cmd_queue = []
        self._worker_thread = None
        self._log_thread = None
        self._resolver = None
        self.process = None
        self.sock = None
        self.mpv_path = None
        self.ytdlp_path = None
        self._socket_dir = None
        self.sock_path = None
        if enabled:
            self.start()

    def _diagnostic(self, line):
        # Keep diagnostics bounded, printable, and free of signed media URLs.
        line = re.sub(r'https?://\S+', '[stream URL]', str(line))
        line = ''.join(c for c in line if c.isprintable())[:500].strip()
        if line:
            self.diagnostics.append(line)

    def _fail(self, message):
        if self._stop_event.is_set():
            return
        self.error_message = message
        self.status = 'error'
        self.is_buffering = False
        self._diagnostic(message)

    def _refresh_status(self):
        if self.error_message:
            self.status = 'error'
        elif not self.enabled:
            self.status = 'disabled'
        elif self.is_paused:
            self.status = 'paused'
        elif self._ready and self.audio_output and not self._cache_paused:
            self.status = 'playing'
        elif self.is_connected:
            self.status = 'buffering'
        else:
            self.status = 'connecting'
        self.is_buffering = self.status in ('connecting', 'buffering')

    def start(self):
        if not self.enabled or self._worker_thread:
            return
        self.mpv_path = find_executable('mpv')
        if not self.mpv_path:
            self._fail('mpv is missing. Install it with: brew install mpv')
            return
        self.ytdlp_path = find_executable('yt-dlp')
        if _is_youtube(self.stream_url) and not self.ytdlp_path:
            self._fail('yt-dlp is missing. Install it with: brew install yt-dlp')
            return
        self._socket_dir = tempfile.TemporaryDirectory(prefix='claudefm-')
        self.sock_path = os.path.join(self._socket_dir.name, 'mpv.sock')
        self._worker_thread = threading.Thread(target=self._worker_loop,
                                               name='claudefm-audio', daemon=True)
        self._worker_thread.start()

    def _child_env(self):
        env = os.environ.copy()
        paths = env.get('PATH', '').split(os.pathsep)
        for name in ('mpv', 'yt-dlp', 'deno', 'node'):
            path = find_executable(name)
            if path:
                paths.append(os.path.dirname(path))
        paths.extend(('/opt/homebrew/bin', '/usr/local/bin', '/usr/bin', '/bin'))
        env['PATH'] = os.pathsep.join(dict.fromkeys(p for p in paths if p))
        # Frozen Linux builds must not pass bundled library paths to system mpv.
        if 'LD_LIBRARY_PATH_ORIG' in env:
            env['LD_LIBRARY_PATH'] = env['LD_LIBRARY_PATH_ORIG']
        elif getattr(__import__('sys'), 'frozen', False):
            env.pop('LD_LIBRARY_PATH', None)
        return env

    def _resolve_stream(self, env):
        if not _is_youtube(self.stream_url):
            return self.stream_url, None
        with self._cleanup_lock:
            if self._stop_event.is_set():
                return None, None
            self._resolver = subprocess.Popen(
                [self.ytdlp_path, '--dump-single-json', '--skip-download',
                 '--no-playlist', '--no-progress', '--no-warnings',
                 '--socket-timeout', '15', '-f', 'bestaudio/best', self.stream_url],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, env=env, start_new_session=True)
        try:
            stdout, stderr = self._resolver.communicate(timeout=40)
        except subprocess.TimeoutExpired:
            self._terminate(self._resolver)
            self._resolver.communicate()
            self._fail('YouTube took too long to connect. Check your network and try again.')
            return None, None
        if self._stop_event.is_set():
            return None, None
        for line in stderr.splitlines()[-8:]:
            self._diagnostic(line)
        if self._resolver.returncode:
            detail = next((s for s in reversed(stderr.splitlines()) if 'ERROR:' in s), '')
            self._fail('YouTube could not load. Update yt-dlp or check the stream. ' +
                       re.sub(r'https?://\S+', '[stream URL]', detail)[:180])
            return None, None
        try:
            data = json.loads(stdout)
            media_url = data['url']
            if not isinstance(media_url, str) or not media_url.startswith(('https://', 'http://')):
                raise ValueError('No playable media URL')
            self.current_title = data.get('title') or self.current_title
            headers = data.get('http_headers') or {}
            return media_url, headers.get('User-Agent')
        except (ValueError, KeyError, TypeError):
            self._fail('yt-dlp returned no playable audio. Update it with: brew upgrade yt-dlp')
            return None, None
        finally:
            self._resolver = None

    def _worker_loop(self):
        try:
            if self._stop_event.is_set():
                return
            env = self._child_env()
            if self._stop_event.is_set():
                return
            media_url, agent = self._resolve_stream(env)
            if not media_url or self._stop_event.is_set():
                return
            cmd = [self.mpv_path, '--no-config', '--no-video', '--input-terminal=no',
                   '--idle=yes', '--msg-level=all=warn', '--network-timeout=20',
                   '--volume={}'.format(self.volume), '--pause={}'.format('yes' if self.is_paused else 'no'),
                   '--input-ipc-server={}'.format(self.sock_path)]
            if _is_youtube(self.stream_url):
                cmd.extend(('--ytdl=no', '--force-media-title=' + self.current_title))
            elif self.ytdlp_path:
                cmd.append('--script-opts=ytdl_hook-ytdl_path={}'.format(self.ytdlp_path))
            if agent:
                cmd.append('--user-agent={}'.format(agent))
            # Start idle, subscribe first, then load: a fast file failure must
            # not happen before the IPC reader can receive its end-file event.
            with self._cleanup_lock:
                if self._stop_event.is_set():
                    return
                self.process = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                    text=True, start_new_session=True)
            self._log_thread = threading.Thread(target=self._read_log,
                                               name='claudefm-audio-log', daemon=True)
            self._log_thread.start()
            deadline = time.monotonic() + 12
            while not self._stop_event.is_set() and time.monotonic() < deadline:
                if self.process.poll() is not None:
                    self._fail('mpv could not start playback. ' + self._last_error())
                    return
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    s.settimeout(.1)
                    s.connect(self.sock_path)
                    self.sock = s
                    self.is_connected = True
                    self._refresh_status()
                    break
                except OSError:
                    s.close()
                    self._stop_event.wait(.05)
            if not self.is_connected:
                self._fail('Could not connect to mpv. ' + self._last_error())
                return
            for i, prop in enumerate(('media-title', 'pause', 'paused-for-cache',
                     'audio-params', 'audio-out-params', 'audio-codec-name', 'current-ao', 'time-pos')):
                self._send_raw({'command': ['observe_property', i+1, prop]})
            self._send_raw({'command': ['request_log_messages', 'warn']})
            self._send_raw({'command': ['loadfile', media_url, 'replace']})
            playback_deadline = time.monotonic() + 40
            while not self._stop_event.is_set():
                if self.process.poll() is not None:
                    self._fail('Playback stopped. ' + self._last_error())
                    break
                with self._lock:
                    commands, self._cmd_queue = self._cmd_queue, []
                for command in commands:
                    self._send_raw(command)
                try:
                    chunk = self.sock.recv(65536)
                    if not chunk:
                        self._fail('The connection to mpv closed. ' + self._last_error())
                        break
                    self._consume(chunk)
                except socket.timeout:
                    pass
                if not self._ready and not self.is_paused and time.monotonic() > playback_deadline:
                    self._fail('Audio did not start. Check the stream, network, and audio output.')
                    break
                if self.error_message:
                    break
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            self._fail('Audio could not start: {}'.format(exc))
        finally:
            self.is_connected = False
            self._close_processes()

    def _last_error(self):
        for line in reversed(tuple(self.diagnostics)):
            if any(word in line.lower() for word in ('error', 'failed', 'cannot', 'no audio')):
                return line[:180]
        return 'Check mpv, yt-dlp, and your audio output.'

    def _read_log(self):
        process = self.process
        if process and process.stdout:
            try:
                for line in process.stdout:
                    self._diagnostic(line)
            finally:
                process.stdout.close()

    def _consume(self, chunk):
        self._buffer += chunk
        while b'\n' in self._buffer:
            line, self._buffer = self._buffer.split(b'\n', 1)
            try:
                self._handle_message(json.loads(line.decode('utf-8')))
            except (ValueError, UnicodeDecodeError, TypeError):
                continue
        if len(self._buffer) > 1024 * 1024:
            self._buffer = b''

    def _handle_message(self, data):
        if not isinstance(data, dict):
            return
        event = data.get('event')
        if event == 'property-change':
            name, value = data.get('name'), data.get('data')
            if name == 'media-title' and isinstance(value, str) and value:
                self.current_title = value
            elif name == 'pause' and isinstance(value, bool):
                # A notification from before the latest keypress must not undo it.
                if self._requested_pause is None or value == self._requested_pause:
                    self.is_paused = value
                    self._requested_pause = None
            elif name == 'paused-for-cache':
                self._cache_paused = bool(value)
            elif name == 'audio-params':
                self.audio_params = value
            elif name == 'audio-out-params':
                self.audio_output = value
            elif name == 'audio-codec-name':
                self.audio_codec = value
            elif name == 'current-ao':
                self.audio_driver = value
            elif name == 'time-pos' and isinstance(value, (int, float)) and not isinstance(value, bool):
                if self.playback_position is not None and value > self.playback_position:
                    self._ready = True
                self.playback_position = value
        elif event == 'playback-restart':
            self._ready = True
        elif event == 'end-file':
            if data.get('reason') != 'stop':
                self._fail('The stream stopped. ' + self._last_error())
        elif event == 'log-message':
            self._diagnostic('{}: {}'.format(data.get('prefix', 'mpv'), data.get('text', '')))
        self._refresh_status()

    def _send_raw(self, command):
        sock = self.sock
        if sock:
            sock.sendall((json.dumps(command) + '\n').encode('utf-8'))

    def queue_command(self, command):
        if self.enabled and not self._stop_event.is_set():
            with self._lock:
                self._cmd_queue.append(command)

    def toggle_pause(self):
        self.pause() if not self.is_paused else self.play()

    def pause(self):
        self.is_paused = True
        self._requested_pause = True
        self.queue_command({'command': ['set_property', 'pause', True]})
        self._refresh_status()

    def play(self):
        self.is_paused = False
        self._requested_pause = False
        self.queue_command({'command': ['set_property', 'pause', False]})
        self._refresh_status()

    def set_volume(self, val):
        self.volume = max(0, min(100, int(val)))
        self.is_muted = self.volume == 0
        self.queue_command({'command': ['set_property', 'volume', self.volume]})

    def volume_up(self, step=5):
        self.set_volume(self.volume + step)

    def volume_down(self, step=5):
        self.set_volume(self.volume - step)

    def toggle_mute(self):
        if self.is_muted:
            self.set_volume(self._previous_volume or 50)
        else:
            self._previous_volume = self.volume
            self.set_volume(0)

    @staticmethod
    def _terminate(process):
        # Our children have separate sessions; also cancel their JS runtimes.
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=1)
        except (OSError, subprocess.SubprocessError):
            pass

    def _close_processes(self):
        with self._cleanup_lock:
            if self.sock:
                try:
                    self.sock.close()
                except OSError:
                    pass
                self.sock = None
            for process in (self._resolver, self.process):
                if process:
                    self._terminate(process)
            if self._socket_dir:
                self._socket_dir.cleanup()
                self._socket_dir = None

    def stop(self):
        self._stop_event.set()
        self._close_processes()
        for attribute in ('_worker_thread', '_log_thread'):
            thread = getattr(self, attribute)
            if thread and thread is not threading.current_thread():
                thread.join(timeout=2)
        self._close_processes()
        self.is_connected = False
        self.is_buffering = False
