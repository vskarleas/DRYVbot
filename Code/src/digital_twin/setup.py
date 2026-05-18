from setuptools import find_packages, setup

package_name = 'digital_twin'

setup(
    name=package_name,
    version='2.3.0',
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
    description='Digital Twin of our robot for optimized path planning and decision making',
    license='MIT',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            # 'planner_node = digital_twin.planner_node:main',
            # 'replanner_node = digital_twin.replanner_node:main',
        ],
    },
)
