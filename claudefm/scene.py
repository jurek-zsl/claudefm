"""Quiet, layered pixel worlds with cached geometry and sparse ambient motion."""
import math
import random
from functools import lru_cache

SCENE_NAMES = {
    'bike': 'Alpine Daydream', 'walk': 'Fernwood Trail',
    'coding': 'Rainy Window', 'bounce': 'Afterhours Rooftop',
    'wave': 'Blossom Courtyard', 'coffee': 'The Corner Cafe',
    'napping': 'Moonlit Stillwater', 'idle': 'The Quiet Garden',
    'guitar': 'Golden Hour Coast',
}


def blend(a, b, t):
    t = max(0, min(1, t))
    return tuple(round(x + (y-x)*t) for x, y in zip(a, b))


class Canvas:
    def __init__(self, w, h, top=(0, 0, 0), bottom=None, pixels=None):
        self.w, self.h = max(0, int(w)), max(0, int(h))
        self.pixels = ([list(row) for row in pixels] if pixels is not None else
                       [[blend(top, bottom or top, y/max(1, self.h-1))]*self.w
                        for y in range(self.h)])

    def rect(self, x, y, w, h, color):
        x, y, w, h = round(x), round(y), round(w), round(h)
        if w <= 0 or h <= 0:
            return
        left, right = max(0, x), min(self.w, x+w)
        if left >= right:
            return
        for yy in range(max(0, y), min(self.h, y+h)):
            self.pixels[yy][left:right] = [color]*(right-left)

    def line(self, x, y, x2, y2, color):
        # Clip before rasterizing, including very distant off-canvas endpoints.
        if not self.w or not self.h:
            return
        dx, dy, lo, hi = x2-x, y2-y, 0., 1.
        for p, q in ((-dx, x), (dx, self.w-1-x), (-dy, y), (dy, self.h-1-y)):
            if p == 0:
                if q < 0:
                    return
            elif p < 0:
                lo = max(lo, q/p)
            else:
                hi = min(hi, q/p)
        if lo > hi:
            return
        ax, ay, bx, by = x+dx*lo, y+dy*lo, x+dx*hi, y+dy*hi
        n = max(1, round(max(abs(bx-ax), abs(by-ay))))
        for i in range(n+1):
            self.rect(ax+(bx-ax)*i/n, ay+(by-ay)*i/n, 1, 1, color)

    def ellipse(self, x, y, rx, ry, color):
        if rx <= 0 or ry <= 0:
            return
        for yy in range(max(0, math.ceil(y-ry)), min(self.h, math.floor(y+ry)+1)):
            span = rx*math.sqrt(max(0, 1-((yy-y)/ry)**2))
            self.rect(math.ceil(x-span), yy, math.floor(x+span)-math.ceil(x-span)+1, 1, color)

    def poly(self, points, color):
        if len(points) < 3:
            return
        for yy in range(max(0, math.ceil(min(p[1] for p in points))),
                        min(self.h, math.ceil(max(p[1] for p in points))+1)):
            hits = []
            for (x1, y1), (x2, y2) in zip(points, points[1:]+points[:1]):
                if y1 <= yy < y2 or y2 <= yy < y1:
                    hits.append(x1+(x2-x1)*(yy-y1)/(y2-y1))
            hits.sort()
            for a, b in zip(hits[::2], hits[1::2]):
                self.rect(math.ceil(a), yy, math.floor(b)-math.ceil(a)+1, 1, color)


def _glow(c, x, y, rx, ry, color, strength=.3):
    for yy in range(max(0, int(y-ry)), min(c.h, math.ceil(y+ry)+1)):
        for xx in range(max(0, int(x-rx)), min(c.w, math.ceil(x+rx)+1)):
            distance = ((xx-x)/max(1, rx))**2 + ((yy-y)/max(1, ry))**2
            if distance < 1:
                c.pixels[yy][xx] = blend(c.pixels[yy][xx], color,
                                         strength*(1-distance)**2)


def _haze(c, y, height, color, strength=.2):
    for yy in range(max(0, round(y-height)), min(c.h, round(y+height)+1)):
        amount = strength*max(0, 1-abs(yy-y)/max(1, height))
        c.pixels[yy] = [blend(pixel, color, amount) for pixel in c.pixels[yy]]


def _ridge_profile(w, h, base, phase=0, height=.24):
    # Broad overlapping peaks with smaller foothill shoulders, not a zigzag.
    peaks = ((.12, .20, .7), (.43, .13, 1), (.61, .17, .73), (.91, .17, .8))
    return tuple(round(base-h*height*max(
        a*math.exp(-((x/max(1,w-1)-p-.035*math.sin(phase+i)) / span)**2)
        for i, (p, span, a) in enumerate(peaks)) +
        h*.018*math.sin(x/max(1,w)*19+phase) +
        h*.009*math.sin(x/max(1,w)*41+phase)) for x in range(w))


def _ridge(c, base, color, phase=0, height=.24, snow=None):
    profile = _ridge_profile(c.w, c.h, base, phase, height)
    for x, y in enumerate(profile):
        slope = profile[min(c.w-1, x+2)]-profile[max(0, x-2)]
        face = blend(color, (37, 57, 72), .09) if slope < -1 else (
            blend(color, (211, 225, 211), .06) if slope > 1 else color)
        c.rect(x, y, 1, c.h-y, face)
        # Snow starts at the actual ridge, never above it. Its irregular lower
        # edge follows the exposed shoulders rather than a floating triangle.
        if snow and base-y > c.h*.22:
            depth = max(1, round((base-y)*(.22+.05*math.sin(x*.55))))
            c.rect(x, y, 1, depth, snow)
    return profile


def _pine(c, x, y, height, color, trunk):
    c.rect(x, y-height, 1, height, trunk)
    for step in range(4):
        top = y-height+step*height*.16
        half = height*(.13+step*.065)
        c.poly([(x, top), (x-half, top+height*.42), (x+half, top+height*.42)], color)


def _tree(c, x, ground, height, spread, palette, seed=0):
    rng = random.Random(seed)
    crown = ground-height
    trunk, shadow, leaf, lit = palette
    c.poly([(x-1, ground), (x+2, ground), (x+1, crown+height*.1), (x, crown)], trunk)
    for side in (-1, 1):
        tipx, tipy = x+side*spread*.65, crown+height*.06
        c.line(x, crown+height*.6, tipx, tipy, trunk)
        c.line(tipx, tipy, tipx+side*2, tipy-height*.18, trunk)
    for i in range(10):
        xx = x+(rng.random()-.5)*spread*1.7
        yy = crown+(rng.random()-.5)*height*.32
        rx, ry = spread*(.29+rng.random()*.23), height*(.13+rng.random()*.08)
        c.ellipse(xx, yy+1, rx, ry, shadow)
        c.ellipse(xx, yy, rx, max(1, ry-1), leaf)
        if i%2 == 0:
            c.ellipse(xx-1, yy-1, rx*.6, max(1, ry*.42), lit)


def _fern(c, x, ground, scale, leaf, stem):
    for side in (-1, 1):
        c.line(x, ground, x+side*scale, ground-scale*.7, stem)
        for n in range(1, 4):
            xx, yy = x+side*scale*n/4, ground-scale*.7*n/4
            c.line(xx, yy, xx-side, yy-2, leaf)
            c.line(xx, yy, xx+side*2, yy, leaf)


def _pagoda(c, x, y, size, roof, wall):
    for level in range(3):
        ww, yy = size*(.5+.25*level), y+level*size*.26
        c.rect(x-ww*.32, yy, ww*.64, size*.24, wall)
        c.poly([(x-ww*.65, yy+1), (x-ww*.45, yy-1), (x, yy-size*.22),
                (x+ww*.45, yy-1), (x+ww*.65, yy+1)], roof)
        if level == 2:
            for dx in (-.2, .2):
                c.rect(x+ww*dx, yy+1, 1, max(1, size*.15), roof)
    c.rect(x-size*.45, y+size*.78, size*.9, 1, roof)


def _wood_floor(c, top, base, dark, vanishing=.5):
    c.rect(0, top, c.w, c.h-top, base)
    seam = blend(base, (34, 32, 37) if dark else (102, 82, 65), .24)
    for n in range(1, 6):
        y = top+(c.h-top)*(n/6)**1.6
        c.line(0, y, c.w-1, y, seam)
    for x in range(-c.w, c.w*2, max(8, c.w//9)):
        c.line(c.w*vanishing, top-1, x, c.h-1, seam)


def _water(c, horizon, top, bottom, light_x, light, seed=3):
    rng = random.Random(seed)
    for y in range(round(horizon), c.h):
        depth = (y-horizon)/max(1, c.h-horizon)
        c.rect(0, y, c.w, 1, blend(top, bottom, depth))
        width = c.w*(.025+.11*depth)
        # Low contrast light underneath the broken specular ripple strokes.
        for x in range(max(0, round(light_x-width*1.6)), min(c.w, round(light_x+width*1.6))):
            amount = .20*max(0, 1-abs(x-light_x)/(width*1.6))*(1-depth*.4)
            c.pixels[y][x] = blend(c.pixels[y][x], light, amount)
        if y%2 == 0:
            offset = math.sin(y*1.7)*width*.25
            for a, b in ((-.85, -.15), (.12, .68)):
                xx, ww = round(light_x+offset+width*a), max(1, round(width*(b-a)))
                for sx in range(max(0, xx), min(c.w, xx+ww)):
                    c.pixels[y][sx] = blend(c.pixels[y][sx], light, .33+.12*math.sin(sx+y))
    for _ in range(max(7, c.w//4)):
        y = rng.randrange(max(0, round(horizon)+1), max(round(horizon)+2, c.h))
        x = rng.randrange(max(1, c.w))
        if y < c.h:
            width = max(1, round((y-horizon)/max(1, c.h-horizon)*4))
            c.rect(x, y, width, 1, blend(c.pixels[y][x], light, .08))


@lru_cache(maxsize=32)
def scene_geometry(w, h, key):
    """Shared immutable anchors for drawing and physical motion constraints."""
    if key == 'coding':
        x, y, ww, hh = round(w*.57), round(h*.10), round(w*.38), round(h*.66)
        return ('window', (x, y, ww, hh), x+ww//2, y+round(hh*.55))
    if key == 'napping':
        rng = random.Random(30)
        moon = (round(w*.77), round(h*.24))
        positions = set()
        for _ in range(max(14, w//4)):
            x, y = rng.randrange(max(1, w)), rng.randrange(1, max(2, round(h*.47)))
            if abs(x-moon[0]) > 7 or abs(y-moon[1]) > 6:
                positions.add((x, y))
        return ('moon', moon, tuple(sorted(positions)), round(h*.69))
    if key == 'wave':
        return ('canopies', ((w*.08, h*.26), (w*.16, h*.31), (w*.88, h*.28), (w*.96, h*.24)))
    if key in ('bike', 'guitar'):
        return ('sun', round(w*(.77 if key == 'bike' else .74)), round(h*(.68 if key == 'bike' else .56)))
    return ('none',)


def rain_glass_contains(w, h, x, y):
    _, (wx, wy, ww, hh), mx, my = scene_geometry(w, h, 'coding')
    return wx < x < wx+ww-1 and wy < y < wy+hh-1 and x != mx and y != my


@lru_cache(maxsize=18)
def _base(w, h, key, dark):
    floor = h-2
    if key == 'bike':
        c = Canvas(w, h, *((43, 68, 89), (141, 172, 172)) if dark else ((165, 207, 221), (238, 231, 203)))
        _, sun_x, waterline = scene_geometry(w, h, key)
        sunlight = (224, 212, 165) if dark else (255, 235, 179)
        _glow(c, sun_x, h*.22, w*.16, h*.33, sunlight, .35)
        c.ellipse(sun_x, h*.22, 3.5, 3.5, sunlight)
        for xx, yy, rx, ry in ((w*.16, h*.16, w*.17, h*.025),
                               (w*.57, h*.11, w*.12, h*.02)):
            _glow(c, xx, yy, rx, max(1, ry), (222, 231, 224), .30)
        _ridge(c, h*.60, (101, 126, 145) if dark else (155, 179, 190), .8, .38,
               (205, 218, 217) if dark else (237, 241, 229))
        _haze(c, h*.55, h*.09, (158, 182, 186) if dark else (216, 227, 221), .28)
        _ridge(c, h*.70, (58, 97, 105) if dark else (105, 151, 151), 2.8, .17)
        _water(c, waterline, (71, 119, 137) if dark else (137, 188, 197),
               (51, 87, 106) if dark else (109, 157, 170), sun_x, sunlight)
        c.poly([(0, h*.76), (w*.09, h*.78), (w*.19, h*.85), (w*.27, h*.88),
                (w*.42, h*.94), (w*.70, h*.94), (w, h*.85), (w, h), (0, h)],
               (70, 97, 77) if dark else (135, 165, 116))
        for x, size in ((0, .48), (w*.98, .41)):
            _pine(c, x, floor, h*size, (29, 65, 65) if dark else (62, 113, 101), (73, 92, 77))
        c.poly([(0, floor-3), (w*.3, floor-2), (w*.65, floor-3), (w, floor-4), (w, h), (0, h)],
               (106, 111, 96) if dark else (191, 183, 150))
        for x in (w*.09, w*.86, w*.94):
            c.ellipse(x, floor-2, 2, 1, (90, 103, 89) if dark else (157, 166, 128))
    elif key == 'walk':
        c = Canvas(w, h, *((35, 67, 62), (108, 139, 100)) if dark else ((185, 216, 188), (232, 228, 179)))
        _glow(c, w*.69, h*.24, w*.27, h*.5, (237, 229, 159), .30)
        _ridge(c, h*.77, (65, 101, 81) if dark else (150, 181, 137), 1, .17)
        for i in range(10):
            x = i*w/9
            _tree(c, x, h*.84, h*(.28+.06*math.sin(i*3)), w*.07,
                  ((67, 86, 63), (66, 105, 73), (79, 119, 79), (99, 132, 88)) if dark else
                  ((139, 151, 107), (136, 171, 117), (151, 185, 128), (167, 195, 140)), i)
        c.rect(0, h*.79, w, h*.21, (58, 85, 60) if dark else (138, 166, 105))
        # The near trail opens into a broad, unobstructed walking apron.
        # Its fixed margins match the actor's reachable foreground corridor.
        c.poly([(w*.71, h*.69), (w*.74, h*.69), (w*.65, h*.86),
                (w-8, floor-3), (w-8, h), (8, h), (8, floor-3),
                (w*.53, h*.85)], (130, 124, 88) if dark else (210, 195, 144))
        for x, seed in ((w*.025, 5), (w*.98, 9)):
            _tree(c, x, floor, h*.73, w*.13,
                  ((58, 70, 51), (37, 73, 51), (48, 89, 59), (76, 111, 69)) if dark else
                  ((99, 111, 69), (72, 123, 75), (91, 145, 85), (127, 169, 102)), seed)
        for x in (2, 6, w-7, w-3):
            _fern(c, x, floor, 4, (105, 139, 81) if dark else (145, 176, 103), (73, 106, 68))
        _glow(c, w*.45, floor, w*.2, h*.16, (230, 212, 142), .14)
    elif key == 'coding':
        c = Canvas(w, h, *((58, 55, 61), (88, 76, 68)) if dark else ((219, 210, 190), (236, 220, 188)))
        _glow(c, w*.19, h*.28, w*.42, h*.76, (243, 193, 115), .44)
        _, (wx, wy, ww, wh), mx, my = scene_geometry(w, h, key)
        frame = (100, 86, 78) if dark else (125, 109, 91)
        c.rect(wx-2, wy-2, ww+4, wh+4, frame)
        for y in range(wy, wy+wh):
            c.rect(wx, y, ww, 1, blend((46, 66, 86) if dark else (124, 153, 169), (94, 114, 128) if dark else (179, 194, 193), (y-wy)/max(1, wh)))
        for i in range(9):
            bx, bh = wx+i*ww/9, wh*(.18+.32*((i*7)%5)/5)
            color = (57, 75, 91) if dark else (111, 143, 158)
            c.rect(bx, wy+wh-bh, max(2, ww/10), bh, color)
            for yy in range(round(wy+wh-bh)+2, wy+wh-1, 4):
                if i%3:
                    c.rect(bx+1, yy, 1, 1, (186, 163, 119))
        c.rect(mx, wy, 1, wh, frame); c.rect(wx, my, ww, 1, frame)
        c.rect(wx-3, wy+wh+1, ww+6, 2, (110, 87, 67) if dark else (172, 143, 103))
        c.rect(w*.06, h*.31, w*.25, 1, (105, 81, 64) if dark else (159, 126, 88))
        for i, col in enumerate(((127, 149, 129), (170, 124, 103), (190, 171, 124), (123, 145, 161))):
            c.rect(w*.08+i*3, h*.31-4+(i%2), 2, 4-i%2, col)
        c.line(w*.19, 0, w*.19, h*.16, (107, 85, 68))
        c.poly([(w*.19-4, h*.24), (w*.19-2, h*.15), (w*.19+2, h*.15), (w*.19+4, h*.24)], (188, 150, 92))
        c.rect(w*.19-3, h*.24, 7, 1, (244, 213, 148))
        _wood_floor(c, round(h*.84), (88, 72, 60) if dark else (177, 148, 108), dark)
        _fern(c, w*.92, floor-1, 6, (106, 143, 112), (77, 110, 87))
        c.rect(w*.92-2, floor-2, 5, 3, (133, 113, 94))
    elif key == 'bounce':
        c = Canvas(w, h, *((35, 36, 66), (103, 83, 119)) if dark else ((133, 139, 171), (213, 179, 180)))
        _glow(c, w*.77, h*.24, w*.2, h*.4, (222, 182, 183), .27)
        c.ellipse(w*.77, h*.24, 3.3, 3.3, (224, 205, 191))
        for layer, base, color in ((0, .78, (91, 94, 126) if dark else (152, 155, 174)),
                                    (1, .83, (63, 68, 100) if dark else (107, 117, 146)),
                                    (2, .86, (45, 51, 79) if dark else (78, 91, 122))):
            for i in range(12):
                x, bh = i*w/11-2, h*(.10+((i*13+layer*3)%9)/48)
                c.rect(x, h*base-bh, w/12, bh, color)
                if layer:
                    for yy in range(round(h*base-bh)+2, round(h*base)-1, 3):
                        if (i+yy)%3:
                            c.rect(x+2, yy, 1, 1, (177, 161, 149) if i%2 else (113, 167, 171))
        deck = (59, 59, 77) if dark else (118, 116, 134)
        c.rect(0, h*.86, w, h*.14, deck)
        rail = (114, 117, 136) if dark else (160, 160, 172)
        c.line(0, h*.76, w-1, h*.76, rail)
        for x in range(0, w, max(8, w//10)):
            c.line(x, h*.76, x, h*.87, rail)
        c.line(0, h*.87, w-1, h*.87, blend(deck, (190, 169, 174), .28))
        _glow(c, w*.87, h*.85, w*.2, h*.15, (192, 124, 154), .13)
        c.rect(w*.88, h*.65, 7, 2, (178, 133, 163)); c.rect(w*.90, h*.67, 1, h*.09, rail)
    elif key == 'wave':
        c = Canvas(w, h, *((72, 67, 86), (143, 123, 132)) if dark else ((230, 214, 207), (246, 232, 205)))
        _ridge(c, h*.77, (107, 115, 122) if dark else (184, 187, 170), .4, .20)
        _haze(c, h*.68, h*.12, (181, 161, 165) if dark else (239, 226, 207), .25)
        _pagoda(c, w*.77, h*.48, min(w*.22, h*.54), (85, 76, 86) if dark else (145, 108, 101), (173, 148, 126) if dark else (226, 200, 162))
        c.rect(0, h*.84, w, h*.16, (100, 119, 91) if dark else (177, 190, 137))
        c.poly([(w*.31, h*.78), (w*.56, h*.78), (w*.65, h), (w*.19, h)], (135, 126, 119) if dark else (218, 202, 177))
        for x, seed in ((w*.055, 7), (w*.96, 10)):
            _tree(c, x, floor, h*.68, w*.13,
                  ((107, 83, 86), (142, 102, 124), (167, 119, 141), (193, 148, 163)) if dark else
                  ((137, 101, 94), (208, 145, 162), (229, 171, 183), (244, 199, 202)), seed)
        for x in range(2, w, 13):
            c.rect(x, floor, 3, 1, (155, 126, 138) if dark else (230, 183, 190))
    elif key == 'coffee':
        c = Canvas(w, h, *((66, 56, 53), (104, 83, 65)) if dark else ((226, 210, 180), (241, 222, 187)))
        for xx in (w*.18, w*.51, w*.88):
            _glow(c, xx, h*.27, w*.19, h*.55, (247, 199, 120), .34)
        x, y, rx, ry = w*.77, h*.41, w*.17, h*.28
        frame = (106, 82, 64) if dark else (139, 109, 77)
        glass = (77, 111, 108) if dark else (153, 183, 167)
        c.ellipse(x, y, rx+2, ry+2, frame); c.rect(x-rx-2, y, rx*2+5, h*.39, frame)
        c.ellipse(x, y, rx, ry, glass); c.rect(x-rx, y, rx*2+1, h*.36, glass)
        c.poly([(x-rx, y+h*.22), (x-rx*.4, y+h*.14), (x+rx*.3, y+h*.2),
                (x+rx, y+h*.15), (x+rx, y+h*.36), (x-rx, y+h*.36)], (61, 94, 76) if dark else (114, 150, 116))
        c.rect(x, y-ry, 1, h*.65, frame); c.rect(x-rx, y+h*.07, rx*2+1, 1, frame)
        c.rect(x-rx-3, y+h*.37, rx*2+7, 2, frame)
        c.rect(w*.05, h*.36, w*.27, 2, (118, 91, 65) if dark else (172, 137, 92))
        for i in range(4):
            xx = w*.08+i*5
            c.rect(xx, h*.36-3, 3, 3, (208, 200, 175)); c.rect(xx+3, h*.36-2, 1, 1, (208, 200, 175))
        for xx in (w*.18, w*.51, w*.88):
            c.line(xx, 0, xx, h*.13, (112, 87, 65))
            c.poly([(xx-3, h*.19), (xx-1, h*.11), (xx+1, h*.11), (xx+3, h*.19)], (181, 145, 89))
            c.rect(xx-2, h*.19, 5, 1, (244, 214, 151))
        _wood_floor(c, round(h*.85), (111, 85, 61) if dark else (180, 148, 106), dark, .77)
        c.ellipse(w*.84, floor-7, w*.10, 1, (154, 117, 78) if dark else (193, 156, 105))
        c.line(w*.84, floor-6, w*.84, floor, frame)
        c.rect(w*.79, floor-10, 2, 3, (191, 170, 138))
        c.line(w*.80, floor-10, w*.80+1, floor-13, (105, 142, 93))
        c.ellipse(w*.80+1, floor-13, 2, 1, (220, 155, 142))
    elif key == 'napping':
        c = Canvas(w, h, *((22, 34, 61), (65, 88, 119)) if dark else ((85, 105, 145), (153, 171, 187)))
        _, (mx, my), stars, waterline = scene_geometry(w, h, key)
        moon = (230, 234, 213) if dark else (247, 242, 218)
        _glow(c, mx, my, w*.14, h*.28, moon, .22)
        # Draw only the crescent pixels; the cutout retains its sky and halo.
        for yy in range(my-4, my+5):
            for xx in range(mx-4, mx+5):
                if (xx-mx)**2+(yy-my)**2 <= 16 and (xx-mx-2)**2+(yy-my+1)**2 > 13:
                    c.rect(xx, yy, 1, 1, moon)
        for x, y in stars:
            if 0 <= y < h and 0 <= x < w:
                c.rect(x, y, 1, 1, blend(c.pixels[y][x], moon, .48))
        _ridge(c, h*.68, (52, 72, 99) if dark else (115, 140, 160), 2, .19)
        _ridge(c, h*.72, (34, 57, 79) if dark else (90, 121, 139), 4, .10)
        _water(c, waterline, (44, 74, 102) if dark else (113, 147, 171),
               (29, 53, 77) if dark else (81, 119, 145), mx-1, moon, 11)
        c.poly([(0, h*.86), (w*.18, h*.88), (w*.34, h*.93), (w*.61, h*.94),
                (w*.83, h*.97), (w, h*.89), (w, h), (0, h)], (31, 55, 57) if dark else (86, 116, 111))
        for x in (0, w*.04, w*.93, w*.98):
            c.line(x, floor+1, x+2, floor-3, (46, 75, 69) if dark else (109, 143, 126))
    elif key == 'idle':
        c = Canvas(w, h, *((47, 77, 79), (116, 145, 128)) if dark else ((188, 216, 205), (235, 231, 194)))
        _ridge(c, h*.70, (88, 119, 117) if dark else (152, 179, 168), 2.3, .26)
        _haze(c, h*.65, h*.14, (155, 177, 153) if dark else (222, 228, 200), .26)
        _ridge(c, h*.83, (62, 100, 92) if dark else (123, 158, 133), .3, .14)
        _pagoda(c, w*.77, h*.45, min(w*.23, h*.52), (58, 79, 78) if dark else (105, 126, 109), (153, 166, 139) if dark else (220, 216, 175))
        c.rect(0, h*.87, w, h*.13, (80, 105, 79) if dark else (178, 187, 136))
        c.ellipse(w*.83, h*.88, w*.23, h*.13, (112, 131, 99) if dark else (187, 192, 145))
        c.ellipse(w*.83, h*.88, w*.21, h*.10, (60, 103, 105) if dark else (135, 178, 162))
        for i in range(3):
            xx, yy = w*(.72+i*.09), h*(.87+(i%2)*.035)
            c.ellipse(xx, yy, 2, .65, (111, 147, 105) if dark else (183, 202, 141))
        for x, depth in ((1, .14), (5, .26), (w-4, .05), (w-1, .17)):
            bamboo = (63, 105, 84) if dark else (112, 152, 103)
            c.rect(x, h*depth, 2, h*(1-depth), bamboo)
            for yy in range(round(h*depth)+2, floor, 5):
                c.rect(x, yy, 2, 1, blend(bamboo, (211, 214, 158), .25))
                for side in (-1, 1):
                    c.line(x, yy, x+side*4, yy-2, bamboo)
                    c.line(x+side*2, yy-1, x+side*4, yy-1, bamboo)
        c.poly([(w*.27, h*.82), (w*.50, h*.82), (w*.65, h), (w*.15, h)], (125, 134, 105) if dark else (211, 208, 161))
    else:
        c = Canvas(w, h, *((110, 80, 111), (211, 155, 124)) if dark else ((220, 177, 169), (251, 222, 175)))
        _, sun_x, waterline = scene_geometry(w, h, 'guitar')
        sun = (246, 198, 132) if dark else (255, 237, 180)
        _glow(c, sun_x, h*.43, w*.24, h*.48, sun, .35)
        c.ellipse(sun_x, h*.43, 5, 5, sun)
        _haze(c, waterline, h*.10, (233, 177, 144) if dark else (249, 221, 180), .35)
        _water(c, waterline, (91, 129, 145) if dark else (151, 188, 191),
               (55, 91, 115) if dark else (105, 153, 171), sun_x, sun, 27)
        c.poly([(0, h*.57), (w*.08, h*.51), (w*.16, h*.55), (w*.21, h*.59), (w*.31, h*.61), (0, h*.62)], (70, 98, 118) if dark else (122, 158, 170))
        _wood_floor(c, round(h*.88), (100, 84, 76) if dark else (184, 151, 112), dark, .72)
        c.line(0, h*.88, w-1, h*.88, (155, 129, 109) if dark else (213, 183, 137))
        for x in (w*.04, w*.95):
            c.rect(x, h*.80, 2, h*.20, (95, 81, 73) if dark else (164, 133, 99))
            c.rect(x-1, h*.80, 4, 1, (140, 116, 92) if dark else (205, 175, 130))
    return tuple(tuple(row) for row in c.pixels)


def _tint_pixel(c, x, y, color, amount):
    x, y = round(x), round(y)
    if 0 <= x < c.w and 0 <= y < c.h:
        c.pixels[y][x] = blend(c.pixels[y][x], color, amount)


def render_background(w, h, key, dark=False, elapsed=0):
    """Fresh pixels, shared static composition, continuous anchored effects."""
    c = Canvas(w, h, pixels=_base(w, h, key, dark))
    t = math.floor(max(0, elapsed)*8)/8
    floor = h-2
    if key == 'coding':
        _, (wx, wy, ww, wh), _, _ = scene_geometry(w, h, key)
        for i in range(max(8, w//7)):
            phase = (t/(3.7+(i%3)*.4)+i*.173)%1
            x, y = wx+2+(i*7)%max(1, ww-4), wy+1+phase*max(1, wh-3)
            amount = .48*math.sin(math.pi*phase)**.6
            for dx, dy in ((0, 0), (0, 1), (-1, 2)):
                xx, yy = round(x+dx), round(y+dy)
                if rain_glass_contains(w, h, xx, yy):
                    _tint_pixel(c, xx, yy, (169, 193, 204) if dark else (219, 231, 226), amount)
    elif key == 'wave':
        _, canopies = scene_geometry(w, h, key)
        for i in range(6):
            sx, sy = canopies[i%len(canopies)]
            phase = (t/(8+i*.43)+i*.193)%1
            amount = math.sin(math.pi*phase)**.65
            x = sx+math.sin(phase*5+i)*2+phase*w*.045
            y = sy+phase*(floor-sy)
            _tint_pixel(c, x, y, (224, 168, 184) if dark else (252, 209, 215), amount*.8)
    elif key == 'napping':
        _, (mx, my), stars, waterline = scene_geometry(w, h, key)
        for i, (x, y) in enumerate(stars):
            # The same stars are always present: only their luminance breathes.
            amount = .12+.22*(1+math.sin(t*.8+i*2))*.5
            _tint_pixel(c, x, y, (242, 240, 212), amount)
        for i in range(7):
            y = waterline+2+i*2
            x = mx-1+math.sin(i*2.1)*(.5+i*.22)
            if y < h*.90:
                _tint_pixel(c, x, y, (188, 204, 202), .12+.12*math.sin(t*.6+i)**2)
    elif key == 'guitar':
        for i in range(4):
            x = w*(.09 if i<2 else .90)+math.sin(t*.27+i*2)*2
            y = h*(.77+(i%2)*.09)+math.sin(t*.4+i)*1.2
            amount = .10+.45*(.5+.5*math.sin(t*.65+i*1.7))
            _tint_pixel(c, x, y, (247, 221, 142), amount)
        _, sun_x, waterline = scene_geometry(w, h, key)
        for i in range(6):
            y = waterline+2+i*2
            if y < h*.88:
                _tint_pixel(c, sun_x+math.sin(i*2)*i*.3, y,
                            (246, 218, 169), .10+.13*math.sin(t*.7+i)**2)
    elif key == 'bike':
        # Clawd travels over fixed ground; only the distant lake light moves.
        _, sun_x, waterline = scene_geometry(w, h, key)
        for i in range(5):
            y = waterline+2+i*2
            if y < h*.84:
                _tint_pixel(c, sun_x+math.sin(i*2)*i*.25, y,
                            (214, 224, 200), .08+.10*math.sin(t*.6+i)**2)
    elif key == 'bounce':
        for i in range(3):
            x, y = round(w*(.68+i*.09)), round(h*(.62+(i%2)*.08))
            _tint_pixel(c, x, y, (210, 186, 180), .07+.15*(1+math.sin(t*.6+i))*.5)
    elif key == 'idle':
        # A little expanding ripple stays in the open right-hand pond.
        phase = (t/7)%1
        amount = math.sin(math.pi*phase)*.17
        for i in range(8):
            angle = i*math.pi/4
            _tint_pixel(c, w*.84+math.cos(angle)*(1+phase*3),
                        h*.90+math.sin(angle)*phase, (183, 205, 169), amount)
    return c.pixels


class Particle:
    def __init__(self,x,y,char,color,vy=-1.5,vx=0,max_life=2.5):
        self.x,self.y=float(x),float(y);self.char,self.color=char,color
        self.vy,self.vx=vy,vx;self.life,self.max_life=0.0,max_life
    def update(self,dt):
        self.x+=self.vx*dt;self.y+=self.vy*dt;self.life+=dt
        return self.life<self.max_life


class Scene:
    def __init__(self):
        self.cloud_x,self.small_cloud_x=20.0,75.0
        self.road_offset=0.0;self.particles=[];self.spawn_elapsed=0.0
        self.activity=None;self.elapsed=0.0;self._rng=random.Random(17)
    def reset(self,activity):
        self.activity=activity;self.particles.clear();self.spawn_elapsed=0.0;self.elapsed=0.0
    def update(self,dt=1/24,is_biking=True,activity='bike',mascot_x=30,mascot_y=20,particle_origin=None,cols=80):
        if activity!=self.activity:self.reset(activity)
        if dt<=0:return
        self.elapsed+=dt
        self.particles=[p for p in self.particles if p.update(dt)]
        self.spawn_elapsed+=dt
        if particle_origin and self.spawn_elapsed>=1.1:
            self.spawn_elapsed%=1.1;ox,oy=particle_origin
            self.particles.append(Particle(mascot_x+ox,mascot_y+oy/2,
                self._rng.choice(['z','Z'] if activity=='napping' else ['♪','♫']),
                (167,174,177),vx=.45,max_life=2.8))
