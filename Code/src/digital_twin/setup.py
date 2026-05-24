from setuptools import find_packages, setup

package_name = 'digital_twin'

setup(
    name=package_name,
    version='3.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/maps', [
            'maps/corridors_map.pgm',
            'maps/corridors_map.yaml',
            'maps/hospital_map.pgm',
            'maps/hospital_map.yaml',
        ]),
        ('share/' + package_name + '/config', [
            'config/nav2_params.yaml',
        ]),
        ('share/' + package_name + '/launch', [
            'launch/corridors.launch.py',
            'launch/hospital.launch.py',
        ]),
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
        ],
    },
)