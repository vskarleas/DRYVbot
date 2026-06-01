# CloudTwin : Digital Twin pour la navigation autonome et prédictive d'un robot mobile

## Description

This project is a proof-of-concept for a Digital Twin application applied to mobile robotics. The core idea is that we have budget robots with limited onboard processing power that cannot handle heavy computation tasks like trajectory planning and real-time obstacle avoidance on their own. Instead, these robots offload that computation to their digital twin running on a cloud server (in our case, our local computer).

### About the digital twin

The digital twin receives real-time data from the robot (position, sensor data) and from the environment (people affluence, obstacle positions), processes all this information to compute the optimal path, and sends back motion commands to the robot. This creates a closed-loop system where the robot is essentially "remote-controlled" by its intelligent twin that has access to far more computational resources. Beyond reactive obstacle avoidance, the digital twin also implements predictive navigation: an AI model analyzes environmental data (traffic flow, intersection proximity, zone affluence) to anticipate risky situations and proactively adapt the robot's speed and trajectory — for example, slowing down when approaching an intersection even before detecting any obstacle.

### Simulating a real life robot

Since we do not have a physical robot available, the project uses Gazebo Classic to simulate the robot navigating in corridor and hospital environments. The simulation represents what would be a real robot connected via a 5G local network to the cloud. The digital twin runs the Nav2 navigation stack, which is too computationnaly heavy for a budget robot's onboard CPU.

### User Interface

A Foxglove web user interface allows the user to visualise the robot in real-time on the map, select a destination, and monitor the planned path. When a destination is selected, the robot's real-time position and environment affluence data are sent to the digital twin, which continuously computes and updates the best path until the robot reaches its final position. The interface also shows predictive speed adjustments and replanned trajectories as the robot navigates through dynamic environments. All those info are also shown live on the web interface.

---

## Technical aspect of the project

### Goal

Transfer complex path planning calculations on the digital twin of the robot allowing to integrate more data points for better path planning decisions including data for real time affluence as well as information regarding the topology of the map (intersection, dead end, etc.)

### Architecture

The project is organised in the following ROS2 packages:

- **`robot_simulation`** — Contains the world files, saved maps, and the obstacle spawner script. In a real deployement, this package would be replaced by the actual physical robot and its sensors.
- **`digital_twin`** — This is the core of the project. It is the cloud-side intelligence that the robot cannot run onboard due to its limited CPU. It contains the Nav2 configuration, the warehouse map, and the main launch file (`full.launch.py`) that starts the entire system: Gazebo simulation, Nav2 navigation, cmd_vel relay, and Foxglove bridge. It receives real-time data (robot position, lidar scans, destination goal) and runs the Nav2 path planning to compute the optimal trajectory.
- **`bcr_bot`** — The simulated robot. A differential drive robot with lidar, camera, and IMU that works natively with Gazebo Harmonic.

### Technologies

- **ROS2 Humble** — Robotics framework
- **Gazebo Classic v11** — Robot and environment simulation
- **bcr_bot** — Mobile robot model (differential drive with lidar and camera)
- **Nav2** — Navigation engine for path planning and obstacle avoidance
- **slam_toolbox** — SLAM for map generation
- **Foxglove** — Web-based visualisation and user interface platform

### AI navigation manager

It works like a state machine that receives real time and static data and based on that information it decides when to slow down (intersection behavior) and when to reroute due to increased mouvement on a couloir. The data that it receives includes but are not limited to :

* /semantic_map* : static map of the environment that was scanned using a lidar (,yamls and .pmg files using the SAML Toolbox tools - more information at creating the map section below)
* /odom : real time odometry data of the robot meaning position data
* /goal_pose : pose data meaning his final destination coordinates
* /crowd_density : data related to dynamic traffic on the static map for dynamic real time decision taking
* /plan : robot's plan to reach a pose for analysis based on the crowd density and the semantic map

**Nota bene :** The semantic map takes the static map of the scanned environnement and adds a layer of extra info including locations identification, the zones like intersection, colloir, dead end, stairs, etc., as well as predefined places identification (map coordinates for instance saying that at x=1,y=4 is the Radiology department). An example of the `room_registry.yaml` map coordinates can be found below :

```yaml
rooms:
  salle_101:
    x: -5.0
    y: 3.0
    orientation_w: 1.0
    aliases: ["room 101", "salle 101", "chambre 101"]
  urgences:
    x: 2.0
    y: -4.0
    orientation_w: 0.707
    aliases: ["emergency", "urgences", "salle urgences"]
  radiologie:
    x: 8.0
    y: 1.0
    orientation_w: 1.0
    aliases: ["radiology", "radio", "imagerie"]
```

#### How it works ?

There is a path analyser that is doing some cross ref of the inital plan and the semantic_map's zones in order to take action on the robots speed (**intersection logic** below). Moreover, we have a crowd path scorer that based on the crowd density and to the initial plan it creates a temporary costmap that will force the robot to take a new path and prevent it from passing from the densed crowded area (**crowd logic** below)).

**Nota bene :** A costmap is a collsion probability map that can be interpreted from the robot's navigation engine (nav2)

##### Creating the /semantic_map

Using a CNN network to build the semantic map of the environment, meaning for instance : this patch is a corridor, this is an intersection, this is a room entrance, this is a dead-end. That semantic map becomes the backbone for everything else like the velocity zones and the room registry from above.

The CNN runs  **once at startup**. It takes the static occupancy grid (the existing `.pgm` map), slides a window (32×32 cells) across every free-space region, and classifies each patch into one of five categories:

1. intersection,
2. corridor,
3. room entry,
4. dead-end, or
5. open area.

The output is a semantic grid with the same dimensions as the occupancy map, but each cell has a class label instead of an occupancy value. As for the training data, they are generated from our own maps: like the static .pgm map and the teh room_registry file. We can also generated artificial data by rotating or even flipping the static map and then provide all of those info to a tiny 4-layer CNN in PyTorch. We can also generate synthetic training maps programmatically (random corridor layouts) to boost the dataset.

##### Creating the /crowd_density

... I HAVE TO SEE HOW TO CREATE THE CROWD DENSITY GRID

##### Intersection logic

###### Approaching intersection -> ramping down speed

The semantic map flagged an intersection zone within 2.0m of the robot's current position along the path. The node starts ramping down the speed limit linearly: from 0.22 m/s at 2.0m away, to 0.05 m/s at 0.5m away. Crowd monitoring continues in parallel and if rerouting is triggered then the speed ramp is overridden.

###### At intersection -> brief safety pause before crossing

The robot is at the intersection center. The node publishes max_vel = 0.0 for a configurable duration (default 1.5 seconds). During this pause, the node checks crowd density specifically around the intersection zone. If people are detected nearby, the pause extends until density drops below 0.3. This simulates a 'look both ways' behavior scenarion.

###### Crossing intersection -> moving through at reduced speed

The robot crosses the intersection at a reduced speed (default 0.08 m/s, ~36% of normal). This can optionally be configured to accelerate (up to 0.30 m/s) instead, to minimize the time spent exposed in the intersection which is useful in high-traffic zones. The node continues monitoring the semantic map to detect when the robot exits the intersection zone.

##### Crowd logic

###### Rerouting due to high crowd density -> forcing path change

The crowd density along a planned path segment exceeds the threshold (0.6). The node inflates that zone in /crowd_costmap with lethal cost (254) in a radius of ~2.0m around each dense point. Nav2's global costmap picks up the new layer, and the planner automatically computes an alternative path avoiding the congested area. The node watches /plan for the new path. Here is an example below.

![rerouting example](/home/vskarleas/Documents/ROB5-S10-SYS880/Documentation/reroute_example.jpg)

###### Normal navigation -> following predefined Nav2 path

This is the main  main monitoring loop. Every 100ms (10 Hz), the node reads the robot pose, the current Nav2 plan, and the latest crowd density grid. It performs two analyses: (1) scan the planned path for upcoming intersections by cross-referencing waypoints against the semantic map, (2) compute the maximum crowd density along the planned path segments.

##### To sum up...

All of those actions are then interpreted and combined from a **decision engine** that sends the real actions to the robot like speed change and new plan for the robot to follow. Moreover this decision engine sends all the decisions that were made and the data that are collected on the web user interface for real time feedback (check the section Foxglove end-user flow below).

![ai navigation engine explained](/home/vskarleas/Documents/ROB5-S10-SYS880/Documentation/ai_nav_manager_internal_pipeline.svg)

###### **Path analyzer**

It runs on every cycle. It takes the latest Nav2 `/plan` (a sequence of `PoseStamped` waypoints) and cross-references each waypoint against the semantic map grid. For every waypoint, it looks up the CNN classification of that cell: corridor, intersection, room entry, etc. The output is an annotated path — a list like `[(waypoint_0, "corridor"), (waypoint_1, "corridor"), (waypoint_2, "intersection"), (waypoint_3, "corridor"), ...]`. From this, it extracts the next upcoming intersection along the path and computes the distance from the robot's current position to that intersection center. This is what drives the approach/stop/cross state transitions.

###### **Crowd path scorer**

It runs in parallel with the path analyser. It takes the `/crowd_density` grid (from the `crowd_monitor` node) and samples density values along the planned path. For each path segment between consecutive waypoints, it samples 3-5 points and takes the maximum. If any segment's maximum density exceeds the threshold (default 0.6), that segment is flagged. The flagged segments feed into the costmap generator, which inflates those zones with lethal costs. The key insight: we don't just check "is there a crowd somewhere" — we check "is there a crowd  *on our planned path* ", which avoids unnecessary rerouting when crowds are elsewhere in the hospital.

###### **Decision engine**

It receives the annotated path and the crowd scores, evaluates the transition conditions, and dispatches commands to the three output modules. The state machine runs at 10 Hz but some outputs (like `/ai_stats`) are throttled to 1 Hz to avoid flooding the network with too much information.

###### AI navigation parameters

It's simply a file that includes the different thresholds that are used from our decision engine. Here is an example of the `ai_nav_params.yaml` :

```yaml
ai_navigation_manager:
  ros__parameters:
    # Crowd rerouting
    crowd_density_threshold: 0.6    # trigger reroute above this
    crowd_clear_threshold: 0.3      # resume original path below this
    costmap_inflation_radius: 2.0   # meters around dense points
    costmap_lethal_value: 254       # cost value (254 = lethal)
  
    # Intersection behavior
    approach_distance: 2.0          # start slowing at this distance
    stop_distance: 0.5              # full stop at this distance
    stop_duration: 1.5              # seconds to wait
    crossing_speed: 0.08            # m/s through intersection
    crossing_mode: "slow"           # "slow" or "fast" (accelerate)
  
    # General
    normal_speed: 0.22              # m/s cruising speed
    processing_rate: 10.0           # Hz main loop
    stats_rate: 1.0                 # Hz for /ai_stats
```

###### Foxglove end-user flow

In Foxglove, the operator sees three panels. The **3D panel** shows the robot, the lidar, the Nav2 path, plus the crowd density overlay and the semantic map overlay as additional layers.

A **text command panel** will be integrated that will use Foxglove's built-in Publish panel configured to publish `std_msgs/String` on `/room_command`. The operator types for example "Go to room 204", the `room_interpreter` node parses it, looks up the coordinates, and publishes a `/goal_pose`. Then Nav2 picks it up and the robot starts moving. Path changes appear in real-time because Nav2 already publishes `/plan`. 

The **statistics panel** uses Foxglove's Plot panel subscribing to `/ai_stats` to show live graphs: current zone type, crowd density along the planned path, number of intersection stops performed, average speed. Below you can find an example of the /ai_stats node. The `session` block is what feeds the Foxglove statistics plots over time, like the number of reroutes, time distribution across zone types, average speed. It accumulates over the entire navigation session and resets when a new goal is sent.

```json
{
  "timestamp": 1717200000.0,
  "state": "APPROACHING_INTERSECTION",
  "robot_pose": {"x": -3.2, "y": 4.1, "theta": 1.57},
  "current_zone": "corridor",
  "next_intersection": {"id": 3, "distance": 1.4},
  "speed": {"current": 0.15, "limit": 0.18, "normal": 0.22},
  "crowd": {
    "max_on_path": 0.42,
    "reroute_active": false,
    "blocked_zones": []
  },
  "session": {
    "distance_traveled": 12.7,
    "intersections_crossed": 2,
    "reroutes_triggered": 1,
    "time_in_corridors_pct": 68,
    "time_in_intersections_pct": 12,
    "time_stopped_pct": 20
  }
}
```

---

## Installation

### Prerequisites

- Ubuntu 22.04
- Install ROS2 Humble following the instructions at[ https://foxglove.dev/blog/installing-ros2-humble-on-ubuntu](https://foxglove.dev/blog/installing-ros2-humble-on-ubuntu)

### Install Gazebo Classic and ROS2 Bridge

```bash
sudo apt install ros-humble-gazebo-ros-pkgs ros-humble-gazebo-ros
```

This installs Gazebo 11 (Classic) and the `gazebo_ros` bridge for ROS2.

> **Note:** Gazebo Classic and Gazebo Harmonic (gz-tools2) cannot coexist on the same system. If you have Harmonic installed, remove it first: `sudo apt remove gz-harmonic gz-tools2 ros-humble-ros-gzharmonic*`

### Install Navigation and SLAM Packages

```bash
sudo apt install ros-humble-navigation2 \
                 ros-humble-nav2-bringup \
                 ros-humble-slam-toolbox
```

### Install Foxglove Bridge

```bash
sudo apt install ros-humble-foxglove-bridge
```

### Install Additional ROS2 Tools

```bash
sudo apt install python3-colcon-common-extensions \
                 ros-humble-teleop-twist-keyboard \
                 ros-humble-topic-tools \
                 ros-humble-tf2-ros
```

### Clone the Repository

```bash
git clone https://github.com/vskarleas/ROB5-S10-SYS880
cd ROB5-S10-SYS880/Code
```

### Install bcr_bot from Source

The `bcr_bot` package must be present in the workspace `src/` folder. If it is not already there after cloning:

```bash
cd src
git clone https://github.com/blackcoffeerobotics/bcr_bot.git
cd ..
```

> **Note:** The `bcr_bot` supports multiple Gazebo versions. For this project we use its **Gazebo Classic** mode via `gazebo.launch.py`.

### Install Dependencies with rosdep

```bash
sudo apt install python3-rosdep
sudo rosdep init   # skip if already initialised
rosdep update
rosdep install --from-paths src --ignore-src -r -y
```

### Install xarco

Xarco needs to be installed for this repo. Check the installation process depending on your system

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
ros2 launch digital_twin hospital.launch.py
```

Wait approximately 30 seconds for everything to start. Then open Foxglove at `https://app.foxglove.dev`, connect to `ws://localhost:8765`, and send a navigation goal.

You can also send a goal from the terminal:

```bash
ros2 topic pub --once /goal_pose geometry_msgs/PoseStamped \
  "{header: {frame_id: 'map'}, pose: {position: {x: 3.0, y: 0.0, z: 0.0}, orientation: {w: 1.0}}}"
```

You can launch the obstacles spawner as follows (you can choose between hospital and corridor) :

```bash
ros2 run robot_simulation obstacle_spawner.py  --ros-args -p scenario:=hospital
```

---

## Creating the map

The hospital and corridor maspwas generated using slam_toolbox. To recreate them or create a map for a different world:

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
2. Launch slam_toolbox (in a new terminal):

   ```bash
   source /opt/ros/humble/setup.bash
   ros2 run slam_toolbox async_slam_toolbox_node --ros-args \
     -p use_sim_time:=true \
     -r scan:=/bcr_bot/scan
   ```
3. Launch teleop to drive the robot arround (in a new terminal):

   ```bash
   source /opt/ros/humble/setup.bash
   ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args \
     -r cmd_vel:=/bcr_bot/cmd_vel
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
   cd ~/path_to_save_SAML_map
   ros2 run nav2_map_server map_saver_cli -f hospital_map
   ```

---

## Versions

| Version | Details                                                                                                                                                                         |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| V0.1.0  | Repo initialisation with Doxygen configuration                                                                                                                                  |
| V0.1.1  | Tested doxygen                                                                                                                                                                  |
| V1.0.1  | Created test Gazebo world and a launch script that allows to launch that world on Gazebo                                                                                        |
| V1.1.0  | Started building the robot_simulation package that will be used to simulate the real robot so that if we had a real robot navigating on the real world                          |
| V2.1.1  | Created kick_off package for centralised launch. Basicly it only insludes the launch file for vetter centralisation                                                             |
| V2.1.2  | Renamed the kick_off package to launch_project                                                                                                                                  |
| V2.2.1  | Created the digital_twin package                                                                                                                                                |
| V2.3.0  | Updated teh setup.py for the digital twin package                                                                                                                               |
| V2.3.1  | Created the visualization package                                                                                                                                               |
| V2.3.2  | Modfied the Gazebo world so that it can have sun and lighting conditions. Also, we modfied the launch file so that Gazebo server can run our world                              |
| V2.3.3  | Created a map using the SLAM toolbox                                                                                                                                            |
| V3.0.0  | Migration to Gazebo Harmonic + bcr_bot + small_warehouse. Nav2 integration for path planning. Foxglove bridge. Removed launch_project package                                   |
| V3.1.0  | Removed ACML startup for the nav2 because it is not needed for robot's navigation using the /odom topic. ALso increased the acceleration and teh speed of the robot             |
| V3.2.0  | Created a custom warehouse for better navigation results and applied palnning                                                                                                   |
| V4.0.0  | Chnaged to Gazebo classic from Gazebo Harmonic, installed and prpeared a jospital world with its map. The bcr robot was implemented into to that                                |
| V4.0.1  | Added a new topic /goal_pose_foxglove in order to treat correctly the messages sent from the 3D map of foxglove. It works as a relay between foxglove and the robots cmd topics |
| V4.1.0  | Added bcr_robot on the tree of the project, updated the README and tried a first version for spawning automaticly different cylinders that represent the people                 |
| V4.1.1  | Updated the human spawner based on Dounia's logic and interpretation and fixed not-moving cylinders issue. The visualization package was removed as well for better clarity     |
| V4.1.2  | Changed the sdf of cylinder to the Scrub model of a person                                                                                                                      |

## TO-DO

### robot_simulation

* [X] Spawn robot in the world and verify sensors are working
* [X] Implement teleop to manually drive the robot
* [X] Run SLAM to generate a map of the environment
* [X] See if we can simulate people detection on gazebo using Fuel models (standing_person, walking_person)
* [X] Implement the obstacle spawner to inject dynamic people at known positions on the map
* [ ] Maybe apply some computer vision to the system so that it understands that a speciifc section is an intersection

### digital_twin

* [X] Create the digital twin package
* [X] Integrate Nav2 for path planning on the saved map
* [X] Navigation with obstacle avoidance via Nav2 costmaps
* [ ] Add simulated 5G latency on the communication between robot and digital twin
* [X] Implement a local safety controller on the robot side for emergency braking (cannot depend on network)
* [X] Create demo scenarios: nominal navigation, dynamic obstacle avoidance, latency stress test

### visualization

* [X] Connect Foxglove to the system via websocket bridge
* [X] Send navigation goals from Foxglove
* [ ] On foxglove include information like updated path based on affluence and crowd data. Include as well a text promp interface for commanding the robot to go to a specific room or department inside the world.
* [X] If possible show on real time on foxglove the updated path that is provided from the digital twin to the robot, as well as the afluence of things, people from lidar data, and simulation info
* [X] Display robot's current coordinates, goal coordinates, and planning status on the interface
