"""Real foreground journeys, rolling wheels and planted world-space contacts."""
import math
import re
import unittest
from unittest.mock import patch
from claudefm.audio import AudioPlayer
from claudefm.locomotion import (
    sample_locomotion, journey_period, walking_feet, remap_journey_elapsed,
)
from claudefm.sprites import (
    WIDTH, FPS, ACTIVITY_KEYS, sample_activity, sample_travel_pose,
    travel_contact_shadows, _Canvas,
)
from claudefm.tui import TUI, visible_width


class LocomotionTests(unittest.TestCase):
    def states(self,key,cols):
        return [sample_locomotion(key,t/FPS,cols)
                for t in range(math.ceil(journey_period(key,cols)*FPS))]

    def test_complete_trips_travel_return_and_keep_the_canvas_inside_view(self):
        for cols in (64,80,120,160):
            for key in ('walk','bike'):
                states=self.states(key,cols)
                self.assertGreater(max(s.origin_x for s in states)-min(s.origin_x for s in states),12)
                self.assertTrue(any(s.stage=='outbound' and s.moving for s in states))
                self.assertTrue(any(s.stage=='return' and s.moving for s in states))
                self.assertEqual(states[0].origin_x,states[-1].origin_x)
                self.assertEqual(states[0].facing,states[-1].facing)
                for s in states:
                    self.assertTrue(1<=s.origin_x<=cols-WIDTH-1,(cols,key,s))
                for a,b in zip(states,states[1:]):
                    if a.facing!=b.facing:
                        self.assertFalse(a.moving or b.moving)
                        self.assertEqual(a.origin_x,b.origin_x)
                        self.assertEqual(a.look,-1)

    def test_actual_floor_pixels_are_planted_and_do_not_slide_with_the_body(self):
        witnessed_support=False
        for cols in (64,80,160):
            previous=None
            for state in self.states('walk',cols):
                pose=sample_travel_pose('walk',state)
                feet=walking_feet(state)
                actual={state.origin_x+x for x,ch in enumerate(pose[-1]) if ch=='C'}
                predicted={foot.world_x+dx for foot in feet if foot.planted for dx in (0,1)}
                self.assertEqual(actual,predicted,(cols,state))
                runs=re.findall('C+',pose[-1])
                self.assertGreaterEqual(len(runs),3,(cols,state))
                self.assertTrue(all(len(run)==2 for run in runs),(cols,state,runs))
                if not state.moving:self.assertEqual(len(runs),4)
                if previous:
                    old,old_feet=previous
                    if state.facing==old.facing and state.stage==old.stage:
                        for a,b in zip(old_feet,feet):
                            if a.planted and b.planted:
                                self.assertLessEqual(abs(a.world_x-b.world_x),1,(old,state,a,b))
                                witnessed_support |= state.origin_x!=old.origin_x
                    elif state.facing!=old.facing:
                        old_pose=sample_travel_pose('walk',old)
                        old_pixels={old.origin_x+x for x,ch in enumerate(old_pose[-1]) if ch=='C'}
                        self.assertEqual(actual,old_pixels)
                previous=state,feet
        self.assertTrue(witnessed_support)

    def test_bicycle_rolls_by_world_distance_and_freezes_when_stopped(self):
        states=self.states('bike',80)
        for state in states[::17]:
            angles=[]
            with patch.object(_Canvas,'wheel',autospec=True,
                              side_effect=lambda c,x,y,angle:angles.append(angle)):
                sample_travel_pose('bike',state)
            self.assertEqual(angles,[state.distance/4]*2)
        strip_eyes=lambda pose:[''.join('C' if ch=='E' else ch for ch in row) for row in pose]
        stopped=[s for s in states if s.stage=='rest_right' and s.facing==1]
        expected=strip_eyes(sample_travel_pose('bike',stopped[0]))
        for state in stopped:
            self.assertEqual(strip_eyes(sample_travel_pose('bike',state)),expected)
        self.assertEqual(strip_eyes(sample_travel_pose('bike',states[0])),
                         strip_eyes(sample_travel_pose('bike',states[-1])))

    def test_actor_and_physical_shadow_pivots_match_in_both_directions(self):
        for key,pixel_pivot,physical_pivot in [('walk',37,38),('bike',40,41)]:
            state=next(s for s in self.states(key,80) if s.moving)
            reverse=state._replace(facing=-1)
            front=sample_travel_pose(key,state)
            back=sample_travel_pose(key,reverse)
            for y,row in enumerate(front):
                for x,ch in enumerate(row):
                    if ch!=' ':self.assertEqual(back[y][pixel_pivot-x],ch)
            a,b=travel_contact_shadows(key,state),travel_contact_shadows(key,reverse)
            self.assertEqual([p[0] for p in b],[physical_pivot-p[0] for p in a])

    def test_stationary_activities_keep_the_existing_origin_and_exact_pose(self):
        for key in ACTIVITY_KEYS:
            if key in ('walk','bike'):continue
            origins=set()
            for t in (0,2,13,30):
                state=sample_locomotion(key,t,80);origins.add(state.origin_x)
                self.assertFalse(state.moving)
                self.assertEqual(sample_travel_pose(key,state),sample_activity(key,t))
            self.assertEqual(len(origins),1)

    def test_resize_preserves_stage_facing_and_progress(self):
        for key in ('walk','bike'):
            for old_cols,new_cols in ((80,64),(64,160),(160,80)):
                for old in self.states(key,old_cols):
                    remapped=remap_journey_elapsed(key,old.elapsed,old_cols,new_cols)
                    new=sample_locomotion(key,remapped,new_cols)
                    self.assertEqual((old.stage,old.facing,old.moving),
                                     (new.stage,new.facing,new.moving),(old,new))
                    if old.moving:
                        self.assertLess(abs(old.distance/old.span-new.distance/new.span),.02)
        tui=TUI(AudioPlayer(enabled=False),initial_activity='walk',initial_theme='light')
        tui.animation_time=30;tui.scene.elapsed=30
        before=tui._frame_motion(80)
        after=tui._frame_motion(64)
        self.assertEqual((before.stage,before.facing),(after.stage,after.facing))
        self.assertEqual((tui.animation_time,tui.scene.elapsed),(30,30))

    def test_pause_selection_and_redraw_share_a_single_frame_state(self):
        tui=TUI(AudioPlayer(enabled=False),initial_activity='walk',initial_theme='light')
        tui.advance(7)
        before=tui._frame_motion(80)
        tui.audio.is_paused=True;tui.advance(11)
        self.assertEqual(tui._frame_motion(80),before)
        tui._motion_cache=None
        with patch('claudefm.tui.sample_locomotion',wraps=sample_locomotion) as sample:
            lines=tui.render_lines(80,24)
            self.assertEqual(sample.call_count,1)
            self.assertTrue(all(visible_width(line)==80 for line in lines))
        tui.set_activity('bike')
        self.assertEqual(tui.animation_time,0)
        self.assertEqual(tui._journey_offset,0)
        self.assertFalse(tui._frame_motion(80).moving)


if __name__=='__main__':unittest.main()
