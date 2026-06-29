# Foxglove user interface

## Edge / fog computing architecture

The system is designed around an edge/fog computing model. The simulation (or in a real deployment, the physical robot and its sensors) runs **on-site** as the edge layer. The digital twin processes navigation intelligence locally or on a nearby fog server. Foxglove acts as a **remote supervision panel (RP2)** that can be accessed from any computer, either on the same machine, on the local network, or remotely over the cloud via an API.

This architecture means that:

- The edge (robot + environment sensors) produces raw data on-site
- The fog/cloud (digital twin) processes that data and computes navigation commands
- The RP2 (Foxglove) allows a human operator to monitor, visualise, and send commands from anywhere, all that is needed is the IP address of the machine running the digital twin

```
┌──────────────────────────────┐
│  Edge / On-site              │
│  Gazebo (or real robot)      │
│  Sensors, motors, lidar      │
└──────────┬───────────────────┘
           │ ROS2 topics
           ▼
┌──────────────────────────────┐
│  Fog / Cloud                 │
│  Digital twin (Nav2, AI)     │
│  Foxglove bridge :8765       │
└──────────┬───────────────────┘
           │ WebSocket
           ▼
┌──────────────────────────────┐
│  RP2 — Remote panel          │
│  Foxglove (any browser)      │
│  ws://<ip>:8765              │
└──────────────────────────────┘
```

---

## Connection setup

1. Open [https://app.foxglove.dev](https://app.foxglove.dev) in a browser (Chrome recommended)
2. Select **Open connection** → **Foxglove WebSocket**
3. Enter `ws://<ip>:8765` — use `localhost` if running on the same machine, or the IP address of the computer running the digital twin if accessing remotely
4. The Foxglove bridge runs on port 8765, started automatically by `hospital.launch.py`

---

## Installing the layout

A pre-configured layout is saved in the project repository:

```
Foxglove/foxglove_layout/CloudTwin.json
```

To load it: in Foxglove, click **Layout** (top-left) → **Import layout** → select `CloudTwin.json`.

---

## Installing the room command panel

The custom Foxglove extension for voice/text room commands is in:

```
Foxglove/foxglove_panels/room-command-panel/
```

Pre-built `.foxe` files are available in that directory. To install:

1. Transfer the `.foxe` file to the computer running Foxglove (if different from the build machine)
2. In Foxglove → **Profile icon** → **Extensions** → **Install local extension**
3. Select the `.foxe` file

> Please use teh latest version of the .foxe file. To this date the latets version is `vasileiosfilipposskarleas.room-command-panel-2.0.0`

To rebuild from source:

```bash
cd ~/Documents/CloudTwin/Foxglove/foxglove_panels/room-command-panel
npm install
npm install --save-dev @foxglove/extension
npm run package
```

---

## Layout structure

The layout is split into two main areas: a **3D map panel** on the left (50% width), and a **tabbed panel** on the right with three tabs.

```
┌──────────────────────┬──────────────────────┐
│                      │  [Navigation] [Debug]│
│                      │  [Teleop]            │
│     3D map panel     ├──────────────────────┤
│                      │                      │
│  - Hospital map      │  Tab content varies  │
│  - Robot position    │  (see below)         │
│  - Planned path      │                      │
│  - Crowd density     │                      │
│  - People positions  │                      │
│                      │                      │
└──────────────────────┴──────────────────────┘
```

---

## 3D map panel (left side)

The main visualisation panel. Fixed frame is `map`, follow mode is `follow-pose`.

### Visible topics

| Topic                               | Type                      | What it shows                                            |
| ----------------------------------- | ------------------------- | -------------------------------------------------------- |
| `/map`                            | OccupancyGrid             | Static hospital map (dark blue walls, red obstacles)     |
| `/people_positions`               | PoseArray                 | Green arrows showing current human positions             |
| `/crowd_density`                  | OccupancyGrid             | Turquoise overlay showing Gaussian density around people |
| `/plan`                           | Path                      | Nav2 global planned path                                 |
| `/plan_smoothed`                  | Path                      | Smoothed version of the global plan                      |
| `/local_plan`                     | Path                      | Nav2 local planner trajectory                            |
| `/received_global_plan`           | Path                      | Path received by the local planner                       |
| `/global_costmap/costmap_updates` | OccupancyGrid             | Global costmap incremental updates                       |
| `/local_costmap/costmap_updates`  | OccupancyGrid             | Local costmap updates                                    |
| `/cost_cloud`                     | PointCloud2               | DWB cost evaluation point cloud                          |
| `/robot_description`              | RobotModel                | bcr_bot 3D model                                         |
| `/initialpose`                    | PoseWithCovarianceStamped | Initial pose estimate                                    |

### Hidden topics (available for debug)

| Topic                        | Why hidden                                                                         |
| ---------------------------- | ---------------------------------------------------------------------------------- |
| `/map_dynamic`             | Same as`/map` but with crowd walls — redundant with `/crowd_density` visually |
| `/bcr_bot/scan`            | Lidar scan — clutters the view                                                    |
| `/global_costmap/costmap`  | Full costmap — heavy to render, use updates instead                               |
| `/local_costmap/costmap`   | Same reason                                                                        |
| `/bcr_bot/kinect_camera/*` | Camera feeds shown in the Teleop tab instead                                       |

### Publishing goals

The 3D panel is configured to publish **pose goals** on `/goal_pose_foxglove` when you click on the map. The `goal_relay` node forwards these to Nav2's `/goal_pose` with corrected timestamps.

To send a goal: select the **Publish pose** tool in the 3D panel toolbar, then click and drag on the map to set position and orientation.

---

## Navigation tab

The primary operational tab. Contains the room command panel and real-time telemetry plots.

```
┌──────────────────────────────────┐
│     Room command panel           │  ← Text/voice destination commands
│  [Text input] [Send] [🎤]        │
│  [Language toggle] [Feedback]    │
├──────────────────────────────────┤
│  /bcr_bot/cmd_vel (linear)       │  ← Linear velocity plot (x, y, z)
├──────────────────────────────────┤
│  /bcr_bot/cmd_vel (angular)      │  ← Angular velocity plot (x, y, z)
├──────────────────────────────────┤
│  /bcr_bot/imu angular velocity   │  ← IMU angular velocity (gyroscope)
├──────────────────────────────────┤
│  /bcr_bot/imu linear accel.      │  ← IMU linear acceleration
└──────────────────────────────────┘
```

### Room command panel

The custom extension that allows sending navigation commands:

- **Type** a room name (e.g., "Go to urgences", "Salle 101") and press Enter
- **Click 🎤** to trigger voice recording on the microphone connected to the digital twin's computer (requires `speech_node` running via `logic.launch.py`)
- **Language toggle** switches between French (default) and English for speech recognition
- **Feedback area** shows green for "Navigating to..." or red for "Room not found"

### Telemetry plots

Four real-time plots showing:

- **cmd_vel linear** (x, y, z) : the velocity commands Nav2 sends to the robot
- **cmd_vel angular** (x, y, z) : the rotation commands
- **IMU angular velocity** : what the robot's gyroscope actually measures
- **IMU linear acceleration** : accelerometer readings (gravity visible on z-axis)

Comparing cmd_vel (commanded) vs IMU (measured) helps verify the robot is executing commands correctly.

---

## Debug tab

For troubleshooting and manual testing.

```
┌──────────────────┬──────────────────┐
│  Publish panel   │  Diagnostics     │
│  /goal_pose_     │  summary         │
│   foxglove       │                  │
├──────────────────┴──────────────────┤
│           ROS logs                  │
├──────────────────┬──────────────────┤
│  Raw messages    │  Markdown        │
│  /goal_pose_     │  (launch         │
│   foxglove       │   instructions)  │
└──────────────────┴──────────────────┘
```

- **Publish panel** — manually publish a PoseStamped goal on `/goal_pose_foxglove` with specific coordinates
- **Diagnostics** — Nav2 diagnostic messages (planner status, controller status)
- **ROS logs** — live log output from all running nodes (filtered to INFO and above)
- **Raw messages** — inspect the raw content of `/goal_pose_foxglove` messages
- **Markdown** — quick-reference launch instructions

---

## Teleop tab

For manual robot control and camera monitoring.

```
┌──────────────────┬──────────────────┐
│  Depth camera    │  Teleop joystick │
│  /bcr_bot/       │  publishes to    │
│  kinect_camera/  │  /bcr_bot/       │
│  depth/image_raw │  cmd_vel         │
├──────────────────┼──────────────────┤
│  RGB camera      │  Transform tree  │
│  /bcr_bot/       │  TF hierarchy    │
│  kinect_camera/  │  visualisation   │
│  image_raw       │                  │
└──────────────────┴──────────────────┘
```

- **Depth camera** — raw depth image from the Kinect-style sensor
- **RGB camera** — colour camera feed from the robot
- **Teleop joystick** — arrow-key style controls publishing directly to `/bcr_bot/cmd_vel` (bypasses Nav2 for manual driving)
- **Transform tree** — visual hierarchy of all TF frames (map → odom → base_footprint → wheels, sensors, etc.)

---

## Project file structure

```
Foxglove/
├── foxglove_layout/
│   └── DRYVbot.json          # Foxglove layout configuration
└── foxglove_panels/
    └── room-command-panel/
        ├── src/
        │   ├── index.ts              # Extension entry point
        │   └── RoomCommandPanel.ts   # Panel UI + logic
        ├── package.json
        └── *.foxe                    # Built extension files (versioned)
```
