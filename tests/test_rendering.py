"""Contact shadows stay on the floor and leave cached scenery reusable."""
import io
import sys
import termios
import unittest
from unittest.mock import patch

from claudefm.audio import AudioPlayer
from claudefm.scene import render_background
from claudefm.tui import TUI, _composite_contact_shadows


class GroundingTests(unittest.TestCase):
    def test_soft_contact_never_darkens_pixels_above_the_floor(self):
        color = (100, 150, 200)
        pixels = [[color] * 40 for _ in range(30)]
        _composite_contact_shadows(pixels, 0, 0, [(20, 26, 8, .2)])
        self.assertTrue(all(pixel == color for row in pixels[:26] for pixel in row))
        self.assertTrue(all(pixel == color for row in pixels[28:] for pixel in row))
        self.assertLess(pixels[26][19][0], pixels[26][12][0])
        self.assertGreater(pixels[26][19][0], 0)
        self.assertLess(pixels[26][19][0], pixels[27][19][0])

    def test_contact_patches_clip_safely_at_terminal_edges(self):
        pixels = [[(100, 100, 100)] * 8 for _ in range(4)]
        _composite_contact_shadows(pixels, -3, 0, [(0, 3, 7, .2)])
        self.assertEqual([len(row) for row in pixels], [8] * 4)
        self.assertEqual(pixels[:3], [[(100, 100, 100)] * 8 for _ in range(3)])
        self.assertLess(pixels[3][0][0], 100)
        _composite_contact_shadows([], 0, 0, [(0, 0, 1, .2)])

    def test_compositing_keeps_cached_scenery_pristine(self):
        player = AudioPlayer(enabled=False)
        tui = TUI(player, initial_theme='light', initial_activity='bike')
        before = render_background(80, 40, 'bike', False, 0)
        first = tui.render_lines(80, 24)
        self.assertEqual(render_background(80, 40, 'bike', False, 0), before)
        self.assertEqual(tui.render_lines(80, 24), first)


class SynchronizedOutputTests(unittest.TestCase):
    def tui(self):
        tui=TUI(AudioPlayer(enabled=False),initial_theme='light')
        tui.start_time=100
        return tui

    def test_changed_rows_form_one_balanced_frame_with_resize_inside(self):
        tui=self.tui()
        with patch('claudefm.tui.shutil.get_terminal_size',return_value=(80,24)), \
             patch('claudefm.tui.time.monotonic',return_value=100), \
             patch('claudefm.tui.sys.stdout',new_callable=io.StringIO) as out:
            tui.render()
            written=out.getvalue()
            self.assertTrue(written.startswith('\033[?2026h'))
            self.assertTrue(written.endswith('\033[?2026l'))
            self.assertEqual(written.count('\033[?2026h'),1)
            self.assertEqual(written.count('\033[?2026l'),1)
            self.assertLess(written.index('\033[?2026h'),written.index('\033[2J'))
            self.assertLess(written.index('\033[2J'),written.index('\033[?2026l'))
            out.seek(0);out.truncate()
            tui.render()
            self.assertEqual(out.getvalue(),'')

    def test_failed_or_interrupted_frame_still_attempts_end_mode(self):
        for failure in (OSError('frame write failed'),KeyboardInterrupt()):
            tui=self.tui();attempts=[]
            class Output:
                def write(self,text):
                    attempts.append(text)
                    if text.startswith('\033[?2026h'):raise failure
                def flush(self):pass
            with patch('claudefm.tui.shutil.get_terminal_size',return_value=(80,24)), \
                 patch('claudefm.tui.sys.stdout',Output()):
                with self.assertRaises(type(failure)):tui.render()
            self.assertEqual(attempts[-1],'\033[?2026l')
            self.assertEqual(tui._previous_lines,[])

    def test_cleanup_resets_mode_first_and_restores_termios_even_if_output_fails(self):
        tui=self.tui();tui.old_termios=['saved tty state']
        with patch('claudefm.tui.sys.stdout',new_callable=io.StringIO) as out, \
             patch('claudefm.tui.termios.tcsetattr') as restore:
            tui.restore_terminal()
            text=out.getvalue()
            self.assertTrue(text.startswith('\033[?2026l'))
            self.assertLess(text.index('\033[?2026l'),text.index('\033[?25h'))
            restore.assert_called_once_with(sys.stdin,termios.TCSADRAIN,tui.old_termios)
        attempts=[]
        class BrokenOutput:
            def write(self,text):
                attempts.append(text)
                raise OSError('pipe closed')
            def flush(self):pass
        with patch('claudefm.tui.sys.stdout',BrokenOutput()), \
             patch('claudefm.tui.termios.tcsetattr') as restore:
            with self.assertRaises(OSError):tui.restore_terminal()
            restore.assert_called_once_with(sys.stdin,termios.TCSADRAIN,tui.old_termios)
        self.assertTrue(attempts[0].startswith('\033[?2026l'))

    def test_run_stops_audio_when_terminal_output_cleanup_fails(self):
        tui=self.tui()
        class BrokenOutput:
            def write(self,text):raise OSError('pipe closed')
            def flush(self):pass
        with patch.object(tui,'setup_terminal'), \
             patch.object(tui,'handle_input',side_effect=lambda:setattr(tui,'running',False)), \
             patch.object(tui.audio,'stop') as stop, \
             patch('claudefm.tui.signal.signal'), \
             patch('claudefm.tui.sys.stdout',BrokenOutput()):
            with self.assertRaises(OSError):tui.run()
            stop.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
