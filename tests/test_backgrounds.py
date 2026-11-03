"""Scene pairing, elapsed-time carousel, compositing and responsive layout."""
import unittest
from claudefm.audio import AudioPlayer
from claudefm.scene import SCENE_NAMES, render_background
from claudefm.sprites import ACTIVITIES, ACTIVITY_KEYS
from claudefm.tui import TUI, visible_width


class BackgroundTests(unittest.TestCase):
    def tui(self,key='bike'):
        return TUI(AudioPlayer(enabled=False), initial_activity=key)

    def test_nine_stable_distinct_scene_pairings(self):
        self.assertEqual(set(SCENE_NAMES),set(ACTIVITY_KEYS))
        self.assertEqual(len({v['background'] for v in ACTIVITIES.values()}),9)
        for dark in (False,True):
            worlds=[render_background(80,40,key,dark,1) for key in ACTIVITY_KEYS]
            self.assertEqual(len({str(world) for world in worlds}),9)
            for key,world in zip(ACTIVITY_KEYS,worlds):
                self.assertEqual(world,render_background(80,40,key,dark,1))
                self.assertEqual((len(world),len(world[0])),(40,80))
                self.assertGreater(len(set(pixel for row in world for pixel in row)),8)

    def test_five_minute_boundary_changes_activity_and_scene_together(self):
        tui=self.tui();tui.advance(299.99)
        self.assertEqual(tui.activity_key,'bike')
        tui.advance(.01)
        self.assertEqual(tui.activity_key,'walk')
        self.assertEqual(ACTIVITIES[tui.activity_key]['background'],'walk')
        self.assertAlmostEqual(tui.activity_elapsed,0)
        tui.advance(601.5)
        self.assertEqual(tui.activity_key,'bounce')
        self.assertAlmostEqual(tui.activity_elapsed,1.5)
        self.assertAlmostEqual(tui.animation_time,1.5)

    def test_paused_carousel_still_changes_after_five_minutes(self):
        tui=self.tui();tui.advance(17)
        tui.audio.is_paused=True;tui.advance(280)
        self.assertEqual(tui.animation_time,17)
        self.assertEqual(tui.scene.elapsed,17)
        self.assertEqual(tui.activity_key,'bike')
        tui.advance(3)
        self.assertEqual(tui.activity_key,'walk')
        self.assertEqual(tui.animation_time,0)
        self.assertEqual(tui.activity_elapsed,0)

    def test_manual_choice_resets_five_minute_timer_even_same_key(self):
        tui=self.tui();tui.advance(280);tui.set_activity('bike')
        self.assertEqual(tui.activity_elapsed,0)
        tui.advance(299)
        self.assertEqual(tui.activity_key,'bike')
        tui.set_activity('coffee')
        self.assertEqual(tui.activity_elapsed,0)
        tui.advance(300)
        self.assertEqual(tui.activity_key,'napping')

    def test_visuals_and_errors_do_not_claim_playback(self):
        tui=self.tui();lines=tui.render_lines(80,24)
        self.assertIn('VISUALS',lines[0]);self.assertNotIn('PLAYING',lines[0])
        # A lightweight stand-in exercises the TUI/audio status contract.
        class Failed:
            enabled=True;is_paused=False;is_buffering=False;is_muted=False
            status='error';error_message='Stream unavailable. Press Q to quit.'
            current_title='Claude FM';volume=80
        tui.audio=Failed();lines=tui.render_lines(80,24)
        self.assertIn('AUDIO ERROR',lines[0])
        self.assertIn('Stream unavailable',lines[-3])
        self.assertNotIn('PLAYING',lines[0])

    def test_every_world_and_theme_fits_after_resize(self):
        tui=self.tui()
        for cols,rows in [(64,18),(80,24),(100,30),(160,48)]:
            for key in ACTIVITY_KEYS:
                tui.set_activity(key)
                for dark in (False,True):
                    from claudefm.themes import LIGHT_THEME,DARK_THEME
                    tui.theme=DARK_THEME if dark else LIGHT_THEME
                    lines=tui.render_lines(cols,rows)
                    self.assertEqual(len(lines),rows)
                    self.assertTrue(all(visible_width(line)==cols for line in lines))
                    self.assertIn('Next 05:00',lines[-2])

    def test_ambient_motion_is_sparse_and_does_not_mutate_cached_world(self):
        for key in ('coding','wave','guitar','napping'):
            a=render_background(80,40,key,False,0)
            b=render_background(80,40,key,False,1.2)
            changed=sum(x!=y for ra,rb in zip(a,b) for x,y in zip(ra,rb))
            self.assertGreater(changed,0,key)
            self.assertLess(changed,120,key)
            self.assertEqual(a,render_background(80,40,key,False,0))


if __name__=='__main__':unittest.main()
