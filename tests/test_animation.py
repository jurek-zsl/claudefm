"""Geometry/timing regressions behind visible jitter and terminal corruption."""
import io
import re
import unittest
from unittest.mock import patch
from claudefm.audio import AudioPlayer
from claudefm.sprites import ACTIVITY_KEYS, HEIGHT, WIDTH, SPRITE_PALETTE, sample_activity, ACTIVITY_PERIODS, contact_shadows
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

    def test_walk_has_three_weight_bearing_feet_and_distinct_legs(self):
        lifted = False
        for tick in range(round(ACTIVITY_PERIODS['walk']*24)):
            pose=sample_activity('walk',tick/24)
            contacts=re.findall('C+',pose[-1])
            self.assertGreaterEqual(len(contacts),3,tick)
            self.assertTrue(all(len(foot)==2 for foot in contacts),tick)
            lifted |= len(contacts)==3
            # The hip row can move with the body, but the four slots stay apart.
            lower=''.join(pose[23:])
            self.assertNotIn('CCCC',lower,tick)
        self.assertTrue(lifted)

    def test_jump_gathers_leaves_floor_and_lands_before_recovering(self):
        neutral=sample_activity('bounce',0)
        crouch=sample_activity('bounce',1.65)
        apex=sample_activity('bounce',2.25)
        landing=sample_activity('bounce',2.8)
        first=lambda pose:min(y for y,row in enumerate(pose) if 'C' in row)
        self.assertGreater(first(crouch),first(neutral))
        self.assertLess(first(apex),first(neutral))
        self.assertNotIn('C',''.join(apex[-4:]))
        self.assertEqual(len(re.findall('C+',landing[-1])),4)
        self.assertEqual(neutral,sample_activity('bounce',ACTIVITY_PERIODS['bounce']))
        ground=contact_shadows('bounce',0)[0]
        airborne=contact_shadows('bounce',2.25)[0]
        self.assertEqual(ground[1],26)
        self.assertLess(airborne[2],ground[2])
        self.assertLess(airborne[3],ground[3])

    @staticmethod
    def coral_components(pose):
        remaining={(x,y) for y,row in enumerate(pose) for x,ch in enumerate(row) if ch=='C'}
        groups=[]
        while remaining:
            group={remaining.pop()};todo=list(group)
            while todo:
                x,y=todo.pop()
                for q in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                    if q in remaining:
                        remaining.remove(q);group.add(q);todo.append(q)
            groups.append(group)
        return sorted(groups,key=len,reverse=True)

    def test_visible_hands_and_legs_remain_connected_during_full_actions(self):
        for key in ACTIVITY_KEYS:
            for tick in range(round(ACTIVITY_PERIODS[key]*24)):
                groups=self.coral_components(sample_activity(key,tick/24))
                # A desk or guitar may occlude a leg. No isolated hand, elbow,
                # or unoccluded leg is allowed above those foreground props.
                if key in ('coding','guitar'):
                    self.assertTrue(all(all(y>=24 for x,y in g) for g in groups[1:]),(key,tick))
                else:
                    self.assertEqual(len(groups),1,(key,tick))

    def test_coding_bursts_have_reading_pauses_and_static_furniture(self):
        rest=sample_activity('coding',3)
        self.assertEqual(rest,sample_activity('coding',3.6))
        self.assertNotEqual(sample_activity('coding',1.25),sample_activity('coding',1.45))
        for tick in range(round(ACTIVITY_PERIODS['coding']*24)):
            pose=sample_activity('coding',tick/24)
            for y,row in enumerate(rest):
                for x,ch in enumerate(row):
                    hand_over_keyboard = 23<=x<=25 and 19<=y<=21
                    if ch in 'TtMNe' and not hand_over_keyboard:
                        self.assertEqual(pose[y][x],ch,(tick,x,y))

    def test_coffee_has_a_long_sip_and_a_front_grip(self):
        for t in (0,3.5,4.5,5.5,6.5,7,8):
            pose=sample_activity('coffee',t)
            cup=[(x,y) for y,row in enumerate(pose) for x,ch in enumerate(row) if ch=='G']
            left=min(x for x,y in cup);top=min(y for x,y in cup)
            self.assertEqual(pose[top+2][left:left+2],'CC')
            self.assertEqual(pose[top+3][left:left+2],'CC')
        # Steam drifts independently; cup and hand stay held at sip height.
        a,b=sample_activity('coffee',4.6),sample_activity('coffee',6.1)
        self.assertEqual([r[23:34] for r in a[14:23]],[r[23:34] for r in b[14:23]])

    def test_action_loop_seams_return_to_rest_without_a_pose_jump(self):
        for key,period in ACTIVITY_PERIODS.items():
            before=sample_activity(key,period-1/24)
            start=sample_activity(key,0)
            change=sum(a!=b for ra,rb in zip(before,start) for a,b in zip(ra,rb))
            # Only wheel spokes or a newly emitted wisp may cross the seam.
            self.assertLessEqual(change,20,(key,change))
            self.assertTrue(all(ch==' ' for ch in start[0]),key)

    def test_contact_descriptors_share_the_constant_floor(self):
        self.assertEqual([s[0] for s in contact_shadows('bike',1)],[9,31])
        for key,period in ACTIVITY_PERIODS.items():
            for t in (0,period/3,period*.75):
                shadows=contact_shadows(key,t)
                self.assertTrue(shadows)
                for x,y,radius,alpha in shadows:
                    self.assertTrue(0<x<WIDTH and y==HEIGHT)
                    self.assertTrue(0<radius<WIDTH/2)
                    self.assertTrue(0<alpha<.3)

    def test_hop_shadow_samples_the_same_frame_as_the_actor(self):
        for frame in (43,44,53,63,64,65):
            start=frame/24
            inside=(frame+.9)/24
            self.assertEqual(sample_activity('bounce',inside),sample_activity('bounce',start))
            self.assertEqual(contact_shadows('bounce',inside),contact_shadows('bounce',start))
            # Repeated time additions can land a few ulps below a frame edge.
            self.assertEqual(contact_shadows('bounce',start-1e-12),contact_shadows('bounce',start))

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

    @staticmethod
    def eye_pixels(pose):
        return {(x,y) for y,row in enumerate(pose) for x,ch in enumerate(row) if ch=='E'}

    @staticmethod
    def without_steam(pose):
        return [row.replace('S',' ') for row in pose]

    def test_idle_and_wave_eyes_lead_a_grounded_counterbalanced_lean(self):
        for key,notice,lean_time in [('idle',2.0,3.2),('wave',1.1,2.7)]:
            rest=sample_activity(key,0)
            looking=sample_activity(key,notice)
            leaning=sample_activity(key,lean_time)
            self.assertNotEqual(self.eye_pixels(rest),self.eye_pixels(looking),key)
            head_left=lambda pose:min(x for x,ch in enumerate(pose[10]) if ch in 'CE')
            self.assertEqual(head_left(rest),head_left(looking),key)
            self.assertLess(head_left(leaning),head_left(rest),key)
            for frame in range(round(ACTIVITY_PERIODS[key]*24)):
                self.assertEqual(sample_activity(key,frame/24)[-1],rest[-1],(key,frame))
        # The raised hand and torso move in opposite directions, with a real hold.
        self.assertEqual(sample_activity('wave',3.3),sample_activity('wave',3.6))
        raised=sample_activity('wave',2.7)
        self.assertTrue(any('C' in row[29:] for row in raised[:10]))

    def test_coffee_gaze_precedes_weighted_cup_arc_and_a_held_sip(self):
        rest=sample_activity('coffee',0)
        notice=sample_activity('coffee',1.7)
        cup=lambda pose:{(x,y) for y,row in enumerate(pose) for x,ch in enumerate(row) if ch in 'Gg'}
        self.assertEqual(cup(rest),cup(notice))
        self.assertNotEqual(self.eye_pixels(rest),self.eye_pixels(notice))
        lifted=sample_activity('coffee',3.0)
        sipping=sample_activity('coffee',4.6)
        self.assertGreater(min(x for x,y in cup(lifted)),min(x for x,y in cup(rest)))
        self.assertLess(min(x for x,y in cup(sipping)),min(x for x,y in cup(lifted)))
        self.assertEqual(self.without_steam(sipping),self.without_steam(sample_activity('coffee',6.1)))
        self.assertEqual(len(self.eye_pixels(sipping)),4)
        for frame in range(round(ACTIVITY_PERIODS['coffee']*24)):
            self.assertEqual(sample_activity('coffee',frame/24)[-1],rest[-1],frame)

    def test_nap_snuggles_before_a_slow_exhale_without_moving_its_lower_edge(self):
        rest=sample_activity('napping',0)
        snuggle=sample_activity('napping',1)
        hand_top=lambda pose:min(y for y,row in enumerate(pose) if row[8]=='C')
        self.assertLess(hand_top(snuggle),hand_top(rest))
        body_top=lambda pose:min(y for y,row in enumerate(pose) if 'C' in row)
        self.assertEqual(body_top(sample_activity('napping',1.4)),14)
        self.assertEqual(body_top(sample_activity('napping',1.8)),13)
        self.assertEqual(body_top(sample_activity('napping',4.4)),13)
        self.assertEqual(body_top(sample_activity('napping',5.0)),14)
        for frame in range(round(ACTIVITY_PERIODS['napping']*24)):
            pose=sample_activity('napping',frame/24)
            # Hands may snuggle above the cushion; the body base stays put.
            self.assertEqual(pose[22][11:27],rest[22][11:27],frame)
            self.assertEqual(pose[23:],rest[23:],frame)

    def test_authored_poses_keep_two_intact_square_or_peacefully_closed_eyes(self):
        for key in ('wave','coffee','idle','napping','bounce'):
            for frame in range(round(ACTIVITY_PERIODS[key]*24)):
                eyes=self.eye_pixels(sample_activity(key,frame/24))
                groups=[]
                while eyes:
                    group={eyes.pop()};todo=list(group)
                    while todo:
                        x,y=todo.pop()
                        for neighbor in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                            if neighbor in eyes:
                                eyes.remove(neighbor);group.add(neighbor);todo.append(neighbor)
                    groups.append(group)
                self.assertEqual(len(groups),2,(key,frame))
                for eye in groups:
                    self.assertEqual(max(x for x,y in eye)-min(x for x,y in eye),1,(key,frame))
                    self.assertIn(len(eye),(2,4),(key,frame))



if __name__=='__main__':unittest.main()
