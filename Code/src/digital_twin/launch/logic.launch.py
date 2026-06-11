import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    digital_twin_dir = get_package_share_directory('digital_twin')
    logic_params = os.path.join(digital_twin_dir, 'config', 'logic_params.yaml')

    # ── 1. Crowd Monitor ────────────────────────────────────────────────
    #   Subscribes to /map (map_server) + /gazebo/model_states
    #   Publishes  /map_dynamic (Nav2 replanning) + /crowd_density (Foxglove)
    crowd_monitor = Node(
        package='digital_twin',
        executable='crowd_monitor',
        name='crowd_monitor',
        parameters=[logic_params, {'use_sim_time': True}],
        output='screen',
    )

    # ── 2. Room Interpreter ─────────────────────────────────────────────
    #   Subscribes to /room_command (std_msgs/String)
    #   Publishes  Nav2 goal poses
    room_interpreter = Node(
        package='digital_twin',
        executable='room_interpreter',
        name='room_interpreter',
        parameters=[logic_params, {'use_sim_time': True}],
        output='screen',
    )

    # ── 3. Speech Node ────────────────────────────────────────────────
    #   Subscribes to /speech_trigger (std_msgs/String)
    #   Publishes  /room_command (std_msgs/String) + /speech_status (std_msgs/String)
    speech_node = Node(
        package='digital_twin',
        executable='speech_node',
        name='speech_node',
        parameters=[logic_params, {'use_sim_time': True}],
        output='screen',
    )

    return LaunchDescription([
        crowd_monitor,
        room_interpreter,
        speech_node,
    ])