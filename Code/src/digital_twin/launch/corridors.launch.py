import os
from os.path import join
from launch import LaunchDescription
from launch.actions import (
    ExecuteProcess, TimerAction,
    IncludeLaunchDescription, AppendEnvironmentVariable
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    digital_twin_dir = get_package_share_directory('digital_twin')
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')
    bcr_bot_dir = get_package_share_directory('bcr_bot')

    map_file = os.path.join(digital_twin_dir, 'maps', 'corridors_map.yaml')
    nav2_params = os.path.join(digital_twin_dir, 'config', 'nav2_params.yaml')
    corridors_world = os.path.expanduser(
        '~/Documents/ROB5-S10-SYS880/Code/src/robot_simulation/worlds/corridors.world')
    models_path = os.path.expanduser(
        '~/Documents/ROB5-S10-SYS880/Code/src/robot_simulation/models')

    # ===== Environment: model paths for Gazebo Classic =====
    env_models = AppendEnvironmentVariable(
        name='GAZEBO_MODEL_PATH',
        value=models_path)
    env_bcr_models = AppendEnvironmentVariable(
        name='GAZEBO_MODEL_PATH',
        value=join(bcr_bot_dir, "models"))

    # ===== 1. BCR_BOT in Gazebo Classic with corridors world =====
    bcr_bot_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            join(bcr_bot_dir, 'launch', 'gazebo.launch.py')
        ),
        launch_arguments={
            'two_d_lidar_enabled': 'True',
            'camera_enabled': 'True',
            'world_file': corridors_world,
            'position_x': '-5.0',
            'position_y': '0.0',
        }.items(),
    )

    # ===== 2. Static TF: map -> odom =====
    static_tf_map_odom = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_tf_map_odom',
        arguments=['0', '0', '0', '0', '0', '0', 'map', 'odom'],
        output='screen',
    )

    # ===== 3. cmd_vel relay: Nav2 -> robot =====
    cmd_vel_relay = Node(
        package='topic_tools',
        executable='relay',
        name='cmd_vel_relay',
        arguments=['/cmd_vel', '/bcr_bot/cmd_vel'],
        output='screen',
    )

    # ===== 4. Nav2 stack (delayed 15s for Gazebo to fully start) =====
    nav2_bringup = TimerAction(
        period=15.0,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(nav2_bringup_dir, 'launch', 'bringup_launch.py')
                ),
                launch_arguments={
                    'map': map_file,
                    'params_file': nav2_params,
                    'use_sim_time': 'true',
                }.items(),
            ),
        ]
    )

    # ===== 5. Publish initial pose repeatedly =====
    set_initial_pose = TimerAction(
        period=30.0,
        actions=[
            ExecuteProcess(
                cmd=['ros2', 'topic', 'pub', '--times', '10', '--rate', '0.2',
                     '/initialpose',
                     'geometry_msgs/PoseWithCovarianceStamped',
                     '{header: {frame_id: "map"}, pose: {pose: {position: {x: -5.0, y: 0.0, z: 0.0}, orientation: {w: 1.0}}}}'],
                output='screen',
            ),
        ]
    )

    # ===== 6. Foxglove Bridge =====
    foxglove_bridge = Node(
        package='foxglove_bridge',
        executable='foxglove_bridge',
        name='foxglove_bridge',
        parameters=[{
            'port': 8765,
            'address': '0.0.0.0',
            'send_buffer_limit': 10000000,
            'use_sim_time': True,
        }],
        output='screen',
    )

    return LaunchDescription([
        env_models,
        env_bcr_models,
        bcr_bot_launch,
        static_tf_map_odom,
        cmd_vel_relay,
        nav2_bringup,
        set_initial_pose,
        foxglove_bridge,
    ])