# Contributing

Thanks for helping make this a calm, reliable little terminal companion. Open an [issue](https://github.com/jurek-zsl/claudefm/issues) to discuss a bug or a substantial change before starting a large implementation.

## Local setup

Use Python 3.8 or newer on macOS or Linux:

```sh
git clone https://github.com/jurek-zsl/claudefm.git
cd claudefm
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
claudefm --no-audio
```

Install `mpv` and `yt-dlp` separately to exercise audio. On macOS, `brew install mpv yt-dlp` supplies both. Use `claudefm --check-audio` to confirm playback without entering the full-screen interface.

## Checks

```sh
python -m unittest discover -s tests -v
python -m compileall -q claudefm
```

Tests cover animation geometry, scene pairing, five-minute timing, terminal layout, startup appearance, and the audio worker's status and IPC behavior. Audio unit tests do not require network access or a working speaker. A live playback check does.

For a packaging change, build a wheel and verify it in a fresh environment:

```sh
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*.whl dist/*.tar.gz
python3 -m venv /tmp/claudefm-wheel-check
/tmp/claudefm-wheel-check/bin/python -m pip install dist/*.whl
/tmp/claudefm-wheel-check/bin/claudefm --help
/tmp/claudefm-wheel-check/bin/claudefm --version
```

Standalone builds use `uv` (install it with `python -m pip install uv` if needed). `./build_binary.sh` builds a local standalone executable in `dist/`. Installation is a separate, explicit action: `./build_binary.sh --install`. The executable targets the platform and architecture on which it was built.

## Visual changes

The app has no Python runtime dependencies. Pillow is an optional development tool for previews:

```sh
python -m pip install Pillow
python scripts/preview_animations.py --scenes-only --scene-motion
```

Previews are written under `art/out/clawd/` by default and are ignored by Git. Use `--out /path/to/output` to choose another directory. The script renders the app's actual terminal output; it does not use a separate mockup. Curated README media lives in `docs/assets/`.

When changing animation or rendering:

- Keep four distinct feet, a stable floor, connected hands, and stationary props.
- Sample motion from elapsed time; redraws must not advance it. Keep ambient motion sparse.
- Check light and dark palettes at 64×18 and a larger window. Every rendered row must fit its terminal width.
- Confirm pause, manual scene selection, automatic rotation, resizing, help, and clean exit.
- Keep system probes and process creation out of the frame loop.

`claudefm/sprites.py` defines Clawd's poses, `scene.py` composes the worlds, `tui.py` draws and handles controls, and `audio.py` owns playback. Theme detection runs once at startup in `themes.py`.

## Homebrew formula

`Formula/claudefm.rb` uses an immutable version-tag archive and SHA-256 checksum. The formula installs the standard-library app directly into `libexec`, uses Homebrew's Python, and declares `mpv` and `yt-dlp` as dependencies. It does not need pip or a build backend.

To test a formula change on macOS:

```sh
brew tap jurek-zsl/claudefm https://github.com/jurek-zsl/claudefm
cp Formula/claudefm.rb "$(brew --repository jurek-zsl/claudefm)/Formula/claudefm.rb"
brew install --build-from-source jurek-zsl/claudefm/claudefm
brew test jurek-zsl/claudefm/claudefm
```

If it is already installed, use `brew reinstall --build-from-source` in place of `brew install`. On Homebrew versions with formula trust prompts, review and trust this specific formula with `brew trust --formula jurek-zsl/claudefm/claudefm` before testing. The Homebrew workflow checks the formula from the current checkout, including pull-request changes.

For a new version:

1. Update `claudefm.__version__` and the changelog, run the checks, and commit the release source.
2. Create and push a version tag such as `v1.0.1`. Never move an existing release tag.
3. Download that exact tag archive and compute its checksum:

   ```sh
   curl --fail --location --output /tmp/claudefm-v1.0.1.tar.gz \
     https://github.com/jurek-zsl/claudefm/archive/refs/tags/v1.0.1.tar.gz
   shasum -a 256 /tmp/claudefm-v1.0.1.tar.gz
   ```

4. Update the formula's archive URL and `sha256`, test the installation, and commit the formula change. Use the new version in the commands above for each release.

The formula has no bottles; Homebrew installs from the verified source archive. The formula currently supports macOS; the pipx and source installations also support Linux.

## Pull requests and issues

Describe the concrete problem, resulting behavior, and checks run. Include an actual terminal render for visual changes. Keep generated experiments, local environments, build outputs, and machine-specific settings out of commits.

For a bug report, include the operating system, terminal, Python version, command used, and a minimal reproduction. For audio problems, include the result of `--check-audio`; do not post private stream URLs or signed media URLs.

Please keep the project's [NOTICE](NOTICE) intact and use only assets and code you have permission to contribute.
