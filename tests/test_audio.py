"""Playback truth, dependency discovery, IPC framing and cleanup regressions."""
import io
import json
import os
import threading
import unittest
from unittest.mock import Mock, patch
from claudefm.audio import AudioPlayer, find_executable


class AudioTests(unittest.TestCase):
    def active_player(self):
        p = AudioPlayer(enabled=False)
        p.enabled = True
        p.is_connected = True
        return p

    def event(self, player, name, data):
        player._handle_message({'event':'property-change', 'name':name, 'data':data})

    def test_unlinked_homebrew_extractor_is_found(self):
        target = '/opt/homebrew/opt/yt-dlp/bin/yt-dlp'
        with patch('claudefm.audio.shutil.which', return_value=None), \
             patch('claudefm.audio.os.path.isfile', side_effect=lambda p:p==target), \
             patch('claudefm.audio.os.access', return_value=True):
            self.assertEqual(find_executable('yt-dlp'), target)

    def test_missing_dependencies_are_visible_before_launch(self):
        for name in ('mpv', 'yt-dlp'):
            with patch('claudefm.audio.find_executable', side_effect=lambda n:None if n==name else '/bin/'+n), \
                 patch('claudefm.audio.subprocess.Popen') as launch:
                p = AudioPlayer()
                self.assertEqual(p.status, 'error')
                self.assertIn(name, p.error_message)
                self.assertFalse(p.is_buffering)
                launch.assert_not_called()
                p.stop()

    def test_ipc_connection_and_decoding_alone_do_not_claim_playback(self):
        p=self.active_player();p._refresh_status()
        self.assertEqual(p.status,'buffering')
        self.event(p,'audio-params',{'samplerate':44100})
        self.event(p,'audio-out-params',{'samplerate':44100})
        self.assertEqual(p.status,'buffering')
        self.event(p,'time-pos',0)
        self.assertEqual(p.status,'buffering')
        self.event(p,'time-pos',.5)
        self.assertEqual(p.status,'playing')
        self.event(p,'paused-for-cache',True)
        self.assertEqual(p.status,'buffering')
        self.event(p,'paused-for-cache',False)
        self.assertEqual(p.status,'playing')

    def test_ipc_preserves_fragmented_and_combined_utf8_messages(self):
        p=self.active_player()
        messages=[{'event':'property-change','name':'media-title','data':'Clawd café ♪'},
                  {'event':'property-change','name':'audio-out-params','data':{'samplerate':44100}},
                  {'event':'playback-restart'}]
        payload=''.join(json.dumps(m,ensure_ascii=False)+'\n' for m in messages).encode()
        for b in payload: p._consume(bytes([b]))
        self.assertEqual(p.current_title,'Clawd café ♪')
        self.assertEqual(p.status,'playing')
        self.assertEqual(p._buffer,b'')

    def test_responses_are_not_confused_with_observed_properties(self):
        p=self.active_player();p.pause()
        p._handle_message({'data':False,'request_id':7,'error':'success'})
        self.assertTrue(p.is_paused)
        self.assertEqual(p.status,'paused')
        self.event(p,'pause',False)
        self.assertTrue(p.is_paused)  # Notification predates the pending keypress.
        self.event(p,'pause',True)
        p.play();self.event(p,'pause',False)
        self.assertFalse(p.is_paused)

    def test_stream_failure_remains_error_after_later_property(self):
        p=self.active_player()
        p._diagnostic('Audio output failed')
        p._handle_message({'event':'end-file','reason':'error','error':'loading failed'})
        self.event(p,'pause',False)
        self.assertEqual(p.status,'error')
        self.assertIn('Audio output failed',p.error_message)
        self.assertFalse(p.is_buffering)

    def test_diagnostics_bounded_printable_and_redact_media_urls(self):
        p=AudioPlayer(enabled=False)
        for i in range(100): p._diagnostic('error https://media.example/private?sig=secret\n'+str(i))
        self.assertEqual(len(p.diagnostics),24)
        self.assertTrue(all('secret' not in x and '\n' not in x for x in p.diagnostics))

    def test_mute_restores_volume_and_positive_volume_unmutes(self):
        p=AudioPlayer(enabled=False,initial_volume=60)
        p.toggle_mute();self.assertEqual((p.volume,p.is_muted),(0,True))
        p.toggle_mute();self.assertEqual((p.volume,p.is_muted),(60,False))
        p.toggle_mute();p.volume_up();self.assertEqual((p.volume,p.is_muted),(5,False))
        p.set_volume(1000);self.assertEqual(p.volume,100)

    def test_fast_load_failure_is_observed_after_subscribing(self):
        p = self.active_player()
        p.is_connected = False
        p.stream_url = '/missing-audio.mp3'
        p.mpv_path, p.sock_path = '/fake/mpv', '/tmp/fake-mpv.sock'
        process = Mock()
        process.poll.return_value = None
        process.stdout = io.StringIO('Failed to open media file.\n')
        sock = Mock()
        sock.recv.return_value = b'{"event":"end-file","reason":"error"}\n'
        with patch('claudefm.audio.subprocess.Popen', return_value=process) as launch, \
             patch('claudefm.audio.socket.socket', return_value=sock), \
             patch.object(p, '_terminate'):
            p._worker_loop()
            commands = [json.loads(call.args[0])['command'] for call in sock.sendall.call_args_list]
            load_index = next(i for i,c in enumerate(commands) if c[0]=='loadfile')
            self.assertTrue(all(c[0]=='observe_property' for c in commands[:load_index-1]))
            self.assertEqual(commands[load_index], ['loadfile', p.stream_url, 'replace'])
            self.assertNotIn(p.stream_url, launch.call_args.args[0])
            self.assertEqual(p.status, 'error')
            self.assertFalse(p.is_buffering)
            p.stop()

    def test_stop_during_environment_discovery_cannot_launch_late_child(self):
        entered, resume = threading.Event(), threading.Event()
        def slow_environment(player):
            entered.set()
            resume.wait(1)
            return {}
        with patch('claudefm.audio.find_executable', return_value='/fake/tool'), \
             patch.object(AudioPlayer, '_child_env', slow_environment), \
             patch('claudefm.audio.subprocess.Popen') as launch:
            p = AudioPlayer()
            self.assertTrue(entered.wait(1))
            stopper = threading.Thread(target=p.stop)
            stopper.start()
            try:
                self.assertTrue(p._stop_event.wait(1))
            finally:
                resume.set()
            stopper.join(timeout=1)
            self.assertFalse(stopper.is_alive())
            self.assertFalse(p._worker_thread.is_alive())
            launch.assert_not_called()
            self.assertIsNone(p._socket_dir)

    def test_disabled_and_repeated_stop_are_safe(self):
        p=AudioPlayer(enabled=False)
        self.assertEqual(p.status,'disabled')
        p.stop();p.stop()
        self.assertFalse(p.is_connected)
        self.assertFalse(p.is_buffering)


if __name__=='__main__': unittest.main()
