import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess


def generate_launch_description():
    pkg_dir = get_package_share_directory('digital_twin_robot')
    world_file = os.path.join(pkg_dir, 'worlds', 'corridors.sdf')

    return LaunchDescription([
        ExecuteProcess(
            cmd=['ign', 'gazebo', world_file, '-v', '4'],
            output='screen',
        ),
    ])