#!/usr/bin/env python3
"""Developer QA: render the actual square-pixel poses and ANSI terminal scene.

Run: uv run --with pillow python scripts/preview_animations.py
Pillow is used only for exporting previews, never by the CLI.
"""
import argparse
import os
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw, ImageFont
from claudefm.sprites import ACTIVITIES, ACTIVITY_KEYS, SPRITE_PALETTE, sample_activity, WIDTH, HEIGHT
from claudefm.audio import AudioPlayer
from claudefm.tui import TUI

BG = (244,240,232)
OUT = Path(__file__).resolve().parents[1] / 'art' / 'out' / 'clawd'


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
    font_path='/System/Library/Fonts/Menlo.ttc'
    font=ImageFont.truetype(font_path,14) if os.path.exists(font_path) else ImageFont.load_default()
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
    args=parser.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    for dark in (False, True):
        montage=Image.new('RGB',(1800,1080),(25,25,30))
        for i,key in enumerate(ACTIVITY_KEYS):
            shot=terminal(key,dark,cols=100,rows=30,time=1)
            shot.save(args.out/('scene-'+key+('-dark' if dark else '-light')+'.png'))
            montage.paste(shot.resize((600,360)),((i%3)*600,(i//3)*360))
        montage.save(args.out/('scenes-dark.png' if dark else 'scenes-light.png'))
    terminal().save(args.out/'terminal-light.png')
    terminal('wave',True).save(args.out/'terminal-dark.png')
    terminal('bike',cols=64,rows=18).save(args.out/'terminal-small.png')
    for key in ('coding','wave','napping'):
        terminal(key,cols=64,rows=18).save(args.out/('scene-'+key+'-small.png'))
    if args.scene_motion:
        for key,duration in [('coding',8),('wave',5.6),('guitar',7.65)]:
            shots=[terminal(key,True,time=j/12) for j in range(round(duration*12))]
            shots[0].save(args.out/('scene-'+key+'-motion.gif'),save_all=True,
                          append_images=shots[1:],duration=83,loop=0)
    if args.scenes_only:
        print(args.out);return
    sheet=Image.new('RGB',(3*280,3*210),BG); d=ImageDraw.Draw(sheet)
    for i,key in enumerate(ACTIVITY_KEYS):
        x,y=(i%3)*280,(i//3)*210
        sheet.paste(pose(key,1),(x+20,y+25));d.text((x+20,y+185),ACTIVITIES[key]['name'],fill=(65,59,53))
        cycles = {'bike':7.2, 'walk':7.5, 'bounce':7.2, 'wave':11.2,
                  'coffee':7.2, 'napping':11.2, 'idle':8, 'guitar':7.65, 'coding':8}
        frames=[pose(key,j/24) for j in range(round(cycles[key]*24))]
        frames[0].save(args.out/(key+'.gif'),save_all=True,append_images=frames[1:],duration=42,loop=0)
    sheet.save(args.out/'contact-sheet.png')
    terminal().save(args.out/'terminal-light.png')
    terminal('wave',True).save(args.out/'terminal-dark.png')
    terminal('bike',cols=64,rows=18).save(args.out/'terminal-small.png')
    print(args.out)

if __name__=='__main__':main()
