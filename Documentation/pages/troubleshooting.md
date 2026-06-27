# Troubleshooting

This page documents the significant issues encountered during the development of CloudTwin and how they were resolved. These are listed in order of severity and frequency.

---

## Gazebo Classic vs Gazebo Harmonic

**Problem:** The project initially used Gazebo Harmonic (gz-tools2), but the hospital world file was incompatible. Models failed to load, plugins were not found, and the simulation was unstable.

**Solution:** Migrated to Gazebo Classic 11. This required:

- Installing `ros-humble-gazebo-ros-pkgs` instead of `ros-humble-ros-gzharmonic`
- Removing all Harmonic packages: `sudo apt remove gz-harmonic gz-tools2 ros-humble-ros-gzharmonic*`
- The two versions **cannot coexist** on the same system
- Gazebo Classic requires explicit plugin declarations in world SDF files: `libgazebo_ros_factory.so` for spawn/delete, `libgazebo_ros_state.so` for get/set state
- Mesh-based models must use `model://` URI, not inlined SDF strings

---

## use_sim_time must be set on all nodes

**Problem:** Some nodes were publishing transforms using wall-clock time while Nav2 and Gazebo used simulation time. This caused TF lookups to fail with "transform extrapolation into the future" errors, and the entire navigation stack broke silently.

**Solution:** Every node must have `use_sim_time: True`, including static TF publishers:

```python
static_tf_map_odom = Node(
    package='tf2_ros',
    executable='static_transform_publisher',
    parameters=[{'use_sim_time': True}],  # This is critical
)
```

Missing `use_sim_time` on even one node causes wall-clock/sim-time TF mismatches that break the entire nav stack.

---

## Nav2 TF timing race conditions

**Problem:** Nav2 nodes would crash at startup with "Could not transform" errors, even though all transforms were being published. The issue was a race condition: Nav2 started requesting transforms before the simulation clock had propagated.

**Solution:** Set `transform_tolerance: 5.0` throughout `nav2_params.yaml` for all components that perform TF lookups. This gives the system a 5-second window to stabilise transforms at startup.

---

## ROS_DOMAIN_ID isolation

**Problem:** On the ÉTS campus network, other students running ROS2 on default domain 0 injected foreign transforms into our TF tree. This caused the robot's localisation to jump randomly, and multiple map frames appeared.

**Solution:** Set a unique domain ID before launching:

```bash
export ROS_DOMAIN_ID=42  # Any unique number 0-232
```

Add this to `~/.bashrc` to make it persistent.

---

## Map mismatch between nodes

**Problem:** The navigation logic nodes were loading `corridors_map.yaml` (278×237 pixels, ~14×12m) while Nav2 was using `hospital_map.yaml` (501×1127 pixels, ~25×56m). The crowd monitor was computing density positions relative to the wrong map, so the Gaussian blobs appeared in completely wrong locations. This caused no visible errors — just silently wrong behaviour.

**Solution:** All nodes that load or reference a map must use the **exact same map file**. In `logic_params.yaml`, the `map_yaml_path` parameter was corrected to point to `hospital_map.yaml`. For the current architecture, `crowd_monitor` subscribes to `/map` from map_server (avoiding this issue entirely) instead of loading the map file directly.

---

## ROS2 Humble SIGINT shutdown crash

**Problem:** Python nodes using `try/except KeyboardInterrupt` would crash on Ctrl+C with:

```
rclpy._rclpy_pybind11.RCLError: failed to shutdown: rcl_shutdown already called
```

ROS2 Humble destroys the context before Python raises `KeyboardInterrupt`, so by the time `finally` runs and calls `rclpy.shutdown()`, the context is already dead.

**Solution:** Use `signal.signal(SIGINT, handler)` to intercept the signal before ROS2 destroys the context:

```python
import signal
import sys

def main(args=None):
    rclpy.init(args=args)
    node = MyNode()

    def _shutdown(sig, frame):
        node.get_logger().info('Shutting down')
        node.destroy_node()
        rclpy.shutdown()
        sys.exit(0)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        rclpy.spin(node)
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()
```

This pattern is used in all Python nodes: `crowd_monitor.py`, `room_interpreter.py`, `speech_node.py`.

---

## bcr_bot namespaced topics

**Problem:** bcr_bot publishes all its topics under the `/bcr_bot/` namespace (e.g., `/bcr_bot/scan`, `/bcr_bot/odom`, `/bcr_bot/cmd_vel`). Subscribing to `/odom` or `/scan` without the prefix produced no data.

**Solution:** Always use the fully namespaced topic names. The most common ones:

- `/bcr_bot/scan` (LaserScan)
- `/bcr_bot/odom` (Odometry)
- `/bcr_bot/cmd_vel` (velocity commands to the robot)

A `cmd_vel_relay` node bridges Nav2's `/cmd_vel` to `/bcr_bot/cmd_vel`.

---

## bcr_bot must not be modified

**Problem:** Early attempts to modify bcr_bot's launch files to fix namespace issues introduced bugs and broke the robot description.

**Solution:** bcr_bot is a correctly functioning dependency. Never modify it and configure around it using relays and remappings in your own launch files.

---

## Foxglove goal pose timestamp mismatch

**Problem:** Goals published from Foxglove's 3D panel used wall-clock timestamps. Nav2 rejected them because it expected simulation-time timestamps (which start from 0 when Gazebo launches).

**Solution:** A `goal_relay` node subscribes to `/goal_pose_foxglove`, resets the timestamp to zero, and republishes on `/goal_pose`:

```python
goal.header.stamp.sec = 0
goal.header.stamp.nanosec = 0
```

---

## Costmap inflation filling narrow doors

**Problem:** Nav2's inflation radius was too large, inflating lethal cells until they filled the hospital's narrow doorways. The robot could not plan a path through any door.

**Solution:** Reduce the inflation radius and increase `cost_scaling_factor` in `nav2_params.yaml`:

```yaml
inflation_layer:
  inflation_radius: 0.3          # reduced from default 0.55
  cost_scaling_factor: 5.0       # steeper cost dropoff
```

This keeps a safety margin around walls without blocking doorways.

---

## NumPy float32 JSON serialisation

**Problem:** Publishing diagnostic data containing NumPy `float32` values crashed with `TypeError: Object of type float32 is not JSON serializable`.

**Solution:** Explicitly cast NumPy types to Python native types before serialisation:

```python
float(numpy_value)
int(numpy_value)
bool(numpy_value)
```

---

## PortAudio library not found

**Problem:** The speech_node crashed on import with `OSError: PortAudio library not found` when using the `sounddevice` Python package.

**Solution:** Install the system library:

```bash
sudo apt install libportaudio2 portaudio19-dev
```

---

## Audio device selection

**Problem:** The speech_node recorded silence (RMS = 0.000000) even when speaking into the built-in microphone. The default audio device was not the correct input.

**Solution:** List devices and test each one:

```bash
python3 -c "import sounddevice; print(sounddevice.query_devices())"
```

On the HP ProBook, device 5 (`sof-hda-dsp: - (hw:0,7)`) was the correct input. Some devices also rejected 16kHz sample rate with "Invalid sample rate" errors. Set the correct `device_index` in `logic_params.yaml`.

---

## Web Speech API in Foxglove extensions

**Problem:** The Foxglove Room Command panel initially used the browser's Web Speech API for voice input. It failed with "speech error: network" because Chrome's Web Speech API sends audio to Google's servers, and Foxglove's extension sandbox blocks that network request. This affects both the web and desktop (Electron) versions.

**Solution:** Moved speech processing to a dedicated ROS2 node (`speech_node`) running on Ubuntu. The Foxglove panel sends a trigger message (`/speech_trigger`), the node records from the local microphone, transcribes with Whisper (local, no internet needed), and publishes the text to `/room_command`. This architecture keeps all audio processing local and avoids browser sandbox limitations.

---

## OccupancyGrid Y-axis inversion

**Problem:** The crowd density visualisation in Foxglove appeared mirrored vertically. Gaussian blobs were in the correct X position but inverted in Y.

**Solution:** The `_world_to_grid` coordinate transform was incorrectly inverting the Y axis. The fix was to compute `row` directly:

```python
row = int((wy - info.origin.position.y) / info.resolution)
```

without negating or subtracting from `height`. ROS2 OccupancyGrid origin is at the bottom-left, and row 0 corresponds to the minimum Y value.
