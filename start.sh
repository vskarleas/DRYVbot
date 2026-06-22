cd Code
rm -rf build/ install/ log/
colcon build
source install/setup.bash
ros2 launch digital_twin simulation.launch.py