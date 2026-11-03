#!/usr/bin/env python3
"""Developer QA: render the actual square-pixel poses and ANSI terminal scene.

Run: uv run --with pillow python scripts/preview_animations.py
Pillow is used only for exporting previews, never by the CLI.
"""
import argparse
import math
import os
import re
import sys
from functools import lru_cache
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw, ImageFont
from claudefm.sprites import ACTIVITIES, ACTIVITY_KEYS, SPRITE_PALETTE, sample_activity, WIDTH, HEIGHT
from claudefm.audio import AudioPlayer
from claudefm.tui import TUI
from claudefm import sprites

BG = (244,240,232)
OUT = Path(__file__).resolve().parents[1] / 'art' / 'out' / 'clawd'
SHOWCASE_PHASES = {
    'bike': .30, 'walk': .26, 'coding': .13, 'bounce': .47,
    'wave': .40, 'coffee': .45, 'napping': .44, 'idle': .58, 'guitar': .05,
}


@lru_cache(maxsize=1)
def terminal_font():
    for path in ('/System/Library/Fonts/Menlo.ttc',
                 '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'):
        if os.path.exists(path):
            return ImageFont.truetype(path, 14)
    return ImageFont.load_default()


def action_period(key):
    periods = getattr(sprites, 'ACTIVITY_PERIODS', {
        'bike': 1.2, 'walk': 1.25, 'coding': .8, 'bounce': 2.4,
        'wave': 5.6, 'coffee': 7.2, 'napping': 5.6, 'idle': 8, 'guitar': .85,
    })
    return periods[key]


def scene_period(key, cols=80):
    if key in ('walk', 'bike'):
        from claudefm.locomotion import journey_period
        return journey_period(key, cols)
    return action_period(key)


def export_motion(out, key, dark, fps=12, cols=80, rows=24):
    """Capture complete journeys/actions using the real terminal compositor."""
    period = scene_period(key, cols)
    duration = period * max(1, math.ceil(8 / period))
    count = max(2, round(duration * fps))
    shots = [terminal(key, dark, cols, rows, time=i * duration / count)
             for i in range(count)]
    # One palette avoids artificial color shimmer between GIF frames.
    palette = shots[0].quantize(colors=256, dither=Image.Dither.NONE)
    frames = [palette] + [shot.quantize(palette=palette, dither=Image.Dither.NONE)
                          for shot in shots[1:]]
    delays = [max(10, 10 * (round((i + 1) * duration * 100 / count) -
                             round(i * duration * 100 / count)))
              for i in range(count)]
    name = 'scene-{}-{}-motion.gif'.format(key, 'dark' if dark else 'light')
    frames[0].save(out / name, save_all=True, append_images=frames[1:],
                   duration=delays, loop=0)
    return out / name


def export_journey_strip(out, key, dark):
    duration = scene_period(key)
    width, height = 400, 264
    strip = Image.new('RGB', (width * 5, height * 2), BG)
    draw = ImageDraw.Draw(strip)
    for i, phase in enumerate((0, .08, .20, .34, .46, .54, .67, .80, .92, .999)):
        time = duration * phase
        shot = terminal(key, dark, time=time)
        x, y = (i % 5) * width, (i // 5) * height
        strip.paste(shot.resize((width, 240), Image.Resampling.LANCZOS), (x, y))
        draw.text((x + 8, y + 244), '{}: {:.1f}s'.format(key, time), fill=(65, 59, 53))
    strip.save(out / ('journey-' + key + ('-dark' if dark else '-light') + '.png'))


def export_motion_strip(out, key):
    period = action_period(key)
    cell_w, cell_h = WIDTH * 4 + 16, HEIGHT * 4 + 28
    strip = Image.new('RGB', (cell_w * 8, cell_h), BG)
    draw = ImageDraw.Draw(strip)
    for i in range(8):
        t = period * i / 8
        strip.paste(pose(key, t, 4), (cell_w * i + 8, 4))
        draw.text((cell_w * i + 8, cell_h - 20), '{:.2f}s'.format(t), fill=(65, 59, 53))
    strip.save(out / ('motion-strip-' + key + '.png'))


def pose(key, time, scale=6):
    im = Image.new('RGB',(WIDTH,HEIGHT),BG)
    im.putdata([SPRITE_PALETTE[ch] or BG for row in sample_activity(key,time) for ch in row])
    return im.resize((WIDTH*scale,HEIGHT*scale),Image.Resampling.NEAREST)


def terminal(key='bike', dark=False, cols=80, rows=24, time=1):
    tui = TUI(AudioPlayer(enabled=False), initial_activity=key,
              initial_theme='dark' if dark else 'light')
    tui.animation_time = time
    tui.scene.elapsed = time
    tui.activity_elapsed = time % 300
    lines = tui.render_lines(cols,rows)
    cw,ch = 10,20
    im = Image.new('RGB',(cols*cw,rows*ch),tui.theme.bg_sky)
    d=ImageDraw.Draw(im)
    font=terminal_font()
    for y,line in enumerate(lines):
        fg,bg=(235,235,235),(32,32,32)
        x=0
        for token in re.split(r'(\x1b\[[0-9;]*m)',line):
            if token.startswith('\x1b['):
                codes=[int(c) for c in token[2:-1].split(';') if c]
                i=0
                while i<len(codes):
                    if codes[i] in (38,48) and codes[i+1:i+2]==[2]:
                        color=tuple(codes[i+2:i+5])
                        if codes[i]==38: fg=color
                        else: bg=color
                        i+=5
                    else:
                        if codes[i]==0: fg,bg=(235,235,235),(32,32,32)
                        i+=1
                continue
            for c in token:
                d.rectangle((x*cw,y*ch,(x+1)*cw-1,(y+1)*ch-1),fill=bg)
                if c in ('▀','▄','█'):
                    top=y*ch if c!='▄' else y*ch+ch//2
                    bottom=(y+1)*ch-1 if c!='▀' else y*ch+ch//2-1
                    d.rectangle((x*cw,top,(x+1)*cw-1,bottom),fill=fg)
                elif c!=' ': d.text((x*cw,y*ch),c,font=font,fill=fg)
                x+=1
    return im


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,default=OUT)
    parser.add_argument('--scenes-only',action='store_true')
    parser.add_argument('--scene-motion',action='store_true')
    parser.add_argument('--motion-all', action='store_true',
                        help='Capture all scenes and full travel journeys in both themes')
    parser.add_argument('--motion-strips', action='store_true',
                        help='Save eight-pose timing strips for every action')
    parser.add_argument('--journey-strips', action='store_true',
                        help='Show outbound, rest, turn, and return positions')
    parser.add_argument('--fps', type=int, choices=(12, 24), default=12)
    args=parser.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    for dark in (False, True):
        montage=Image.new('RGB',(1800,1080),(25,25,30))
        for i,key in enumerate(ACTIVITY_KEYS):
            shot=terminal(key,dark,cols=100,rows=30,
                          time=scene_period(key, 100)*SHOWCASE_PHASES[key])
            shot.save(args.out/('scene-'+key+('-dark' if dark else '-light')+'.png'))
            montage.paste(shot.resize((600,360),Image.Resampling.LANCZOS),((i%3)*600,(i//3)*360))
        montage.save(args.out/('scenes-dark.png' if dark else 'scenes-light.png'))
    terminal().save(args.out/'terminal-light.png')
    terminal('wave',True).save(args.out/'terminal-dark.png')
    terminal('bike',cols=64,rows=18).save(args.out/'terminal-small.png')
    for key in ('coding','wave','napping'):
        terminal(key,cols=64,rows=18).save(args.out/('scene-'+key+'-small.png'))
    if args.scene_motion or args.motion_all:
        keys = ACTIVITY_KEYS if args.motion_all else ('coding', 'wave', 'guitar')
        themes = (False, True) if args.motion_all else (True,)
        for key in keys:
            for dark in themes:
                path = export_motion(args.out, key, dark, args.fps)
                if dark and args.scene_motion:
                    # Preserve the filenames used by existing documentation.
                    (args.out / ('scene-' + key + '-motion.gif')).write_bytes(path.read_bytes())
    if args.motion_strips:
        for key in ACTIVITY_KEYS:
            export_motion_strip(args.out, key)
    if args.journey_strips:
        for key in ('walk', 'bike'):
            for dark in (False, True):
                export_journey_strip(args.out, key, dark)
    if args.scenes_only:
        print(args.out);return
    sheet=Image.new('RGB',(3*280,3*210),BG); d=ImageDraw.Draw(sheet)
    for i,key in enumerate(ACTIVITY_KEYS):
        x,y=(i%3)*280,(i//3)*210
        sheet.paste(pose(key,action_period(key)*SHOWCASE_PHASES[key]),(x+20,y+25));d.text((x+20,y+185),ACTIVITIES[key]['name'],fill=(65,59,53))
        period = action_period(key)
        duration = period * max(1, math.ceil(8 / period))
        count = max(2, round(duration * 24))
        frames = [pose(key, j * duration / count) for j in range(count)]
        delays = [max(10, 10 * (round((j+1)*duration*100/count) -
                                 round(j*duration*100/count))) for j in range(count)]
        frames[0].save(args.out/(key+'.gif'),save_all=True,append_images=frames[1:],duration=delays,loop=0)
    sheet.save(args.out/'contact-sheet.png')
    terminal().save(args.out/'terminal-light.png')
    terminal('wave',True).save(args.out/'terminal-dark.png')
    terminal('bike',cols=64,rows=18).save(args.out/'terminal-small.png')
    print(args.out)

if __name__=='__main__':main()
