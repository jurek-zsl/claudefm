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
        knee_y = min(foot_y-1, hip_y+2)
        # The ankle is drawn before its foot, so no stroke can cross the floor.
        c.line(hip_x, hip_y, hip_x, knee_y, thickness=2)
        c.line(hip_x, knee_y, foot_x, foot_y-1, thickness=2)
        c.rect(foot_x,foot_y,2,1)


def _rest_arms(c, y=10):
    _arm(c,(11,y+6),(10,y+7),(9,y+4))
    _arm(c,(26,y+6),(26,y+7),(25,y+4))


def _hop_state(t):
    """Shared flight/contact geometry for the actor and its floor shadow."""
    p=t % ACTIVITY_PERIODS['bounce']
    if 1.8 <= p < 2.7:
        u=(p-1.8)/.9
        lift=20*u*(1-u)  # ballistics: one gravity-driven arc, five pixels high
        return lift, 10-round(lift), 12, u
    if 1.5 <= p < 1.8 or 2.7 <= p < 2.9:
        return 0, 11, 11, None
    if 2.9 <= p < 3.08:
        return 0, 9, 13, None  # a short spring recovery with the feet planted
    return 0, 10, 12, None


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


def _draw(key, t, blink):
    c = _Canvas()
    tau = 2 * math.pi
    if key == 'bike':
        phase = tau*t/ACTIVITY_PERIODS[key]
        for wx in (9,31):
            c.wheel(wx,21,phase)
        for a,b in (((9,21),(20,19)),((9,21),(15,14)),
                    ((15,14),(20,19)),((15,14),(27,14)),
                    ((20,19),(27,14)),((27,14),(31,21)),
                    ((27,14),(29,10)),((15,14),(15,13))):
            c.line(*a,*b,'B')
        c.rect(12,13,7,1,'K')
        c.line(27,10,32,10,'S')
        c.rect(27,10,2,1,'K');c.rect(31,10,2,1,'K')
        bob=round(.65*(1-math.cos(phase*2))/2)
        # A seated body retains Clawd's native 16 x 12 proportions.
        _torso(c,10,1+bob,blink=blink)
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
        p=(t % ACTIVITY_PERIODS[key])/ACTIVITY_PERIODS[key]
        bob=round(.65*math.sin(tau*p*2)**2)
        feet=[]
        # Four short swing windows, with three feet bearing weight at all times.
        for i,hip_x in enumerate((11,15,21,25)):
            u=(p-(.06+i*.24))/.18
            lift=round(2*math.sin(math.pi*u)) if 0<u<1 else 0
            bend=(-1 if i in (0,2) else 1) if lift else 0
            feet.append((hip_x+bend,25-lift))
        _legs(c,22-bob,feet)
        _torso(c,y=10-bob,blink=blink)
        # A tiny opposing arm follow-through accompanies the weight transfer.
        sway=round(.55*math.sin(tau*p))
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
        lift,y,h,flight=_hop_state(t)
        if flight is None:
            _legs(c,y+h)
        else:
            # Feet tuck just a little near the apex, then extend for landing.
            tuck=round(math.sin(math.pi*flight))
            feet=[(x,25-round(lift)-tuck) for x in (11,15,21,25)]
            _legs(c,y+h,feet)
        _torso(c,y=y,height=h,blink=blink)
        lag=round(math.sin(math.pi*flight)) if flight is not None else 0
        _arm(c,(11,y+6),(9,y+7),(9,y+4-lag))
        _arm(c,(26,y+6),(28,y+7),(25,y+4-lag))
    elif key == 'wave':
        p=t % ACTIVITY_PERIODS[key]
        reach=_track(p,[(0,0),(1.5,0),(2.3,1),(4.5,1),(5.4,0),(8,0)])
        wag=round(math.sin((p-2.3)*tau/1.1)) if 2.3<p<4.5 else 0
        _legs(c);_torso(c,blink=blink)
        _arm(c,(11,16),(10,17),(9,14))
        _arm(c,(26,16),(27+round(2*reach),16-round(reach)),
             (25+round(4*reach)+wag,14-round(7*reach)))
    elif key == 'coffee':
        p=t % ACTIVITY_PERIODS[key]
        sip=_track(p,[(0,0),(3,0),(4.25,1),(6.5,1),(7.75,0),(12,0)])
        mx,my=27-round(3*sip),17-round(3*sip)
        _legs(c);_torso(c,blink=blink,closed=sip>.85)
        _arm(c,(11,16),(10,17),(9,14))
        # The forearm stays behind the cup, and a visible front grip is last.
        c.line(26,16,mx-1,my+3,thickness=2)
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
        p=(t % ACTIVITY_PERIODS[key])/ACTIVITY_PERIODS[key]
        breath=round((1-math.cos(tau*p))*.5)
        # Lower edge and cushion stay planted while the upper body rises.
        y=14-breath
        _torso(c,11,y,height=9+breath,closed=True,look_y=1 if .73<p<.94 else 0)
        _arm(c,(11,20),(10,21),(8,19))
        _arm(c,(26,20),(28,21),(27,19))
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
        expand=1 if (1-math.cos(tau*p/6))*.5>.75 else 0
        look=_track(p,[(0,0),(2.4,0),(2.8,-1),(4.1,-1),(4.5,0),
                       (6.5,0),(6.9,1),(8.2,1),(8.6,0),(12,0)])
        down=_track(p,[(0,0),(9.2,0),(9.5,1),(10.1,1),(10.4,0),(12,0)])
        _legs(c)
        _torso(c,y=10-expand,height=12+expand,look=look,look_y=down,blink=blink)
        _rest_arms(c,10-expand)
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
