<?php

use App\Enums\OrderStatus;
use App\Models\DeliveryPlan;
use App\Models\Order;
use App\Models\Room;
use App\Models\User;
use App\Services\DeliveryPlannerService;
use App\Services\DtOutboundQueueService;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\Cache;

it('initializes a fixed delivery batch from pharmacist listing using reception as start room', function () {
    Cache::forget('dt:outbound_room_commands_queue');
    Cache::put('dt:last_status_payload', [
        'type' => 'status',
        'state' => 'idle',
    ], now()->addHour());

    $pharmacist = User::factory()->pharmacist()->create();

    $startRoom = Room::factory()->create([
        'name' => 'Reception',
        'code' => DeliveryPlannerService::START_ROOM_CODE,
    ]);

    $arrivalOne = Room::factory()->create(['code' => 'salle_301']);
    $arrivalTwo = Room::factory()->create(['code' => 'salle_302']);
    $arrivalOutside = Room::factory()->create(['code' => 'salle_399']);

    $eligibleOrderOne = Order::factory()->create([
        'created_by' => $pharmacist->id,
        'departure_room_id' => $startRoom->id,
        'arrival_room_id' => $arrivalOne->id,
        'status' => OrderStatus::Pending,
        'expected_delivery_at' => Carbon::now()->addMinutes(5),
    ]);

    $eligibleOrderTwo = Order::factory()->create([
        'created_by' => $pharmacist->id,
        'departure_room_id' => $startRoom->id,
        'arrival_room_id' => $arrivalTwo->id,
        'status' => OrderStatus::Pending,
        'expected_delivery_at' => Carbon::now()->subMinutes(10),
    ]);

    $outsideWindowOrder = Order::factory()->create([
        'created_by' => $pharmacist->id,
        'departure_room_id' => $startRoom->id,
        'arrival_room_id' => $arrivalOutside->id,
        'status' => OrderStatus::Pending,
        'expected_delivery_at' => Carbon::now()->addMinutes(45),
    ]);

    $response = $this
        ->actingAs($pharmacist)
        ->post(route('orders.initialize-planning'));

    $response->assertRedirect();
    $response->assertSessionHas('success');

    $activePlan = DeliveryPlan::query()->where('status', 'active')->latest('id')->first();

    expect($activePlan)->not->toBeNull();
    expect($activePlan->sequence)->toHaveCount(2)
        ->and($activePlan->sequence)->toContain($eligibleOrderOne->id)
        ->and($activePlan->sequence)->toContain($eligibleOrderTwo->id)
        ->and($activePlan->sequence)->not->toContain($outsideWindowOrder->id);
    expect($activePlan->current_room_id)->toBe($startRoom->id);

    expect($eligibleOrderOne->fresh()->planned_sequence)->not->toBeNull();
    expect($eligibleOrderTwo->fresh()->planned_sequence)->not->toBeNull();
    expect($outsideWindowOrder->fresh()->planned_sequence)->toBeNull();

    /** @var DtOutboundQueueService $outboundQueue */
    $outboundQueue = app(DtOutboundQueueService::class);

    expect($outboundQueue->all())->toBe([
        [
            'type' => 'room_command',
            'room' => DeliveryPlannerService::START_ROOM_CODE,
        ],
    ]);
});

it('queues start room command immediately even without idle robot status', function () {
    Cache::forget('dt:outbound_room_commands_queue');
    Cache::forget('dt:last_status_payload');

    $pharmacist = User::factory()->pharmacist()->create();

    $startRoom = Room::factory()->create([
        'name' => 'Reception',
        'code' => DeliveryPlannerService::START_ROOM_CODE,
    ]);

    $arrival = Room::factory()->create(['code' => 'salle_301']);

    Order::factory()->create([
        'created_by' => $pharmacist->id,
        'departure_room_id' => $startRoom->id,
        'arrival_room_id' => $arrival->id,
        'status' => OrderStatus::Pending,
        'expected_delivery_at' => Carbon::now()->addMinutes(5),
    ]);

    $response = $this
        ->actingAs($pharmacist)
        ->post(route('orders.initialize-planning'));

    $response->assertRedirect();
    $response->assertSessionHas('success');

    /** @var DtOutboundQueueService $outboundQueue */
    $outboundQueue = app(DtOutboundQueueService::class);

    expect($outboundQueue->all())->toBe([
        [
            'type' => 'room_command',
            'room' => DeliveryPlannerService::START_ROOM_CODE,
        ],
    ]);
});
