"""
Full-screen ANSI Terminal User Interface for Claude FM.
Handles double-buffering, responsive resizing, truecolor half-block compositing,
and keyboard events.
"""
import os
import math
import re
import sys
import time
import tty
import termios
import select
import shutil
import signal
import unicodedata
from claudefm.sprites import (
    SPRITE_PALETTE,
    ACTIVITIES,
    ACTIVITY_KEYS,
    sample_travel_pose,
    travel_contact_shadows,
    WIDTH, HEIGHT, FPS,
)
from claudefm.scene import SCENE_NAMES, Scene, render_background
from claudefm.locomotion import sample_locomotion, remap_journey_elapsed
from claudefm.themes import LIGHT_THEME, DARK_THEME, detect_system_theme

_ANSI_RE = re.compile(r'\033\[[0-9;]*m')

# Unicode ranges that render as double-width (2 terminal columns) in most
# modern terminal emulators. Treating them as width 1 (plain `len()`) is what
# let header/status text silently overflow past `cols` and wrap the whole
# layout onto an extra line.
_WIDE_RANGES = (
    (0x1F300, 0x1FAFF),  # emoji, pictographs, transport symbols
    (0x2600, 0x27BF),    # misc symbols & dingbats (e.g. ☕)
)

def _char_width(ch):
    if unicodedata.combining(ch) or ch in ('\ufe0f', '\ufe0e', '\u200d'):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1

def visible_width(s):
    """Approximate on-screen column width of `s`, ignoring ANSI SGR codes
    and counting emoji/symbol characters as double-width."""
    return sum(_char_width(ch) for ch in _ANSI_RE.sub('', s))

def pad_to_width(s, width):
    """Pad or truncate plain (non-ANSI) text to an exact visible width so it
    can never overflow `width` columns and force a wrap."""
    w = visible_width(s)
    if w <= width:
        return s + ' ' * (width - w)
    out = []
    total = 0
    for ch in s:
        cw = _char_width(ch)
        if total + cw > width:
            break
        out.append(ch)
        total += cw
    return ''.join(out) + ' ' * (width - total)

def compress_row(cells, background):
    """Join one rendered terminal row's per-cell ANSI strings, dropping any
    color codes that repeat the previous cell's.

    Every cell produced below is `<SGR codes><char>\033[0m`. At ~16 frames
    per second this scene was re-painting every single cell with its own
    full truecolor codes and reset even when it was identical to its
    neighbor (a run of plain sky or ground is dozens of cells wide), which
    made each frame ~80KB of mostly-redundant escape codes. Over an SSH
    link, tmux, or a slower terminal that volume of output doesn't arrive
    atomically, and a partially-flushed frame can visibly tear the top of
    the screen -- which is what 'the top bar isn't showing / it breaks'
    looks like from the user's side. Collapsing repeated SGR runs cuts a
    typical frame down by roughly an order of magnitude with an identical
    visual result.
    """
    out = []
    last_sgr = None
    for cell in cells:
        body = cell[:-4] if cell.endswith('\033[0m') else cell  # strip trailing reset
        if '\033[48;2;' not in body:
            body = '\033[48;2;{};{};{}m'.format(*background) + body
        char = body[-1]
        sgr = body[:-1]
        if sgr == last_sgr:
            out.append(char)
        else:
            out.append(sgr)
            out.append(char)
            last_sgr = sgr
    out.append('\033[0m')
    return ''.join(out)


def _composite_contact_shadows(pixels, origin_x, origin_y, patches):
    """Soften contact with the floor without tinting the actor or scenery above it.

    Patches are local (center_x, floor_y, radius, opacity) tuples. The sprite
    pass runs afterward, keeping feet and props crisp over the soft shadow.
    """
    if not pixels or not pixels[0]:
        return
    height, width = len(pixels), len(pixels[0])
    for center, floor, radius, opacity in patches:
        if radius <= 0 or opacity <= 0:
            continue
        center += origin_x
        floor += origin_y
        for y in range(max(0, math.floor(floor)), min(height, math.ceil(floor + 2))):
            vertical = max(0.0, 1 - ((y - floor + .3) / 2) ** 2)
            for x in range(max(0, math.floor(center - radius)),
                           min(width, math.ceil(center + radius))):
                distance = (x + .5 - center) / radius
                softness = max(0.0, 1 - distance * distance) ** 2
                shade = min(.35, opacity) * softness * vertical
                if shade > 0:
                    pixels[y][x] = tuple(round(channel * (1 - shade))
                                         for channel in pixels[y][x])


class TUI:
    def __init__(self, audio_player, initial_theme='auto', initial_activity='bike'):
        self.audio = audio_player
        theme = detect_system_theme() if initial_theme == 'auto' else initial_theme
        self.theme = DARK_THEME if theme == 'dark' else LIGHT_THEME
        self.activity_key = initial_activity if initial_activity in ACTIVITIES else 'bike'
        self.activity_index = ACTIVITY_KEYS.index(self.activity_key)
        self.auto_cycle_activity = True
        self.last_activity_switch = time.monotonic()

        self.scene = Scene()
        self.running = False
        self.show_help = False

        # Frame animation state
        self.frame_index = 0
        self.tick_count = 0
        self.start_time = time.monotonic()
        self.animation_time = 0.0
        self.activity_elapsed = 0.0
        self._previous_lines = []
        self._previous_size = None
        self._motion_cache = None
        self._journey_cols = None
        self._journey_offset = 0.0

        # Terminal settings
        self.old_termios = None
        self.cols, self.rows = shutil.get_terminal_size((80, 24))

    def setup_terminal(self):
        # Save old termios settings
        self.old_termios = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())
        # Alternate buffer, clear screen, hide cursor, disable autowrap.
        # Every row we draw is built to fill the terminal exactly `cols`
        # wide, so we never want the terminal to wrap anything itself. With
        # autowrap left on, writing a full-width row leaves the cursor in a
        # "pending wrap" state that some terminals (and tmux) only resolve
        # on the *next* frame's `\033[H`, which can trigger a spurious
        # scroll and push the header off the top of the screen -- exactly
        # the "top bar isn't showing, I have to scroll for it" bug.
        # Disabling DECAWM (`\033[?7l`) removes that ambiguity entirely.
        sys.stdout.write("\033[?1049h\033[2J\033[H\033[?25l\033[?7l")
        sys.stdout.flush()

    def restore_terminal(self):
        # Re-enable autowrap, show cursor, restore main buffer, restore termios
        sys.stdout.write("\033[?7h\033[?25h\033[?1049l")
        sys.stdout.flush()
        if self.old_termios:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_termios)
            except Exception:
                pass

    def handle_input(self):
        # Non-blocking read straight from the raw fd (not sys.stdin.read).
        # sys.stdin is a buffered TextIOWrapper: a single read(1) call can
        # pull an entire escape sequence ('\x1b', '[', 'A') out of the OS
        # pipe into Python's internal buffer in one syscall. The follow-up
        # select() then checks the *raw fd*, finds nothing left to read
        # (it's already sitting in the Python-level buffer), times out
        # immediately, and the arrow key gets misread as a bare Escape --
        # which is exactly why pressing Up/Down quit the app instead of
        # changing the volume. Reading via os.read() bypasses that buffer.
        fd = sys.stdin.fileno()
        if select.select([fd], [], [], 0)[0]:
            try:
                ch = os.read(fd, 1).decode(errors='ignore')
            except Exception:
                return
            if not ch:
                return

            if ch == '\033': # Escape sequence
                seq = ''
                # Read possible escape sequences like arrow keys. Give the
                # terminal a generous window to deliver the remaining bytes
                # before concluding this was a lone Escape press.
                while len(seq) < 4 and select.select([fd], [], [], 0.05)[0]:
                    nxt = os.read(fd, 1).decode(errors='ignore')
                    if not nxt:
                        break
                    seq += nxt
                if seq in ('[A', 'OA'): # Up Arrow (best-effort; see below)
                    self.audio.volume_up(5)
                elif seq in ('[B', 'OB'): # Down Arrow (best-effort; see below)
                    self.audio.volume_down(5)
                # A bare Escape (nothing followed it) used to quit the app.
                # Arrow-key escape sequences arrive as 2-3 separate bytes,
                # and anything that delays the follow-up bytes past our
                # read window -- a slow terminal, tmux/SSH, or just the
                # audio player's background thread eating a CPU slice at
                # the wrong moment -- makes an arrow key look exactly like
                # a lone Escape. Quitting on that misdetection is why
                # arrow keys could close the app. '+'/'-' below are single,
                # unambiguous bytes with no such race, so they're the
                # documented volume control; Escape no longer quits at all,
                # only 'q'/Ctrl+C do, so a misdetected arrow can no longer
                # close the app.
            elif ch in ('q', 'Q', '\x03'): # Quit or Ctrl+C
                self.running = False
            elif ch == ' ': # Play / Pause
                self.audio.toggle_pause()
            elif ch in ('+', '=', 'k', 'K'): # Vol Up
                self.audio.volume_up(5)
            elif ch in ('-', '_', 'j', 'J'): # Vol Down
                self.audio.volume_down(5)
            elif ch in ('m', 'M'): # Mute
                self.audio.toggle_mute()
            elif ch in ('t', 'T'): # Toggle Theme
                self.theme = DARK_THEME if not self.theme.is_dark else LIGHT_THEME
            elif ch in ('a', 'A', '\t'): # Next Activity
                self.next_activity()
            elif ch in ('h', 'H', '?'): # Help Overlay
                self.show_help = not self.show_help
            elif ch in '123456789':
                idx = int(ch) - 1
                if 0 <= idx < len(ACTIVITY_KEYS):
                    self.set_activity(ACTIVITY_KEYS[idx])

    def next_activity(self):
        self.set_activity(ACTIVITY_KEYS[(self.activity_index + 1) % len(ACTIVITY_KEYS)])

    def set_activity(self, key):
        if key in ACTIVITIES:
            self.activity_key = key
            self.activity_index = ACTIVITY_KEYS.index(key)
            self.frame_index = 0
            self.animation_time = self.activity_elapsed = 0.0
            self.last_activity_switch = time.monotonic()
            self.scene.reset(key)
            self._motion_cache = None
            self._journey_cols = None
            self._journey_offset = 0.0

    def _frame_motion(self, cols):
        if self._journey_cols is not None and cols!=self._journey_cols:
            elapsed=self.animation_time+self._journey_offset
            remapped=remap_journey_elapsed(self.activity_key,elapsed,self._journey_cols,cols)
            self._journey_offset=remapped-self.animation_time
        self._journey_cols=cols
        key=(self.activity_key,self.animation_time+self._journey_offset,cols)
        if self._motion_cache is None or self._motion_cache[0]!=key:
            motion=sample_locomotion(*key)
            # Eye blinks and stationary activities retain the global actor clock.
            actor_time=math.floor(self.animation_time*FPS+1e-9)/FPS
            self._motion_cache=(key,motion._replace(elapsed=actor_time))
        return self._motion_cache[1]

    def mascot_origin(self, cols, rows):
        return self._frame_motion(cols).origin_x, rows - 4 - HEIGHT // 2

    def advance(self, dt):
        """The five-minute carousel uses real elapsed time, even while paused."""
        dt = max(0.0, dt)
        self.activity_elapsed += dt
        motion_dt = dt
        if self.auto_cycle_activity and self.activity_elapsed >= 300.0:
            switches = int(self.activity_elapsed // 300.0)
            remainder = self.activity_elapsed % 300.0
            self.set_activity(ACTIVITY_KEYS[(self.activity_index + switches) % len(ACTIVITY_KEYS)])
            self.activity_elapsed = remainder
            motion_dt = remainder
        if self.audio.is_paused:
            return
        self.animation_time += motion_dt
        self.frame_index = int(self.animation_time * FPS)
        x, y = self.mascot_origin(self.cols, self.rows)
        info = ACTIVITIES[self.activity_key]
        self.scene.update(dt=motion_dt, is_biking=info['has_scrolling_road'],
                          activity=self.activity_key, mascot_x=x, mascot_y=y,
                          particle_origin=info['particle_origin'], cols=self.cols)

    @staticmethod
    def _style(text, foreground, background):
        return '\033[38;2;{};{};{}m\033[48;2;{};{};{}m{}\033[0m'.format(
            *foreground, *background, text)

    @staticmethod
    def _clean(text):
        return ''.join(ch if _char_width(ch) == 1 and ch.isprintable() else '?'
                       for ch in str(text))

    def audio_status(self):
        fallback = ('disabled' if not getattr(self.audio, 'enabled', True) else
                    'paused' if self.audio.is_paused else
                    'connecting' if self.audio.is_buffering else 'playing')
        return getattr(self.audio, 'status', fallback)

    def render_lines(self, cols, rows):
        if cols < 64 or rows < 18:
            lines = ['Claude FM', 'Resize to at least 64 x 18',
                     'Current: {} x {}'.format(cols, rows)]
            return [pad_to_width(line, cols) for line in lines[:rows]] + [' ' * cols] * max(0, rows-len(lines))
        th = self.theme
        info = ACTIVITIES[self.activity_key]
        ground_row = rows - 4
        pixels = render_background(cols, ground_row * 2, self.activity_key,
                                   th.is_dark, self.scene.elapsed)
        # Compose the real background under every transparent half-pixel.
        motion = self._frame_motion(cols)
        pose = sample_travel_pose(self.activity_key, motion)
        mx, my = motion.origin_x, rows - 4 - HEIGHT // 2
        py = (my - 1) * 2
        _composite_contact_shadows(pixels, mx, py,
                                   travel_contact_shadows(self.activity_key, motion))
        for y, sprite_row in enumerate(pose):
            for x, char in enumerate(sprite_row):
                color = SPRITE_PALETTE[char]
                if color is not None and 0 <= mx+x < cols and 0 <= py+y < len(pixels):
                    pixels[py+y][mx+x] = color

        state = self.audio_status()
        status_text = {'disabled':'VISUALS', 'connecting':'CONNECTING',
                       'buffering':'BUFFERING', 'playing':'PLAYING',
                       'paused':'PAUSED', 'error':'AUDIO ERROR'}.get(state, 'CONNECTING')
        status_color = th.status_play if state == 'playing' else th.status_pause
        if state == 'disabled': status_color = th.fg_muted
        elapsed = int(time.monotonic() - self.start_time)
        timer = '{:02d}:{:02d}'.format(*divmod(elapsed, 60))
        volume = 'MUTE' if self.audio.is_muted else 'VOL {:3d}%'.format(self.audio.volume)
        left = ' Claude FM  ·  music for thinking'
        right = '{}  {}  {} '.format(status_text, timer, volume)
        if len(left) + len(right) + 2 > cols: left = ' Claude FM'
        gap = max(1, cols-len(left)-len(right))
        out = [self._style(left + ' '*gap, th.fg_accent, th.bg_sky) +
               self._style(right, status_color, th.bg_sky)]

        particles = {(int(p.x),int(p.y)):p for p in self.scene.particles}
        for r in range(1, ground_row+1):
            cells=[]
            for x in range(cols):
                top, bottom = pixels[(r-1)*2][x], pixels[(r-1)*2+1][x]
                if (x,r) in particles:
                    p=particles[(x,r)]
                    cell=self._style(p.char,p.color,bottom)
                elif top == bottom:
                    cell=self._style(' ',top,bottom)
                else:
                    cell=self._style('▀',top,bottom)
                cells.append(cell)
            out.append(compress_row(cells,th.bg_sky))
        error = self._clean(getattr(self.audio,'error_message',''))
        detail = ' Audio: '+error if state == 'error' and error else ''
        out.append(self._style(pad_to_width(detail,cols),th.fg_text,th.bg_ground))
        seconds = max(0, math.ceil(300-self.activity_elapsed))
        countdown = 'Next {:02d}:{:02d} '.format(*divmod(seconds,60))
        label = ' {}  ·  {}'.format(SCENE_NAMES[self.activity_key],info['name'])
        if not self.auto_cycle_activity: countdown = 'Stay awhile '
        label = pad_to_width(label,cols-len(countdown))
        out.append(self._style(label+countdown,th.fg_text,th.bg_ground))
        controls = ' Space Pause  +/- Volume  A Next  1-9 Scenes  T Theme  H Help  Q Quit'
        out.append(self._style(pad_to_width(controls,cols),th.pill_fg,th.pill_bg))
        if self.show_help:self._render_help_overlay(out,cols,rows)
        return out[:rows]

    def render(self):
        self.cols, self.rows = shutil.get_terminal_size((80, 24))
        lines = self.render_lines(self.cols, self.rows)
        size = (self.cols, self.rows)
        resized = size != self._previous_size
        writes = ['\033[2J'] if resized else []
        for row, line in enumerate(lines):
            if resized or row >= len(self._previous_lines) or line != self._previous_lines[row]:
                writes.append('\033[{};1H{}'.format(row+1, line))
        if writes:
            # Cursor-address each changed row, never print a newline at the floor.
            sys.stdout.write(''.join(writes))
            sys.stdout.flush()
        self._previous_lines, self._previous_size = lines, size

    def _render_help_overlay(self, out_lines, cols, rows):
        help_box = [
            'Claude FM - Shortcuts', '',
            'Space  Play / pause     +/- or k/j  Volume',
            'M      Mute             T           Theme',
            'A/Tab  Next activity    1-9         Choose',
            '1 Bike   2 Walk   3 Coding   4 Bounce',
            '5 Wave   6 Coffee 7 Nap      8 Idle',
            '9 Guitar', '',
            'H / ?  Close help       Q           Quit',
        ]
        box_w = 56
        box_h = len(help_box)
        start_r = max(2, (rows - box_h) // 2)
        start_c = max(2, (cols - box_w) // 2)

        for i, line in enumerate(help_box):
            r_idx = start_r + i
            if 0 <= r_idx < len(out_lines):
                # Replace segment
                cur = out_lines[r_idx]
                # To keep it simple, overwrite line centered
                pad_l = " " * start_c
                pad_r = " " * max(0, cols - start_c - box_w)
                styled = f"\033[1m\033[38;2;255;255;255m\033[48;2;32;32;40m{pad_to_width(line, box_w)}\033[0m"
                sky = '\033[48;2;{};{};{}m'.format(*self.theme.bg_sky)
                out_lines[r_idx] = f"{sky}{pad_l}{styled}{sky}{pad_r}\033[0m"

    def run(self):
        self.setup_terminal()
        self.running = True

        # Signal handlers for clean exit on Ctrl+C or kill
        def sig_handler(sig, frame):
            self.running = False
        signal.signal(signal.SIGINT, sig_handler)
        signal.signal(signal.SIGTERM, sig_handler)

        frame_delay = 1 / FPS
        previous_time = time.monotonic()

        try:
            while self.running:
                t0 = time.monotonic()
                # Attribute time since the previous frame to its pause state,
                # before processing a new pause/resume key.
                self.advance(t0 - previous_time)
                previous_time = t0
                self.handle_input()
                if not self.running:
                    break

                # Render current frame
                self.render()

                # Frame timing
                elapsed = time.monotonic() - t0
                sleep_time = max(0.005, frame_delay - elapsed)
                time.sleep(sleep_time)

        finally:
            self.restore_terminal()
            self.audio.stop()
            print("\n Claude FM stopped. Keep building! ✨\n")
