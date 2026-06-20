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

    # ===== Launch arguments =====
    enable_rviz = LaunchConfiguration('enable_rviz')
    enable_obstacles = LaunchConfiguration('enable_obstacles')
    obstacle_scenario = LaunchConfiguration('obstacle_scenario')

    enable_telemetry = LaunchConfiguration('enable_telemetry')

    enable_test_goal = LaunchConfiguration('enable_test_goal')
    goal_x = LaunchConfiguration('goal_x')
    goal_y = LaunchConfiguration('goal_y')
    goal_z = LaunchConfiguration('goal_z')
    goal_delay_sec = LaunchConfiguration('goal_delay_sec')

    declare_enable_rviz = DeclareLaunchArgument(
        'enable_rviz',
        default_value='true',
        description='Enable RViz2 for Nav2 visualization.'
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
        description='Enable simulation logger.'
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
        ),
        launch_arguments={
            'enable_obstacles': enable_obstacles,
            'obstacle_scenario': obstacle_scenario,
        }.items(),
    )

    # ===== 2. Digital twin logic =====
    logic_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(digital_twin_dir, 'launch', 'logic.launch.py')
        ),
        launch_arguments={
            'enable_sim_logger': enable_telemetry,
            'enable_ws_bridge': 'true',
        }.items(),
    )

    # ===== 3. Optional automatic test goal =====
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
    # ===== 4. RViz2 for Nav2 =====
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
        logic_launch,
        rviz2,
        test_goal,
    ])
