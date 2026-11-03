# Clawd animation direction and research

Research reviewed on 3 November 2026. The target is the appeal and deliberate acting of Claude FM, adapted to a real terminal grid.

## What the references show

The [official Claude FM stream](https://www.youtube.com/watch?v=tRsQsTMvPNg) is the primary visual reference. The segment inspected during this research places a small coral aviator and plane against a largely monochrome, textural landscape. Clear color separation, open space around the character, readable props, and restrained motion do much of the work. This observation describes that segment, rather than every scene in the broadcast. A short local study capture is excluded from the repository; no broadcast frames or extracted mascot assets ship with the app.

Ayotomiwa Wale-Durojaye's [frame-by-frame reconstruction of four official Clawd clips](https://tympanus.net/codrops/2026/05/05/reverse-engineering-claude-ais-mascot-animations-with-svg-and-gsap/) is the strongest technical reference found. It demonstrates floor clipping, coordinated eye/body/leg movement, counterbalance under a raised hand, distinct drawings for changing silhouettes, and unequal pose holds. We apply those principles in original terminal drawings. The author's SVG/React implementation is not a runtime dependency.

[Disney Animation's own process description](https://disneyanimation.com/process/animation/) identifies timing, staging, squash and stretch, anticipation, follow-through, and secondary action as the foundations of a believable performance. These are the review criteria here, rather than the number of interpolated frames.

## Skills evaluated

| Resource | Useful contribution | Decision for this project |
|---|---|---|
| [Anthropic: slack-gif-creator](https://github.com/anthropics/skills/tree/main/skills/slack-gif-creator) | Python/Pillow frame generation, easing, GIF assembly and validation | A useful preview reference. Its Slack limits and decorative advice are not the Clawd specification. Our exporter already renders the actual app. |
| [Pixel Art Animator](https://github.com/willibrandon/pixel-plugin/tree/main/skills/pixel-art-animator) | Named animation sequences, cel durations, linked cels, sprite-sheet workflow | Useful if an Aseprite MCP server is available. Its required Aseprite tools are not connected here. |
| [2D Pixel Art Asset Creation](https://github.com/ervareza/agent-skill-pixel-art/tree/v4.3.0/skills/pixel-art) | Palette locks, exact dimensions, opacity and pixel-grid audits | Useful checklist for bitmap pipelines. The terminal rig already enforces a character palette and canvas directly. |
| [Clawd animation guide](https://github.com/JohnHeibel/ClaudeAnimationBase/blob/main/ANIMATION_GUIDE.md) | Character consistency, drawn views, purposeful acting and shot continuity | Community reference, not an official model sheet. Its watercolor/line-boil style belongs to a different medium. |

These resources were inspected as research. No third-party skill scripts, MCP servers, or paid generation services were installed. The project keeps its standard-library runtime.

## Tools that actually help

| Tool | Role | Status |
|---|---|---|
| [Aseprite](https://www.aseprite.org/docs/animation/) | Manual pixel drawing, frame tags and per-cel timing. [Onion skinning](https://www.aseprite.org/docs/onion-skinning/) makes spacing and silhouette mistakes visible. [CLI export](https://www.aseprite.org/docs/cli/) produces sheets and JSON metadata. | Optional authoring tool; not installed or required by this project. |
| [Pillow](https://pillow.readthedocs.io/en/stable/) | Exact-pixel contact sheets and complete terminal GIFs | Optional development dependency used by the existing preview exporter. |
| [FFmpeg](https://ffmpeg.org/documentation.html) | Bounded reference studies, frame stepping, video/contact-sheet export | Available locally; not needed to run the app. |
| `scripts/animation_lab.py` | Offline playback, frame stepping, before/after comparison, onion skins, pixel grid, world position and contact shadows | Included developer tool; Python standard library only. |
| `scripts/preview_animations.py` | Complete scenes captured from actual ANSI terminal output | Included developer tool; Pillow only. |

Generative video tools do not provide exact control over every foot contact, pixel silhouette, and loop seam in this renderer. They can help explore a direction, but the final Clawd motion needs authored poses and direct inspection.

## The terminal ceiling

At 80 columns by 24 rows, the current scene has an 80-by-40 half-block pixel surface. The actor uses a 40-by-26 canvas, with a roughly 16-by-12 neutral torso. A nominal half-pixel movement can disappear after rounding, then jump a full pixel. Increasing playback from 24 to 60 fps would not create missing poses or more spatial detail.

For the portable renderer, make each changed pixel intentional:

- Keep the coral body flat and recognizable. Build expression through silhouette, gaze, posture and timing.
- Let the eyes lead a lean; let hands settle after the torso. Use discrete poses with clear holds for tiny details.
- Keep stance feet and resting props fixed. Apply counterbalance above those contacts.
- Give gestures an anticipation, action, recovery and quiet rest. Avoid continual bobbing on every part.
- Check the complete loop at native resolution before inspecting an enlarged view.
- Keep walking/cycling distance, gait and shadows on their existing shared clock.

The renderer also brackets changed-frame writes with [DEC2026 synchronized output](https://github.com/contour-terminal/vt-extensions/blob/master/synchronized-output.md). Supporting terminals can present the completed screen instead of painting a partially received update. The mode is ended immediately after writing, including cleanup paths; it is never held during input, animation computation or sleep. This improves presentation without changing the pixel grid. Terminals that ignore the mode retain ordinary half-block output.

There is a higher-resolution path inside some terminals: the [Kitty graphics protocol](https://sw.kovidgoyal.net/kitty/graphics-protocol/) can transmit actual pixel images and animation data. [Ghostty documents Kitty graphics support](https://ghostty.org/docs/features), while [iTerm2 documents inline images, animated GIFs and Kitty graphics](https://iterm2.com/documentation-images.html). A graphics backend would require capability detection, image lifetime/cleanup, pause and resize integration, higher-resolution artwork, and a working half-block fallback. Enlarging today's low-resolution sprite through an image protocol would not add detail. This is a separate future enhancement, not a claim about the current renderer.

## Repeatable authoring and review

Before changing the rig, preserve a snapshot:

```sh
python3 scripts/animation_lab.py --out .local/animation-before
```

After changing it, export the comparison:

```sh
python3 scripts/animation_lab.py \
  --baseline .local/animation-before/poses.json \
  --out .local/animation-after
open .local/animation-after/animation-lab.html
```

The HTML works offline and contains the sampled Python poses. It never invents browser-side tweening. The scene in this lab is a neutral contact stage, so it is easy to see grounded feet and hands; use the complete terminal captures to evaluate backgrounds and UI:

```sh
python scripts/preview_animations.py --scenes-only \
  --motion-all --motion-strips --journey-strips --fps 12 \
  --out .local/animation-scenes
```

Use the lab to step through the raised hand, the cup's arc, compression before a hop, and recovery after a gesture. Compare before and after at the same pixel scale. Then review every full loop in light and dark, at 64×18 and a larger terminal, and exercise pause, selection, five-minute rotation, resize and exit.

Acceptance requires readable acting, stable contacts, attached props, bounded poses and a settled loop seam. Automated geometry checks support this review; they cannot decide whether a character feels appealing.
