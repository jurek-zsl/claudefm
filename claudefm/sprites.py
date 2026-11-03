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


def _body(c, x=11, y=10, height=12, look=0, blink=False,
          arms=None, legs=None, closed=False):
    x, y = round(x), round(y)
    # Four distinct legs; offsets move hips/feet without changing the floor.
    if legs is None:
        legs = [(0, 4)] * 4
    for lx, (dx, length) in zip((0, 4, 10, 14), legs):
        c.rect(x+lx+dx, y+height, 2, length)
    c.rect(x, y, 16, height)
    if arms is None:
        arms = ((x-2, y+4), (x+14, y+4))
    for ax, ay in arms:
        c.line(x if ax < x else x+15, y+6, ax+1, ay+1, thickness=2)
        c.rect(ax, ay, 4, 4)
    for ex in (3, 11):
        c.rect(x+ex+look, y+2 if not closed else y+4,
               2, 1 if blink or closed else 2, 'E')


def _draw(key, t, blink):
    c = _Canvas()
    tau = 2 * math.pi
    if key == 'bike':
        phase = tau * t / 1.2
        for wx in (9, 31):
            c.wheel(wx, 21, phase)
        for a, b in (((9,21),(19,21)), ((9,21),(15,14)),
                     ((15,14),(19,21)), ((15,14),(27,14)),
                     ((19,21),(27,14)), ((27,14),(31,21)),
                     ((27,14),(28,10)), ((15,14),(15,12))):
            c.line(*a, *b, 'B')
        c.rect(12,12,7,1,'K')
        c.line(27,10,31,10,'S')
        bob = round(.55 * math.sin(phase))
        _body(c, 10, 1+bob, height=10, legs=[(0,0)]*4,
              arms=((7,7+bob),(27,9)), blink=blink)
        # Opposite feet share a crank; both remain attached to the rider.
        for a, hip in ((phase, 15), (phase+math.pi, 23)):
            px, py = 20+3*math.cos(a), 18+2*math.sin(a)
            c.line(hip,11+bob,px,py)
            c.rect(px-1,py,3,1)
        c.rect(19,18,2,1,'K')
    elif key == 'walk':
        phase = tau * t / 1.25
        lift = [max(0, math.sin(phase+p)) for p in (0, math.pi, math.pi, 0)]
        legs = [(round(math.cos(phase)), 4-round(2*l)) for l in lift]
        _body(c, legs=legs, blink=blink)
    elif key == 'coding':
        tap = round(max(0, math.sin(tau*t/0.8)))
        _body(c, 7, 10, blink=blink, look=1,
              arms=((4,17),(24,18-tap)))
        c.rect(4,22,31,2,'T')
        c.rect(6,24,2,2,'t'); c.rect(31,24,2,2,'t')
        c.rect(26,13,10,8,'M'); c.rect(27,14,8,5,'N')
        c.rect(28,15,4,1,'e'); c.rect(28,17,6,1,'e')
        c.rect(22,21,14,1,'M')
        c.rect(22,20-tap,3,2)  # typing hand reaches the keyboard
    elif key == 'bounce':
        p = t % 2.4
        # Settle, gather, launch, hang, fall, squash, recover.
        rise = _track(p, [(0,0),(.45,0),(.65,-1),(.88,4),
                          (1.12,5),(1.35,4),(1.58,0),(1.75,-1),(2.0,0),(2.4,0)])
        squash = 1 if rise < -.4 else 0
        y = 10-round(max(0,rise))+squash
        h = 12-squash
        arms = ((8,y+3),(25,y+3)) if rise > 1 else None
        _body(c,y=y,height=h,arms=arms,blink=blink)
    elif key == 'wave':
        p = t % 5.6
        reach = _track(p,[(0,0),(.6,0),(1,1),(2.9,1),(3.3,0),(5.6,0)])
        # Hold a greeting and do two wrist waves, then rest.
        wag = round(math.sin((p-1)*tau/0.65)) if 1 < p < 2.9 else 0
        hand = (25+wag,14-round(10*reach))
        _body(c,arms=((9,14),hand),blink=blink,look=0)
    elif key == 'coffee':
        p = t % 7.2
        sip = _track(p,[(0,0),(2.0,0),(2.7,1),(3.5,1),(4.2,0),(7.2,0)])
        mx, my = 27-round(3*sip), 17-round(3*sip)
        _body(c,arms=((8,17),(mx-1,my+1)),blink=blink,closed=sip>.8)
        c.rect(mx,my,5,5,'G'); c.rect(mx+1,my,3,1,'g')
        c.rect(mx+5,my+1,2,3,'G'); c.rect(mx+5,my+2,1,1,' ')
        # Steam stays tied to the cup, with staggered rising wisps.
        for i in range(2):
            age = (t*.7+i*.5)%1
            c.rect(mx+1+i*2+round(math.sin(age*tau)),my-2-round(age*4),1,1,'S')
    elif key == 'napping':
        c.rect(6,24,28,2,'Z'); c.rect(8,23,24,1,'Z')
        breath = round((1-math.cos(tau*t/5.6))*.5)
        _body(c,11,14-breath,height=9+breath,legs=[(0,0)]*4,closed=True,
              arms=((8,19),(27,19)))
    elif key == 'guitar':
        strum = round(math.sin(tau*t/.85))
        _body(c,blink=blink,arms=((8,17),(28,13)))
        c.rect(18,17,8,7,'A'); c.rect(16,19,12,3,'A')
        c.line(23,19,32,12,'a'); c.rect(31,11,3,3,'A')
        c.rect(20,19,3,3,'a'); c.rect(19,18+strum,3,2)
    else:  # quiet idle/look-around
        p = t % 8
        look = -1 if 2 < p < 3.6 else 1 if 5 < p < 6.6 else 0
        _body(c,look=look,blink=blink)
    return c.rows()


def sample_activity(key, elapsed):
    """Sample by animation time, independent of redraw rate or wall clock."""
    if key not in ACTIVITIES:
        raise KeyError(key)
    t = math.floor(max(0, elapsed) * FPS + 1e-9) / FPS
    # A short blink every several seconds, independent of the action cycle.
    blink = 5.1 <= t % 6.8 < 5.23
    return _draw(key, t, blink)


# Preserve existing numeric shortcuts. Idle and guitar extend the carousel.
ACTIVITY_KEYS = ['bike', 'walk', 'coding', 'bounce', 'wave', 'coffee', 'napping', 'idle', 'guitar']
_NAMES = ['Cruising on Bike', 'Scuttle Walk', 'Deep Focus Coding', 'Bounce & Groove',
          'Waving Hello', 'Coffee Break', 'Power Nap', 'A Little Look Around', 'Guitar Time']
_ICONS = ['🚲', '🦀', '💻', '🎧', '👋', '☕', '😴', '·', '♪']
ACTIVITIES = {key: {
    'name': name, 'icon': icon, 'has_scrolling_road': key in ('bike','walk'),
    'has_desk': key == 'coding', 'background': key,
    'particle_origin': {'napping': (29,13), 'bounce': (29,9), 'guitar': (30,12)}.get(key),
} for key,name,icon in zip(ACTIVITY_KEYS,_NAMES,_ICONS)}
# Small backwards-compatible pose collection for artwork/inspection tools.
for _key, _info in ACTIVITIES.items():
    _info['frames'] = [_draw(_key, i/12, False) for i in range(96)]
