# gazebo_world.launch.py
# This launch file starts the Gazebo simulator with the specified world corridors.sdf file

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, ExecuteProcess
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():

    # Paths
    robot_sim_dir = get_package_share_directory('robot_simulation')
    world_file = os.path.join(robot_sim_dir, 'worlds', 'corridors.world')
    turtlebot3_gazebo_dir = get_package_share_directory('turtlebot3_gazebo')
    model_sdf = os.path.join(turtlebot3_gazebo_dir, 'models','turtlebot3_waffle_pi', 'model.sdf')

    # TurtleBot3 model
    os.environ['TURTLEBOT3_MODEL'] = 'waffle_pi'
 
    # Gazebo needs to find TurtleBot3 meshes and models
    gazebo_models = os.path.join(turtlebot3_gazebo_dir, 'models')
    os.environ['GAZEBO_MODEL_PATH'] = gazebo_models + ':' + \
        os.environ.get('GAZEBO_MODEL_PATH', '')
 
    # Launch Gazebo server with our custom corridor world
    gazebo_server = ExecuteProcess(
        cmd=['gzserver', '--verbose', world_file,
             '-s', 'libgazebo_ros_init.so',
             '-s', 'libgazebo_ros_factory.so'],
        output='screen',
    )
 
    # Launch Gazebo GUI client
    gazebo_client = ExecuteProcess(
        cmd=['gzclient'],
        output='screen',
    )
 
    # Publish the robot URDF via robot_state_publisher (needed for TF)
    robot_state_publisher = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(turtlebot3_gazebo_dir, 'launch',
                         'robot_state_publisher.launch.py')
        ),
        launch_arguments={'use_sim_time': 'true'}.items(),
    )
 
    # Spawn TurtleBot3 using the SDF model file (includes Gazebo plugins)
    spawn_robot = ExecuteProcess(
        cmd=['ros2', 'run', 'gazebo_ros', 'spawn_entity.py',
             '-entity', 'turtlebot3_waffle_pi',
             '-file', model_sdf,
             '-x', '-5.0', '-y', '0.0', '-z', '0.01'],
        output='screen',
    )

    return LaunchDescription([
        gazebo_server,
        gazebo_client,
        robot_state_publisher,
        spawn_robot
    ])