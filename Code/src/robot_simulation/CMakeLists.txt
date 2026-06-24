cmake_minimum_required(VERSION 3.8)
project(robot_simulation)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)

install(PROGRAMS
  scripts/obstacle_spawner.py
  scripts/random_obstacle_spawner.py
  DESTINATION lib/${PROJECT_NAME}
)

install(FILES
  scripts/controlled_emergency_scenario.py
  scripts/controlled_patrol_scenarios.py
  scripts/random_obstacle_core.py
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY
  worlds
  models
  maps
  config
  scripts
  DESTINATION share/${PROJECT_NAME}
  PATTERN "__pycache__" EXCLUDE
  PATTERN "*.pyc" EXCLUDE
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # the following line skips the linter which checks for copyrights
  # comment the line when a copyright and license is added to all source files
  set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # comment the line when this package is in a git repo and when
  # a copyright and license is added to all source files
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()

  find_package(ament_cmake_pytest REQUIRED)
  # Ignore unrelated user-site pytest plugins when detecting/running this test.
  set(ENV{PYTEST_DISABLE_PLUGIN_AUTOLOAD} "1")
  ament_add_pytest_test(
    random_obstacle_tests
    test
    APPEND_ENV PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
  )
endif()

ament_package()
