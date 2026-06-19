import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    digital_twin_dir = get_package_share_directory('digital_twin')
    logic_params = os.path.join(digital_twin_dir, 'config', 'logic_params.yaml')

    # ── Launch arguments ────────────────────────────────────────────────
    enable_sim_logger_arg = DeclareLaunchArgument(
        'enable_sim_logger',
        default_value='false',
        description='Enable the simulation logger (saves JSON to simulation_logs/)',
    )

    enable_ws_bridge_arg = DeclareLaunchArgument(
        'enable_ws_bridge',
        default_value='true',
        description='Enable the WebSocket command bridge for remote control',
    )

    ws_port_arg = DeclareLaunchArgument(
        'ws_port',
        default_value='9090',
        description='WebSocket server port for the command bridge',
    )

    # ── 1. Crowd Monitor ────────────────────────────────────────────────
    #   Subscribes to /map (map_server) + /people_positions
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
    #   Publishes  Nav2 goal poses + /room_command_feedback
    room_interpreter = Node(
        package='digital_twin',
        executable='room_interpreter',
        name='room_interpreter',
        parameters=[logic_params, {'use_sim_time': True}],
        output='screen',
    )

    # ── 3. Speech Node ──────────────────────────────────────────────────
    #   Subscribes to /speech_trigger (std_msgs/String)
    #   Publishes  /room_command + /speech_status
    speech_node = Node(
        package='digital_twin',
        executable='speech_node',
        name='speech_node',
        parameters=[logic_params, {'use_sim_time': True}],
        output='screen',
    )

    # ── 4. Simulation Logger (optional) ─────────────────────────────────
    #   Subscribes to /room_command, /bcr_bot/odom,
    #                 /navigate_to_pose/_action/status, /clock
    #   Saves per-run JSON files to simulation_logs/
    simulation_logger = Node(
        package='digital_twin',
        executable='simulation_logger',
        name='simulation_logger',
        parameters=[logic_params, {'use_sim_time': True}],
        output='screen',
        condition=IfCondition(LaunchConfiguration('enable_sim_logger')),
    )

    # ── 5. WebSocket Command Bridge (optional) ──────────────────────────
    #   WebSocket server for remote room commands.
    #   Subscribes to /room_command_feedback,
    #                 /navigate_to_pose/_action/status, /bcr_bot/odom
    #   Publishes  /room_command
    ws_command_bridge = Node(
        package='digital_twin',
        executable='ws_command_bridge',
        name='ws_command_bridge',
        parameters=[
            logic_params,
            {'use_sim_time': True},
            {'ws_port': LaunchConfiguration('ws_port')},
        ],
        output='screen',
        condition=IfCondition(LaunchConfiguration('enable_ws_bridge')),
    )

    return LaunchDescription([
        # Declare arguments first
        enable_sim_logger_arg,
        enable_ws_bridge_arg,
        ws_port_arg,

        # Core nodes (always launched)
        crowd_monitor,
        room_interpreter,
        speech_node,

        # Optional nodes (controlled by launch arguments)
        simulation_logger,
        ws_command_bridge,
    ])