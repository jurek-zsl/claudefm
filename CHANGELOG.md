# Changelog

## 1.2.0 — 2026-11-03

- Reauthored waving, coffee, idle, napping, and bouncing with deliberate key poses, eye-leading anticipation, body counterbalance, held gestures, and hand follow-through.
- Kept feet, cushions, held props, and jump shadows connected to the same grounded action geometry.
- Added an offline animation lab with frame stepping, onion skins, pixel grids, world-space contacts, and before/after comparisons at equal elapsed time.
- Documented original-stream research, useful animation skills and tools, and the practical limits of half-block rendering.
- Added synchronized frame output to reduce partial-update tearing on supporting terminals, with cleanup on rendering failure and exit.

## 1.1.1 — 2026-11-03

- Walking and cycling now travel between visible foreground destinations, rest, turn, and return.
- Matched walking stance to world movement and wheel/pedal rotation to traveled distance.
- Kept position, direction, shadows, and gait together during pauses, scene changes, and resizing.
- Opened the forest's foreground trail and kept the ground stationary under moving feet and wheels.

## 1.1.0 — 2026-11-03

- Reauthored all nine action timelines with planted walking feet, connected cycling limbs, typing rests, a longer coffee sip, and softer jump recovery.
- Added subtle floor-contact shadows synchronized with the character's motion.
- Rebuilt the worlds with atmospheric mountain layers, attached snowcaps, organic trees, warm interior lighting, wood floors, and a grounded rooftop deck.
- Replaced rigid reflection bars with broken water highlights, confined rain to window glass, and anchored petals and twinkles to their scenery.
- Added complete action previews in both palettes, timing strips, and stable-palette GIF exports for visual review.

## 1.0.0 — 2026-11-03

Initial open-source version.

- Terminal playback of Claude FM through `mpv` and `yt-dlp`, with pause, volume, mute, and a playback verification command.
- Nine Clawd activities and matching layered pixel worlds, with ambient movement and light/dark palettes.
- Time-based animation with occasional blinks, stable props, and connected, distinct limbs.
- Paired activity and scenery rotation every five minutes, a visible countdown, and manual scene selection.
- Startup theme selection from macOS appearance, explicit theme flags, and a manual toggle.
- Responsive half-block rendering, changed-row updates, help, and terminal restoration on exit.
- Honest playback states and useful audio errors, including discovery of Homebrew's unlinked `yt-dlp` installation.
- Standard-library runtime, regression tests, and a developer preview exporter.
- macOS Homebrew installation through the project's community tap, with declared audio dependencies and a checked source archive.
