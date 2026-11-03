"""Startup appearance selection and unobstructed scene rendering."""
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from claudefm import cli
from claudefm.audio import AudioPlayer
from claudefm.themes import detect_system_theme
from claudefm.tui import TUI


class ThemeTests(unittest.TestCase):
    def test_macos_dark_and_light_appearance(self):
        for appearance,expected in [('Dark\n','dark'),('Light\n','light')]:
            with patch('claudefm.themes.sys.platform','darwin'), \
                 patch('claudefm.themes.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=appearance)) as run:
                self.assertEqual(detect_system_theme(),expected)
                self.assertEqual(run.call_args.args[0],['/usr/bin/defaults','read','-g','AppleInterfaceStyle'])
                self.assertLessEqual(run.call_args.kwargs['timeout'],1)

    def test_missing_appearance_key_falls_back_to_light(self):
        with patch('claudefm.themes.sys.platform','darwin'), \
             patch('claudefm.themes.subprocess.run',return_value=SimpleNamespace(returncode=1,stdout='')):
            self.assertEqual(detect_system_theme(),'light')

    def test_timeout_and_process_errors_fall_back_to_light(self):
        for error in (subprocess.TimeoutExpired('defaults',.5),OSError('unavailable')):
            with patch('claudefm.themes.sys.platform','darwin'), \
                 patch('claudefm.themes.subprocess.run',side_effect=error):
                self.assertEqual(detect_system_theme(),'light')

    def test_non_macos_never_spawns_appearance_process(self):
        with patch('claudefm.themes.sys.platform','linux'), \
             patch('claudefm.themes.subprocess.run') as run:
            self.assertEqual(detect_system_theme(),'light');run.assert_not_called()

    def test_tui_detects_once_at_startup_and_explicit_choices_skip_detection(self):
        player=AudioPlayer(enabled=False)
        with patch('claudefm.tui.detect_system_theme',return_value='dark') as detect:
            tui=TUI(player)
            self.assertTrue(tui.theme.is_dark)
            tui.render_lines(80,24);tui.render_lines(80,24)
            detect.assert_called_once_with()
        with patch('claudefm.tui.detect_system_theme') as detect:
            self.assertFalse(TUI(player,initial_theme='light').theme.is_dark)
            self.assertTrue(TUI(player,initial_theme='dark').theme.is_dark)
            detect.assert_not_called()

    def test_cli_automatic_default_and_explicit_overrides(self):
        for flags,expected in [([], 'auto'),(['--light'],'light'),(['--dark'],'dark')]:
            with patch('sys.argv',['claudefm','--no-audio']+flags), \
                 patch('claudefm.cli.AudioPlayer'),patch('claudefm.cli.TUI') as tui:
                cli.main()
                self.assertEqual(tui.call_args.kwargs['initial_theme'],expected)

    def test_track_title_banner_is_absent_from_the_scene(self):
        player=AudioPlayer(enabled=False)
        player.current_title='UNIQUE_TRACK_TITLE_SENTINEL'
        tui=TUI(player,initial_theme='light')
        output='\n'.join(tui.render_lines(80,24))
        self.assertNotIn(player.current_title,output)
        self.assertIn('Claude FM',output)
        self.assertIn('VISUALS',output)


if __name__=='__main__':unittest.main()
