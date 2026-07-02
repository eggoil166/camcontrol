# camcontrol

Streams head-tracking events over a local TCP port. A webcam + MediaPipe track
your head; for each frame the server pushes a JSON line with the raw and
filtered (yaw, pitch) plus an estimated normalized screen position `[0,1]²`
derived from a 4-corner calibration. Cross-platform (Linux, macOS, Windows) —
pure sockets, OpenCV, and MediaPipe; no OS-specific code.

## Requirements

- A webcam and [uv](https://docs.astral.sh/uv/).
- Dependencies (OpenCV, MediaPipe) are managed by uv; no manual venv activation.

## Usage

Run from this directory (where `pyproject.toml` lives) so uv picks up the project
environment:

```bash
uv run camcontrol calibrate            # 4-corner calibration (look at each, press ENTER)
uv run camcontrol serve                # stream events on 127.0.0.1:8765
uv run camcontrol serve --port 9000 --host 0.0.0.0 --camera 1
```

Connect any TCP client to read the stream, e.g.:

```bash
nc 127.0.0.1 8765
```

Each line is one event:

```json
{"t": 1719500000.123, "detected": true,
 "raw": {"yaw": -4.2, "pitch": 3.1},
 "filtered": {"yaw": -3.9, "pitch": 3.0},
 "screen": {"x": 0.42, "y": 0.58}}
```

`screen` is normalized `[0,1]²` (top-left origin); multiply by your resolution
for pixels. Frames with no face detected emit `{"t", "detected": false}` only.
Calibration is stored under `~/.camcontrol/calibration.json`; without it, serve
falls back to a rough placeholder mapping.

## Development

```bash
uv run pytest
```
