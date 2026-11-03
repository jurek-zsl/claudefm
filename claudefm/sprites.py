"""Clawd, drawn on a square-pixel rig for terminal half-block rendering.

Original terminal artwork, studied from Claude FM and Anthropic's Clawd clips.
These are adaptations, not extracted or official animation assets. Every pose
uses the same 40 x 26 canvas and floor, so props and feet cannot jump on swaps.
"""
import math

WIDTH, HEIGHT = 40, 26
FPS = 24
SPRITE_PALETTE = {
    ' ': None, 'C': (221, 119, 91), 'E': (28, 25, 24),
    'K': (47, 45, 44), 'S': (150, 151, 147), 's': (204, 202, 191),
    'B': (96, 120, 117), 'T': (157, 115, 81), 't': (117, 85, 63),
    'M': (114, 127, 130), 'N': (40, 51, 53), 'e': (143, 183, 158),
    'G': (231, 213, 177), 'g': (83, 59, 45), 'Z': (130, 143, 165),
    'H': (70, 65, 61), 'A': (198, 151, 86), 'a': (100, 73, 49),
}


def _mix(a, b, u):
    u = max(0.0, min(1.0, u))
    return a + (b - a) * u * u * (3 - 2 * u)


def _track(t, keys):
    for (ta, a), (tb, b) in zip(keys, keys[1:]):
        if t < tb:
            return _mix(a, b, (t - ta) / (tb - ta))
    return keys[-1][1]


def _sample_time(elapsed):
    """One clock quantization for the actor and all dependent contact geometry."""
    return math.floor(max(0,elapsed)*FPS+1e-9)/FPS


class _Canvas:
    def __init__(self):
        self.pixels = [[' '] * WIDTH for _ in range(HEIGHT)]

    def rect(self, x, y, w, h, color='C'):
        x, y = round(x), round(y)
        for yy in range(max(0, y), min(HEIGHT, y + h)):
            for xx in range(max(0, x), min(WIDTH, x + w)):
                self.pixels[yy][xx] = color

    def line(self, x0, y0, x1, y1, color='C', thickness=1):
        steps = max(abs(round(x1 - x0)), abs(round(y1 - y0)), 1)
        for i in range(steps + 1):
            self.rect(x0 + (x1-x0)*i/steps, y0 + (y1-y0)*i/steps, thickness, thickness, color)

    def wheel(self, x, y, angle):
        # Stable circular rim; only the two narrow spokes rotate.
        for a in (angle, angle + math.pi/2):
            dx, dy = 3*math.cos(a), 3*math.sin(a)
            self.line(x-dx, y-dy, x+dx, y+dy, 'S')
        for yy in range(-4, 5):
            for xx in range(-4, 5):
                r = xx*xx + yy*yy
                if 10 <= r <= 20:
                    self.rect(x+xx, y+yy, 1, 1, 'K')
        self.rect(x, y, 1, 1, 'K')

    def rows(self):
        return [''.join(row) for row in self.pixels]


# One complete, deliberately paced primary action. Blinks run independently.
ACTIVITY_PERIODS = {
    'bike': 2.4, 'walk': 3.2, 'coding': 10.4, 'bounce': 4.8,
    'wave': 8.0, 'coffee': 12.0, 'napping': 8.0, 'idle': 12.0,
    'guitar': 8.0,
}


def _arm(c, shoulder, elbow, wrist, hand=(4, 4)):
    """Two short connected segments; the hand is anchored at the wrist."""
    c.line(*shoulder, *elbow, thickness=2)
    joint_y = wrist[1] + (1 if hand[1] >= 3 else 0)
    c.line(*elbow, wrist[0]+1, joint_y, thickness=2)
    c.rect(*wrist, *hand)


def _torso(c, x=11, y=10, height=12, look=0, look_y=0,
           blink=False, closed=False):
    x, y = round(x), round(y)
    c.rect(x, y, 16, height)
    for ex in (3, 11):
        c.rect(x+ex+round(look), y+(4 if closed else 2)+round(look_y),
               2, 1 if blink or closed else 2, 'E')


def _legs(c, hip_y=22, feet=None):
    """Each hip, knee and two-pixel foot stays in its own small leg slot."""
    if feet is None:
        feet = [(x,25) for x in (11,15,21,25)]
    for hip_x, (foot_x, foot_y) in zip((11,15,21,25), feet):
        knee_y = min(foot_y-2, hip_y+1)
        # The ankle is drawn before its foot, so no stroke can cross the floor.
        c.line(hip_x, hip_y, hip_x, knee_y, thickness=2)
        c.line(hip_x, knee_y, foot_x, foot_y-2, thickness=2)
        c.rect(foot_x,foot_y,2,1)


def _rest_arms(c, y=10):
    _arm(c,(11,y+6),(10,y+7),(9,y+4))
    _arm(c,(26,y+6),(26,y+7),(25,y+4))


# Authored poses have holds and unequal transition times. Each table returns to
# the same quiet pose; eye and hand tracks deliberately lead or lag the torso.
ACTING_BEATS = {
    'wave': ((0,'rest'),(.85,'notice'),(1.4,'gather'),(2.2,'raise'),
             (2.9,'first wave'),(3.7,'hold'),(4.05,'second wave'),
             (5.0,'lower'),(5.7,'follow through'),(6.2,'rest')),
    'coffee': ((0,'rest'),(1.4,'notice mug'),(2.25,'gather'),(3,'lift'),
               (4.25,'sip'),(6.5,'lower'),(7.8,'settle'),(8.4,'rest')),
    'idle': ((0,'rest'),(1.8,'look left'),(2.3,'lean left'),(4.1,'recover'),
             (5.1,'rest'),(6.3,'look right'),(6.9,'lean right'),
             (8.4,'recover'),(9.4,'rest')),
    'napping': ((0,'rest'),(.7,'snuggle'),(1.6,'inhale'),(2.7,'hold'),
                (3.3,'sigh'),(6.4,'rest')),
    'bounce': ((0,'rest'),(1.25,'look down'),(1.5,'gather'),(1.8,'launch'),
               (2.25,'apex'),(2.7,'land'),(2.9,'rebound'),(3.3,'rest')),
}

_WAVE = {
    'look': ((0,0),(.8,0),(1.05,1),(5.7,1),(6.15,0),(8,0)),
    'lean': ((0,0),(1.2,0),(1.55,-.7),(2.2,-2),(2.8,-2),
             (3.2,-1),(3.7,-1),(4.05,-2),(4.55,-1.4),(5.0,-1.4),
             (5.6,.7),(6.2,0),(8,0)),
    'drop': ((0,0),(1.2,0),(1.48,1),(1.65,1),(2.0,0),(8,0)),
    'hand_x': ((0,25),(1.1,25),(1.45,26),(1.75,29),(2.2,31),
               (2.55,30),(2.9,32),(3.2,29),(3.7,29),(4.05,32),
               (4.38,30),(4.65,30),(5,30),(5.45,28),(5.7,25),(8,25)),
    'hand_y': ((0,14),(1.1,14),(1.45,15),(1.75,14),(2.2,9),
               (2.55,6),(2.9,7),(3.2,6),(3.7,6),(4.05,7),
               (4.38,6),(4.65,6),(5,8),(5.45,13),(5.7,16),(6.15,14),(8,14)),
}
_COFFEE = {
    'look': ((0,0),(1.3,0),(1.55,1),(3.75,1),(4.2,0),
             (6.5,0),(6.9,1),(8.2,1),(8.6,0),(12,0)),
    'look_y': ((0,0),(1.3,0),(1.7,1),(2.5,1),(3.1,0),(12,0)),
    'lean': ((0,0),(1.85,0),(2.4,-1),(3.1,-1),(4.25,1.3),
             (6.5,1.3),(7.4,-.7),(8.4,0),(12,0)),
    'drop': ((0,0),(2.05,0),(2.35,1),(2.6,1),(3.0,0),
             (7.5,0),(7.8,1),(8.25,0),(12,0)),
    'cup_x': ((0,27),(1.85,27),(2.4,28),(3,30),(3.7,29),
              (4.25,26),(6.5,26),(7.3,28),(7.8,27),(12,27)),
    'cup_y': ((0,17),(1.85,17),(2.4,18),(3,16),(3.7,14),
              (4.25,14),(6.5,14),(7.3,16),(7.8,18),(8.35,17),(12,17)),
}
_IDLE = {
    'look': ((0,0),(1.7,0),(1.95,-1),(3.95,-1),(4.15,0),
             (6.2,0),(6.4,1),(8.1,1),(8.3,0),(12,0)),
    'look_y': ((0,0),(9.7,0),(10.0,1),(10.5,1),(10.85,0),(12,0)),
    'lean': ((0,0),(2.15,0),(2.75,-2),(3.95,-2),(4.65,.6),
             (5.1,0),(6.7,0),(7.4,2),(8.1,2),(8.95,-.6),(9.4,0),(12,0)),
}
_NAP = {
    'lean': ((0,0),(.4,0),(1.1,-1.2),(2.8,-1.2),(4.8,-.3),(6.6,0),(8,0)),
    'breath': ((0,0),(.6,0),(1.6,.5),(2.5,1),(3.1,1),(6.4,0),(8,0)),
    'snuggle': ((0,0),(.45,0),(.85,1),(1.25,1),(1.8,0),(8,0)),
    'droop': ((0,0),(3.2,0),(4.2,1),(5.8,1),(6.5,0),(8,0)),
}


def _shear_offsets(height, lean, hip_shift=None):
    if hip_shift is None:hip_shift=round(lean*.35)
    return [round(lean*(1-(row+.5)/height)+hip_shift*((row+.5)/height))
            for row in range(height)]


def _acting_torso(c, y=10, height=12, lean=0, look=0, look_y=0,
                  blink=False, closed=False, hip_shift=None):
    """Flat row-wise lean, anchored at the hips; the two eyes stay square."""
    offsets=_shear_offsets(height,lean,hip_shift)
    for row,offset in enumerate(offsets):
        c.rect(11+offset,y+row,16,1)
    eye_y=(4 if closed else 2)+round(look_y)
    eye_offset=offsets[max(0,min(height-1,eye_y))]
    for ex in (3,11):
        c.rect(11+eye_offset+ex+round(look),y+eye_y,
               2,1 if blink or closed else 2,'E')
    shoulder_row=min(6,height-1)
    return (11+offsets[shoulder_row],y+shoulder_row),(26+offsets[shoulder_row],y+shoulder_row)


def _acting_legs(c, lean, hip_y=22):
    """Counter-angled legs retain the exact same four ground footprints."""
    shift=round(lean*.35)
    for foot in (11,15,21,25):
        hip=foot+shift
        c.line(hip,hip_y,hip,23,thickness=2)
        c.line(hip,23,foot,23,thickness=2)
        c.rect(foot,24,2,2)


def _relaxed_acting_arms(c, left, right, lean=0):
    # The far hand drops as the torso counterbalances; elbows follow late.
    _arm(c,left,(left[0]-1,left[1]+1),
         (left[0]-2,left[1]-2+round(max(0,lean)*.4)))
    _arm(c,right,(right[0]+1,right[1]+1),
         (right[0]-1,right[1]-2+round(max(0,-lean)*.4)))


def _hop_state(t):
    """Authored gather/stretch around one shared ballistic contact trajectory."""
    p=t % ACTIVITY_PERIODS['bounce']
    if 1.8 <= p < 2.7:
        u=(p-1.8)/.9
        lift=20*u*(1-u)
        stretch=1 if p<1.96 else 0
        return lift,10-round(lift)-stretch,12+stretch,u
    if 1.67 <= p < 1.8 or 2.7 <= p < 2.8:
        return 0,12,10,None
    if 1.5 <= p < 1.67 or 2.8 <= p < 2.9:
        return 0,11,11,None
    if 2.9 <= p < 3.08:
        return 0,9,13,None
    return 0,10,12,None


def contact_shadows(key, elapsed):
    """Local (center_x, floor_y, radius_x, opacity), shared with the TUI."""
    if key not in ACTIVITY_PERIODS:
        raise KeyError(key)
    if key=='bike':
        return [(9,26,4,.22),(31,26,4,.22)]
    if key=='bounce':
        lift, _, _, _ = _hop_state(_sample_time(elapsed))
        return [(19,26,8-2*lift/5,.20-.10*lift/5)]
    radius={'napping':14, 'coding':15, 'guitar':10}.get(key,9)
    return [(20 if key in ('napping','coding') else 19,26,radius,.16)]


def _draw(key, t, blink, travel=None):
    c = _Canvas()
    tau = 2 * math.pi
    if key == 'bike':
        phase = tau*travel.phase if travel is not None else tau*t/ACTIVITY_PERIODS[key]
        wheel_angle = travel.distance/4 if travel is not None else phase
        for wx in (9,31):
            c.wheel(wx,21,wheel_angle)
        for a,b in (((9,21),(20,19)),((9,21),(15,14)),
                    ((15,14),(20,19)),((15,14),(27,14)),
                    ((20,19),(27,14)),((27,14),(31,21)),
                    ((27,14),(29,10)),((15,14),(15,13))):
            c.line(*a,*b,'B')
        c.rect(12,13,7,1,'K')
        c.line(27,10,32,10,'S')
        c.rect(27,10,2,1,'K');c.rect(31,10,2,1,'K')
        bob=round(.65*(1-math.cos(phase*2))/2)
        if travel is not None and not travel.moving:bob=0
        # A seated body retains Clawd's native 16 x 12 proportions.
        _torso(c,10,1+bob,blink=blink,look=travel.look if travel is not None else 0)
        c.rect(19,18,2,2,'B')
        # Knees lead the pedals. The opposite pair is tucked behind the body.
        for a,hip_x,knee_side in ((phase+math.pi,14,-1),(phase,23,1)):
            px,py=20+3*math.cos(a),19+2*math.sin(a)
            ky=15.5+bob+.5*math.sin(a)
            kx=hip_x+knee_side*2
            c.line(hip_x,12+bob,kx,ky,thickness=2)
            c.line(kx,ky,px,py-1,thickness=2)
            c.rect(px-1,py,3,1)
            c.rect(px,py+1,2,1,'K')
        # Both small hands meet fixed grips; the elbows absorb the body bob.
        _arm(c,(10,7+bob),(20,11),(26,9),(3,3))
        _arm(c,(25,7+bob),(28,9),(30,9),(3,3))
    elif key == 'walk':
        if travel is not None:
            from claudefm.locomotion import walking_feet
            p=travel.phase
            feet=[(foot.local_x,foot.y) for foot in walking_feet(travel)]
            bob=round(.65*math.sin(tau*p*2)**2) if travel.moving else 0
        else:
            p=(t % ACTIVITY_PERIODS[key])/ACTIVITY_PERIODS[key]
            bob=round(.65*math.sin(tau*p*2)**2)
            feet=[]
            # The static pose API remains useful to sprite-sheet consumers.
            for i,hip_x in enumerate((11,15,21,25)):
                u=(p-(.06+i*.24))/.18
                lift=round(2*math.sin(math.pi*u)) if 0<u<1 else 0
                bend=(-1 if i in (0,2) else 1) if lift else 0
                feet.append((hip_x+bend,25-lift))
        _legs(c,22-bob,feet)
        _torso(c,y=10-bob,blink=blink,look=travel.look if travel is not None else 0)
        sway=round(.55*math.sin(tau*p)) if travel is None or travel.moving else 0
        _arm(c,(11,16-bob),(10,17-bob),(9,14-bob+sway))
        _arm(c,(26,16-bob),(27,17-bob),(25,14-bob-sway))
    elif key == 'coding':
        p=t % ACTIVITY_PERIODS[key]
        typing=1.2<=p<2.4 or 4.4<=p<5.8
        beat=(p-1.2)%.4 if p<2.4 else (p-4.4)%.35
        tap=1 if typing and beat<.13 else 0
        look=0 if 8.7<p<9.5 else 1
        # The desk, feet and screen remain completely still during the bursts.
        for x in (7,11,17,21):c.rect(x,22,2,4)
        _torso(c,7,10,look=look,blink=blink)
        c.rect(4,22,31,2,'T')
        c.rect(6,24,2,2,'t');c.rect(31,24,2,2,'t')
        c.rect(26,13,10,8,'M');c.rect(27,14,8,5,'N')
        c.rect(28,15,4,1,'e');c.rect(28,17,6,1,'e')
        c.rect(22,21,14,1,'M')
        _arm(c,(7,16),(5,18),(4,19),(3,3))
        _arm(c,(22,16),(24,18),(23,19+tap),(3,2))
    elif key == 'bounce':
        p=t % ACTIVITY_PERIODS[key]
        lift,y,h,flight=_hop_state(t)
        lean=_track(p,((0,0),(1.45,0),(1.7,-.8),(1.95,1),
                       (2.2,0),(2.6,-.6),(2.8,-.6),(3.15,.4),(3.5,0),(4.8,0)))
        if flight is None:
            _acting_legs(c,lean,y+h)
        else:
            tuck=round(math.sin(math.pi*flight))
            feet=[(x,25-round(lift)-tuck) for x in (11,15,21,25)]
            _legs(c,y+h,feet)
        look_y=_track(p,((0,0),(1.15,0),(1.35,1),(1.7,1),(1.9,-1),
                         (2.12,-1),(2.3,0),(4.8,0)))
        left,right=_acting_torso(c,y=y,height=h,lean=lean,look_y=look_y,blink=blink)
        lag=_track(p,((0,0),(1.4,0),(1.68,2),(1.84,2),(2.14,-2),
                      (2.35,-2),(2.65,0),(2.78,2),(2.95,2),(3.3,0),(4.8,0)))
        _arm(c,left,(left[0]-2,left[1]+1),(9,y+4+round(lag)))
        _arm(c,right,(right[0]+2,right[1]+1),(25,y+4+round(lag)))
    elif key == 'wave':
        p=t % ACTIVITY_PERIODS[key]
        lean=_track(p,_WAVE['lean']);drop=round(_track(p,_WAVE['drop']))
        _acting_legs(c,lean)
        left,right=_acting_torso(c,y=10+drop,height=12-drop,lean=lean,
                                 look=_track(p,_WAVE['look']),blink=blink)
        _arm(c,left,(left[0]-1,left[1]+2),
             (left[0]-2,left[1]-2+round(max(0,-lean)*.5)))
        hand=(round(_track(p,_WAVE['hand_x'])),round(_track(p,_WAVE['hand_y'])))
        reach=max(0,min(1,(14-hand[1])/8))
        elbow=(right[0]+2+round(reach*2),right[1]-round(reach*2))
        _arm(c,right,elbow,hand)
    elif key == 'coffee':
        p=t % ACTIVITY_PERIODS[key]
        lean=_track(p,_COFFEE['lean']);drop=round(_track(p,_COFFEE['drop']))
        mx,my=round(_track(p,_COFFEE['cup_x'])),round(_track(p,_COFFEE['cup_y']))
        sipping=4.15<=p<=6.5
        _acting_legs(c,lean)
        left,right=_acting_torso(c,y=10+drop,height=12-drop,lean=lean,
                                 look=_track(p,_COFFEE['look']),
                                 look_y=_track(p,_COFFEE['look_y']),
                                 blink=blink,closed=sipping)
        _arm(c,left,(left[0]-1,left[1]+1),(left[0]-2,left[1]-2))
        # Cup and grip share the authored arc. The forearm sits behind the mug.
        elbow=(max(right[0]+1,mx),max(right[1]+1,my+3))
        c.line(*right,*elbow,thickness=2)
        c.line(*elbow,mx,my+3,thickness=2)
        c.rect(mx,my,5,5,'G');c.rect(mx+1,my,3,1,'g')
        c.rect(mx+5,my+1,2,3,'G');c.rect(mx+5,my+2,1,1,' ')
        c.rect(mx-1,my+2,3,2)
        for i in range(2):
            age=(t/4+i*.5)%1
            sy=my-2-round(age*6)
            sx=mx+1+i*2+round(math.sin(age*tau))
            c.rect(sx,sy,1,1,'S')
            if .2<age<.7:c.rect(sx+1,sy-1,1,1,'S')
    elif key == 'napping':
        c.rect(6,24,28,2,'Z');c.rect(8,23,24,1,'Z')
        p=t % ACTIVITY_PERIODS[key]
        breath=round(_track(p,_NAP['breath']))
        lean=_track(p,_NAP['lean']);snuggle=round(_track(p,_NAP['snuggle']))
        left,right=_acting_torso(c,y=14-breath,height=9+breath,lean=lean,
                                 look_y=_track(p,_NAP['droop']),closed=True,hip_shift=0)
        _arm(c,left,(10,21),(8,19-snuggle))
        _arm(c,right,(28,21),(27,19-snuggle))
    elif key == 'guitar':
        p=t % ACTIVITY_PERIODS[key]
        stroke=_track(p%1.6,[(0,0),(.12,0),(.29,1),(.48,1),(1.05,0),(1.6,0)])
        fret=_track(p,[(0,0),(2.4,0),(2.9,1),(5.4,1),(6,0),(8,0)])
        _legs(c);_torso(c,blink=blink)
        # A fixed neck and two blocky bouts; hand motion does not move the prop.
        c.rect(18,17,8,7,'A');c.rect(16,20,12,4,'A')
        c.rect(17,19,10,3,'A');c.rect(20,19,3,3,'a')
        c.line(24,18,32,11,'a',thickness=2);c.rect(31,10,3,3,'A')
        c.line(23,20,32,12,'G')
        _arm(c,(26,16),(30,16),(28+round(fret),12-round(fret)),(3,3))
        _arm(c,(11,16),(16,17),(20,18+round(3*stroke)),(3,2))
    else:
        p=t % ACTIVITY_PERIODS['idle']
        lean=_track(p,_IDLE['lean'])
        _acting_legs(c,lean)
        left,right=_acting_torso(c,lean=lean,look=_track(p,_IDLE['look']),
                                 look_y=_track(p,_IDLE['look_y']),blink=blink)
        _relaxed_acting_arms(c,left,right,lean)
    return c.rows()


def _blink(t):
    # Uneven spacing plus one occasional double blink, never one blink per action.
    p=t % 31.2
    return any(start<=p<start+duration for start,duration in (
        (5.10,.13),(12.60,.13),(20.05,.11),(20.36,.11),(28.75,.14)))


def sample_activity(key, elapsed):
    """Sample by animation time, independent of redraw rate or wall clock."""
    if key not in ACTIVITIES:
        raise KeyError(key)
    t=_sample_time(elapsed)
    return _draw(key,t,_blink(t))


def sample_travel_pose(key, motion):
    """Draw a world-aware pose using one already-sampled locomotion state."""
    if key not in ('walk','bike'):
        return sample_activity(key,motion.elapsed)
    pose=_draw(key,motion.elapsed,_blink(motion.elapsed),travel=motion)
    if motion.facing==1:
        return pose
    pivot=37 if key=='walk' else 40
    mirrored=[]
    for row in pose:
        out=[' ']*WIDTH
        for x,char in enumerate(row):
            nx=pivot-x
            if 0<=nx<WIDTH:out[nx]=char
        mirrored.append(''.join(out))
    return mirrored


def travel_contact_shadows(key, motion):
    """Mirror physical cell centers about the same actor pivot as its pixels."""
    patches=contact_shadows(key,motion.elapsed)
    if key=='bike':
        # Wheel center indices9/31 correspond to physical cell centers9.5/31.5.
        patches=[(x+.5,y,r,a) for x,y,r,a in patches]
    if motion.facing==-1:
        pivot=38 if key=='walk' else 41
        patches=[(pivot-x,y,r,a) for x,y,r,a in patches]
    return patches


# Preserve existing numeric shortcuts. Idle and guitar extend the carousel.
ACTIVITY_KEYS = ['bike', 'walk', 'coding', 'bounce', 'wave', 'coffee', 'napping', 'idle', 'guitar']
_NAMES = ['Cruising on Bike', 'Scuttle Walk', 'Deep Focus Coding', 'Bounce & Groove',
          'Waving Hello', 'Coffee Break', 'Power Nap', 'A Little Look Around', 'Guitar Time']
_ICONS = ['🚲', '🦀', '💻', '🎧', '👋', '☕', '😴', '·', '♪']
ACTIVITIES = {key: {
    'name': name, 'icon': icon, 'duration': ACTIVITY_PERIODS[key],
    'has_scrolling_road': key in ('bike','walk'),
    'has_desk': key == 'coding', 'background': key,
    'particle_origin': {'napping': (29,13), 'bounce': (29,9), 'guitar': (30,12)}.get(key),
} for key,name,icon in zip(ACTIVITY_KEYS,_NAMES,_ICONS)}
# Small backwards-compatible pose collection for artwork/inspection tools.
for _key, _info in ACTIVITIES.items():
    _info['frames'] = [_draw(_key, i/12, False)
                       for i in range(round(ACTIVITY_PERIODS[_key]*12))]
