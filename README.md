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
pip install faster-whisper sounddevice numpy pyyaml --break-system-packages
```

### Clone and build

```bash
git clone https://github.com/vskarleas/ROB5-S10-SYS880
cd ROB5-S10-SYS880/Code
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

### Terminal 1 - Base stack

Starts Gazebo with the hospital world, bcr_bot, Nav2 navigation, obstacle spawner, cmd_vel relay, initial pose publisher, and Foxglove bridge:

```bash
cd ~/Documents/CloudTwin/Code
source install/setup.bash
ros2 launch digital_twin hospital.launch.py
```

Wait approximately 30 seconds for everything to initialise.

### Terminal 2 - AI intelligence layer

Starts the crowd monitor (dynamic map overlay), room interpreter (text commands), and speech node (voice commands):

```bash
cd ~/Documents/CloudTwin/Code
source install/setup.bash
ros2 launch digital_twin logic.launch.py
```

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
   export GAZEBO_MODEL_PATH=$HOME/Documents/ROB5-S10-SYS880/Code/src/robot_simulation/models:$GAZEBO_MODEL_PATH

   ros2 launch bcr_bot gazebo.launch.py \
     two_d_lidar_enabled:=True \
     camera_enabled:=True \
     world_file:=$HOME/Documents/ROB5-S10-SYS880/Code/src/robot_simulation/worlds/hospital.world \
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

| Version | Details                                                                                                             |
| ------- | ------------------------------------------------------------------------------------------------------------------- |
| V0.1.0  | Repo initialisation with Doxygen configuration                                                                      |
| V0.1.1  | Tested Doxygen                                                                                                      |
| V1.0.1  | Created test Gazebo world and launch script                                                                         |
| V1.1.0  | Started building the robot_simulation package                                                                       |
| V2.1.1  | Created kick_off package for centralised launch                                                                     |
| V2.1.2  | Renamed kick_off to launch_project                                                                                  |
| V2.2.1  | Created the digital_twin package                                                                                    |
| V2.3.0  | Updated setup.py for the digital_twin package                                                                       |
| V2.3.1  | Created the visualisation package                                                                                   |
| V2.3.2  | Modified Gazebo world for sun/lighting. Updated launch file for Gazebo server                                       |
| V2.3.3  | Created map using SLAM toolbox                                                                                      |
| V3.0.0  | Migration to Gazebo Harmonic + bcr_bot + small_warehouse. Nav2 integration. Foxglove bridge. Removed launch_project |
| V3.1.0  | Removed AMCL startup, increased acceleration and speed                                                              |
| V3.2.0  | Custom warehouse for better navigation, applied planning                                                            |
| V4.0.0  | Changed to Gazebo Classic from Gazebo Harmonic, hospital world with bcr_bot                                         |
| V4.0.1  | Added goal_pose relay for Foxglove timestamp fix                                                                    |
| V4.1.0  | Added bcr_bot to project tree, first version of people spawner                                                      |
| V4.1.1  | Updated human spawner logic, fixed non-moving cylinders                                                             |
| V4.1.2  | Changed cylinder SDF to Scrub person model                                                                          |
| V4.1.3  | Updated Nav2 params for narrow doors                                                                                |
| V4.1.4  | Added /people_positions publisher to obstacle spawner                                                               |
| V5.0.0  | YAML registry files for intersections and rooms                                                                     |
| V6.0.1  | Smart automatic re-navigation based on crowd affluence data                                                         |
| V6.0.2  | Foxglove layout V1 saved                                                                                            |
| V6.1.0  | Custom Foxglove panel for voice/text room commands                                                                  |
| V6.1.1  | Released version 1.0.0 of Foxglove panel                                                                            |
| V6.2.1  | hospital.launch.py updated to include obstacle_spawner                                                              |
| V6.2.2  | Speech node for voice commands, integrated into logic.launch.py and Foxglove panel                                  |

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
