import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, ExecuteProcess, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    digital_twin_dir = get_package_share_directory('digital_twin')
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')
    bcr_bot_dir = get_package_share_directory('bcr_bot')

    map_file = os.path.join(digital_twin_dir, 'maps', 'warehouse_map.yaml')
    nav2_params = os.path.join(digital_twin_dir, 'config', 'nav2_params.yaml')

    # ===== 1. BCR_BOT in Gazebo Harmonic with warehouse world =====
    bcr_bot_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(bcr_bot_dir, 'launch', 'gz.launch.py')
        ),
        launch_arguments={
            'two_d_lidar_enabled': 'True',
            'camera_enabled': 'True',
            'world_file': 'small_warehouse.sdf',
        }.items(),
    )

    # ===== 2. Static TF: map -> odom (bypasses AMCL timing issues) =====
    static_tf_map_odom = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_tf_map_odom',
        arguments=['0', '0', '0', '0', '0', '0', 'map', 'odom'],
        output='screen',
    )

    # ===== 3. Nav2 stack (delayed 10s for Gazebo to be ready) =====
    nav2_bringup = TimerAction(
        period=10.0,
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

    # ===== 4. Auto initial pose (delayed 20s) =====
    set_initial_pose = TimerAction(
        period=20.0,
        actions=[
            ExecuteProcess(
                cmd=['ros2', 'topic', 'pub', '--once', '/initialpose',
                     'geometry_msgs/PoseWithCovarianceStamped',
                     '{header: {frame_id: "map"}, pose: {pose: {position: {x: 0.0, y: 0.0, z: 0.0}, orientation: {w: 1.0}}}}'],
                output='screen',
            ),
        ]
    )

    # ===== 5. Retry initial pose (delayed 25s) =====
    set_initial_pose_retry = TimerAction(
        period=25.0,
        actions=[
            ExecuteProcess(
                cmd=['ros2', 'topic', 'pub', '--once', '/initialpose',
                     'geometry_msgs/PoseWithCovarianceStamped',
                     '{header: {frame_id: "map"}, pose: {pose: {position: {x: 0.0, y: 0.0, z: 0.0}, orientation: {w: 1.0}}}}'],
                output='screen',
            ),
        ]
    )

    # ===== 6. cmd_vel relay: Nav2 -> robot =====
    cmd_vel_relay = Node(
        package='topic_tools',
        executable='relay',
        name='cmd_vel_relay',
        arguments=['/cmd_vel', '/bcr_bot/cmd_vel'],
        output='screen',
    )

    # ===== 7. Foxglove Bridge =====
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
        bcr_bot_launch,
        static_tf_map_odom,
        cmd_vel_relay,
        nav2_bringup,
        set_initial_pose,
        set_initial_pose_retry,
        foxglove_bridge,
    ])