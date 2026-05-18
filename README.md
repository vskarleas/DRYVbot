# ROB5-S10-SYS880

## Description

This project is a proof-of-concept for a **Digital Twin** application applied to mobile robotics. The core idea is that we have budget robots with limited onboard processing power that cannot handle heavy computation tasks like trajectory planning and real-time obstacle avoidance on their own. Instead, these robots offload that computation to their digital twin running on a cloud server (in our case, our local computer).

The digital twin receives real-time data from the robot (position, sensor data) and from the environment (people affluence, obstacle positions), processes all this information to compute the optimal path, and sends back motion commands to the robot. This creates a closed-loop system where the robot is essentially "remote-controlled" by its intelligent twin that has access to far more computational resources.

To simulate the real robot we usre **Gazebo Fortress** to simulate the robot navigating in a corridor environment. The simulation represents what would be a real robot connected via a 5G local network to the cloud. The digital twin is a separate ROS2 program (not another Gazebo instance) that runs the planning algorithms and decision-making.

A **Foxglove** web interface (running on localhost) allows the user to visualise the robot in real-time on the map, select a destination, and monitor the planned path. When a destination is selected, the robot's real-time position and environment affluence data are sent to the digital twin, which continuously computes and updates the best path until the robot reaches its final position. All those info are also shown live on the web interface.

### Architecture

The project is organised in three ROS2 packages:

- **`robot_simulation`** — Simulates the "real robot" in Gazebo. Contains the corridor world environment, the TurtleBot3 robot model, and the obstacle spawner that injects dynamic obstacles (people) into the simulation. In a real deployement, this package would be replaced by the actual physical robot and its sensors. This package publishes the robot's position and sensor data, and receives motion commands.
- **`digital_twin`** — This is the core of the project. It is the cloud-side intelligence that the robot cannot run onboard due to its limited CPU. It receives real-time data (robot position, environment affluence, destination goal) and runs the path planning algorithms to compute the optimal trajectory. It continuously replans the path as new obstacle data comes in, and sends motion commands (`cmd_vel`) back to the robot. The planning loop runs until the robot reaches its destination.
- **`visualization`** — Provides a Foxglove web interface for monitoring and control. The user can see the robot's live position on the map, visualise the planned path, observe the affluence of people, and select navigation goals by clicking on the map.

### Technologies

- **ROS2 Humble** — Robotics framework
- **Gazebo Fortress** — Robot and environment simulation
- **TurtleBot3** — Mobile robot model (differential drive)
- **Nav2** — Navigation stack for path planning
- **slam_toolbox** — SLAM for map generation
- **Foxglove** — Web-based visualisation interface (free edition, localhost)
- **DDS** — Middleware for inter-process communication

## Installation

### Prerequisites

- Ubuntu 22.04
- ROS2 Humble (`sudo apt install ros-humble-desktop`)
- Gazebo Fortress (`sudo apt install ros-humble-ros-gz`)
- TurtleBot3 packages:
  ```bash
  sudo apt install ros-humble-turtlebot3*
  ```
- Nav2 and SLAM:
  ```bash
  sudo apt install ros-humble-navigation2 ros-humble-nav2-bringup ros-humble-slam-toolbox
  ```
- Foxglove Bridge:
  ```bash
  sudo apt install ros-humble-foxglove-bridge
  ```

### Environment Setup

Add the following to your `~/.bashrc`:

```bash
export TURTLEBOT3_MODEL=burger
source /opt/ros/humble/setup.bash
```

### Build

```bash
cd ~/Documents/ROB5-S10-SYS880/Code
colcon build
source install/setup.bash
```

### Launch the Gazebo World

```bash
ros2 launch robot_simulation gazebo_world.launch.py
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

## TO-DO

* [X] Move the luanch file outside of a specific package

### robot_simulation

* [ ] Modify the corridors.sdf with Yanis's desoign
* [ ] Spawn TurtleBot3 in the corridor world and verify sensors are working
* [ ] Implement teleop to manually drive the robot in the corridors
* [ ] Run SLAM to generate a map of the corridor environment
* [ ] See if we can simulate people like detection on gazebo
* [ ] Implement the obstacle spawner to inject dynamic people at known positions on the map
* [ ] Maybe apply some computer vision to the system so that we do not give directly teh information that on a specific point of the map there are people moving. We could use OpenCV if applicable

### digital_twin

* [X] Create the digital twin package
* [ ] Create the planner node that receives robot position + goal + affluence data
* [ ] Integrate Nav2 (or custom A*) for path planning on the saved map
* [ ] Implement the continuous replanning loop: recompute path every time new obstacle data arrives, until robot reaches destination
* [ ] Implement the cmd_vel generator that sends motion commands back to the robot
* [ ] Add simulated 5G latency on the communication between robot and digital twin
* [ ] Implement a local safety controller on the robot side for emergency braking (cannot depend on network)

### visualization

* [ ] Create a foxglove interface
* [ ] Connect foxglove localhost and see how to be applied on the ros pkg
* [ ] On foxglove show an approve first_path when Nav2 proposes the path. This path however is free to be updated on real time when the robots runs and the digital twin control's its mouvement
* [ ] If possible show on real time on foxglove the updated path that is provided from the digital twin to the robot, as well as the afluence of things, people from lidar data, and simulation info (or the computer vision module)
* [ ] Display robot's current coordinates, goal coordinates, and planning status on the interface
