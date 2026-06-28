#!/usr/bin/env bash
#
#
# Installs everything needed to run the project:
#   * ROS 2 Humble system packages (Gazebo, Nav2, SLAM, Foxglove bridge, ...)
#   * Python dependencies for the AI layer (faster-whisper, sounddevice, ...)
#   * bcr_bot robot package (cloned into Code/src if missing)
#   * PHP 8.3 + extensions and Composer (for the delivery_optimization web app)
#   * Composer / npm dependencies and .env / database setup for the web app
#
# Anything already present is detected and skipped. Re-run it safely at any time.
#
# It does NOT install ROS 2 Humble itself. If ROS 2 is missing, follow:
#   https://foxglove.dev/blog/installing-ros2-humble-on-ubuntu

set -u

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
WS_DIR="$ROOT_DIR/Code"
SRC_DIR="$WS_DIR/src"
WEB_DIR="$SRC_DIR/delivery_optimization"
ROS_DISTRO="humble"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}==>${NC} $*"; }
ok()    { echo -e "${GREEN}  ✓${NC} $*"; }
warn()  { echo -e "${YELLOW}  !${NC} $*"; }
err()   { echo -e "${RED}  ✗${NC} $*"; }
section(){ echo; echo -e "${BLUE}########## $* ##########${NC}"; }

SUDO=""
if [ "$(id -u)" -ne 0 ]; then SUDO="sudo"; fi

# Collect apt packages that are not yet installed, then install them in one go.
apt_install_missing() {
    local missing=()
    local pkg
    for pkg in "$@"; do
        if dpkg -s "$pkg" >/dev/null 2>&1; then
            ok "$pkg already installed"
        else
            missing+=("$pkg")
        fi
    done
    if [ "${#missing[@]}" -gt 0 ]; then
        info "Installing: ${missing[*]}"
        $SUDO apt-get install -y "${missing[@]}"
    fi
}

# ---------------------------------------------------------------------------
# 0. Sanity checks
# ---------------------------------------------------------------------------
section "Environment checks"
if [ ! -d "/opt/ros/$ROS_DISTRO" ]; then
    warn "ROS 2 $ROS_DISTRO not found at /opt/ros/$ROS_DISTRO."
    warn "Install it first: https://foxglove.dev/blog/installing-ros2-humble-on-ubuntu"
    warn "Continuing with the rest of the setup, but ROS launching will not work."
else
    ok "ROS 2 $ROS_DISTRO detected"
fi

info "Updating apt package index"
$SUDO apt-get update -y

# ---------------------------------------------------------------------------
# 1. ROS 2 system packages
# ---------------------------------------------------------------------------
section "ROS 2 system packages"
apt_install_missing \
    ros-$ROS_DISTRO-gazebo-ros-pkgs \
    ros-$ROS_DISTRO-gazebo-ros \
    ros-$ROS_DISTRO-navigation2 \
    ros-$ROS_DISTRO-nav2-bringup \
    ros-$ROS_DISTRO-slam-toolbox \
    ros-$ROS_DISTRO-foxglove-bridge \
    python3-colcon-common-extensions \
    ros-$ROS_DISTRO-teleop-twist-keyboard \
    ros-$ROS_DISTRO-topic-tools \
    ros-$ROS_DISTRO-tf2-ros \
    ros-$ROS_DISTRO-xacro \
    python3-rosdep \
    libportaudio2 \
    portaudio19-dev \
    git curl unzip

# ---------------------------------------------------------------------------
# 2. Python dependencies (Navigation layer)
# ---------------------------------------------------------------------------
section "Python dependencies (Navigation layer)"
PY_PKGS=(faster-whisper sounddevice numpy pyyaml websockets)
MISSING_PY=()
for mod in faster_whisper sounddevice numpy yaml websockets; do
    if python3 -c "import $mod" >/dev/null 2>&1; then
        ok "python module '$mod' available"
    else
        MISSING_PY+=("$mod")
    fi
done
if [ "${#MISSING_PY[@]}" -gt 0 ]; then
    info "Installing Python packages: ${PY_PKGS[*]}"
    pip install "${PY_PKGS[@]}" --break-system-packages
fi

# ---------------------------------------------------------------------------
# 3. rosdep + bcr_bot
# ---------------------------------------------------------------------------
section "ROS dependencies and bcr_bot"
if [ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]; then
    info "Initialising rosdep"
    $SUDO rosdep init || warn "rosdep already initialised"
fi
rosdep update || warn "rosdep update failed (continuing)"

if [ ! -d "$SRC_DIR/bcr_bot" ]; then
    info "Cloning bcr_bot into $SRC_DIR"
    git clone https://github.com/blackcoffeerobotics/bcr_bot.git "$SRC_DIR/bcr_bot"
else
    ok "bcr_bot already present"
fi

if [ -d "/opt/ros/$ROS_DISTRO" ]; then
    info "Resolving ROS dependencies with rosdep"
    # ROS/ament setup scripts reference unset vars (e.g. AMENT_TRACE_SETUP_FILES),
    # which trip `set -u`. Relax it only while sourcing them.
    set +u
    # shellcheck disable=SC1090
    source "/opt/ros/$ROS_DISTRO/setup.bash"
    set -u
    rosdep install --from-paths "$SRC_DIR" --ignore-src -r -y || \
        warn "rosdep install reported issues (often safe to ignore)"
fi

# ---------------------------------------------------------------------------
# 4. PHP 8.4 + extensions (delivery_optimization web app)
# ---------------------------------------------------------------------------
# The web app's composer.lock is resolved on PHP 8.4 (some locked deps, e.g.
# symfony/clock, require php >= 8.4.1), so 8.4 is the required baseline.
section "PHP 8.4 and extensions"
php_ok=false
if command -v php >/dev/null 2>&1; then
    PHP_VER="$(php -r 'echo PHP_MAJOR_VERSION.".".PHP_MINOR_VERSION;')"
    if php -r 'exit(PHP_VERSION_ID >= 80400 ? 0 : 1);'; then
        ok "PHP $PHP_VER detected (>= 8.4)"
        php_ok=true
    else
        warn "PHP $PHP_VER is too old (need >= 8.4); installing PHP 8.4"
    fi
fi

if [ "$php_ok" = false ]; then
    if ! grep -rq "ondrej/php" /etc/apt/sources.list.d/ 2>/dev/null; then
        info "Adding ondrej/php PPA (provides PHP 8.4 on Ubuntu 22.04)"
        apt_install_missing software-properties-common
        $SUDO add-apt-repository -y ppa:ondrej/php
        $SUDO apt-get update -y
    fi
    apt_install_missing \
        php8.4-cli \
        php8.4-common \
        php8.4-mbstring \
        php8.4-xml \
        php8.4-curl \
        php8.4-zip \
        php8.4-gd \
        php8.4-sqlite3 \
        php8.4-bcmath \
        php8.4-intl

    # Make php8.4 the default `php` so `php artisan` (and the Vite build) use it.
    if [ -x /usr/bin/php8.4 ]; then
        $SUDO update-alternatives --set php /usr/bin/php8.4 >/dev/null 2>&1 || true
    fi
fi

# ---------------------------------------------------------------------------
# 5. Composer
# ---------------------------------------------------------------------------
section "Composer"
if command -v composer >/dev/null 2>&1; then
    ok "Composer already installed ($(composer --version 2>/dev/null | head -1))"
else
    info "Installing Composer to /usr/local/bin/composer"
    EXPECTED_SIG="$(curl -fsSL https://composer.github.io/installer.sig)"
    php -r "copy('https://getcomposer.org/installer', '/tmp/composer-setup.php');"
    ACTUAL_SIG="$(php -r "echo hash_file('sha384', '/tmp/composer-setup.php');")"
    if [ "$EXPECTED_SIG" != "$ACTUAL_SIG" ]; then
        err "Composer installer signature mismatch; aborting Composer install"
        rm -f /tmp/composer-setup.php
    else
        php /tmp/composer-setup.php --install-dir=/tmp --filename=composer
        $SUDO mv /tmp/composer /usr/local/bin/composer
        rm -f /tmp/composer-setup.php
        ok "Composer installed"
    fi
fi

# ---------------------------------------------------------------------------
# 6. Node.js / npm
# ---------------------------------------------------------------------------
section "Node.js / npm"
if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    NODE_VER="$(node -v 2>/dev/null | sed 's/^v//')"
    if printf '%s
' "$NODE_VER" | grep -Eq '^[0-9]+(\.[0-9]+){0,2}$' && [ "$(printf '%s
' "$NODE_VER" | awk -F. '{printf "%d%02d%02d", $1,$2,$3}')" -ge 20000 ]; then
        ok "Node $(node -v) and npm $(npm -v) detected"
    else
        warn "Node.js $(node -v 2>/dev/null || echo unknown) is older than required; installing Node 20+"
        info "Installing Node.js 20.x via NodeSource"
        curl -fsSL https://deb.nodesource.com/setup_20.x | $SUDO -E bash -
        apt_install_missing nodejs
    fi
else
    info "Installing Node.js 20.x via NodeSource"
    curl -fsSL https://deb.nodesource.com/setup_20.x | $SUDO -E bash -
    apt_install_missing nodejs
fi

# ---------------------------------------------------------------------------
# 7. Web application setup (delivery_optimization)
# ---------------------------------------------------------------------------
section "delivery_optimization web app setup"
if [ ! -d "$WEB_DIR" ]; then
    warn "$WEB_DIR not found; skipping web app setup"
elif ! command -v composer >/dev/null 2>&1; then
    warn "Composer unavailable; skipping web app setup"
else
    cd "$WEB_DIR"

    if [ ! -f vendor/autoload.php ]; then
        info "Installing PHP dependencies (composer install)"
        composer install || warn "composer install failed (check PHP version / extensions above)"
    else
        ok "PHP dependencies already installed (vendor/ present)"
    fi

    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            info "Creating .env from .env.example"
            cp .env.example .env
        else
            err "No .env.example found; cannot create .env. Provide one and re-run."
        fi
    else
        ok ".env already present"
    fi

    # The artisan-based steps need Composer dependencies to be installed.
    if [ -f .env ] && [ -f vendor/autoload.php ]; then
        if ! grep -qE '^APP_KEY=base64:' .env; then
            info "Generating application key"
            php artisan key:generate --force
        else
            ok "APP_KEY already set"
        fi

        # SQLite database file (default DB_CONNECTION=sqlite)
        if grep -qE '^DB_CONNECTION=sqlite' .env; then
            if [ ! -f database/database.sqlite ]; then
                info "Creating SQLite database file"
                touch database/database.sqlite
            else
                ok "SQLite database file already present"
            fi
        fi

        info "Running database migrations"
        php artisan migrate --force --graceful || warn "migrate reported issues"
    elif [ ! -f vendor/autoload.php ]; then
        warn "Skipping artisan setup: Composer dependencies (vendor/) are missing."
    fi

    if command -v npm >/dev/null 2>&1; then
        if [ ! -d node_modules ]; then
            info "Installing JS dependencies (npm install)"
            npm install
        else
            ok "JS dependencies already installed (node_modules/ present)"
        fi

        # The Vite build runs Wayfinder, which calls `php artisan` and therefore
        # needs vendor/. Skip the build (don't fail) if Composer deps are absent.
        if [ -f vendor/autoload.php ]; then
            info "Building front-end assets (npm run build)"
            npm run build || warn "npm run build reported issues"
        else
            warn "Skipping 'npm run build': Composer dependencies (vendor/) are missing."
        fi
    fi

    cd "$ROOT_DIR"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
section "Installation complete"
ok "All checks finished."
echo
echo "Next steps:"
echo "  * Review $WEB_DIR/.env (REVERB_HOST is currently a hard-coded LAN IP;"
echo "    set it to 'localhost' or this machine's IP, and make sure REVERB_PORT"
echo "    does not clash with the ROS WebSocket bridge on port 9090)."
echo "  * Launch everything with:   ./start.sh"
