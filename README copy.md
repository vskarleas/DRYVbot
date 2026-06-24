# CloudTwin : Digital Twin pour la navigation autonome et prédictive d'un robot mobile

## Description

This project is a proof-of-concept for a Digital Twin application applied to mobile robotics. The core idea is that budget robots with limited onboard processing power offload heavy computation (trajectory planning, dynamic obstacle avoidance, predictive navigation) to their digital twin running on a cloud server — in our case, the local computer.

The digital twin receives real-time data from the robot and the environment, computes the optimal path, and sends back motion commands. This creates a closed-loop feedback system (boucle de rétroaction) detailed in [Documentation/pages/architecture.md](Documentation/pages/architecture.md).

Since we do not have a physical robot, Gazebo Classic 11 simulates the robot navigating a hospital environment. The simulation represents what would be a real robot connected via a 5G local network to the cloud.

> For the full system architecture, feedback loop, and data flow diagrams, see **[Documentation/pages/architecture.md](Documentation/pages/architecture.md)**
>
> For the AI intelligence layer (crowd avoidance, room commands, voice control), see **[Documentation/pages/ai_layer.md](Documentation/pages/ai_layer.md)**
>
> For the Foxglove user interface (layout, panels, topic visualisation), see **[Documentation/pages/foxglove.md](Documentation/pages/foxglove.md)**
>
> For known issues and their solutions, see **[Documentation/pages/troubleshooting.md](Documentation/pages/troubleshooting.md)**

---

## Architecture overview

The project is organised in the following ROS2 packages:

- **`robot_simulation`** : World files (.world), saved maps, and the obstacle spawner that injects dynamic human models into the simulation. In a real deployment, this package would be replaced by the physical robot and its sensors.
- **`digital_twin`** : The core of the project. Cloud-side intelligence that the robot cannot run onboard. Contains Nav2 configuration, hospital map, launch files, and the AI intelligence layer (crowd monitor, room interpreter, speech node).
- **`bcr_bot`** : The simulated robot. A differential drive robot with 2D lidar, camera, and IMU. Used in Gazebo Classic mode.

## Technologies

| Component     | Technology               | Role                                     |
| ------------- | ------------------------ | ---------------------------------------- |
| Framework     | ROS2 Humble              | Robotics middleware                      |
| Simulation    | Gazebo Classic 11        | Robot and environment simulation         |
| Robot         | bcr_bot                  | Differential drive with lidar and camera |
| Navigation    | Nav2 (DWB local planner) | Path planning and obstacle avoidance     |
| Mapping       | slam_toolbox             | SLAM for map generation                  |
| Visualisation | Foxglove (web)           | Real-time monitoring and user interface  |
| Speech        | faster-whisper           | Local speech-to-text for voice commands  |
| Perception    | OpenCV                   | Crowd density computation                |

---

## Installation

### Prerequisites

- Ubuntu 22.04
- ROS2 Humble ([installation guide](https://foxglove.dev/blog/installing-ros2-humble-on-ubuntu))

### System packages

```bash
# Gazebo Classic 11 + ROS2 bridge
sudo apt install ros-humble-gazebo-ros-pkgs ros-humble-gazebo-ros

# Navigation and SLAM
sudo apt install ros-humble-navigation2 \
                 ros-humble-nav2-bringup \
                 ros-humble-slam-toolbox

# Foxglove bridge
sudo apt install ros-humble-foxglove-bridge

# ROS2 tools
sudo apt install python3-colcon-common-extensions \
                 ros-humble-teleop-twist-keyboard \
                 ros-humble-topic-tools \
                 ros-humble-tf2-ros

# Audio (for speech node)
sudo apt install libportaudio2 portaudio19-dev
```

> **Note:** Gazebo Classic and Gazebo Harmonic (gz-tools2) cannot coexist. If Harmonic is installed, remove it first: `sudo apt remove gz-harmonic gz-tools2 ros-humble-ros-gzharmonic*`

### Python dependencies

```bash
pip install faster-whisper sounddevice numpy pyyaml websockets --break-system-packages

```

### Clone and build

```bash
git clone https://github.com/vskarleas/CloudTwin
cd CloudTwin/Code
```

If `bcr_bot` is not already in `src/`:

```bash
cd src
git clone https://github.com/blackcoffeerobotics/bcr_bot.git
cd ..
```

Install ROS dependencies:

```bash
sudo apt install python3-rosdep
sudo rosdep init   # skip if already initialised
rosdep update
rosdep install --from-paths src --ignore-src -r -y
```

> Xacro needs to be installed for this repo. Check the installation process depending on your system.

Build:

```bash
cd ~/Documents/CloudTwin/Code
colcon build
source install/setup.bash
```

Add to `~/.bashrc` if not already there:

```bash
source /opt/ros/humble/setup.bash
```

---

## Launching the system

### Full simulation

Starts Gazebo with the hospital world, bcr_bot, Nav2 navigation, obstacle
spawner, digital twin logic, RViz, cmd_vel relay, initial pose publisher, and
Foxglove bridge:

```bash
cd ~/Documents/CloudTwin/Code
source install/setup.bash
ros2 launch digital_twin simulation.launch.py \
  obstacle_mode:=random \
  random_obstacle_scenario:=normal
```

Wait approximately 30 seconds for everything to initialise.

The launch argument is still named `random_obstacle_scenario` for compatibility,
but the current human scenarios are deterministic and controlled.

### Obstacle modes

The default obstacle mode remains `fixed` for backward compatibility.

- `obstacle_mode:=fixed` launches the original `obstacle_spawner.py`.
- `obstacle_mode:=random` launches the controlled moving-human spawner.
- `obstacle_mode:=disabled` launches the simulation without obstacles.
- `enable_obstacles:=false` also disables obstacle spawning.

For controlled moving humans, use:

```bash
ros2 launch digital_twin simulation.launch.py \
  obstacle_mode:=random \
  random_obstacle_scenario:=normal
```

```bash
ros2 launch digital_twin simulation.launch.py \
  obstacle_mode:=random \
  random_obstacle_scenario:=crowd
```

```bash
ros2 launch digital_twin simulation.launch.py \
  obstacle_mode:=random \
  random_obstacle_scenario:=emergency
```

Available controlled scenarios are:

- `normal`: 10 humans follow predefined patrol loops through the hospital.
- `crowd`: 18 humans follow predefined patrol loops with wider coverage.
- `emergency`: 8 humans follow fixed emergency routes. After
  `emergency_start_time` seconds, they move to a separated gathering area. The
  return phase begins after `emergency_duration` seconds, and a new emergency
  can start after complete dispersal when `emergency_loop` is enabled.

The controlled spawner parameters are in
`robot_simulation/config/random_obstacles_params.yaml`. This file configures the
map, wall/robot/person safety distances, Gazebo update rate, spawn timeout, and
emergency timing. It no longer generates random trajectories.

The spawner publishes `/people_positions` for the crowd monitor and
`/people_markers` for RViz. The full simulation remaps the enabled Nav2
`MarkerArray` display to `/people_markers`, showing each person as a small
coloured circle.

The standalone spawner command, with Gazebo already running, is:

```bash
ros2 run robot_simulation random_obstacle_spawner.py --ros-args \
  --params-file $(ros2 pkg prefix robot_simulation)/share/robot_simulation/config/random_obstacles_params.yaml \
  -p scenario:=normal
```

### Separate base stack

If you only want Gazebo, bcr_bot, Nav2, the obstacle mode selected in
`hospital.launch.py`, and Foxglove bridge, launch:

```bash
cd ~/Documents/CloudTwin/Code
source install/setup.bash
ros2 launch digital_twin hospital.launch.py
```

### Separate AI intelligence layer

`simulation.launch.py` already includes this layer. Launch it separately only
when using `hospital.launch.py` directly.

Starts the crowd monitor (dynamic map overlay), room interpreter (text commands), and speech node (voice commands):

```bash
cd ~/Documents/CloudTwin/Code
source install/setup.bash
ros2 launch digital_twin logic.launch.py
```

To enable the simulation logger (records departure/arrival data per room command to `simulation_logs/`):

```bash
ros2 launch digital_twin logic.launch.py enable_sim_logger:=true
```

##### Simulation log format

Each simulation run produces a JSON file in `simulation_logs/` named `simulation_<YYYY-MM-DD_HH-MM-SS>.json`. The file contains one record per room command:

```json
{
"simulation_id":"2026-06-18_14-32-10",
"started_at":"2026-06-18T14:32:10.123Z",
"records":[
{
"record_id":1,
"raw_command":"Go to room 101",
"room_id":"salle_101",
"room_display_name":"salle 101",
"target_position":{
"x":-8.1,
"y":-6.62
},
"departure":{
"wall_time":"2026-06-18T14:32:15.456Z",
"sim_time_s":120.345,
"robot_position":{"x":0.0,"y":1.95,"z":0.0}
},
"arrival":{
"wall_time":"2026-06-18T14:32:38.789Z",
"sim_time_s":143.678,
"robot_position":{"x":-8.09,"y":-6.60,"z":0.0}
},
"duration_s":23.333,
"position_error_m":0.0224,
"status":"succeeded",
"feedback":"Navigating to salle 101 (x=-8.1, y=-6.62)"
}
]
}
```

Field descriptions:

* **`target_position`** — theoretical coordinates from `room_registry.yaml`
* **`departure.robot_position`** — where the robot was when the command was received
* **`arrival.robot_position`** — where the robot actually stopped
* **`duration_s`** — simulation time elapsed between departure and arrival
* **`position_error_m`** — Euclidean distance between `target_position` and `arrival.robot_position`, representing the navigation accuracy error
* **`status`** — outcome of the navigation: `succeeded`, `aborted`, `canceled`, `interrupted` (new command received before arrival), or `shutdown` (node stopped mid-navigation)

---

### Websocket for communication to the system via a computer that do not run ROS

The `ws_command_bridge` node runs a WebSocket server on port 9090 (configurable via `ws_port` launch argument). Any computer on the network can connect without ROS being installed. To disable the WebSocket bridge or change its port on the server side:

```bash
ros2 launch digital_twin logic.launch.py enable_ws_bridge:=false
ros2 launch digital_twin logic.launch.py ws_port:=8080
```

**Connection:**
```
ws://<ROS_MACHINE_IP>:9090
```

On connect, the server immediately sends the current navigation state.

#### Client → Server messages

**Send the robot to a room:**
```json
{"type": "room_command", "room": "salle 101"}
```
The `room` field accepts any name or alias from `room_registry.yaml` (e.g. `"room 101"`, `"cuisine"`, `"pharmacy"`, `"charging station"`). The command is validated against the registry before being forwarded to the robot — invalid rooms return an error.

**List available rooms:**
```json
{"type": "list_rooms"}
```

**Query current navigation state:**
```json
{"type": "get_status"}
```

#### Server → Client messages

**Acknowledgement** (sent to the requesting client after a valid room command):
```json
{
  "type": "ack",
  "command": "room_command",
  "room": "salle 101",
  "resolved_room_id": "salle_101",
  "target_position": {"x": -8.1, "y": -6.62}
}
```

**Navigation status** (broadcast to all connected clients on state changes):
```json
{"type": "status", "state": "navigating", "target": "salle_101",
 "target_position": {"x": -8.1, "y": -6.62}}
```
```json
{"type": "status", "state": "arrived", "target": "salle_101",
 "robot_position": {"x": -8.09, "y": -6.60, "z": 0.0},
 "position_error_m": 0.0224, "duration_s": 23.333}
```
```json
{"type": "status", "state": "aborted", "target": "salle_101"}
```
```json
{"type": "status", "state": "idle", "target": null}
```

Possible `state` values: `idle`, `navigating`, `arrived`, `aborted`, `canceled`.

**Feedback** (forwarded from the room interpreter):
```json
{"type": "feedback", "text": "Navigating to salle 101 (x=-8.1, y=-6.62)"}
```

**Room list** (response to `list_rooms`):
```json
{
  "type": "rooms",
  "rooms": {
    "salle_101": {"x": -8.1, "y": -6.62, "aliases": ["room 101", "salle 101", "chambre 101"]},
    "salle_cuisine": {"x": -8.66, "y": -27.77, "aliases": ["cuisine", "salle cuisine", "kitchen"]}
  }
}
```

**Error** (invalid room, malformed message, etc.):
```json
{"type": "error", "message": "Room not found: \"xyz\". Available: [\"salle_101\", ...]"}
```

#### Standalone client

Here is an example of a ready to run client:

```python
import argparse
import asyncio
import json
import sys
 
try:
    import websockets
except ImportError:
    print('Install websockets: pip install websockets')
    sys.exit(1)
 
 
async def main(host: str, port: int):
    uri = f'ws://{host}:{port}'
    print(f'Connecting to {uri} ...')
 
    try:
        async with websockets.connect(uri) as ws:
            print(f'Connected to {uri}')
            print()
            print('Commands:')
            print('  Type a room name or command to send the robot')
            print('  "rooms"   — list available rooms')
            print('  "status"  — query current navigation state')
            print('  "quit"    — disconnect')
            print()
 
            # Task to receive and print server messages
            async def receiver():
                try:
                    async for raw in ws:
                        data = json.loads(raw)
                        msg_type = data.get('type', '')
 
                        if msg_type == 'status':
                            state = data.get('state', '?')
                            target = data.get('target', '')
                            print(f'\n  [STATUS] {state}', end='')
                            if target:
                                print(f'  target={target}', end='')
                            if data.get('robot_position'):
                                pos = data['robot_position']
                                print(
                                    f'  robot=({pos["x"]}, {pos["y"]})',
                                    end='',
                                )
                            if data.get('position_error_m') is not None:
                                print(
                                    f'  error={data["position_error_m"]}m',
                                    end='',
                                )
                            if data.get('duration_s') is not None:
                                print(
                                    f'  duration={data["duration_s"]}s',
                                    end='',
                                )
                            print()
 
                        elif msg_type == 'feedback':
                            print(f'  [FEEDBACK] {data.get("text", "")}')
 
                        elif msg_type == 'ack':
                            room = data.get('room', '')
                            resolved = data.get('resolved_room_id', '')
                            pos = data.get('target_position', {})
                            print(
                                f'  [ACK] "{room}" → {resolved} '
                                f'(x={pos.get("x")}, y={pos.get("y")})'
                            )
 
                        elif msg_type == 'rooms':
                            print('\n  Available rooms:')
                            for rid, info in data.get('rooms', {}).items():
                                aliases = ', '.join(info.get('aliases', []))
                                print(
                                    f'    {rid:20s}  '
                                    f'x={info["x"]:8.2f}  '
                                    f'y={info["y"]:8.2f}  '
                                    f'aliases: {aliases}'
                                )
                            print()
 
                        elif msg_type == 'error':
                            print(
                                f'  [ERROR] {data.get("message", "unknown")}'
                            )
 
                        else:
                            print(f'  [MSG] {json.dumps(data)}')
 
                        # Re-show prompt
                        print('> ', end='', flush=True)
 
                except websockets.exceptions.ConnectionClosed:
                    print('\nConnection closed by server.')
 
            recv_task = asyncio.create_task(receiver())
 
            # Input loop (run in executor so it doesn't block)
            loop = asyncio.get_event_loop()
            try:
                while True:
                    print('> ', end='', flush=True)
                    line = await loop.run_in_executor(
                        None, sys.stdin.readline
                    )
                    line = line.strip()
 
                    if not line:
                        continue
 
                    if line.lower() == 'quit':
                        break
 
                    elif line.lower() == 'rooms':
                        await ws.send(json.dumps({
                            'type': 'list_rooms',
                        }))
 
                    elif line.lower() == 'status':
                        await ws.send(json.dumps({
                            'type': 'get_status',
                        }))
 
                    else:
                        await ws.send(json.dumps({
                            'type': 'room_command',
                            'room': line,
                        }))
 
            except (KeyboardInterrupt, EOFError):
                pass
            finally:
                recv_task.cancel()
 
    except ConnectionRefusedError:
        print(f'Could not connect to {uri} — is ws_command_bridge running?')
        sys.exit(1)
    except Exception as e:
        print(f'Connection error: {e}')
        sys.exit(1)
 
 
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='WebSocket client for CloudTwin robot commands',
    )
    parser.add_argument(
        '--host', default='localhost',
        help='IP or hostname of the ROS machine (default: localhost)',
    )
    parser.add_argument(
        '--port', type=int, default=9090,
        help='WebSocket port (default: 9090)',
    )
    args = parser.parse_args()
 
    asyncio.run(main(args.host, args.port))
```

To run it, type a room name to navigate, `rooms` to list destinations, `status` to poll, `quit` to disconnect. The client prints all status updates as they arrive, so you know when the robot has reached its destination before sending the next command.

```bash
python3 ws_robot_client.py --host 192.168.1.42 --port 9090
```

---

### Foxglove (remote panel)

1. Open [https://app.foxglove.dev](https://app.foxglove.dev) in a browser
2. Connect to `ws://<ip>:8765` (use `localhost` if on the same machine, or the digital twin's IP if remote)
3. Install the Room Command panel extension (`.foxe` file) for voice/text destination commands
4. Send a navigation goal from the 3D panel or the Room Command panel

You can also send a goal from the terminal:

```bash
ros2 topic pub --once /goal_pose geometry_msgs/PoseStamped \
  "{header: {frame_id: 'map'}, pose: {position: {x: 3.0, y: 0.0, z: 0.0}, orientation: {w: 1.0}}}"
```

---

## Creating the map

The hospital map was generated using slam_toolbox. To recreate it or create a map for a different world:

1. Launch the robot in the world:

   ```bash
   export GAZEBO_MODEL_PATH=$HOME/Documents/CloudTwin/Code/src/robot_simulation/models:$GAZEBO_MODEL_PATH

   ros2 launch bcr_bot gazebo.launch.py \
     two_d_lidar_enabled:=True \
     camera_enabled:=True \
     world_file:=$HOME/Documents/CloudTwin/Code/src/robot_simulation/worlds/hospital.world \
     position_x:=0.0 \
     position_y:=5.0
   ```
2. Launch slam_toolbox (new terminal):

   ```bash
   source /opt/ros/humble/setup.bash
   ros2 run slam_toolbox async_slam_toolbox_node --ros-args \
     -p use_sim_time:=true \
     -r scan:=/bcr_bot/scan
   ```
3. Launch teleop to drive the robot (new terminal):

   ```bash
   source /opt/ros/humble/setup.bash
   ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args \
     -r cmd_vel:=/bcr_bot/cmd_vel
   ```
4. Visualize in RViz: set Fixed Frame to `odom`, add `/map` and `/bcr_bot/scan` topics.
5. Drive the robot through the entire environment.
6. Save the map:

   ```bash
   cd ~/path_to_save_map
   ros2 run nav2_map_server map_saver_cli -f hospital_map
   ```

---

## Versions

| Version | Details                                                                                                                                  |
| ------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| V0.1.0  | Repo initialisation with Doxygen configuration                                                                                           |
| V0.1.1  | Tested Doxygen                                                                                                                           |
| V1.0.1  | Created test Gazebo world and launch script                                                                                              |
| V1.1.0  | Started building the robot_simulation package                                                                                            |
| V2.1.1  | Created kick_off package for centralised launch                                                                                          |
| V2.1.2  | Renamed kick_off to launch_project                                                                                                       |
| V2.2.1  | Created the digital_twin package                                                                                                         |
| V2.3.0  | Updated setup.py for the digital_twin package                                                                                            |
| V2.3.1  | Created the visualisation package                                                                                                        |
| V2.3.2  | Modified Gazebo world for sun/lighting. Updated launch file for Gazebo server                                                            |
| V2.3.3  | Created map using SLAM toolbox                                                                                                           |
| V3.0.0  | Migration to Gazebo Harmonic + bcr_bot + small_warehouse. Nav2 integration. Foxglove bridge. Removed launch_project                      |
| V3.1.0  | Removed AMCL startup, increased acceleration and speed                                                                                   |
| V3.2.0  | Custom warehouse for better navigation, applied planning                                                                                 |
| V4.0.0  | Changed to Gazebo Classic from Gazebo Harmonic, hospital world with bcr_bot                                                              |
| V4.0.1  | Added goal_pose relay for Foxglove timestamp fix                                                                                         |
| V4.1.0  | Added bcr_bot to project tree, first version of people spawner                                                                           |
| V4.1.1  | Updated human spawner logic, fixed non-moving cylinders                                                                                  |
| V4.1.2  | Changed cylinder SDF to Scrub person model                                                                                               |
| V4.1.3  | Updated Nav2 params for narrow doors                                                                                                     |
| V4.1.4  | Added /people_positions publisher to obstacle spawner                                                                                    |
| V5.0.0  | YAML registry files for intersections and rooms                                                                                          |
| V6.0.1  | Smart automatic re-navigation based on crowd affluence data                                                                              |
| V6.0.2  | Foxglove layout V1 saved                                                                                                                 |
| V6.1.0  | Custom Foxglove panel for voice/text room commands                                                                                       |
| V6.1.1  | Released version 1.0.0 of Foxglove panel                                                                                                 |
| V6.2.1  | hospital.launch.py updated to include obstacle_spawner                                                                                   |
| V6.2.2  | Speech node for voice commands, integrated into logic.launch.py and Foxglove panel                                                       |
| V6.3.0  | Created websocket to receive command from a no ROS system (do not like the idea) and added support to save a simulation in a JSON format |

---

## TO-DO

### robot_simulation

- [X] Spawn robot and verify sensors
- [X] Implement teleop for manual driving
- [X] Run SLAM to generate map
- [X] Simulate people detection using Gazebo Fuel models
- [X] Obstacle spawner for dynamic people at known positions

### digital_twin

- [X] Create the digital_twin package
- [X] Integrate Nav2 for path planning
- [X] Navigation with obstacle avoidance via Nav2 costmaps
- [X] Dynamic map overlay for crowd-aware replanning
- [X] Room interpreter for text/voice destination commands
- [X] Speech-to-text node with Whisper
- [ ] Add simulated 5G latency on robot ↔ digital twin communication
- [X] Local safety controller for emergency braking
- [X] Demo scenarios: nominal navigation, dynamic obstacle avoidance

### visualisation

- [X] Connect Foxglove via websocket bridge
- [X] Send navigation goals from Foxglove
- [X] Real-time display of updated path, crowd density, and robot status
- [X] Custom Foxglove panel for room commands (text + voice)
- [X] Display robot coordinates, goal, and planning status
