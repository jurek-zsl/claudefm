"""
Command-line interface entry point for Claude FM.
"""
import sys
import argparse
import time
from claudefm import __version__
from claudefm.audio import AudioPlayer, DEFAULT_STREAM_URL
from claudefm.tui import TUI
from claudefm.sprites import ACTIVITY_KEYS


def parse_args():
    parser = argparse.ArgumentParser(
        prog="claudefm",
        description="Claude FM 🎵 24/7 Lo-Fi Radio for Thinking and Building in your Terminal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Activities (original terminal adaptations of Clawd):
  bike      Cruising on a bicycle
  walk      Four-legged scuttle
  coding    Typing at a laptop
  bounce    Anticipation, hop and soft landing
  wave      A little greeting, then a rest
  coffee    Slowly raise, sip and lower a warm mug
  napping   Breathing on a stationary cushion
  idle      Looking around with occasional blinks
  guitar    Strumming a little guitar

Keyboard Controls:
  Space       Play / Pause
  + / k       Volume Up (+5%)
  - / j       Volume Down (-5%)
  m           Mute / Unmute
  a / Tab     Cycle Activity (or keys 1-9)
  t           Toggle Light / Dark Theme
  h / ?       Help Overlay
  q           Quit
        """
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=DEFAULT_STREAM_URL,
        help=f"Stream URL to play (default: Claude FM on YouTube)"
    )
    parser.add_argument(
        "--dark",
        action="store_true",
        help="Start in Midnight Dark theme"
    )
    parser.add_argument(
        "--light",
        action="store_true",
        help="Start in Paper Light theme"
    )
    parser.add_argument(
        "--volume", "-v",
        type=int,
        default=80,
        help="Initial volume level from 0 to 100 (default: 80)"
    )
    parser.add_argument(
        "--activity", "-a",
        choices=ACTIVITY_KEYS,
        default="bike",
        help="Initial activity for Claude mascot (default: bike)"
    )
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="Visuals only mode (disables mpv audio playback)"
    )
    parser.add_argument(
        "--check-audio",
        action="store_true",
        help="Test a few seconds of real audio playback without entering the TUI"
    )
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"%(prog)s {__version__}"
    )
    return parser.parse_args()

def check_audio(player, timeout=45):
    """Require an active output and advancing decoded audio, not just IPC."""
    previous_status = None
    playing_at = None
    first_position = None
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            if player.status != previous_status:
                print("Audio: {}".format(player.status), flush=True)
                previous_status = player.status
            if player.status == 'error':
                print(player.error_message, file=sys.stderr)
                return 1
            if player.status == 'playing' and player.playback_position is not None:
                if playing_at is None:
                    playing_at, first_position = time.monotonic(), player.playback_position
                elif time.monotonic() - playing_at >= 3 and player.playback_position > first_position + 1:
                    output = player.audio_output or {}
                    print("Audio OK: {} via {}, {} Hz, {}. Playback advanced {:.1f}s.".format(
                        player.audio_codec or 'decoded audio', player.audio_driver or 'audio output', output.get('samplerate', '?'),
                        output.get('channels', '?'), player.playback_position-first_position))
                    return 0
            else:
                playing_at, first_position = None, None
            time.sleep(.1)
        print("Audio did not start in time. Check the stream, network, and audio output.", file=sys.stderr)
        return 1
    finally:
        player.stop()


def main():
    args = parse_args()

    if args.check_audio and args.no_audio:
        raise SystemExit('--check-audio cannot be combined with --no-audio')

    theme_choice = 'dark' if args.dark else 'light' if args.light else 'auto'

    # Initialize Audio Player
    player = AudioPlayer(
        stream_url=args.url,
        initial_volume=args.volume,
        enabled=not args.no_audio
    )

    if args.check_audio:
        raise SystemExit(check_audio(player))

    # Initialize TUI
    tui = TUI(
        audio_player=player,
        initial_theme=theme_choice,
        initial_activity=args.activity
    )

    # Run full-screen TUI loop
    try:
        tui.run()
    except Exception as e:
        player.stop()
        raise e

if __name__ == "__main__":
    main()
