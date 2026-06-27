# System architecture

## The digital twin concept

In a traditional mobile robot deployment, path planning and obstacle avoidance run onboard. For budget robots with limited CPUs, this is not feasible since Nav2 alone requires significant processing power. The solution is to offload computation to a **digital twin** running on a cloud server.

The digital twin is a cloud-side replica of the robot's navigation intelligence. It receives sensor data from the physical robot, processes it using Nav2 and the navigation logic layer, and sends back velocity commands. The robot itself becomes a thin client: it only runs sensors, motor drivers, and a lightweight safety controller.

```
┌──────────────────────────────────────────────────────────┐
│                     CLOUD SERVER                         │
│                                                          │
│  ┌─────────────┐   ┌──────────┐   ┌───────────────────┐  │
│  │  Nav2 Stack │   │ Costmap  │   │  Navigation Logic │  │
│  │  (Planner + │◄──┤ (static  │◄──┤  Layer            │  │
│  │   DWB)      │   │  + crowd)│   │  (crowd_monitor)  │  │
│  └──────┬──────┘   └──────────┘   └───────────────────┘  │
│         │                                ▲               │
│    /cmd_vel                       /people_positions      │
│         │                                │               │
│  ═══════╪════════════════════════════════╪═══════════════│
│         │         5G Network             │               │
│  ═══════╪════════════════════════════════╪═══════════════│
│         ▼                                │               │
│  ┌──────────────────────────────────────────────────┐    │
│  │              PHYSICAL ROBOT                      │    │
│  │  Motors ◄── Safety Controller ◄── /cmd_vel       │    │
│  │  Lidar  ──► /scan ──────────────────────────────►│    │
│  │  Odometry ► /odom ──────────────────────────────►│    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │  Hospital cameras ──► /people_positions          │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

In our proof-of-concept, Gazebo Classic replaces the physical robot and 5G network. The `robot_simulation` package provides the simulated environment, while `digital_twin` provides the cloud intelligence.

---

## The feedback loop (Boucle de Rétroaction)

The system operates as a continuous closed-loop control system. The digital twin does not simply plan once — it continuously replans as the environment changes.

### Loop steps

```
1. SENSE    Robot sensors produce /odom, /scan, /people_positions
      │
      ▼
2. PERCEIVE crowd_monitor builds a density map of moving humans
      │
      ▼
3. FUSE     crowd_monitor overlays crowd walls onto the static /map
            → publishes /map_dynamic (updated at 2 Hz)
      │
      ▼
4. PLAN     Nav2 global costmap reads /map_dynamic
            Nav2 global planner computes a new path avoiding crowd zones
            Nav2 local planner (DWB) generates velocity commands
      │
      ▼
5. ACT      /cmd_vel → relay → /bcr_bot/cmd_vel → robot moves
      │
      ▼
6. FEEDBACK Robot's new position changes /odom
            Humans continue to move → new /people_positions
            → Loop restarts at step 1
```

### What makes this "Predictive"

Traditional obstacle avoidance is reactive: the robot detects an obstacle in its lidar scan and stops or swerves. Our approach is **predictive** because:

- The crowd monitor tracks humans that are **not in the lidar's field of view**. It uses Gazebo's global model state (simulating what would be camera networks or IoT sensors in a real deployment) to know where people are across the entire map.
- The dynamic map overlay creates **virtual walls** around crowd zones. Nav2 sees these as physical obstacles and plans a global path that avoids the entire corridor — not just the person directly ahead.
- The Gaussian density field creates a **graduated cost zone**: cells near a person become lethal (cost 100), while cells farther away have elevated cost. This causes Nav2 to prefer paths that keep maximum distance from crowds.

The result: the robot chooses an alternative corridor **before** it would have encountered the crowd, rather than stopping in front of people and waiting.

---

## ROS2 topic flow

The following diagram shows all topics and how they connect the nodes:

```
                        ┌──────────────────────┐
                        │   Foxglove (RP2)     │
                        │   Browser UI         │
                        └──┬───────────────┬───┘
                           │               │
               /goal_pose_foxglove    /room_command
                           │               │
                           ▼               ▼
                     ┌───────────┐   ┌──────────────┐   ┌──────────────┐
                     │goal_relay │   │room_interpret│  │ speech_node  │
                     └─────┬─────┘   └──────┬───────┘   └──────┬───────┘
                           │                │                  │
                       /goal_pose      /goal_pose        /room_command
                           │                │          (transcribed text)
                           ▼                ▼                  │
                     ┌──────────────────────────┐              │
                     │         Nav2             │◄─────────────┘
                     │  (planner + controller)  │
                     └──────────┬───────────────┘
                                │
                            /cmd_vel
                                │
                        ┌───────┴────────┐
                        │  cmd_vel_relay │
                        └───────┬────────┘
                                │
                         /bcr_bot/cmd_vel
                                │
                                ▼
                     ┌──────────────────┐
                     │  bcr_bot (Gazebo)│──► /bcr_bot/odom
                     │                  │──► /bcr_bot/scan
                     └──────────────────┘

    ┌─────────────────┐         ┌──────────────┐
    │obstacle_spawner │────────►│ crowd_monitor│
    │ (Gazebo models) │         │              │
    └─────────────────┘         └──────┬───────┘
           │                           │
    /people_positions           /map_dynamic ──► Nav2 global_costmap
    (PoseArray)                 /crowd_density ──► Foxglove (visualisation)
                                       ▲
                                       │
                                 /map (static)
                                       │
                                ┌──────┴───────┐
                                │  map_server  │
                                └──────────────┘
```

---

## Package structure

### robot_simulation

Represents the physical world. In a real deployment, this is replaced by the actual robot and environment.

```
robot_simulation/
├── worlds/
│   ├── hospital.world          # Gazebo Classic SDF world
│   └── corridors.world         # Alternative smaller world
├── models/
│   └── Scrubs/                 # Human person model for spawning
├── maps/                       # Pre-generated SLAM maps
│   ├── hospital_map.yaml / corridors_map.yaml
│   └── hospital_map.pgm / corridors_map.pgm
└── scripts/
    └── obstacle_spawner.py     # Spawns/moves human models in Gazebo
```

**Key executable:**

```bash
ros2 run robot_simulation obstacle_spawner.py --ros-args -p scenario:=hospital
```

### digital_twin

The cloud-side intelligence includes everything the robot cannot run onboard

```
digital_twin/
├── config/
│   ├── nav2_params.yaml        # Nav2 planner/controller/costmap configuration
│   ├── logic_params.yaml      # Navigation logic layer parameters (crowd, speech, rooms)
│   └── room_registry.yaml      # Room name → map coordinate mapping
├── maps/
│   ├── hospital_map.yaml       # Static map loaded by map_server
│   └── hospital_map.pgm
├── launch/
│   ├── hospital.launch.py      # Base stack: Gazebo + Nav2 + Foxglove + obstacle spawner
│   └── logic.launch.py         # Navigation logic layer: crowd_monitor + room_interpreter + speech_node
├── digital_twin/
│   ├── crowd_monitor.py        # Dynamic map overlay for Nav2 replanning
│   ├── room_interpreter.py     # Text command → Nav2 goal pose
│   ├── speech_node.py          # Mic recording + Whisper transcription
│   └── goal_relay.py           # Foxglove timestamp fix for goal poses
└── setup.py                    # Entry points for all executables
```

**Key executables:**

```bash
ros2 launch digital_twin hospital.launch.py     # Base stack
ros2 launch digital_twin logic.launch.py         # Navigation logic layer
```

---

## Nav2 integration

Nav2 is the robot's navigation engine. It runs entirely on the digital twin (cloud side) because it is too computationally heavy for a budget robot.

### Costmap architecture

Nav2 uses a layered costmap to decide where the robot can go:

```
┌─────────────────────────────────────┐
│         Global Costmap              │
│                                     │
│  ┌───────────────────────────────┐  │
│  │ Static Layer                  │  │
│  │ subscribes to: /map_dynamic   │  │  ◄── crowd_monitor publishes here
│  │ (instead of default /map)     │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │ Obstacle Layer                │  │
│  │ subscribes to: /bcr_bot/scan  │  │  ◄── lidar data from robot
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │ Inflation Layer               │  │
│  │ inflates around lethal cells  │  │  ◄── safety margin around obstacles
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

The critical configuration change: the `static_layer` subscribes to `/map_dynamic` (published by `crowd_monitor` at 2 Hz) instead of the default `/map` (published once by `map_server`). This is what enables real-time replanning around crowds.

In `nav2_params.yaml`:

```yaml
global_costmap:
  global_costmap:
    ros__parameters:
      static_layer:
        plugin: "nav2_costmap_2d::StaticLayer"
        map_subscribe_transient_local: True
        map_topic: "/map_dynamic"
```

### cmd_vel relay

bcr_bot uses namespaced topics (`/bcr_bot/cmd_vel`), but Nav2 publishes to `/cmd_vel`. A relay bridges them:

```
Nav2 → /cmd_vel → [relay node] → /bcr_bot/cmd_vel → robot motors
```

### Goal relay

Foxglove publishes goal poses with wall-clock timestamps, but Nav2 expects sim-time stamps. The `goal_relay` node resets the timestamp to zero so Nav2 accepts the goal:

```
Foxglove → /goal_pose_foxglove → [goal_relay] → /goal_pose → Nav2
```
