"""Scene pairing, elapsed-time carousel, compositing and responsive layout."""
import unittest
from claudefm.audio import AudioPlayer
from claudefm.scene import (SCENE_NAMES, Canvas, render_background, _base,
                            scene_geometry, rain_glass_contains, _ridge_profile)
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

    def test_rain_never_overpaints_window_frames_or_mullions(self):
        for w,h in ((64,28),(100,52),(160,88)):
            for dark in (False,True):
                base=_base(w,h,'coding',dark)
                changes=0
                for step in range(64):
                    world=render_background(w,h,'coding',dark,step/8)
                    for y,(before,after) in enumerate(zip(base,world)):
                        for x,(a,b) in enumerate(zip(before,after)):
                            if a!=b:
                                changes+=1
                                self.assertTrue(rain_glass_contains(w,h,x,y),(w,h,x,y))
                self.assertGreater(changes,0)

    def test_snow_begins_on_actual_mountain_ridge(self):
        w,h=120,64
        world=_base(w,h,'bike',False)
        ridge=_ridge_profile(w,h,h*.60,.8,.38)
        snow=(237,241,229)
        count=0
        for x in range(w):
            ys=[y for y in range(h) if world[y][x]==snow]
            if ys:
                count+=len(ys)
                self.assertEqual(ys[0],ridge[x],x)
                self.assertEqual(ys,list(range(ys[0],ys[-1]+1)),x)
                self.assertTrue(all(y>=ridge[x] for y in ys))
        self.assertGreater(count,50)

    def test_petals_stay_below_their_canopies_without_sky_wrap(self):
        w,h=100,52
        _,canopies=scene_geometry(w,h,'wave')
        base=_base(w,h,'wave',False)
        changed=0
        for frame in range(96):
            world=render_background(w,h,'wave',False,frame/8)
            for y,(before,after) in enumerate(zip(base,world)):
                for x,(a,b) in enumerate(zip(before,after)):
                    if a!=b:
                        changed+=1
                        self.assertTrue(any(abs(x-sx)<w*.045+4 and sy-1<=y<=h-2
                                            for sx,sy in canopies),(x,y))
        self.assertGreater(changed,0)

    def test_stars_twinkle_in_place_without_appearing_at_unrelated_coordinates(self):
        w,h=100,52
        _,moon,positions,_=scene_geometry(w,h,'napping')
        positions=set(positions)
        base=_base(w,h,'napping',True)
        changed=set()
        for i in range(60):
            world=render_background(w,h,'napping',True,i/4)
            for y in range(round(h*.47)):
                for x in range(w):
                    if base[y][x]!=world[y][x]:
                        changed.add((x,y))
                        self.assertIn((x,y),positions)
        self.assertEqual(changed,positions)
        self.assertFalse(any(abs(x-moon[0])<4 and abs(y-moon[1])<4 for x,y in positions))

    def test_water_reflections_are_below_and_aligned_with_their_light(self):
        w,h=120,64
        for key in ('bike','napping','guitar'):
            info=scene_geometry(w,h,key)
            light_x,waterline=(info[1][0]-1,info[3]) if key=='napping' else (info[1],info[2])
            for dark in (False,True):
                world=_base(w,h,key,dark)
                for y in range(waterline+2,round(h*.84),3):
                    left,right=round(w*.50),round(w*.94)
                    brightest=max(range(left,right),key=lambda x:sum(world[y][x]))
                    self.assertLess(abs(brightest-light_x),w*.16,(key,dark,y,brightest,light_x))

    def test_clipped_drawing_keeps_canvas_rectangular(self):
        c=Canvas(8,7,(1,2,3))
        c.rect(-100,0,20,2,(9,9,9));c.rect(-3,-2,7,5,(9,9,9))
        c.rect(7,5,20,20,(7,7,7));c.rect(1,2,-5,3,(6,6,6))
        c.line(-1000000,3,1000000,3,(8,8,8))
        c.line(20,-10,20,100,(8,8,8))
        c.ellipse(-3,4,7,4,(5,5,5))
        c.poly([(-30,-20),(100,3),(-30,20)],(4,4,4));c.poly([],(0,0,0))
        self.assertEqual(len(c.pixels),7)
        self.assertEqual([len(row) for row in c.pixels],[8]*7)
        empty=Canvas(0,0);empty.line(-1,-1,2,2,(0,0,0))
        self.assertEqual(empty.pixels,[])

    def test_animation_never_mutates_a_cached_world_or_another_frame(self):
        for key in SCENE_NAMES:
            before=_base(100,52,key,False)
            snapshot=tuple(tuple(row) for row in before)
            frame=render_background(100,52,key,False,1)
            frame[0][0]=(0,0,0)
            self.assertEqual(_base(100,52,key,False),snapshot)
            for step in range(24):
                world=render_background(100,52,key,False,step/8)
                self.assertEqual((len(world),len(world[0])),(52,100))
                changed=sum(a!=b for ra,rb in zip(snapshot,world) for a,b in zip(ra,rb))
                self.assertLess(changed,100*52*.1,key)

    def test_travel_scenes_have_stationary_foreground_for_foot_and_wheel_contact(self):
        for width, height in ((64, 28), (80, 40), (160, 88)):
            for key in ('walk', 'bike'):
                for dark in (False, True):
                    ground = render_background(width, height, key, dark, 0)[-3:]
                    for elapsed in (1.5, 8, 17, 31):
                        self.assertEqual(render_background(width, height, key, dark, elapsed)[-3:],
                                         ground, (width, key, dark, elapsed))



if __name__=='__main__':unittest.main()
