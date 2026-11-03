"""Geometry/timing regressions behind visible jitter and terminal corruption."""
import io
import re
import unittest
from unittest.mock import patch
from claudefm.audio import AudioPlayer
from claudefm.sprites import ACTIVITY_KEYS, HEIGHT, WIDTH, SPRITE_PALETTE, sample_activity
from claudefm.tui import TUI, visible_width


class AnimationTests(unittest.TestCase):
    def make_tui(self, key='bike'):
        return TUI(AudioPlayer(enabled=False), initial_activity=key)

    def test_fixed_canvas_and_known_pixels_across_actions(self):
        for key in ACTIVITY_KEYS:
            for tick in range(240):
                pose = sample_activity(key, tick/24)
                self.assertEqual(len(pose), HEIGHT, (key,tick))
                self.assertEqual({len(row) for row in pose}, {WIDTH}, (key,tick))
                self.assertTrue(set(''.join(pose)) <= set(SPRITE_PALETTE))

    def test_fixed_bicycle_rims_and_pillow(self):
        for key, color in [('bike','K'),('napping','Z')]:
            poses = [sample_activity(key,t/24) for t in range(120)]
            floor = lambda pose: tuple(row for row in pose[-2:]) if key=='napping' else tuple(
                (x,y) for y,row in enumerate(pose) for x,c in enumerate(row)
                if c==color and y>=17 and (x<14 or x>26))
            self.assertTrue(all(floor(p)==floor(poses[0]) for p in poses))

    def test_walk_keeps_four_separated_legs_throughout_stride(self):
        for tick in range(120):
            pose=sample_activity('walk',tick/24)
            legs=re.findall('C+',pose[22])
            self.assertEqual(legs,['CC']*4,tick)

    def test_jump_has_anticipation_air_and_return_to_floor(self):
        neutral=sample_activity('bounce',0)
        apex=sample_activity('bounce',1.1)
        self.assertIn('C', neutral[-1])
        self.assertNotIn('C', ''.join(apex[-4:]))
        self.assertEqual(neutral,sample_activity('bounce',2.4))

    def test_blink_does_not_repeat_every_action_cycle(self):
        count=lambda t: ''.join(sample_activity('idle',t)).count('E')
        self.assertEqual(count(0),8)
        self.assertEqual(count(5.15),4)
        self.assertEqual(count(5.4),8)

    def test_pause_freezes_pose_and_scene_motion(self):
        tui=self.make_tui('napping');tui.advance(2)
        before=(tui.animation_time,tui.scene.cloud_x,
                [(p.x,p.y,p.life) for p in tui.scene.particles])
        tui.audio.is_paused=True;tui.advance(90)
        self.assertEqual(before,(tui.animation_time,tui.scene.cloud_x,
                         [(p.x,p.y,p.life) for p in tui.scene.particles]))
        tui.audio.is_paused=False;tui.advance(.1)
        self.assertAlmostEqual(tui.animation_time,2.1)

    def test_time_sampling_independent_of_redraw_rate(self):
        a,b=self.make_tui('walk'),self.make_tui('walk')
        for _ in range(24): a.advance(1/24)
        for _ in range(12): b.advance(1/12)
        self.assertEqual(sample_activity('walk',a.animation_time),
                         sample_activity('walk',b.animation_time))

    def test_activity_change_resets_pose_and_particles(self):
        tui=self.make_tui('napping');tui.advance(2)
        self.assertTrue(tui.scene.particles)
        tui.set_activity('wave')
        self.assertEqual(tui.animation_time,0)
        self.assertEqual(tui.scene.particles,[])

    def test_terminal_rows_fit_minimum_and_large_sizes(self):
        tui=self.make_tui()
        for cols,rows in [(64,18),(80,24),(120,40),(20,6),(1,1)]:
            for key in ACTIVITY_KEYS:
                tui.set_activity(key)
                for help_shown in (False,True):
                    tui.show_help=help_shown
                    lines=tui.render_lines(cols,rows)
                    self.assertEqual(len(lines),rows,(cols,rows,key))
                    self.assertTrue(all(visible_width(s)==cols for s in lines),
                                    (cols,rows,key,[visible_width(s) for s in lines]))

    def test_redraw_has_no_simulation_side_effects_and_skips_identical_rows(self):
        tui=self.make_tui()
        with patch('claudefm.tui.shutil.get_terminal_size',return_value=(80,24)), \
             patch('claudefm.tui.sys.stdout',new_callable=io.StringIO) as out:
            tui.render(); first=out.getvalue();out.seek(0);out.truncate()
            tui.render()
            self.assertTrue(first)
            self.assertEqual(out.getvalue(),'')
            self.assertEqual(tui.animation_time,0)


if __name__=='__main__':unittest.main()
