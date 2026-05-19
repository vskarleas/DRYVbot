# ROB5-S10-SYS880

## Description

This project is a proof-of-concept for a **Digital Twin** application applied to mobile robotics. The core idea is that we have budget robots with limited onboard processing power that cannot handle heavy computation tasks like trajectory planning and real-time obstacle avoidance on their own. Instead, these robots offload that computation to their digital twin running on a cloud server (in our case, our local computer).

The digital twin receives real-time data from the robot (position, sensor data) and from the environment (people affluence, obstacle positions), processes all this information to compute the optimal path, and sends back motion commands to the robot. This creates a closed-loop system where the robot is essentially "remote-controlled" by its intelligent twin that has access to far more computational resources.

Since we do not have a physical robot available, the project uses **Gazebo Harmonic** to simulate the robot navigating in a warehouse environment. The simulation represents what would be a real robot connected via a 5G local network to the cloud. The digital twin runs the **Nav2** navigation stack, which is too computationnaly heavy for a budget robot's onboard CPU.

A **Foxglove** web interface (running on localhost) allows the user to visualise the robot in real-time on the map, select a destination, and monitor the planned path. When a destination is selected, the robot's real-time position and environment affluence data are sent to the digital twin, which continuously computes and updates the best path until the robot reaches its final position. All those info are also shown live on the web interface.

### Architecture

The project is organised in the following ROS2 packages:

- **`robot_simulation`** — Contains the world files, saved maps, and the obstacle spawner script. In a real deployement, this package would be replaced by the actual physical robot and its sensors.

- **`digital_twin`** — This is the core of the project. It is the cloud-side intelligence that the robot cannot run onboard due to its limited CPU. It contains the Nav2 configuration, the warehouse map, and the main launch file (`full.launch.py`) that starts the entire system: Gazebo simulation, Nav2 navigation, cmd_vel relay, and Foxglove bridge. It receives real-time data (robot position, lidar scans, destination goal) and runs the Nav2 path planning to compute the optimal trajectory.

- **`visualization`** — Reserved for future Foxglove custom panels and visualization tools. Currently, the Foxglove bridge is launched from the digital_twin launch file.

- **`bcr_bot`** (external) — The simulated robot. A differential drive robot with lidar, camera, and IMU that works natively with Gazebo Harmonic.

### Technologies

- **ROS2 Humble** — Robotics framework
- **Gazebo Harmonic** — Robot and environment simulation
- **bcr_bot** — Mobile robot model (differential drive with lidar and camera)
- **Nav2** — Navigation stack for path planning and obstacle avoidance
- **slam_toolbox** — SLAM for map generation
- **Foxglove** — Web-based visualisation interface (free edition, localhost)
- **ros_gz_bridge** — Bridge between Gazebo Harmonic and ROS2 topics


## Installation

### Prerequisites

- Ubuntu 22.04
- ROS2 Humble (`sudo apt install ros-humble-desktop`)
- Gazebo Harmonic:
  ```bash
  sudo apt install gz-harmonic ros-humble-ros-gzharmonic
  ```
- Nav2 and SLAM:
  ```bash
  sudo apt install ros-humble-navigation2 ros-humble-nav2-bringup ros-humble-slam-toolbox
  ```
- Foxglove Bridge:
  ```bash
  sudo apt install ros-humble-foxglove-bridge
  ```
- Topic tools (for cmd_vel relay):
  ```bash
  sudo apt install ros-humble-topic-tools
  ```

### Environment Setup

Add the following to your `~/.bashrc` if not already there:

```bash
source /opt/ros/humble/setup.bash
```

### Build

```bash
cd ~/Documents/ROB5-S10-SYS880/Code
colcon build
source install/setup.bash
```

### Launch everything

The `full.launch.py` starts the entire system in one command: Gazebo with the warehouse world and the bcr_bot, Nav2 navigation stack, cmd_vel relay, initial pose publisher, and Foxglove bridge.

```bash
ros2 launch digital_twin full.launch.py
```

Wait approximately 30 seconds for everything to start. Then open Foxglove at `https://app.foxglove.dev`, connect to `ws://localhost:8765`, and send a navigation goal.

You can also send a goal from the terminal:

```bash
ros2 topic pub --once /goal_pose geometry_msgs/PoseStamped \
  "{header: {frame_id: 'map'}, pose: {position: {x: 3.0, y: 0.0, z: 0.0}, orientation: {w: 1.0}}}"
```


## Creating the map

The warehouse map was generated using slam_toolbox. To recreate it or create a map for a different world:

1. Launch the robot in the world:
   ```bash
   ros2 launch bcr_bot gz.launch.py two_d_lidar_enabled:=True camera_enabled:=True world_file:=small_warehouse.sdf
   ```

2. Launch slam_toolbox (in a new terminal):
   ```bash
   ros2 run slam_toolbox async_slam_toolbox_node --ros-args -p use_sim_time:=true -r scan:=/bcr_bot/scan
   ```

3. Launch teleop to drive the robot arround (in a new terminal):
   ```bash
   ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -r /cmd_vel:=/bcr_bot/cmd_vel
   ```

4. Visualize the map in RViz (in a new terminal):
   ```bash
   rviz2
   ```
   - Set **Fixed Frame** to `odom`
   - **Add** → **By topic** → `/map` → **Map**
   - **Add** → **By topic** → `/bcr_bot/scan` → **LaserScan**

5. Drive the robot through the entire environment to complete the map.

6. Save the map:
   ```bash
   cd ~/Documents/ROB5-S10-SYS880/Code/src/digital_twin/maps
   ros2 run nav2_map_server map_saver_cli -f warehouse_map
   ```


## Versions

| Version | Details                                                                                                                                                |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| V0.1.0  | Repo initialisation with Doxygen configuration                                                                                                         |
| V0.1.1  | Tested doxygen                                                                                                                                         |
| V1.0.1  | Created test Gazebo world and a launch script that allows to launch that world on Gazebo                                                               |
| V1.1.0  | Started building the robot_simulation package that will be used to simulate the real robot so that if we had a real robot navigating on the real world |
| V2.1.1  | Created kick_off package for centralised launch. Basicly it only insludes the launch file for vetter centralisation                                    |
| V2.1.2  | Renamed the kick_off package to launch_project                                                                                                         |
| V2.2.1  | Created the digital_twin package                                                                                                                       |
| V2.3.0  | Updated teh setup.py for the digital twin package                                                                                                      |
| V2.3.1  | Created the visualization package                                                                                                                      |
| V2.3.2  | Modfied the Gazebo world so that it can have sun and lighting conditions. Also, we modfied the launch file so that Gazebo server can run our world     |
| V2.3.3  | Created a map using the SLAM toolbox                                                                                                                   |
| V3.0.0  | Migration to Gazebo Harmonic + bcr_bot + small_warehouse. Nav2 integration for path planning. Foxglove bridge. Removed launch_project package          |


## TO-DO

### robot_simulation
* [X] Spawn robot in the world and verify sensors are working
* [X] Implement teleop to manually drive the robot
* [X] Run SLAM to generate a map of the environment
* [ ] See if we can simulate people detection on gazebo using Fuel models (standing_person, walking_person)
* [ ] Implement the obstacle spawner to inject dynamic people at known positions on the map
* [ ] Maybe apply some computer vision to the system so that we do not give directly teh information that on a specific point of the map there are people moving. We could use OpenCV if applicable

### digital_twin
* [X] Create the digital twin package
* [X] Integrate Nav2 for path planning on the saved map
* [X] Navigation with obstacle avoidance via Nav2 costmaps
* [ ] Add simulated 5G latency on the communication between robot and digital twin
* [ ] Implement a local safety controller on the robot side for emergency braking (cannot depend on network)
* [ ] Create demo scenarios: nominal navigation, dynamic obstacle avoidance, latency stress test

### visualization
* [X] Connect Foxglove to the system via websocket bridge
* [X] Send navigation goals from Foxglove
* [ ] On foxglove show an approve first_path when Nav2 proposes the path. This path however is free to be updated on real time when the robots runs and the digital twin control's its mouvement
* [ ] If possible show on real time on foxglove the updated path that is provided from the digital twin to the robot, as well as the afluence of things, people from lidar data, and simulation info
* [ ] Display robot's current coordinates, goal coordinates, and planning status on the interface