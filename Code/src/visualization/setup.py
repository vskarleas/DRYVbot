from setuptools import find_packages, setup

package_name = 'visualization'

setup(
    name=package_name,
    version='2.3.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', []),
        ('share/' + package_name + '/config', []),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='vskarleas',
    maintainer_email='vskarleas@icloud.com',
    description='Visualization and control interface. Provides a Foxglove web UI to monitor the robot in real-time, view the planned path, and select navigation goals.',
    license='MIT',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            # e.g.: 'goal_publisher = visualization.goal_publisher:main',
        ],
    },
)
