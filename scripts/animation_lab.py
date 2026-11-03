#!/usr/bin/env python3
"""Export an offline, frame-steppable study of the actual runtime sprite rig.

No runtime or development dependencies. The lab studies poses and contacts;
preview_animations.py remains the source for complete ANSI scene captures.
"""
import argparse
import importlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sample_library(source, cols):
    sys.path.insert(0, str(source.resolve()))
    sprites = importlib.import_module('claudefm.sprites')
    motion = importlib.import_module('claudefm.locomotion')
    package = importlib.import_module('claudefm')
    poses, indices, activities = [], {}, {}
    for key in sprites.ACTIVITY_KEYS:
        period = motion.journey_period(key, cols)
        frames = []
        for tick in range(math.ceil(period * sprites.FPS)):
            elapsed = tick / sprites.FPS
            state = motion.sample_locomotion(key, elapsed, cols)
            pose = sprites.sample_travel_pose(key, state)
            signature = '\n'.join(pose)
            if signature not in indices:
                indices[signature] = len(poses)
                poses.append(pose)
            frames.append([indices[signature], state.origin_x, state.stage,
                           state.facing, state.moving,
                           sprites.travel_contact_shadows(key, state)])
        activities[key] = {'name': sprites.ACTIVITIES[key]['name'],
                           'period': period, 'frames': frames,
                           'beats': getattr(sprites, 'ACTING_BEATS', {}).get(key, [])}
    return {'version': package.__version__, 'fps': sprites.FPS,
            'width': sprites.WIDTH, 'height': sprites.HEIGHT, 'cols': cols,
            'palette': sprites.SPRITE_PALETTE, 'poses': poses,
            'activities': activities}


HTML = r'''<!doctype html>
<html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Clawd animation lab</title>
<style>
:root{color-scheme:light dark;font:15px/1.5 system-ui,sans-serif;background:#f5f1e9;color:#342d29}
*{box-sizing:border-box}body{max-width:1440px;margin:0 auto;padding:28px}
h1{font-size:26px;margin:0 0 6px}p{margin:0 0 22px;color:#716860}
button,select{font:inherit;padding:7px 12px;border:1px solid #b6aba0;border-radius:7px;background:#fff8ed;color:#342d29}
button{cursor:pointer}button:focus-visible,select:focus-visible,input:focus-visible{outline:3px solid #bc613e;outline-offset:3px}
.controls{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:18px 0}
label{display:flex;align-items:center;gap:6px}.views{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:20px}
figure{margin:0;border:1px solid #c8bcb0;border-radius:12px;overflow:hidden;background:#ebe3d5}
figcaption{padding:10px 16px;font-weight:600}canvas{display:block;width:100%;image-rendering:pixelated;background:#eee6d8}
.timeline{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:15px;margin-top:22px}
.timeline input{width:100%;accent-color:#bc613e}output{font-variant-numeric:tabular-nums;min-width:100px}
.readout{font:13px/1.6 ui-monospace,monospace;min-height:42px;white-space:pre-wrap;margin:14px 0}
.legend{font-size:13px;margin-top:12px}.old{color:#bc573e}.next{color:#417fac}
@media(prefers-color-scheme:dark){:root{background:#201e1c;color:#e7ddd0}p{color:#b8aa9b}figure{border-color:#554d44;background:#302a24}button,select{background:#302a24;color:#e7ddd0;border-color:#78695a}}
</style>
<h1>Clawd animation lab</h1>
<p>Actual runtime pose samples, with world position and contact shadows. Use the terminal preview exporter to review scenery and UI.</p>
<div class="controls">
 <label>Activity <select id="activity"></select></label>
 <button id="play" type="button">Pause</button>
 <button id="previous" type="button" aria-label="Previous frame">← Frame</button>
 <button id="next" type="button" aria-label="Next frame">Frame →</button>
 <label>Speed <select id="speed"><option value="0.25">¼×</option><option value="0.5">½×</option><option value="1" selected>1×</option></select></label>
 <label><input id="onion" type="checkbox">Onion skin</label>
 <label><input id="grid" type="checkbox">Pixel grid</label>
 <label><input id="world" type="checkbox" checked>World position</label>
 <label>Palette <select id="theme"><option value="light">Light</option><option value="dark">Dark</option></select></label>
</div>
<div class="views" id="views"></div>
<div class="timeline"><output id="elapsed"></output><input id="scrub" type="range" min="0" value="0" step="1" aria-label="Animation frame"><output id="frame"></output></div>
<div class="readout" id="readout" aria-live="off"></div>
<p class="legend">Space: play/pause · Arrow keys: one frame · <span class="old">Coral onion: previous frame</span> · <span class="next">Blue onion: next frame</span>. All frame changes come from Python; the browser only plays them.</p>
<script id="library" type="application/json">__DATA__</script>
<script>
'use strict';
const libraries=JSON.parse(document.getElementById('library').textContent);
const el=id=>document.getElementById(id), current=libraries[libraries.length-1];
let key='wave',tick=0,playing=true,clock=0,last=0;const captions=[];
const canvases=libraries.map((lib,i)=>{
 const figure=document.createElement('figure'),label=document.createElement('figcaption'),canvas=document.createElement('canvas');
 label.textContent=(libraries.length>1?(i===0?'Before · ':'After · '):'Runtime · ')+lib.version;
 captions.push(label);figure.append(label,canvas);el('views').append(figure);return canvas;
});
Object.entries(current.activities).forEach(([value,activity])=>{const option=document.createElement('option');option.value=value;option.textContent=activity.name;el('activity').append(option)});
el('activity').value=key;
const count=()=>current.activities[key].frames.length;
function frameAt(lib,index){const a=lib.activities[key];return a.frames[(index+a.frames.length)%a.frames.length]}
function drawPose(ctx,lib,frame,color,alpha=1){
 const world=el('world').checked,origin=world?frame[1]:0;ctx.globalAlpha=alpha;
 lib.poses[frame[0]].forEach((row,y)=>{for(let x=0;x<row.length;x++){if(row[x]===' ')continue;const rgb=lib.palette[row[x]];ctx.fillStyle=color||`rgb(${rgb.join(',')})`;ctx.fillRect(x+origin,y+6,1,1)}});ctx.globalAlpha=1;
}
function draw(lib,index,canvas){
 const dark=el('theme').value==='dark',world=el('world').checked,w=world?lib.cols:lib.width,h=lib.height+12;
 canvas.width=w*8;canvas.height=h*8;const ctx=canvas.getContext('2d');ctx.scale(8,8);ctx.imageSmoothingEnabled=false;
 ctx.fillStyle=dark?'#343c37':'#ebe6d7';ctx.fillRect(0,0,w,h);ctx.fillStyle=dark?'#666648':'#c3b48d';ctx.fillRect(0,lib.height+6,w,h);
 const frame=frameAt(lib,index),origin=world?frame[1]:0;
 for(const [x,y,r,a] of frame[5]){ctx.globalAlpha=a;ctx.fillStyle='#211e19';ctx.beginPath();ctx.ellipse(origin+x,y+6,r,1,0,0,Math.PI*2);ctx.fill()}ctx.globalAlpha=1;
 if(el('onion').checked){drawPose(ctx,lib,frameAt(lib,index-1),'#d76b52',.25);drawPose(ctx,lib,frameAt(lib,index+1),'#518bb8',.25)}
 drawPose(ctx,lib,frame);
 if(el('grid').checked){ctx.lineWidth=.06;ctx.strokeStyle=dark?'#ffffff24':'#201a1624';ctx.beginPath();for(let x=0;x<=w;x++){ctx.moveTo(x,0);ctx.lineTo(x,h)}for(let y=0;y<=h;y++){ctx.moveTo(0,y);ctx.lineTo(w,y)}ctx.stroke()}
}
function render(){
 const activity=current.activities[key],f=activity.frames[tick];
 const beats=activity.beats||[],beat=beats.filter(b=>b[0]<=tick/current.fps).slice(-1)[0];
 libraries.forEach((lib,i)=>{
  const index=Math.floor(tick/current.fps*lib.fps)%lib.activities[key].frames.length;
  draw(lib,index,canvases[i]);
  captions[i].textContent=(libraries.length>1?(i===0?'Before · ':'After · '):'Runtime · ')+lib.version+' · '+(index/lib.fps).toFixed(2)+' s / '+lib.activities[key].period.toFixed(2)+' s';
 });
 el('scrub').max=count()-1;el('scrub').value=tick;
 el('elapsed').textContent=(tick/current.fps).toFixed(2)+' s';el('frame').textContent=(tick+1)+' / '+count();
 el('play').textContent=playing?'Pause':'Play';
 el('readout').textContent=`${activity.name} · ${activity.period.toFixed(2)} s loop · ${current.fps} fps\n${beat?beat[1]:f[2]} · world x ${f[1]} · facing ${f[3]===1?'right':'left'} · travel ${f[4]?'moving':'stopped'}`;
}
function step(delta){playing=false;tick=(tick+delta+count())%count();clock=tick/current.fps;render()}
el('play').onclick=()=>{playing=!playing;last=0;render()};
el('previous').onclick=()=>step(-1);el('next').onclick=()=>step(1);
el('scrub').oninput=()=>{playing=false;tick=Number(el('scrub').value);clock=tick/current.fps;render()};
el('activity').onchange=()=>{key=el('activity').value;tick=0;clock=0;last=0;render()};
['theme','world','onion','grid'].forEach(id=>el(id).onchange=render);
document.addEventListener('keydown',e=>{if(/INPUT|SELECT|BUTTON/.test(e.target.tagName))return;if(e.code==='Space'){e.preventDefault();el('play').click()}else if(e.code==='ArrowLeft'){e.preventDefault();step(-1)}else if(e.code==='ArrowRight'){e.preventDefault();step(1)}});
function animate(now){if(playing){if(last)clock+=(now-last)/1000*Number(el('speed').value);const nextTick=Math.floor(clock*current.fps)%count();if(nextTick!==tick){tick=nextTick;render()}}last=now;requestAnimationFrame(animate)}
render();requestAnimationFrame(animate);
</script></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / '.local/animation-lab')
    parser.add_argument('--source', type=Path, default=ROOT,
                        help='Source checkout to sample, useful for a before snapshot')
    parser.add_argument('--baseline', type=Path,
                        help='Earlier poses.json to show beside this version')
    parser.add_argument('--cols', type=int, default=80)
    args = parser.parse_args()
    if args.cols < 64:
        parser.error('--cols must be at least 64')
    library = sample_library(args.source, args.cols)
    libraries = []
    if args.baseline:
        libraries.append(json.loads(args.baseline.read_text()))
    libraries.append(library)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'poses.json').write_text(json.dumps(library, separators=(',', ':')))
    data = json.dumps(libraries, separators=(',', ':')).replace('<', chr(92) + 'u003c')
    path = args.out / 'animation-lab.html'
    path.write_text(HTML.replace('__DATA__', data))
    print(path.resolve())


if __name__ == '__main__':
    main()
