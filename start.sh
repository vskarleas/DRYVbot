# 1. Force the script to run from its own directory
cd "$(dirname "$0")"

# 2. Source the main Ubuntu ROS 2 installation
source /opt/ros/humble/setup.bash

cd Code
rm -rf build/ install/ log/
colcon build
source install/setup.bash
ros2 launch digital_twin simulation.launch.py