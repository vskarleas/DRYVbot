# Network connections (IP & ports)

This page explains **who connects to what, on which IP and port**, across the whole DRYVbot system. It exists because the project has two independent machines (or roles) that are easy to confuse:

- the **digital twin computer** : the only machine that runs **ROS 2** (Gazebo, Nav2, the navigation logic layer). It *opens* servers that everyone else
  connects to.
- the **web app computer** : runs the Laravel delivery dashboard. It does **not **need ROS 2, so it can be any computer on the network. Managers and pharmacy accounts use it through a browser.

A third, optional interface — **Foxglove** : is a technical IHM with its own purpose (live 3D visualisation and topic inspection). It talks to ROS directly and is independent from the web app.

> For the underlying digital-twin concept and feedback loop, see [architecture.md](architecture.md). For the navigation logic nodes behind the WebSocket commands, see [navigation_logic.md](navigation_logic.md). For the delivery optimizer that decides the order of commands, see [delivery_optimization.md](delivery_optimization.md).

---

## The two systems at a glance

```
        WEB APP COMPUTER (no ROS needed)          DIGITAL TWIN COMPUTER (runs ROS 2)
   ┌──────────────────────────────────────┐   ┌───────────────────────────────────────────┐
   │                                      │   │                                             │
   │  Laravel HTTP server      :8000  ◄───┼───┼── browser (manager / pharmacy)              │
   │  Laravel Reverb (WS)      :8080  ◄───┼───┼── browser (live UI updates)                 │
   │  Vite dev server          :5173      │   │                                             │
   │                                      │   │  ws_command_bridge (WS) :9090  ◄────────────┼── web app (send/observe commands)
   │  Laravel app ────────────────────────┼──►│  foxglove_bridge (WS)   :8765  ◄────────────┼── Foxglove IHM (technical)
   │     │  ws://<ROS_IP>:9090            │   │                                             │
   │     │  http://<PRED_IP>:8001         │   │  Prediction microservice (HTTP) :8001 ◄─────┼── web app (LightGBM travel-time)
   │     ▼                                │   │                                             │
   └──────────────────────────────────────┘   └───────────────────────────────────────────┘
```

If everything runs on a single machine, every `<..._IP>` below is simply `localhost` / `127.0.0.1`. On a real multi-machine LAN, replace each placeholder with the LAN IP of the machine that *opens* that port.

---

## Ports opened by the DIGITAL TWIN computer (ROS2 side)

These servers are started by the ROS launch files. Everything that is not on the ROS machine connects *to* these.

| Service                            | Port     | Protocol    | Opened by                                                                  | Who connects                                  | Purpose                                                                                                                                                                                     |
| ---------------------------------- | -------- | ----------- | -------------------------------------------------------------------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **WebSocket command bridge** | `9090` | `ws://`   | `ws_command_bridge` node (in `logic.launch.py`)                        | Laravel web app, standalone Python client     | Send`room_command` / `list_rooms` / `get_status`; receive `ack` / `status` / `feedback`. **This is the bridge that lets a non-ROS computer drive and observe the robot.** |
| **Foxglove bridge**          | `8765` | `ws://`   | `foxglove_bridge` (in `hospital.launch.py` / `simulation.launch.py`) | Foxglove Studio (app.foxglove.dev or desktop) | Stream all ROS 2 topics for live 3D visualisation and the Room Command panel.                                                                                                               |
| **Prediction microservice**  | `8001` | `http://` | LightGBM service (separate Python process, can live on its own host)       | Laravel web app                               | `POST /predict` → returns `predicted_duration_s` for the delivery optimizer.                                                                                                           |

Notes:

- Port `9090` is configurable with the `ws_port` launch argument, and the bridge can be disabled entirely:

  ```bash
  ros2 launch digital_twin logic.launch.py ws_port:=8080
  ros2 launch digital_twin logic.launch.py enable_ws_bridge:=false
  ```
- The bridge listens on all interfaces, so any computer on the network can reach `ws://<ROS_MACHINE_IP>:9090` **without ROS installed**. On connect, the server immediately pushes the current navigation state. See the WebSocket message contract in the [README](../../README.md) ("Websocket for communication…").
- The prediction service is logically separate from ROS; its default address is `http://172.30.0.20:8001` (env `PREDICTION_SERVICE_URL`). It may run on the digital twin computer, the web app computer, or a dedicated host.

---

## Ports opened by the WEB APP computer (Laravel side)

Started together by `composer run dev` (which `start.sh` launches in the
background).

| Service                   | Port     | Protocol    | Process                      | Who connects                                           | Purpose                                                                                          |
| ------------------------- | -------- | ----------- | ---------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| **Laravel HTTP**    | `8000` | `http://` | `php artisan serve`        | Manager & pharmacy browsers                            | The dashboard UI — open`http://<WEBAPP_IP>:8000` to log in and create / supervise deliveries. |
| **Laravel Reverb**  | `8080` | `ws://`   | `php artisan reverb:start` | The same browser (via`laravel-echo` + `pusher-js`) | Pushes real-time UI updates (order status, optimised sequence) to the open page.                 |
| **Vite dev server** | `5173` | `http://` | `npm run dev`              | The browser (dev builds only)                          | Hot-module reload for the React front end during development.                                    |

Notes:

- Reverb's port comes from `REVERB_PORT` (`.env`, default `8080`); the browser client uses `VITE_REVERB_HOST` / `VITE_REVERB_PORT`. On a multi-machine setup these **must point at the web app computer's LAN IP**, not `127.0.0.1`, or the browser cannot reach Reverb.
- `8000` and `8080` are the *Laravel side*. Don't confuse Reverb's `8080` with the ROS bridge's `9090` — they are different WebSocket servers for different
  jobs (UI fan-out vs. robot commands).

---

## Connections opened by the WEB APP toward the ROS side

The Laravel app is a **client** of the ROS machine. Two outbound connections,
both configured in the web app's `.env`:

| From        | To                        | Setting                    | Default                     | Purpose                                                                                   |
| ----------- | ------------------------- | -------------------------- | --------------------------- | ----------------------------------------------------------------------------------------- |
| Laravel app | `ws://<ROS_IP>:9090`    | `DT_SOCKET_ADDRESS`      | `ws://127.0.0.1:9090`     | Send ordered`room_command`s to the robot and observe `status` events for re-planning. |
| Laravel app | `http://<PRED_IP>:8001` | `PREDICTION_SERVICE_URL` | `http://172.30.0.20:8001` | Ask the LightGBM model for predicted travel time between two rooms.                       |

The ROS machine's address is also editable from the dashboard under **Settings → Connection**. If ROS runs on another computer, set
`DT_SOCKET_ADDRESS=ws://<that computer's LAN IP>:9090`.

---

## Foxglove (the technical IHM)

Foxglove is **not** the manager/pharmacy interface. It is a separate technical tool for inspecting the running ROS system (3D scene, costmaps, topics) and for
the custom Room Command panel.

| Step                 | Connection                                                    |
| -------------------- | ------------------------------------------------------------- |
| Open the client      | `https://app.foxglove.dev` (browser) or the desktop app     |
| Connect to the robot | `ws://<ROS_IP>:8765` (`localhost` if on the same machine) |

Foxglove talks **only** to the ROS machine (port `8765`). It does not go through Laravel, Reverb, or the prediction service. See [foxglove.md](foxglove.md) for
the panel layout and topic visualisation.

---

## Who can open what — summary

| Actor                               | Opens (in a browser / client) | Reaches             | On                    |
| ----------------------------------- | ----------------------------- | ------------------- | --------------------- |
| **Manager / Pharmacy**        | `http://<WEBAPP_IP>:8000`   | Laravel dashboard   | Web app computer      |
| Manager / Pharmacy (automatic)      | `ws://<WEBAPP_IP>:8080`     | Reverb live updates | Web app computer      |
| **Web app (server-side)**     | `ws://<ROS_IP>:9090`        | ROS command bridge  | Digital twin computer |
| Web app (server-side)               | `http://<PRED_IP>:8001`     | LightGBM prediction | Prediction host       |
| **Technical user (Foxglove)** | `ws://<ROS_IP>:8765`        | ROS Foxglove bridge | Digital twin computer |
| Developer / script                  | `ws://<ROS_IP>:9090`        | ROS command bridge  | Digital twin computer |

Rule of thumb:

- **Browser-facing, human ports** live on the **web app computer**: `8000` (dashboard) and `8080` (live updates).
- **Robot-facing, ROS ports** live on the **digital twin computer**: `9090` (commands, for non-ROS clients) and `8765` (Foxglove visualisation).
- The **`8001`** prediction service is an internal HTTP dependency of the web app only — no human opens it directly.

---

## Single-machine vs. multi-machine

| Placeholder     | Single machine | Multi-machine                                        |
| --------------- | -------------- | ---------------------------------------------------- |
| `<ROS_IP>`    | `localhost`  | LAN IP of the digital twin computer                  |
| `<WEBAPP_IP>` | `localhost`  | LAN IP of the web app computer                       |
| `<PRED_IP>`   | `localhost`  | LAN IP of the prediction host (often`172.30.0.20`) |

On a single demo machine you can leave all the defaults (`localhost` / `127.0.0.1`) and nothing needs changing. On a LAN, edit the web app's `.env`
(`DT_SOCKET_ADDRESS`, `PREDICTION_SERVICE_URL`, `REVERB_HOST` / `VITE_REVERB_HOST`) so each placeholder resolves to the correct machine.
