import os
from os.path import join
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess, TimerAction,
    IncludeLaunchDescription, AppendEnvironmentVariable,
    SetEnvironmentVariable
)
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory




def generate_launch_description():
    digital_twin_dir = get_package_share_directory('digital_twin')
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')
    bcr_bot_dir = get_package_share_directory('bcr_bot')
    gazebo_ros_dir = get_package_share_directory('gazebo_ros')
    robot_simulation_dir = get_package_share_directory('robot_simulation')

    map_file = os.path.join(digital_twin_dir, 'maps', 'hospital_map.yaml')
    nav2_params = os.path.join(digital_twin_dir, 'config', 'nav2_params.yaml')
    hospital_world = join(robot_simulation_dir, 'worlds', 'hospital.world')
    models_path = join(robot_simulation_dir, 'models')

    # ===== Environment: model paths for Gazebo Classic =====
    env_models = AppendEnvironmentVariable(
        name='GAZEBO_MODEL_PATH',
        value=models_path)
    env_bcr_models = AppendEnvironmentVariable(
        name='GAZEBO_MODEL_PATH',
        value=join(bcr_bot_dir, "models"))
    env_gazebo_resources = SetEnvironmentVariable(
        name='GAZEBO_RESOURCE_PATH',
        value="/usr/share/gazebo-11:" + join(bcr_bot_dir, "worlds"))
    
    # ===== Launch arguments for obstacles =====
    enable_obstacles = LaunchConfiguration('enable_obstacles')
    obstacle_scenario = LaunchConfiguration('obstacle_scenario')

    declare_enable_obstacles = DeclareLaunchArgument(
        'enable_obstacles',
        default_value='true',
        description='Enable dynamic obstacle spawning.'
    )
    declare_obstacle_scenario = DeclareLaunchArgument(
        'obstacle_scenario',
        default_value='hospital',
        description='Obstacle scenario to use: hospital or corridors.'
    )

    # ===== 1a. Gazebo (with force_system DISABLED to prevent X4 drone) =====
    gazebo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            join(gazebo_ros_dir, 'launch', 'gazebo.launch.py')
        ),
        launch_arguments={
            'world': hospital_world,
            'force_system': 'false',
        }.items(),
    )

    # ===== 1b. Spawn BCR_BOT into the running Gazebo =====
    spawn_bcr_bot = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            join(bcr_bot_dir, 'launch', 'bcr_bot_gazebo_spawn.launch.py')
        ),
        launch_arguments={
            'two_d_lidar_enabled': 'True',
            'camera_enabled': 'True',
            'position_x': '0.0',
            'position_y': '2.0',
            'use_sim_time': 'true',
        }.items(),
    )

    # ===== 2. Static TF: map -> odom =====
    static_tf_map_odom = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_tf_map_odom',
        arguments=['0', '0', '0', '0', '0', '0', 'map', 'odom'],
        parameters=[{'use_sim_time': True}],
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

    goal_relay = Node(
        package='digital_twin',
        executable='goal_relay',
        name='goal_relay',
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
                     '{header: {frame_id: "map"}, pose: {pose: {position: {x: 0.0, y: 2.0, z: 0.0}, orientation: {w: 1.0}}}}'],
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
            'asset_uri_allowlist': ['package://bcr_bot/**'],
        }],
        output='screen',
    )

    # ===== 7. Run obstacle spawner =====
    obstacle_spawner = TimerAction(
        period=20.0,
        actions=[
            ExecuteProcess(
                cmd=[
                    'python3',
                    os.path.join(
                        robot_simulation_dir,
                        'scripts',
                        'obstacle_spawner.py'
                    ),
                    '--ros-args',
                    '-p',
                    ['scenario:=', obstacle_scenario],
                ],
                condition=IfCondition(enable_obstacles),
                output='screen',
            )
        ]
    )

    return LaunchDescription([
        declare_enable_obstacles,
        declare_obstacle_scenario,
        env_models,
        env_bcr_models,
        env_gazebo_resources,
        gazebo_launch,
        spawn_bcr_bot,
        static_tf_map_odom,
        cmd_vel_relay,
        nav2_bringup,
        set_initial_pose,
        foxglove_bridge,
        goal_relay,
        obstacle_spawner,
    ])