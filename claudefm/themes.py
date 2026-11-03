"""
Themes and color palettes for Claude FM TUI.
"""

import subprocess
import sys


def detect_system_theme():
    """Read the macOS appearance once at startup; use light elsewhere."""
    if sys.platform != 'darwin':
        return 'light'
    try:
        result = subprocess.run(
            ['/usr/bin/defaults', 'read', '-g', 'AppleInterfaceStyle'],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, timeout=0.5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return 'light'
    return 'dark' if result.returncode == 0 and result.stdout.strip().lower() == 'dark' else 'light'


class Theme:
    def __init__(self, name, is_dark, bg_sky, bg_ground, fg_text, fg_muted, fg_accent,
                 fg_cloud, fg_mountain, fg_ground, pill_bg, pill_fg, status_play, status_pause):
        self.name = name
        self.is_dark = is_dark
        self.bg_sky = bg_sky
        self.bg_ground = bg_ground
        self.fg_text = fg_text
        self.fg_muted = fg_muted
        self.fg_accent = fg_accent
        self.fg_cloud = fg_cloud
        self.fg_mountain = fg_mountain
        self.fg_ground = fg_ground
        self.pill_bg = pill_bg
        self.pill_fg = pill_fg
        self.status_play = status_play
        self.status_pause = status_pause

LIGHT_THEME = Theme(
    name="Paper (Classic)",
    is_dark=False,
    bg_sky=(244, 240, 232),       # #F4F0E8 warm cream
    bg_ground=(234, 233, 223),    # #EAE9DF
    fg_text=(45, 45, 50),         # #2D2D32 dark charcoal
    fg_muted=(120, 115, 110),     # #78736E muted warm grey
    fg_accent=(221, 131, 97),     # #DD8361 Claude coral
    fg_cloud=(155, 150, 145),     # #9B9691 ASCII cloud
    fg_mountain=(135, 130, 125),  # #87827D ASCII mountain
    fg_ground=(115, 110, 105),    # #736E69 ASCII ground
    pill_bg=(32, 30, 35),         # #201E23 dark pill
    pill_fg=(245, 245, 245),      # #F5F5F5
    status_play=(34, 197, 94),    # #22C55E green
    status_pause=(234, 179, 8),   # #EAB308 amber
)

DARK_THEME = Theme(
    name="Midnight Lo-Fi",
    is_dark=True,
    bg_sky=(22, 22, 26),          # #16161A midnight slate
    bg_ground=(28, 28, 34),       # #1C1C22
    fg_text=(230, 230, 235),      # #E6E6EB
    fg_muted=(130, 135, 145),     # #828791
    fg_accent=(240, 138, 102),    # #F08A66 vibrant coral
    fg_cloud=(85, 90, 102),       # #555A66
    fg_mountain=(70, 75, 88),     # #464B58
    fg_ground=(80, 85, 95),       # #50555F
    pill_bg=(40, 42, 50),         # #282A32
    pill_fg=(255, 255, 255),      # #FFFFFF
    status_play=(74, 222, 128),   # #4ADE80
    status_pause=(250, 204, 21),  # #FACC15
)
