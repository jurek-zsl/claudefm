"""Deterministic foreground journeys and world-space foot contacts.

Only walking and cycling travel. A single sampled state controls the actor,
its facing, contacts, wheels and particles; drawing never advances a clock.
"""
import math
from typing import NamedTuple
from claudefm.sprites import ACTIVITY_PERIODS, WIDTH, FPS


class LocomotionState(NamedTuple):
    origin_x: int
    facing: int
    moving: bool
    distance: float
    stride: float
    phase: float
    elapsed: float
    start_x: float
    span: float
    look: int
    stage: str


class FootContact(NamedTuple):
    local_x: int
    y: int
    planted: bool
    world_x: int


def _raster(value):
    return math.floor(value+.5+1e-9)


def _time(elapsed):
    return math.floor(max(0,elapsed)*FPS+1e-9)/FPS


def _route(activity, cols):
    available=max(0,cols-WIDTH-4)
    span=min(64,available)
    if activity=='bike':
        # Each trip ends at a complete spoke quarter-turn, so flipping a
        # stationary bicycle cannot snap its wheels to a different angle.
        span=math.floor(span/(2*math.pi))*2*math.pi
        cycles=max(1,round(span/10))
        duration=span/5+1
        rests=(2.5,4.2,3.3)
    else:
        cycles=max(1,math.ceil(span/4))
        duration=cycles*1.6
        rests=(2.8,4.8,3.2)
    left=math.floor((cols-WIDTH-span)/2)
    left=max(1,left)
    return left,span,cycles,duration,rests


def journey_period(activity, cols):
    """A complete out/rest/back/turn journey, sized to the actual viewport."""
    if activity not in ACTIVITY_PERIODS:
        raise KeyError(activity)
    if activity not in ('walk','bike'):
        return ACTIVITY_PERIODS[activity]
    _,_,_,duration,rests=_route(activity,cols)
    return sum(rests)+2*duration


def remap_journey_elapsed(activity, elapsed, old_cols, new_cols):
    """Preserve the current trip/rest and its progress when the viewport changes."""
    if activity not in ('walk','bike') or old_cols==new_cols:
        return elapsed
    old_route=_route(activity,old_cols)
    new_route=_route(activity,new_cols)
    def segments(route):
        _,_,_,duration,rests=route
        return (rests[0],duration,rests[1]/2,rests[1]/2,
                duration,rests[2]/2,rests[2]/2)
    old,new=segments(old_route),segments(new_route)
    old_period,new_period=sum(old),sum(new)
    elapsed=_time(elapsed)
    cycles=math.floor(elapsed/old_period)
    phase=elapsed-cycles*old_period
    mapped=cycles*new_period
    for old_length,new_length in zip(old,new):
        if phase<old_length-1e-9:
            result=mapped+(phase/old_length)*new_length
            # Keep floor-to-frame sampling inside this same segment, including
            # a stop/turn boundary whose timestamp falls between two frames.
            earliest=math.ceil(mapped*FPS-1e-9)/FPS
            latest=(math.ceil((mapped+new_length)*FPS-1e-9)-1)/FPS
            return max(earliest,min(latest,result))
        phase=max(0,phase-old_length)
        mapped+=new_length
    return mapped


def _progress(u):
    """A long constant-speed middle with gentle, zero-velocity end ramps."""
    edge=.12
    u=max(0,min(1,u))
    v=1/(1-edge)
    if u<edge:
        return v*(u/2-edge*math.sin(math.pi*u/edge)/(2*math.pi))
    if u>1-edge:
        back=1-u
        return 1-v*(back/2-edge*math.sin(math.pi*back/edge)/(2*math.pi))
    return v*(u-edge/2)


def sample_locomotion(activity, elapsed, cols):
    """Sample a closed route. Distance is forward travel within the current leg."""
    if activity not in ACTIVITY_PERIODS:
        raise KeyError(activity)
    t=_time(elapsed)
    if activity not in ('walk','bike'):
        origin=max(1,min(cols-WIDTH-1,cols//3-8))
        return LocomotionState(origin,1,False,0,0,0,t,origin,0,0,'stationary')
    left,span,cycles,duration,rests=_route(activity,cols)
    first,right_rest,left_rest=rests
    period=sum(rests)+2*duration
    p=t % period
    right=left+span
    stride=span/cycles if span else 1
    if p<first:
        start,distance,facing,moving=left,0,1,False
        look=1 if p>first-.8 else 0
        stage='rest_left'
    elif p<first+duration:
        start,distance,facing,moving=left,span*_progress((p-first)/duration),1,True
        look=1;stage='outbound'
    elif p<first+duration+right_rest:
        wait=p-first-duration
        turned=wait>=right_rest/2
        start,distance,facing= (right,0,-1) if turned else (left,span,1)
        moving=False
        look=1 if turned else -1 if wait>right_rest/2-1 else 0
        stage='rest_right'
    elif p<first+2*duration+right_rest:
        start=right
        distance=span*_progress((p-first-duration-right_rest)/duration)
        facing,moving,look=-1,True,1;stage='return'
    else:
        wait=p-first-2*duration-right_rest
        turned=wait>=left_rest/2
        start,distance,facing= (left,0,1) if turned else (right,span,-1)
        moving=False
        look=1 if turned else -1 if wait>left_rest/2-1 else 0
        stage='rest_left'
    if span<=0:
        moving=False
    phase=(distance/stride)%1
    if phase<1e-9 or phase>1-1e-9:phase=0.0
    return LocomotionState(_raster(start+facing*distance),facing,moving,
                           distance,stride,phase,t,start,span,look,stage)


def walking_feet(state):
    """Feet recover in the air; each planted world coordinate stays fixed.

    The origin's raster rounding is explicitly cancelled here. Moving the
    torso one column therefore moves a stance foot one column backward in
    local coordinates, rather than dragging it across the ground.
    """
    q=state.distance/state.stride if state.stride else 0
    precise_origin=state.start_x+state.facing*state.distance
    feet=[]
    for hip,offset in zip((11,15,21,25),(.05,.30,.50,.75)):
        step=q+offset
        phase=step-math.floor(step)
        planted=phase<=.8
        if planted:
            delta=(.4-phase)*state.stride
            y=25
        else:
            u=(phase-.8)/.2
            ease=u*u*(3-2*u)
            delta=(-.4+.8*ease)*state.stride
            y=25-max(1,round(2*math.sin(math.pi*u)))
        local=hip+delta
        if state.facing==1:
            world=_raster(precise_origin+local)
            local_x=world-state.origin_x
        else:
            # A width-two foot mirrored about index18.5 has left index36-x.
            world=_raster(precise_origin+36-local)
            local_x=state.origin_x+36-world
        feet.append(FootContact(local_x,y,planted,world))
    return tuple(feet)
