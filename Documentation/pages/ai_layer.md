# AI intelligence layer

The AI intelligence layer adds smart navigation capabilities on top of Nav2. It consists of three ROS2 nodes and a Foxglove extension panel, all launched together via `logic.launch.py`.

---

## Overview

```
┌───────────────────────────────────────────────────────────────────┐
│                    AI Intelligence Layer                          │
│                                                                   │
│  ┌────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│  │ crowd_monitor  │  │ room_interpreter │  │   speech_node    │   │
│  │                │  │                  │  │                  │   │
│  │ /people_posit. │  │ /room_command    │  │ /speech_trigger  │   │ 
│  │      ↓         │  │      ↓           │  │      ↓           │   │
│  │ Gaussian       │  │ YAML lookup      │  │ Mic recording    │   │
│  │ density        │  │      ↓           │  │      ↓           │   │
│  │      ↓         │  │ /goal_pose       │  │ Whisper STT      │   │
│  │ /map_dynamic   │  │   → Nav2         │  │      ↓           │   │
│  │ /crowd_density │  │                  │  │ /room_command    │   │
│  │   → Nav2       │  │ /room_command_   │  │ /speech_status   │   │
│  │   → Foxglove   │  │    feedback      │  │   → Foxglove     │   │
│  └────────────────┘  └──────────────────┘  └──────────────────┘   │
└───────────────────────────────────────────────────────────────────┘
```

---

## crowd_monitor.py : Dynamic obstacle avoidance

### Purpose

Makes Nav2 replan around corridors blocked by moving humans. Without this node, Nav2 only sees the static hospital map and obstacles in the lidar's direct line of sight. The crowd monitor gives Nav2 a "bird's eye view" of all human positions across the entire map.

### How it works

```
/map (static, from map_server)
  +
/people_positions (PoseArray, from obstacle_spawner at ~10 Hz)
  │
  ▼
┌──────────────────────────────────────┐
│          crowd_monitor               │
│                                      │
│  1. Cache the static map (501×1127)  │
│  2. For each human position:         │
│     - Compute a 2D Gaussian blob     │
│       (sigma = 0.80m, 3σ radius)     │
│     - Peak value = density_scale     │
│  3. Sum all Gaussians → density grid │
│  4. Scale to 0-100                   │
│  5. Where density ≥ threshold → 100  │
│     (= occupied wall in OccGrid)     │
│  6. Overlay onto static map copy     │
│                                      │
│  Publish at 2 Hz:                    │
│  /map_dynamic  → Nav2 replanning     │
│  /crowd_density → Foxglove display   │
└──────────────────────────────────────┘
```

### Gaussian density field

For each human at position (x, y), the node computes a 2D Gaussian:

```
density(r, c) = exp( -((r - row)² + (c - col)²) / (2 × σ_px²) )
```

where `σ_px = gaussian_sigma / map_resolution`. With `sigma = 0.80m` and `resolution = 0.05m/px`, the 3σ influence radius extends approximately 48 pixels (2.4m) from each person's centre.

Cells where the scaled density exceeds `lethal_threshold` are marked as **occupied (value 100)** in the OccupancyGrid, identical to a wall. Nav2's costmap treats them as impassable, forcing a global replan through an alternative corridor.

### Tuning the wall size

The `lethal_threshold` parameter controls how far from each person the virtual wall extends:

Approximate wall radius with the current `gaussian_sigma: 0.80` and `density_scale: 30.0`:

| lethal_threshold | Approximate wall radius |
| ---------------- | ----------------------- |
| 25               | ~0.5 m                  |
| 15               | ~0.9 m                  |
| 10               | ~1.2 m                  |

A lower threshold creates larger exclusion zones, making Nav2 more conservative.

### Parameters (in logic_params.yaml)

```yaml
crowd_monitor:
  ros__parameters:
    publish_rate: 2.0           # Hz
    gaussian_sigma: 0.80        # metres
    density_scale: 30.0         # peak value at person centre
    lethal_threshold: 25        # cells above this → wall
```

### Topics

| Topic             | Type          | Direction | Description                           |
| ----------------- | ------------- | --------- | ------------------------------------- |
| /map              | OccupancyGrid | Subscribe | Static map from map_server            |
| /people_positions | PoseArray     | Subscribe | Human positions from obstacle_spawner |
| /map_dynamic      | OccupancyGrid | Publish   | Static map + crowd walls (→ Nav2)    |
| /crowd_density    | OccupancyGrid | Publish   | Density-only overlay (→ Foxglove)    |

---

## room_interpreter.py : Natural language destination commands

### Purpose

Translates human-readable room names into Nav2 navigation goals. Instead of manually clicking a goal on the map, the user can type "go to urgences" or "salle 101" and the robot navigates there.

### How it works

```
/room_command ("Go to urgences")
  │
  ▼
┌──────────────────────────────────────────┐
│           room_interpreter               │
│                                          │
│  1. Strip command prefixes:              │
│     "Go to", "Navigate to", "Aller à"    │
│  2. Remove articles: "the", "la", "le"   │
│  3. Search room_registry.yaml:           │
│     - Exact alias match                  │
│     - Substring match                    │
│     - Partial word overlap               │
│  4. Look up (x, y, orientation)          │
│  5. Publish PoseStamped on /goal_pose    │
│                                          │
│  Feedback → /room_command_feedback       │
└──────────────────────────────────────────┘
```

### Room registry format (room_registry.yaml)

```yaml
rooms:
  urgences:
    display_name: "Urgences"
    x: 5.2
    y: -12.8
    orientation_z: 0.0
    orientation_w: 1.0
    aliases:
      - "urgences"
      - "emergency"
      - "er"
      - "salle urgences"

  salle_101:
    display_name: "Salle 101"
    x: 3.0
    y: 0.0
    orientation_z: 0.0
    orientation_w: 1.0
    aliases:
      - "salle 101"
      - "room 101"
      - "101"
```

### Supported command patterns

The parser handles both English and French commands:

- "Go to urgences"
- "Navigate to room 204"
- "Aller à la salle 101"
- "Va à urgences"
- "urgences" (just the room name)

### Topics

| Topic                  | Type        | Direction | Description                                     |
| ---------------------- | ----------- | --------- | ----------------------------------------------- |
| /room_command          | String      | Subscribe | Text command from Foxglove panel or speech_node |
| /goal_pose             | PoseStamped | Publish   | Navigation goal for Nav2                        |
| /room_command_feedback | String      | Publish   | Status text for Foxglove panel                  |

---

## speech_node.py : Voice command processing

### Purpose

Enables voice control of the robot. Since the Foxglove extension panel runs in a sandboxed environment that blocks microphone access, the speech processing happens on the Ubuntu machine where the microphone is physically connected.

### How it works

```
Foxglove panel                         Digital twin computer
┌────────────┐                        ┌────────────────────────┐
│ Click 🎤   │── /speech_trigger ──►  │     speech_node        │
│            │   ("fr" or "en")       │                        │
│            │                        │  1. Start recording    │
│ "Recording"│◄─ /speech_status ────  │     (device_index: 5)  │
│            │   ("recording")        │                        │
│            │                        │  2. Silence detection  │
│            │                        │     (1.5s threshold)   │
│"Transcrib."│◄─ /speech_status ────  │                        │
│            │   ("transcribing")     │  3. Whisper transcribe │
│            │                        │     (faster-whisper,   │
│ "Aller à"  │◄─ /speech_status ────  │      base model)       │
│            │   ("heard:aller à")    │                        │
│            │                        │  4. Publish text       │
│            │                        │     → /room_command    │
└────────────┘                        └────────────────────────┘
```

### Recording strategy

- Records in 100 ms chunks from the specified audio input device
- Monitors RMS amplitude of each chunk
- Stops recording after `silence_duration` seconds of consecutive silence (RMS below `silence_threshold`), but only if some speech was detected first
- Maximum recording length: `max_duration` seconds

### Audio device selection

The Ubuntu machine may have multiple audio inputs. Use this to identify the correct one:

```bash
python3 -c "import sounddevice; print(sounddevice.query_devices())"
```

Then test each input device:

```bash
python3 -c "
import sounddevice as sd
import numpy as np
audio = sd.rec(int(3 * 16000), samplerate=16000, channels=1, dtype='float32', device=5)
print('Speak now...')
sd.wait()
print(f'RMS: {np.sqrt(np.mean(audio**2)):.6f}')
"
```

Set `device_index` in `logic_params.yaml` to the device that shows non-zero RMS when you speak.

### Parameters

```yaml
speech_node:
  ros__parameters:
    model_size: "base"            # Whisper model: tiny, base, small, medium
    default_language: "fr"         # Fallback if trigger has no language
    sample_rate: 16000
    max_duration: 8.0              # Max recording time (seconds)
    silence_threshold: 0.005       # RMS below this = silence
    silence_duration: 1.5          # Seconds of silence to stop recording
    device_index: 5                # Audio input device (-1 = system default)
```

### Topics

| Topic           | Type   | Direction | Description                                                                           |
| --------------- | ------ | --------- | ------------------------------------------------------------------------------------- |
| /speech_trigger | String | Subscribe | Language code ("fr"/"en") from Foxglove panel                                         |
| /room_command   | String | Publish   | Transcribed text → room_interpreter                                                  |
| /speech_status  | String | Publish   | UI state: "ready", "recording", "transcribing", "heard:...", "no_speech", "error:..." |

---

## Foxglove Room command panel

### Purpose

A custom Foxglove extension panel that provides a user interface for sending room commands. It connects the Foxglove browser UI to the ROS2 nodes running on the digital twin's computer.

### Features

- **Text input** : type a room command and press Enter or click Send
- **Voice input** : click the 🎤 button to trigger recording on the Ubuntu microphone via the speech_node
- **Language toggle** : switch between French and English for speech recognition
- **Feedback display** : shows navigation status (green) or errors (red) from room_interpreter

### Building the extension

```bash
cd ~/Documents/CloudTwin/Foxglove/foxglove_panels/room-command-panel
npm install
npm install --save-dev @foxglove/extension
npm run package
```

This produces a `.foxe` file. Transfer it to the computer running Foxglove and install via Foxglove → Extensions → Install local extension.

### Panel communication

```
┌─────────────────────────────────────────────────────┐
│              Foxglove panel (browser)               │
│                                                     │
│  [Text Input] ──► publishes /room_command           │
│  [🎤 Button]  ──► publishes /speech_trigger         │
│                                                     │
│  subscribes /room_command_feedback ──► [Feedback]   │
│  subscribes /speech_status ──► [Recording status]   │
└─────────────────────────────────────────────────────┘
```
