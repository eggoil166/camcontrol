# camcontrol

Head-pose pointer with dwell-to-select for the terminal. A webcam + MediaPipe
track your head; a calibrated gaze point maps to a grid over the foreground
terminal window, and dwelling on a cell commits a selection. Built to later drive
tmux pane focus (see the design notes referenced in the code's SPEC markers).

A detached, windowless daemon owns the camera; foreground commands talk to it over
a localhost JSON-lines control socket. Windows-only today, but OS-specific pieces
(process spawn, window/DPI, global hotkey) sit behind `sys.platform` seams for a
future Linux backend.

## Requirements

- Windows, a webcam, and [uv](https://docs.astral.sh/uv/).
- Dependencies (OpenCV, MediaPipe) are managed by uv; no manual venv activation.

## Usage

Run from this directory (where `pyproject.toml` lives) so uv picks up the project
environment:

```powershell
uv run camcontrol start      # launch the background daemon (disarmed; camera off)
uv run camcontrol gui        # fullscreen calibrate + live-preview window
uv run camcontrol calibrate  # headless 4-corner calibration (TOP-LEFT -> TR -> BL -> BR)
uv run camcontrol status     # daemon state
uv run camcontrol stop       # shut the daemon down
uv run camcontrol run        # run the daemon in the foreground (debug; logs to stdout)
```

Press the toggle hotkey (default `Ctrl+Alt+H`) to arm/disarm. Config and
calibration live under `~/.camcontrol/`.

## Development

```powershell
uv run pytest
```
