#!/usr/bin/env bash
#
#
# 1. Lets you pick the obstacle scenario (emergency / normal / crowd).
# 2. Starts the delivery_optimization web app (Laravel + React) in the
#    background, logging to logs/web.log. It is stopped automatically when
#    you Ctrl+C the simulation.
# 3. Builds the ROS 2 workspace and launches the Gazebo simulation in the
#    foreground.
#
# Usage:
#   ./start.sh                # interactive scenario menu
#   ./start.sh emergency      # or: normal | crowd
#   NO_WEB=1 ./start.sh       # skip the web app, ROS only
#   RESET_DB=1 ./start.sh     # reset + seed the database, no prompt
#   RESET_DB=0 ./start.sh     # keep the existing database, no prompt
#
# Dependencies are installed by ./installation.sh.

set -e

# Run from the script's own directory.
cd "$(dirname "$0")"
ROOT_DIR="$(pwd)"
WS_DIR="$ROOT_DIR/Code"
WEB_DIR="$WS_DIR/src/delivery_optimization"
LOG_DIR="$ROOT_DIR/logs"

# ---------------------------------------------------------------------------
# 1. Scenario selection
# ---------------------------------------------------------------------------
SCENARIO="${1:-}"
valid_scenario() { case "$1" in emergency|normal|crowd|fixed) return 0 ;; *) return 1 ;; esac; }

if ! valid_scenario "$SCENARIO"; then
    echo "Select the obstacle scenario:"
    echo "  1) emergency  (default) - 8 humans on emergency routes, gather then disperse"
    echo "  2) normal               - 10 humans on patrol loops"
    echo "  3) crowd                - 18 humans, wider coverage"
    echo "  4) fixed (simple)       - original obstacle_spawner.py, default launch"
    read -rp "Choice [1-4]: " choice
    case "$choice" in
        2) SCENARIO=normal ;;
        3) SCENARIO=crowd ;;
        4) SCENARIO=fixed ;;
        *) SCENARIO=emergency ;;
    esac
fi
echo "==> Scenario: $SCENARIO"

# ---------------------------------------------------------------------------
# 2. Web app (Laravel + React) in the background
# ---------------------------------------------------------------------------
WEB_PID=""
cleanup() {
    if [ -n "$WEB_PID" ] && kill -0 "$WEB_PID" 2>/dev/null; then
        echo
        echo "==> Stopping web app (PID $WEB_PID) ..."
        kill "$WEB_PID" 2>/dev/null || true
        pkill -P "$WEB_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

if [ "${NO_WEB:-0}" = "1" ]; then
    echo "==> NO_WEB=1 set; skipping web app."
elif command -v php >/dev/null 2>&1 && command -v composer >/dev/null 2>&1 && [ -d "$WEB_DIR/vendor" ]; then
    mkdir -p "$LOG_DIR"
    WEB_LOG="$LOG_DIR/web.log"

    # -----------------------------------------------------------------------
    # Optional database reset + seed.
    # "Reset" drops every table, re-runs the migrations, and re-seeds the
    # default users, rooms and medications (a clean, empty-of-orders state).
    # "Keep" leaves the existing database (orders, plans, ...) untouched.
    # Pre-set RESET_DB=1 / RESET_DB=0 to skip the prompt.
    # -----------------------------------------------------------------------
    if [ -z "${RESET_DB:-}" ]; then
        read -rp "Reset and seed the database? This deletes all orders/plans and recreates default data. [y/N]: " db_choice
        case "$db_choice" in
            y|Y|yes|YES) RESET_DB=1 ;;
            *)           RESET_DB=0 ;;
        esac
    fi

    if [ "${RESET_DB:-0}" = "1" ]; then
        echo "==> Resetting and seeding the database ..."
        ( cd "$WEB_DIR" && php artisan migrate:fresh --seed --force ) \
            || echo "==> WARNING: database reset/seed failed (continuing)."
    else
        echo "==> Keeping the existing database (no reset/seed)."
    fi

    echo "==> Starting delivery_optimization web app (logs: $WEB_LOG)"
    ( cd "$WEB_DIR" && composer run dev ) > "$WEB_LOG" 2>&1 &
    WEB_PID=$!
    echo "    Web app PID: $WEB_PID"
    echo "    Laravel: http://localhost:8000   Vite dev server: http://localhost:5173"
else
    echo "==> WARNING: web app dependencies missing. Run ./installation.sh first."
    echo "    Continuing with the ROS simulation only."
fi

# ---------------------------------------------------------------------------
# 3. Build and launch the ROS 2 simulation (foreground)
# ---------------------------------------------------------------------------
# VS Code installed through Snap exports GTK/GIO paths from its Core20 runtime.
# Native ROS/Qt applications such as RViz must use the host Ubuntu libraries.
if [ "${SNAP_NAME:-}" = "code" ]; then
    echo "==> Cleaning VS Code Snap environment for ROS/RViz"

    if [ -n "${XDG_DATA_DIRS_VSCODE_SNAP_ORIG:-}" ]; then
        export XDG_DATA_DIRS="$XDG_DATA_DIRS_VSCODE_SNAP_ORIG"
    else
        export XDG_DATA_DIRS="/usr/share/ubuntu:/usr/local/share:/usr/share:/var/lib/snapd/desktop"
    fi

    unset GIO_MODULE_DIR
    unset GTK_PATH GTK_EXE_PREFIX GTK_IM_MODULE_FILE
    unset GDK_PIXBUF_MODULEDIR GDK_PIXBUF_MODULE_FILE
    unset GSETTINGS_SCHEMA_DIR LOCPATH XDG_DATA_HOME
fi

# shellcheck disable=SC1091
source /opt/ros/humble/setup.bash

cd "$WS_DIR"
rm -rf build/ install/ log/
colcon build
# shellcheck disable=SC1091
source install/setup.bash

if [ "$SCENARIO" = "fixed" ]; then
    # Simple/default launch: original obstacle_spawner.py (obstacle_mode:=fixed)
    ros2 launch digital_twin simulation.launch.py \
        obstacle_mode:=fixed
else
    ros2 launch digital_twin simulation.launch.py \
        obstacle_mode:=random \
        random_obstacle_scenario:="$SCENARIO"
fi
