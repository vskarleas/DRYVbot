from setuptools import find_packages, setup
from glob import glob
import os

package_name = 'digital_twin'

setup(
    name=package_name,
    version='3.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/maps', glob('maps/*')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
        ('share/' + package_name + '/launch', glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='vskarleas',
    maintainer_email='vskarleas@icloud.com',
    description='Digital Twin - Cloud-side Nav2 path planning for the robot',
    license='MIT',
    entry_points={
        'console_scripts': [
            'goal_relay = digital_twin.goal_relay:main',
            'crowd_monitor = digital_twin.crowd_monitor:main',
            'room_interpreter = digital_twin.room_interpreter:main',
            'speech_node = digital_twin.speech_node:main',
            'simulation_logger = digital_twin.simulation_logger:main',
            'ws_command_bridge = digital_twin.ws_command_bridge:main',
        ],
    },
)