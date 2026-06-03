import os

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    TimerAction,
    ExecuteProcess,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    digital_twin_dir = get_package_share_directory('digital_twin')
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')
    robot_simulation_dir = get_package_share_directory('robot_simulation')

    # ===== Launch arguments =====
    target_url = LaunchConfiguration('target_url')
    send_frequency_hz = LaunchConfiguration('send_frequency_hz')
    enable_rviz = LaunchConfiguration('enable_rviz')
    enable_obstacles = LaunchConfiguration('enable_obstacles')
    obstacle_scenario = LaunchConfiguration('obstacle_scenario')

    enable_telemetry = LaunchConfiguration('enable_telemetry')

    enable_test_goal = LaunchConfiguration('enable_test_goal')
    goal_x = LaunchConfiguration('goal_x')
    goal_y = LaunchConfiguration('goal_y')
    goal_z = LaunchConfiguration('goal_z')
    goal_delay_sec = LaunchConfiguration('goal_delay_sec')

    declare_target_url = DeclareLaunchArgument(
        'target_url',
        default_value='',
        description='Target URL for telemetry export. If empty, JSON is printed in terminal.'
    )
    declare_enable_rviz = DeclareLaunchArgument(
        'enable_rviz',
        default_value='true',
        description='Enable RViz2 for Nav2 visualization.'
    )
    declare_send_frequency_hz = DeclareLaunchArgument(
        'send_frequency_hz',
        default_value='1.0',
        description='Telemetry sending frequency in Hz.'
    )

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

    declare_enable_telemetry = DeclareLaunchArgument(
        'enable_telemetry',
        default_value='true',
        description='Enable telemetry exporter.'
    )

    declare_enable_test_goal = DeclareLaunchArgument(
        'enable_test_goal',
        default_value='false',
        description='Automatically publish a test goal after startup.'
    )

    declare_goal_x = DeclareLaunchArgument(
        'goal_x',
        default_value='3.0',
        description='Test goal x position in map frame.'
    )

    declare_goal_y = DeclareLaunchArgument(
        'goal_y',
        default_value='0.0',
        description='Test goal y position in map frame.'
    )

    declare_goal_z = DeclareLaunchArgument(
        'goal_z',
        default_value='0.0',
        description='Test goal z position in map frame.'
    )

    declare_goal_delay_sec = DeclareLaunchArgument(
        'goal_delay_sec',
        default_value='35.0',
        description='Delay before publishing the test goal.'
    )

    # ===== 1. Existing hospital system =====
    hospital_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(digital_twin_dir, 'launch', 'hospital.launch.py')
        )
    )

    
    # ===== 2. Dynamic obstacles =====
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

    # ===== 3. Telemetry exporter =====
    telemetry_exporter = TimerAction(
        period=12.0,
        actions=[
            Node(
                package='digital_twin',
                executable='telemetry_exporter',
                name='telemetry_exporter',
                parameters=[{
                    'target_url': target_url,
                    'send_frequency_hz': send_frequency_hz,
                    'frame_id': 'map',
                    'odom_topic': '/bcr_bot/odom',
                    'cmd_vel_topic': '/cmd_vel',
                    'plan_topic': '/plan',
                    'goal_topic': '/goal_pose',
                    'obstacles_topic': '/people_positions',
                    'clock_topic': '/clock',
                    'trajectory_history_size': 100,
                    'max_plan_points': 150,
                    'obstacle_on_path_threshold_m': 0.75,
                    'base_path_weight': 1.0,
                    'obstacle_weight_increment': 0.25,
                }],
                condition=IfCondition(enable_telemetry),
                output='screen',
            )
        ]
    )

    # ===== 4. Optional automatic test goal =====
    test_goal = TimerAction(
        period=goal_delay_sec,
        actions=[
            ExecuteProcess(
                cmd=[
                    'ros2',
                    'topic',
                    'pub',
                    '--once',
                    '/goal_pose',
                    'geometry_msgs/PoseStamped',
                    [
                        '{header: {frame_id: "map"}, pose: {position: {x: ',
                        goal_x,
                        ', y: ',
                        goal_y,
                        ', z: ',
                        goal_z,
                        '}, orientation: {w: 1.0}}}'
                    ],
                ],
                condition=IfCondition(enable_test_goal),
                output='screen',
            )
        ]
    )
        # ===== 5. RViz2 for Nav2 =====
    rviz_config_file = os.path.join(
        nav2_bringup_dir,
        'rviz',
        'nav2_default_view.rviz'
    )

    rviz2 = TimerAction(
        period=18.0,
        actions=[
            Node(
                package='rviz2',
                executable='rviz2',
                name='rviz2',
                arguments=['-d', rviz_config_file],
                parameters=[{
                    'use_sim_time': True,
                }],
                condition=IfCondition(enable_rviz),
                output='screen',
            )
        ]
    )


    return LaunchDescription([
        declare_target_url,
        declare_send_frequency_hz,

        declare_enable_obstacles,
        declare_obstacle_scenario,

        declare_enable_telemetry,
        declare_enable_rviz,

        declare_enable_test_goal,
        declare_goal_x,
        declare_goal_y,
        declare_goal_z,
        declare_goal_delay_sec,

        hospital_launch,
        obstacle_spawner,
        telemetry_exporter,
        rviz2,
        test_goal,
    ])