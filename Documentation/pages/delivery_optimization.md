# Delivery optimization (==logic== & ML model)

This page explains the **==logic==** behind the delivery optimizer — not the web application itself (for the app, its dependencies and how to run it, see the `delivery_optimization` section of the main [README](../../README.md)).

The optimizer answers one operational question: when the pharmacy has several deliveries waiting, **in what order should the robot deliver them** so that critical medication arrives first and total travel time is minimised? It does this with a learned travel-time model and a greedy sequencing algorithm, and it
keeps improving because every real robot movement is recorded and fed back into the model.

---

## Big picture

```
                    PHARMACY MANAGER (pharmacien responsable)
                                │  creates delivery orders
                                │  (arrival room, deadline, critical?)
                                ▼
        ┌───────────────────────────────────────────────┐
        │            DeliveryPlannerService             │
        │                                               │
        │   1. Split orders: critical  vs  non-critical │
        │   2. Order each batch by predicted travel time│
        │      (greedy nearest-neighbour)               │
        │   3. Produce an ordered delivery sequence     │
        └───────────────────┬───────────────────────────┘
                            │ asks "how long from room A to room B
                            │  leaving at time T?"
                            ▼
        ┌───────────────────────────────────────────────┐
        │   PredictionService → LightGBM model (HTTP)    │
        │   predicted_duration_s = f(dep, arr, time)     │
        └───────────────────┬───────────────────────────┘
                            │ ordered room commands
                            ▼
        ┌───────────────────────────────────────────────┐
        │   Digital twin / ROS (robot executes routes)   │
        └───────────────────┬───────────────────────────┘
                            │ actual departure/arrival times,
                            │ measured durations
                            ▼
        ┌───────────────────────────────────────────────┐
        │   Recorded movements → retraining data         │
        │   (simulation logs + per-order DT timings)     │
        └───────────────────────────────────────────────┘
                            │
                            └──► model is retrained → better predictions
```

There are **two feedback loops** in CloudTwin. The navigation feedback loop (robot ↔ digital twin, replanning around crowds) is described in [architecture.md](architecture.md). This page describes the second one: the **model feedback loop**, where recorded deliveries make the travel-time predictor more accurate over time.

---

## The travel-time model (LightGBM regression)

### What it predicts

The model is a **gradient-boosted regression model (LightGBM)** that estimates how long the robot needs to travel between two rooms:

|                             |                                              |
| --------------------------- | -------------------------------------------- |
| **Inputs (features)** | departure room, arrival room, departure time |
| **Target**            | travel duration in**seconds**          |

The departure *time* matters because the hospital is not equally busy at all hours: during a `crowd` or `emergency` scenario (see [navigation_==logic==.md](navigation_logic.md)) corridors fill with people and Nav2 has to detour, so the same A→B trip takes longer. By learning from time-stamped trips, the model captures these congestion patterns instead of assuming a fixed distance/speed.

### Where the model lives

The trained model runs as a **separate Python microservice**, not inside theLaravel application. Laravel talks to it over HTTP:

- Configured by `services.prediction.url`
  (env `PREDICTION_SERVICE_URL`, default `http://172.30.0.20:8001`).
- Endpoint: `POST /predict`
- Request body:

  ```json
  {
    "room_departure_id": "salle_pharmacie",
    "room_arrival_id": "salle_101",
    "departure_time": "2026-06-27T14:32:10Z"
  }
  ```
- Response:

  ```json
  { "predicted_duration_s": 23.7 }
  ```

> The model service and its training code/notebooks are kept outside this
> Laravel repository (the `delivery_optimization/AI/` folder is the intended
> home for them). This page documents the contract and the data flow; the
> training scripts themselves are maintained alongside the model service.

### How Laravel consumes it

`app/Services/PredictionService.php` wraps the call:

- 3-second HTTP timeout.
- Converts `predicted_duration_s` to **minutes** (rounded to 2 decimals).
- **Fallback:** if the service is unreachable or returns an invalid value, it
  returns a constant heuristic so planning never blocks on the model being down.

This means the optimizer degrades gracefully: without the model it still produces a sequence (just a less accurate one).

---

## Training data: recording real robot movements

The model is trained — and **retrained** — on data produced by the robot actually moving. Two complementary sources feed the training set.

### 1. Simulation logs (ROS side)

The `simulation_logger.py` node in the `digital_twin` package records one JSON record per room command, into `simulation_logs/simulation_<timestamp>.json`. Each record contains the departure position + timestamp, the target room, thearrival position + timestamp, the measured `duration_s`, and the
`position_error_m`. The full schema is documented in the
[README](../../README.md) ("Simulation log format").

These logs are the **ground-truth travel times** the model learns from. Because
they are produced under the controlled `normal` / `crowd` / `emergency`
scenarios, they cover a realistic spread of congestion conditions.

### 2. Per-order delivery timings (web side)

When the digital twin completes a delivery, it posts the real timings back to
the web app via `POST` to `DtWebhookController` (`/api/...`):

```json
{
  "order_id": 42,
  "salle_id_depart": "salle_pharmacie",
  "salle_id_arrivee": "salle_101",
  "date_depart": "2026-06-27T14:32:10Z",
  "date_arrivee": "2026-06-27T14:32:34Z",
  "duree": { "annee": 0, "mois": 0, "jour": 0, "heure": 0, "minute": 0 },
  "status": "delivered"
}
```

This updates the order's `dt_*` columns and is also the basis of the `DtData`
model (`salle_code_depart`, `salle_code_arrivee`, `date_depart`, `date_arrivee`,
`duree`, `order_id`) — a clean, per-trip record of where the robot went and how
long it took, tied to a real delivery.

### Synthesising data and producing weights

The raw recordings are relatively few, so they are **augmented / synthesised** into a larger, balanced training set (for example, interpolating across
departure times and room pairs that share corridors) before fitting the LightGBM regressor. Training produces the model **weights (les poids)** that the
prediction service loads to answer `/predict`.

As more deliveries are completed, new movements accumulate and the model is retrained on the larger set,  closing the model feedback loop.

---

## The optimization algorithm

All of the sequencing ==logic== lives in `app/Services/DeliveryPlannerService.php`. There are two ideas: **criticality first**, then **shortest predicted time** within each criticality batch.

### Step 1 — Criticality batching

Orders carry an `is_critical` flag (set by the pharmacy manager). When a planning cycle starts (`initializeBatchPlan`):

- **Critical** orders form an `active` plan that runs **first**.
- **Non-critical** orders form a `queued` plan that becomes active only once the
  critical batch is finished.

So a life-critical medication is never delayed behind routine deliveries, even if the routine one is physically closer.

### Step 2 — Greedy nearest-neighbour by predicted time

Within a batch, the order of stops is chosen by a greedy nearest-neighbour search that uses **predicted travel time** as the distance metric
(`computeSequence`):

```
current_room = salle_pharmacie         # START_ROOM_CODE
sequence = []
while orders remain:
    best = argmin over remaining orders of
           PredictionService.predict(current_room, order.arrival_room, order.deadline)
    sequence.append(best)
    current_room = best.arrival_room
    remove best from remaining
```

This is a classic heuristic for the travelling-salesman-style problem: at each step go to the stop that is *predicted* to be reached fastest from where the
robot currently is. It is fast (no exhaustive search) and good enough for the handful of stops in a typical batch. The per-order estimates
(`predicted_minutes`, sequence position, departure/arrival rooms) are stored in the plan's `estimated_times` and shown in the UI's "Séquence optimisée".

> Because the metric is **learned predicted time**, not straight-line distance, the sequence automatically accounts for things like a corridor that is slow at
> 2pm

### Step 3 — Dynamic re-planning while delivering

The plan is not computed once and frozen. As the robot reports progress through the digital-twin socket (`navigating` / `arrived` events handled by
`DtStatusService`), the planner recomputes the **remaining** sequence from the robot's *actual* current room (`recalculateRemainingSequence` / `plan`):

- delivered and cancelled orders drop out
- the still-pending orders are re-ordered from the new position
- if a critical batch finishes, the queued non-critical plan is activated
  (`activateNextQueuedPlan`)

This keeps the sequence optimal even if a delivery is added, cancelled, or takes longer than predicted.

---

## End-to-end execution loop

```
1. Pharmacy manager creates orders (arrival room, deadline, is_critical)
        │
2. DeliveryPlannerService builds the batches + ordered sequence
   (using PredictionService → LightGBM for every A→B estimate)
        │
3. Planned rooms are queued (DtTaskQueueService) and dispatched to ROS
   as room_command messages over the digital-twin socket
        │
4. ROS / Nav2 navigates the robot; status events return
   (navigating → arrived) via the socket
        │
5. DtStatusService marks orders in_transit / delivered, advances the
   queue, and triggers re-planning of the remainder
        │
6. Real timings are recorded (simulation logs + DtData / webhook)
        │
        └──► added to the training set → model retrained → step 2 gets better
```

---

## Key code map

| Concern                            | File                                                                            |
| ---------------------------------- | ------------------------------------------------------------------------------- |
| Sequencing & batching==logic== | `app/Services/DeliveryPlannerService.php`                                     |
| Travel-time model client           | `app/Services/PredictionService.php`                                          |
| Model service URL                  | `config/services.php` → `prediction.url`                                   |
| Room→robot command queue          | `app/Services/DtTaskQueueService.php`                                         |
| Status handling / re-plan trigger  | `app/Services/DtStatusService.php`                                            |
| Recording delivery timings         | `app/Http/Controllers/Api/DtWebhookController.php`, `app/Models/DtData.php` |
| Ground-truth trip logs (ROS)       | `digital_twin/digital_twin/simulation_logger.py`                              |

---

## Relationship to the rest of CloudTwin

- The **navigation** feedback loop (crowd-aware replanning) is independent and described in [architecture.md](architecture.md). The optimizer sits *above*
  it: it decides the *order of destinations*; Nav2 decides *how to drive* to each one.
- The room names the optimizer uses (`salle_pharmacie`, `salle_101`, …) are the same registry entries used by the room interpreter — see
  [navigation_==logic==.md](navigation_logic.md) and `room_registry.yaml`.
- Commands reach the robot over the same digital-twin socket described in the README's WebSocket section; the ROS machine's address is configurable from the web app under **Settings → Connection**.
