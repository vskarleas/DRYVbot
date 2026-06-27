<?php

use App\Enums\OrderStatus;
use App\Models\DeliveryPlan;
use App\Models\Order;
use App\Models\Room;
use App\Models\User;
use App\Services\DeliveryPlannerService;
use App\Services\DtStatusService;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;

it('dispatches first order only after arriving to pharmacy in active batch', function () {
    Http::fake(['*' => Http::response(['predicted_minutes' => 5], 200)]);

    $creator = User::factory()->create();
    $departure = Room::factory()->create(['code' => DeliveryPlannerService::START_ROOM_CODE]);
    $arrivalOne = Room::factory()->create(['code' => 'salle_101']);

    $firstOrder = Order::factory()->create([
        'created_by' => $creator->id,
        'departure_room_id' => $departure->id,
        'arrival_room_id' => $arrivalOne->id,
        'status' => OrderStatus::Pending,
    ]);

    $plan = DeliveryPlan::query()->create([
        'current_room_id' => $departure->id,
        'status' => 'active',
        'sequence' => [$firstOrder->id],
        'estimated_times' => [],
    ]);

    Cache::put("delivery-plan:{$plan->id}:phase", 'awaiting_pharmacy', now()->addDay());

    $messages = app(DtStatusService::class)->handleStatusEvent([
        'type' => 'status',
        'state' => 'arrived',
        'target' => DeliveryPlannerService::START_ROOM_CODE,
        'robot_position' => ['x' => -8.09, 'y' => -6.60, 'z' => 0.0],
        'position_error_m' => 0.023,
        'duration_s' => 14.2,
    ]);

    expect($messages)->toBe([
        ['type' => 'room_command', 'room' => 'salle_101'],
    ]);

    expect($firstOrder->fresh()->status)->toBe(OrderStatus::InTransit);
});

it('queues pharmacy command when robot is idle outside pharmacy during awaiting phase', function () {
    $creator = User::factory()->create();
    $departure = Room::factory()->create(['code' => DeliveryPlannerService::START_ROOM_CODE]);
    $arrival = Room::factory()->create(['code' => 'salle_110']);

    $order = Order::factory()->create([
        'created_by' => $creator->id,
        'departure_room_id' => $departure->id,
        'arrival_room_id' => $arrival->id,
        'status' => OrderStatus::Pending,
    ]);

    $plan = DeliveryPlan::query()->create([
        'current_room_id' => $departure->id,
        'status' => 'active',
        'sequence' => [$order->id],
        'estimated_times' => [],
    ]);

    Cache::put("delivery-plan:{$plan->id}:phase", 'awaiting_pharmacy', now()->addDay());

    $messages = app(DtStatusService::class)->handleStatusEvent([
        'type' => 'status',
        'state' => 'idle',
        'target' => 'salle_999',
        'robot_position' => ['x' => 0.0, 'y' => 0.0, 'z' => 0.0],
        'position_error_m' => 0.0,
        'duration_s' => 0.0,
    ]);

    expect($messages)->toBe([
        ['type' => 'room_command', 'room' => DeliveryPlannerService::START_ROOM_CODE],
    ]);

    expect($order->fresh()->status)->toBe(OrderStatus::Pending);
});

it('dispatches first order when robot is idle at pharmacy during awaiting phase', function () {
    Http::fake(['*' => Http::response(['predicted_minutes' => 5], 200)]);

    $creator = User::factory()->create();
    $departure = Room::factory()->create(['code' => DeliveryPlannerService::START_ROOM_CODE]);
    $arrival = Room::factory()->create(['code' => 'salle_120']);

    $order = Order::factory()->create([
        'created_by' => $creator->id,
        'departure_room_id' => $departure->id,
        'arrival_room_id' => $arrival->id,
        'status' => OrderStatus::Pending,
    ]);

    $plan = DeliveryPlan::query()->create([
        'current_room_id' => $departure->id,
        'status' => 'active',
        'sequence' => [$order->id],
        'estimated_times' => [],
    ]);

    Cache::put("delivery-plan:{$plan->id}:phase", 'awaiting_pharmacy', now()->addDay());

    $messages = app(DtStatusService::class)->handleStatusEvent([
        'type' => 'status',
        'state' => 'idle',
        'target' => DeliveryPlannerService::START_ROOM_CODE,
        'robot_position' => ['x' => 0.0, 'y' => 0.0, 'z' => 0.0],
        'position_error_m' => 0.0,
        'duration_s' => 0.0,
    ]);

    expect($messages)->toBe([
        ['type' => 'room_command', 'room' => 'salle_120'],
    ]);

    $freshOrder = $order->fresh();
    expect($freshOrder->status)->toBe(OrderStatus::InTransit)
        ->and($freshOrder->departure_room_id)->toBe($departure->id);
});

it('dispatches nearest next order and finally returns robot to pharmacy', function () {
    Http::fake(['*' => Http::response(['predicted_minutes' => 5], 200)]);

    $creator = User::factory()->create();
    $departure = Room::factory()->create(['code' => DeliveryPlannerService::START_ROOM_CODE]);
    $arrivalOne = Room::factory()->create(['code' => 'salle_201']);
    $arrivalTwo = Room::factory()->create(['code' => 'salle_202']);

    $firstOrder = Order::factory()->create([
        'created_by' => $creator->id,
        'departure_room_id' => $departure->id,
        'arrival_room_id' => $arrivalOne->id,
        'status' => OrderStatus::InTransit,
    ]);

    $secondOrder = Order::factory()->create([
        'created_by' => $creator->id,
        'departure_room_id' => $departure->id,
        'arrival_room_id' => $arrivalTwo->id,
        'status' => OrderStatus::Pending,
    ]);

    $plan = DeliveryPlan::query()->create([
        'current_room_id' => $departure->id,
        'status' => 'active',
        'sequence' => [$firstOrder->id, $secondOrder->id],
        'estimated_times' => [],
    ]);

    Cache::put("delivery-plan:{$plan->id}:phase", 'delivering', now()->addDay());

    $messagesAfterFirstArrival = app(DtStatusService::class)->handleStatusEvent([
        'type' => 'status',
        'state' => 'arrived',
        'target' => 'salle_201',
        'robot_position' => ['x' => 0.0, 'y' => 0.0, 'z' => 0.0],
        'position_error_m' => 0.0,
        'duration_s' => 0.0,
    ]);

    expect($messagesAfterFirstArrival)->toBe([
        ['type' => 'room_command', 'room' => 'salle_202'],
    ]);

    expect($firstOrder->fresh()->status)->toBe(OrderStatus::Delivered);
    expect($secondOrder->fresh()->status)->toBe(OrderStatus::InTransit);

    $messagesAfterSecondArrival = app(DtStatusService::class)->handleStatusEvent([
        'type' => 'status',
        'state' => 'arrived',
        'target' => 'salle_202',
        'robot_position' => ['x' => 0.0, 'y' => 0.0, 'z' => 0.0],
        'position_error_m' => 0.0,
        'duration_s' => 0.0,
    ]);

    expect($messagesAfterSecondArrival)->toBe([
        ['type' => 'room_command', 'room' => DeliveryPlannerService::START_ROOM_CODE],
    ]);

    expect($secondOrder->fresh()->status)->toBe(OrderStatus::Delivered);

    $messagesAtPharmacy = app(DtStatusService::class)->handleStatusEvent([
        'type' => 'status',
        'state' => 'arrived',
        'target' => DeliveryPlannerService::START_ROOM_CODE,
        'robot_position' => ['x' => 0.0, 'y' => 0.0, 'z' => 0.0],
        'position_error_m' => 0.0,
        'duration_s' => 0.0,
    ]);

    expect($messagesAtPharmacy)->toBe([]);
    expect($plan->fresh()->status)->toBe('completed');
});

it('does not publish room command when no active plan and no queue', function () {
    Cache::forget('dt:planned_rooms_queue');

    $messages = app(DtStatusService::class)->handleStatusEvent([
        'type' => 'status',
        'state' => 'idle',
        'target' => 'salle_000',
        'robot_position' => ['x' => 0.0, 'y' => 0.0, 'z' => 0.0],
        'position_error_m' => 0.0,
        'duration_s' => 0.0,
    ]);

    expect($messages)->toBe([]);
});
